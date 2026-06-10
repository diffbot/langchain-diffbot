"""Diffbot tools — agent-callable wrappers around individual SDK methods.

Each tool is a thin BaseTool around one `diffbot` method. Args schemas mirror
the SDK signatures one-for-one so agents calling these tools see the same
shape as a direct SDK call.
"""

from __future__ import annotations

from typing import Any, Literal

from diffbot import Ontology
from diffbot.errors import ExtractionError
from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr

from langchain_diffbot._base import _BaseDiffbotComponent


class _DiffbotExtractInput(BaseModel):
    url: str = Field(description="URL to extract structured content from.")
    api: str = Field(
        default="analyze",
        description=(
            "Diffbot extract API to call. Defaults to `analyze` "
            "(auto-detects content type)."
        ),
    )
    fmt: str = Field(
        default="markdown",
        description="Output format. `markdown` uses Diffbot's LLM-optimized mode.",
    )


class DiffbotExtractTool(_BaseDiffbotComponent, BaseTool):
    """Tool that extracts structured content from a URL via Diffbot's analyze API.

    Returns a small dict so the agent doesn't have to wade through the full
    raw response. On extraction failure (a 200 response with an `errorCode`
    body) returns a structured error dict instead of raising, so the agent
    can react. Auth / rate-limit errors propagate as exceptions — those are
    infra problems, not per-call signals.
    """

    name: str = "diffbot_extract"
    description: str = (
        "Extract structured content (title, text, type, resolved URL) from a "
        "single web page. Use for reading the contents of a known URL."
    )
    args_schema: type[BaseModel] = _DiffbotExtractInput

    @staticmethod
    def _shape_response(raw: dict[str, Any]) -> dict[str, Any]:
        objects = raw.get("objects") or []
        first = objects[0] if objects else {}
        return {
            "content": first.get("text") or raw.get("markdown") or "",
            "title": first.get("title") or raw.get("title"),
            "pageUrl": first.get("pageUrl") or raw.get("url"),
            "resolvedPageUrl": first.get("resolvedPageUrl"),
            "type": first.get("type") or raw.get("type"),
        }

    def _run(
        self,
        url: str,
        api: str = "analyze",
        fmt: str = "markdown",
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> dict[str, Any]:
        try:
            with self._sync_db() as db:
                raw = db.extract(url, api=api, fmt=fmt)
        except ExtractionError as e:
            return {"error": str(e), "errorCode": e.error_code}
        return self._shape_response(raw)

    async def _arun(
        self,
        url: str,
        api: str = "analyze",
        fmt: str = "markdown",
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> dict[str, Any]:
        try:
            async with self._async_db() as db:
                raw = await db.extract(url, api=api, fmt=fmt)
        except ExtractionError as e:
            return {"error": str(e), "errorCode": e.error_code}
        return self._shape_response(raw)


class _DiffbotWebSearchInput(BaseModel):
    text: str = Field(description="Natural-language search query.")
    num_results: int | None = Field(
        default=None, description="Max results to return. Server default if unset."
    )
    max_tokens: int | None = Field(
        default=None, description="Optional total content-token cap."
    )


class DiffbotWebSearchTool(_BaseDiffbotComponent, BaseTool):
    """Tool that performs a Diffbot web search and returns the raw result list.

    Use this when the agent needs the search results as-is (with score, title,
    pageUrl, content). For LangChain `Document` output use
    `DiffbotWebSearchRetriever` instead.
    """

    name: str = "diffbot_web_search"
    description: str = (
        "Search the web via Diffbot. Returns a list of results, each with "
        "title, pageUrl, score, and content."
    )
    args_schema: type[BaseModel] = _DiffbotWebSearchInput

    def _run(
        self,
        text: str,
        num_results: int | None = None,
        max_tokens: int | None = None,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> list[dict[str, Any]]:
        with self._sync_db() as db:
            body = db.web_search(text, num_results=num_results, max_tokens=max_tokens)
        return body.get("search_results", [])

    async def _arun(
        self,
        text: str,
        num_results: int | None = None,
        max_tokens: int | None = None,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> list[dict[str, Any]]:
        async with self._async_db() as db:
            body = await db.web_search(
                text, num_results=num_results, max_tokens=max_tokens
            )
        return body.get("search_results", [])


class _DiffbotEntitiesInput(BaseModel):
    text: str = Field(description="Text to extract entities and sentiment from.")
    lang: str = Field(default="auto", description="Language hint (`auto` to detect).")


class DiffbotEntitiesTool(_BaseDiffbotComponent, BaseTool):
    """Tool that identifies entities and sentiment in text via Diffbot NLP.

    Returns the SDK response dict as-is — it's small (entity list + sentiment).
    Entity IDs in the response can be looked up in the KG via
    `DiffbotKnowledgeGraphTool` or `DiffbotKnowledgeGraphRetriever` using
    `id:or("id1","id2",...)`.
    """

    name: str = "diffbot_entities"
    description: str = (
        "Identify entities (people, organizations, places, ...) and sentiment "
        "in a piece of text. Returns entity IDs that can be looked up in the "
        "Diffbot Knowledge Graph."
    )
    args_schema: type[BaseModel] = _DiffbotEntitiesInput

    def _run(
        self,
        text: str,
        lang: str = "auto",
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> dict[str, Any]:
        with self._sync_db() as db:
            return db.entities(text, lang=lang)

    async def _arun(
        self,
        text: str,
        lang: str = "auto",
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> dict[str, Any]:
        async with self._async_db() as db:
            return await db.entities(text, lang=lang)


class _DiffbotDQLInput(BaseModel):
    query: str = Field(
        description='DQL query, e.g. `type:Organization name:"Diffbot"`.'
    )
    size: int = Field(default=10, description="Max results.")
    from_: int = Field(default=0, description="Result offset.")
    filter: str | None = Field(
        default=None, description="Optional DQL filter expression."
    )


class DiffbotKnowledgeGraphTool(_BaseDiffbotComponent, BaseTool):
    """Tool that runs a DQL query against the Diffbot Knowledge Graph.

    Returns the raw response dict (with `data`, `hits`, etc.). For LangChain
    `Document` output use `DiffbotKnowledgeGraphRetriever` instead.

    Best for agents that have been instructed in DQL syntax.
    """

    name: str = "diffbot_knowledge_graph"
    description: str = (
        "Query the Diffbot Knowledge Graph with a DQL expression "
        '(e.g. `type:Organization location.city.name:"Boston"`). '
        "Returns the raw response — use only if you know DQL syntax."
    )
    args_schema: type[BaseModel] = _DiffbotDQLInput

    def _run(
        self,
        query: str,
        size: int = 10,
        from_: int = 0,
        filter: str | None = None,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> dict[str, Any]:
        with self._sync_db() as db:
            body = db.dql(query, size=size, from_=from_, filter=filter)
        if not isinstance(body, dict):
            msg = "Unexpected non-JSON DQL response."
            raise TypeError(msg)
        return body

    async def _arun(
        self,
        query: str,
        size: int = 10,
        from_: int = 0,
        filter: str | None = None,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> dict[str, Any]:
        async with self._async_db() as db:
            body = await db.dql(query, size=size, from_=from_, filter=filter)
        if not isinstance(body, dict):
            msg = "Unexpected non-JSON DQL response."
            raise TypeError(msg)
        return body


_OntologyOp = Literal[
    "types", "composites", "enums", "taxonomies", "fields", "taxonomy", "enum", "search"
]


def _ontology_lookup(
    ont: Ontology, op: str, name: str | None, search: str | None
) -> list[str] | dict[str, str]:
    """Run one ontology navigation op, returning a list or a recoverable error dict.

    `KeyError` (unknown type/taxonomy/enum) and missing-argument `ValueError`s are
    returned as `{"error": ...}` so the agent can correct itself and retry rather
    than the tool call raising.
    """
    try:
        if op == "types":
            return ont.types()
        if op == "composites":
            return ont.composites()
        if op == "enums":
            return ont.enums()
        if op == "taxonomies":
            return ont.taxonomies()
        if op == "fields":
            if not name:
                msg = "op='fields' requires `name` (the entity type or composite)."
                raise ValueError(msg)
            fields = ont.fields_for(name)
            return [
                Ontology.format_field(n, m)
                for n, m in Ontology.filter_fields(fields, search)
            ]
        if op == "taxonomy":
            if not name:
                msg = "op='taxonomy' requires `name` (the taxonomy)."
                raise ValueError(msg)
            return ont.taxonomy_values(name, search)
        if op == "enum":
            if not name:
                msg = "op='enum' requires `name` (the enum)."
                raise ValueError(msg)
            return ont.enum_values(name)
        if op == "search":
            if not name:
                msg = "op='search' requires `name` (the regex to match)."
                raise ValueError(msg)
            return ont.find_named(name)
        msg = f"Unknown op {op!r}."
        raise ValueError(msg)
    except (KeyError, ValueError) as exc:
        return {
            "error": str(exc).strip('"'),
            "hint": (
                "Valid ops: types, composites, enums, taxonomies, fields, "
                "taxonomy, enum, search. List names first (e.g. op='types') "
                "before drilling into fields/taxonomy/enum."
            ),
        }


class _DiffbotOntologyInput(BaseModel):
    op: _OntologyOp = Field(
        description=(
            "Which part of the ontology to inspect: `types`/`composites`/`enums`/"
            "`taxonomies` list names; `fields` lists the fields of a type or "
            "composite; `taxonomy`/`enum` list a named taxonomy's/enum's values; "
            "`search` matches any name anywhere in the ontology by regex."
        )
    )
    name: str | None = Field(
        default=None,
        description=(
            "Target name for `fields` (a type/composite), `taxonomy`, or `enum`; "
            "the regex pattern for `search`. Unused by the list ops."
        ),
    )
    search: str | None = Field(
        default=None,
        description=(
            "Optional case-insensitive regex to filter `fields` or `taxonomy` results."
        ),
    )


class DiffbotOntologyTool(_BaseDiffbotComponent, BaseTool):
    """Tool that navigates the Diffbot Knowledge Graph ontology.

    Lets an agent discover real entity types, field paths, taxonomy values, and
    enum values *before* writing a DQL query — so it constructs valid queries
    instead of guessing field names. The ontology is fetched once over HTTP via
    `Diffbot.dql_fetch_ontology()` and cached in memory on the tool instance for
    the rest of its lifetime (pass `refresh=True` in a call to re-fetch).
    """

    name: str = "diffbot_ontology"
    description: str = (
        "Inspect the Diffbot Knowledge Graph schema to build valid DQL. Ops: "
        "`types`/`composites`/`enums`/`taxonomies` (list names), `fields` "
        "(fields of a type/composite — pass `name`), `taxonomy`/`enum` (values "
        "of a named taxonomy/enum — pass `name`), `search` (regex over all "
        "names — pass the pattern as `name`). Look fields up here before "
        "writing a DQL query."
    )
    args_schema: type[BaseModel] = _DiffbotOntologyInput

    _ontology: Ontology | None = PrivateAttr(default=None)

    def _run(
        self,
        op: str,
        name: str | None = None,
        search: str | None = None,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> list[str] | dict[str, str]:
        if self._ontology is None:
            with self._sync_db() as db:
                self._ontology = db.dql_fetch_ontology()
        return _ontology_lookup(self._ontology, op, name, search)

    async def _arun(
        self,
        op: str,
        name: str | None = None,
        search: str | None = None,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> list[str] | dict[str, str]:
        if self._ontology is None:
            async with self._async_db() as db:
                self._ontology = await db.dql_fetch_ontology()
        return _ontology_lookup(self._ontology, op, name, search)


class _DiffbotAskInput(BaseModel):
    question: str = Field(
        description="Natural-language question for Diffbot's RAG LLM."
    )


class DiffbotAskTool(_BaseDiffbotComponent, BaseTool):
    """Tool that asks Diffbot's LLM RAG (`ask`) endpoint a natural-language question.

    Where `DiffbotKnowledgeGraphTool` runs a precise DQL query, this delegates a
    fuzzy question to Diffbot's own LLM — grounded in the Knowledge Graph and the
    live web — and returns a synthesized answer. Drop it into any tool-calling
    agent so the agent can *consult* Diffbot for things it can't express in DQL.

    The SDK streams the answer; this tool aggregates the stream into a single
    string (use `ChatDiffbot` when you want the chat-model surface with streaming).
    """

    name: str = "diffbot_ask"
    description: str = (
        "Ask Diffbot's LLM a natural-language question. It answers using "
        "Diffbot's Knowledge Graph and a live web search, returning a synthesized "
        "answer with sources. Use for open-ended questions you can't express as a "
        "precise Knowledge Graph (DQL) query."
    )
    args_schema: type[BaseModel] = _DiffbotAskInput

    def _run(
        self,
        question: str,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> str:
        messages = [{"role": "user", "content": question}]
        with self._sync_db() as db:
            return "".join(db.ask(messages))

    async def _arun(
        self,
        question: str,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> str:
        messages = [{"role": "user", "content": question}]
        parts: list[str] = []
        async with self._async_db() as db:
            async for chunk in db.ask(messages):
                parts.append(chunk)
        return "".join(parts)


class _DiffbotDQLProbeInput(BaseModel):
    queries: list[str] = Field(
        description=(
            "DQL query variants to probe. Each is run with size=0 (hit count only)."
        )
    )
    workers: int = Field(default=8, description="Max concurrent requests.")


class DiffbotDQLProbeTool(_BaseDiffbotComponent, BaseTool):
    """Tool that probes DQL query variants in parallel, returning hit counts only.

    Each query runs with `size=0`, so the response carries the match count but no
    entity data — cheap and fast. Use it to check a query's selectivity (too
    broad? too narrow?) and compare variants before committing to a full
    `diffbot_knowledge_graph` query. Backed by `Diffbot.dql_parallel()`.
    """

    name: str = "diffbot_dql_probe"
    description: str = (
        "Probe one or more DQL query variants in parallel and get the hit count "
        "for each (size=0, no entity data). Use to validate that a query is "
        "well-shaped — not matching zero results or millions — before running it."
    )
    args_schema: type[BaseModel] = _DiffbotDQLProbeInput

    @staticmethod
    def _shape(queries: list[str], results: list[Any]) -> list[dict[str, Any]]:
        return [
            {
                "query": q,
                "hits": r.get("hits") if isinstance(r, dict) else None,
            }
            for q, r in zip(queries, results, strict=False)
        ]

    def _run(
        self,
        queries: list[str],
        workers: int = 8,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> list[dict[str, Any]]:
        reqs = [{"query": q, "size": 0} for q in queries]
        with self._sync_db() as db:
            results = db.dql_parallel(reqs, workers=workers)
        return self._shape(queries, results)

    async def _arun(
        self,
        queries: list[str],
        workers: int = 8,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> list[dict[str, Any]]:
        reqs = [{"query": q, "size": 0} for q in queries]
        async with self._async_db() as db:
            results = await db.dql_parallel(reqs, workers=workers)
        return self._shape(queries, results)
