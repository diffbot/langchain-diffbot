"""Tools the agent can call.

We give the agent three Diffbot-backed surfaces:

- `search_kg(dql)` — Diffbot Knowledge Graph via DQL.
- `web_search(query)` — Diffbot web search.
- `extract_url(url)` — Diffbot Analyze extract on a single URL.

Each tool is a thin `@tool` wrapper that:
  1. Calls the package's pre-built Diffbot class.
  2. Shapes / truncates the response so a single tool call doesn't blow
     past the model's per-minute input-token budget. Diffbot KG entities,
     web search results, and extracted pages can each run thousands of
     tokens — without shaping, a multi-step agent will hit rate limits
     fast. The same projection-allowlist + content-truncation pattern is
     applied to each surface so the example demonstrates how to keep an
     agent loop token-efficient end-to-end.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from diffbot import Diffbot
from diffbot.errors import APIError
from langchain_core.tools import tool

from langchain_diffbot import (
    DiffbotDQLProbeTool,
    DiffbotExtractTool,
    DiffbotKnowledgeGraphRetriever,
    DiffbotOntologyTool,
    DiffbotWebSearchRetriever,
)

# Projection allowlist for KG entities. Only these top-level fields ride
# along in metadata — full entities can easily be thousands of tokens each.
_KG_FIELDS = [
    "id",
    "type",
    "name",
    "homepageUri",
    "nbEmployees",
    "industries",
    "location",
    "employments",
    "date",
]

_WEB_SEARCH_K = 5
_WEB_SEARCH_CONTENT_CHARS = 800
_EXTRACT_CONTENT_CHARS = 4000


@lru_cache(maxsize=1)
def _db() -> Diffbot:
    # One client shared across every Diffbot-backed tool below, so the whole
    # agent run reuses a single connection pool. Lazy so importing this module
    # doesn't require DIFFBOT_API_TOKEN. This agent is sync (the CLI calls
    # `agent.invoke`), so a sync `Diffbot` is all we need.
    return Diffbot(token=os.environ["DIFFBOT_API_TOKEN"])


@lru_cache(maxsize=1)
def _kg_retriever() -> DiffbotKnowledgeGraphRetriever:
    return DiffbotKnowledgeGraphRetriever(client=_db(), k=5, fields=_KG_FIELDS)


@lru_cache(maxsize=1)
def _web_retriever() -> DiffbotWebSearchRetriever:
    return DiffbotWebSearchRetriever(
        client=_db(),
        k=_WEB_SEARCH_K,
        fields=["title", "pageUrl", "score"],
    )


@lru_cache(maxsize=1)
def _extract_tool() -> DiffbotExtractTool:
    return DiffbotExtractTool(client=_db())


@lru_cache(maxsize=1)
def _ontology_tool() -> DiffbotOntologyTool:
    # Cached so the fetched ontology is reused across the whole agent run.
    return DiffbotOntologyTool(client=_db())


@lru_cache(maxsize=1)
def _probe_tool() -> DiffbotDQLProbeTool:
    return DiffbotDQLProbeTool(client=_db())


@tool
def inspect_ontology(
    op: str, name: str | None = None, search: str | None = None
) -> list[str] | dict[str, str]:
    """Inspect the Diffbot KG schema so you can write DQL with real field paths.

    Call this BEFORE guessing field names. Ops:
      - `types` / `composites` / `enums` / `taxonomies` — list available names.
      - `fields` — fields of a type or composite; pass `name` (e.g. "Organization",
        "Location"). Optionally pass `search` (regex) to filter.
      - `taxonomy` — values of a taxonomy; pass `name` (e.g. "OrganizationCategory"),
        optionally `search`.
      - `enum` — values of an enum; pass `name` (e.g. "Language").
      - `search` — regex over every name in the ontology; pass the pattern as `name`.

    Returns a list of strings, or `{"error": ...}` if the name was wrong (list the
    valid names with the matching list op, then retry).
    """
    return _ontology_tool().invoke({"op": op, "name": name, "search": search})


@tool
def probe_dql(queries: list[str]) -> list[dict]:
    """Probe DQL variants in parallel and get the hit count for each (no entity data).

    Use this to sanity-check a query's selectivity before running it with
    `search_kg`: if a variant returns 0 hits it's too narrow; if it returns a
    huge number it's too broad. Pass several variants at once to compare them in
    a single round-trip. Returns `[{"query": ..., "hits": N}, ...]`.
    """
    return _probe_tool().invoke({"queries": queries})


@tool
def search_kg(dql_query: str) -> list[dict]:
    """Search the Diffbot Knowledge Graph with a DQL query.

    DQL (Diffbot Query Language) syntax cheatsheet:

    - Filter by type: `type:Organization`, `type:Person`, `type:Article`
    - Exact match: `name:"Diffbot"`
    - Nested fields use dots: `location.city.name:"Austin"`
    - Combine filters with spaces (AND): `type:Organization industries:"Robotics"`
    - Sort ascending with `sortBy:<field>`, descending with `revSortBy:<field>`
      (e.g. `revSortBy:nbEmployees`). There is no `desc` keyword.

    Examples:
        - `type:Organization location.city.name:"Austin" industries:"Robotics"`
        - `type:Person employments.{employer.name:"Diffbot" isCurrent:true}`
        - `type:Article tags.label:"Artificial Intelligence" revSortBy:date`

    Returns a list of entity dicts. Each entity has `summary` (description/summary
    text), `id`, `type`, `name`, and a few projected fields like `homepageUri`,
    `nbEmployees`, `industries`, `location`, `employments`, `date`. Other KG
    fields are intentionally omitted to keep responses small — refine the DQL
    query if you need different information.
    """
    try:
        docs = _kg_retriever().invoke(dql_query)
    except APIError as exc:
        # Surface DQL syntax errors back to the model so it can refine and retry.
        return [
            {
                "error": (
                    f"Diffbot rejected the query ({exc.status_code}): "
                    f"{exc.message or 'see body'}. Refine the DQL and try again."
                )
            }
        ]
    return [{"summary": d.page_content, **d.metadata} for d in docs]


@tool
def web_search(query: str) -> list[dict]:
    """Search the web via Diffbot. Use when the KG comes up short or you need current info.

    Args:
        query: natural-language search string.

    Returns up to 5 results, each with `title`, `pageUrl`, `score`, and a
    truncated `content` snippet (~800 chars). If you need the full page,
    pass the `pageUrl` to `extract_url`.
    """
    docs = _web_retriever().invoke(query)
    return [
        {
            **d.metadata,
            "content": d.page_content[:_WEB_SEARCH_CONTENT_CHARS],
        }
        for d in docs
    ]


@tool
def extract_url(url: str) -> dict[str, Any]:
    """Fetch and read a single web page via Diffbot's Analyze API.

    Args:
        url: page to extract.

    Returns a dict with `content` (markdown), `title`, `pageUrl`, `type`. The
    content is truncated (~4000 chars) to stay inside per-minute token
    budgets — call this on specific URLs you want to drill into, not on
    everything.
    """
    raw = _extract_tool().invoke({"url": url})
    if "error" in raw:
        return raw
    return {
        **raw,
        "content": (raw.get("content") or "")[:_EXTRACT_CONTENT_CHARS],
    }
