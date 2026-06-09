"""The DQL-authoring agent.

Unlike `company_research`, this agent does NOT run the Knowledge Graph query
itself. It only *authors* it: it inspects the ontology and probes hit counts,
then returns a structured `DQLPlan` (the final DQL plus the columns to show).
The server (see `server.py`) runs that DQL deterministically and builds the
table, so the rendered rows are always real KG data — never model output.
"""

from __future__ import annotations

import os
from functools import lru_cache

from diffbot import Diffbot
from diffbot.errors import APIError
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from langchain_diffbot import DiffbotDQLProbeTool, DiffbotOntologyTool

# Override with DQL_EXPLORER_MODEL=anthropic:claude-sonnet-4-6 (or any
# `provider:model` string the agent factory understands). Default to Haiku for
# the same reason as the CLI example: a multi-step authoring loop on a fresh
# Tier 1 Anthropic account can blow past Sonnet's 30k input-tokens/minute cap.
DEFAULT_MODEL = os.environ.get("DQL_EXPLORER_MODEL", "anthropic:claude-haiku-4-5")


class Column(BaseModel):
    """One column to display in the results table."""

    path: str = Field(
        description=(
            "Dot-path into a KG entity, e.g. 'name', 'nbEmployees', or "
            "'location.city.name'. Must be a real field path you confirmed via "
            "inspect_ontology — do not invent paths."
        )
    )
    label: str = Field(description="Human-readable column header, e.g. 'City'.")


class DQLPlan(BaseModel):
    """The agent's structured answer: a query plus how to display its results."""

    entity_type: str = Field(
        description="The primary KG entity type the query targets, e.g. 'Organization'."
    )
    dql: str = Field(description="The final, validated DQL query to run.")
    columns: list[Column] = Field(
        description="4-6 high-level columns to show. Keep it concise and readable."
    )
    notes: str | None = Field(
        default=None,
        description="Optional one-line note about the query (assumptions, caveats).",
    )


# Cap ontology list results. Full ontology dumps (every type, or every field of
# a big type) run thousands of tokens; re-sent each agent turn they pile up fast
# and trip per-minute input-token rate limits. Capping keeps the loop affordable;
# the agent is told to narrow with `search` when a result is truncated.
_ONTOLOGY_MAX_ITEMS = 80


@lru_cache(maxsize=1)
def _db() -> Diffbot:
    # Shared sync client for the authoring tools. The agent's @tool functions
    # call `.invoke()` (sync) — even under the server's `ainvoke`, LangChain runs
    # a sync tool in a thread — so these need a sync `Diffbot`. The KG query and
    # the Ask tab run async and build a `DiffbotAsync` in server.py instead.
    return Diffbot(token=os.environ["DIFFBOT_API_TOKEN"])


@lru_cache(maxsize=1)
def _ontology_tool() -> DiffbotOntologyTool:
    # Cached so the fetched ontology is reused across the whole process.
    return DiffbotOntologyTool(client=_db())


@lru_cache(maxsize=1)
def _probe_tool() -> DiffbotDQLProbeTool:
    return DiffbotDQLProbeTool(client=_db())


@tool
def inspect_ontology(
    op: str, name: str | None = None, search: str | None = None
) -> list[str] | dict[str, str]:
    """Inspect the Diffbot KG schema so you can write DQL with real field paths.

    Call this BEFORE guessing field names or column paths. Ops:
      - `types` / `composites` / `enums` / `taxonomies` — list available names.
      - `fields` — fields of a type or composite; pass `name` (e.g. "Organization",
        "Location"). Optionally pass `search` (regex) to filter.
      - `taxonomy` — values of a taxonomy; pass `name` (e.g. "OrganizationCategory"),
        optionally `search`.
      - `enum` — values of an enum; pass `name` (e.g. "Language").
      - `search` — regex over every name in the ontology; pass the pattern as `name`.

    Returns a list of strings, or `{"error": ...}` if the name was wrong (list the
    valid names with the matching list op, then retry). Long results are capped;
    if you see a truncation marker, pass a `search` regex to narrow them.
    """
    result = _ontology_tool().invoke({"op": op, "name": name, "search": search})
    if isinstance(result, list) and len(result) > _ONTOLOGY_MAX_ITEMS:
        kept = result[:_ONTOLOGY_MAX_ITEMS]
        kept.append(
            f"... ({len(result) - _ONTOLOGY_MAX_ITEMS} more truncated — "
            "pass a `search` regex to narrow this list)"
        )
        return kept
    return result


@tool
def probe_dql(queries: list[str]) -> list[dict]:
    """Probe DQL variants in parallel and get the hit count for each (no entity data).

    Use this to sanity-check a query's selectivity before settling on it: if a
    variant returns 0 hits it's too narrow; if it returns a huge number it's too
    broad. Pass several variants at once to compare them in a single round-trip.
    Returns `[{"query": ..., "hits": N}, ...]`.

    If Diffbot rejects a variant (DQL syntax error), this returns an `error`
    instead of raising — read it, fix the offending variant, and probe again.
    """
    try:
        return _probe_tool().invoke({"queries": queries})
    except APIError as exc:
        # One bad variant fails the whole batch. Surface the error so the agent
        # can fix the syntax and re-probe, rather than crashing the run.
        return [
            {
                "error": (
                    f"Diffbot rejected a query ({exc.status_code}): "
                    f"{exc.message or 'syntax error'}. Fix the DQL and re-probe."
                )
            }
        ]


SYSTEM_PROMPT = """\
You are a DQL-authoring assistant for the Diffbot Knowledge Graph. The user
gives you a question in plain English. Your job is to turn it into ONE valid DQL
query and choose a small set of high-level columns to display — then return a
`DQLPlan`. You do NOT run the query yourself; the server runs it and renders the
results, so getting the DQL and column paths right is the whole task.

You have two tools:
- `inspect_ontology(op, name?, search?)` — look up the KG schema: entity types,
  the fields of a type/composite, taxonomy values, enum values. Use this to find
  the EXACT field path or taxonomy value before writing DQL — don't guess.
- `probe_dql(queries)` — run several DQL variants at once and get just their hit
  counts. Use it to check a query is well-shaped (not 0 hits, not millions).

DQL syntax cheatsheet:
- Filter by type: `type:Organization`, `type:Person`, `type:Article`
- Exact match: `name:"Diffbot"`
- Nested fields use dots: `location.city.name:"Austin"`
- Combine filters with spaces (AND): `type:Organization industries:"Robotics"`
- Sort ascending with `sortBy:<field>`; sort descending with `revSortBy:<field>`
  (e.g. `revSortBy:nbEmployees` for the largest first). There is NO `desc`
  keyword — `sortBy:nbEmployees desc` is invalid.

Workflow (do this, don't hand-wave the DQL):
  1. Decide the entity type. If unsure a field path or taxonomy/enum value
     exists, confirm it with `inspect_ontology` first. E.g. `op="fields",
     name="Organization"` to see an Organization's fields, or `op="taxonomy",
     name="OrganizationCategory", search="semiconductor"` for a category value.
  2. Draft 2-3 DQL variants and `probe_dql` them together. Keep the variant whose
     hit count looks right; loosen if 0, tighten if huge.
  3. Choose 4-6 high-level columns. Each column `path` MUST be a real field path
     you confirmed in the ontology (e.g. `name`, `nbEmployees`,
     `location.city.name`, `homepageUri`). Prefer short, recognizable fields;
     include `name` first when the type has one.
  4. If a sort makes the table more useful (e.g. largest companies first), add
     `revSortBy:<field>` (descending) or `sortBy:<field>` (ascending) to the DQL.

MANDATORY before you answer: `probe_dql` your FINAL query (the exact string you'll
return) and confirm it returns hits > 0 and no error. If probe reports an error,
the query is invalid — read the message, fix the syntax (re-check the ontology if
it's a bad field path), and probe again. Never return a query you haven't probed
successfully. If after a few attempts you can't get hits, loosen the filters and
return the best probed variant with a `notes` explaining the compromise.

Return a `DQLPlan` with `entity_type`, the final `dql`, the `columns`, and an
optional one-line `notes`. Do not include columns whose paths you did not verify.
"""


def build_dql_agent():
    """Build the structured DQL-authoring agent."""
    # Bound retries so a rate-limited (429) request fails fast and surfaces a
    # clear error in the UI, instead of the SDK silently honoring `retry-after`
    # and hanging for minutes. Tight Anthropic tiers hit this easily — see the
    # rate-limit note in the README.
    model = init_chat_model(DEFAULT_MODEL, max_retries=1)
    return create_agent(
        model=model,
        tools=[inspect_ontology, probe_dql],
        system_prompt=SYSTEM_PROMPT,
        response_format=DQLPlan,
    )
