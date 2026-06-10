"""Diffbot retrievers — Knowledge Graph and Web Search."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.callbacks import (
    AsyncCallbackManagerForRetrieverRun,
    CallbackManagerForRetrieverRun,
)
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import Field

from langchain_diffbot._base import _BaseDiffbotComponent

DEFAULT_KG_CONTENT_FIELDS: tuple[str, ...] = ("description", "summary", "name")
"""Default ordered priority for selecting `page_content` from a KG entity."""

DEFAULT_WEB_CONTENT_FIELDS: tuple[str, ...] = ("content", "snippet")
"""Default ordered priority for selecting `page_content` from a web search result."""

DocumentMapper = Callable[[dict[str, Any]], Document]


def _dict_to_document(
    source: dict[str, Any],
    *,
    content_fields: Sequence[str],
    fields: Sequence[str] | None,
) -> Document:
    """Map a flat dict to a LangChain `Document` using a content-field priority list.

    `page_content` is the first non-empty value among `content_fields`.
    `metadata` is the remaining top-level keys, optionally narrowed to
    `fields` (the projection allowlist).
    """
    page_content = ""
    content_field_used: str | None = None
    for f in content_fields:
        value = source.get(f)
        if value:
            page_content = value if isinstance(value, str) else str(value)
            content_field_used = f
            break

    if fields is None:
        metadata = {k: v for k, v in source.items() if k != content_field_used}
    else:
        metadata = {
            k: source[k] for k in fields if k in source and k != content_field_used
        }
    return Document(page_content=page_content, metadata=metadata)


def _resolve_k(default_k: int, kwargs: dict[str, Any]) -> int:
    k = kwargs.get("k", default_k)
    if not isinstance(k, int) or k <= 0:
        msg = f"`k` must be a positive integer, got {k!r}."
        raise ValueError(msg)
    return k


class DiffbotKnowledgeGraphRetriever(_BaseDiffbotComponent, BaseRetriever):
    """Retriever backed by the Diffbot Knowledge Graph DQL endpoint.

    The `query` passed to `invoke` is a
    [DQL](https://docs.diffbot.com/reference/dql-quickstart) expression
    (e.g. `type:Organization industries:"Artificial Intelligence"`).

    Build a `diffbot.Diffbot` (sync) and/or `diffbot.DiffbotAsync` (async) and
    pass it in; the same client can be shared across many components.

    Example:
        ```python
        from diffbot import Diffbot
        from langchain_diffbot import DiffbotKnowledgeGraphRetriever

        db = Diffbot(token=..., timeout=60.0)
        retriever = DiffbotKnowledgeGraphRetriever(client=db, k=5)
        retriever.invoke('type:Organization location.city.name:"Boston"')
        ```

    Shaping the output (recommended for agent/tool use, where large entity
    payloads can blow past LLM input-token limits):

        ```python
        retriever = DiffbotKnowledgeGraphRetriever(
            client=db,
            k=5,
            fields=["id", "type", "name", "homepageUri", "nbEmployees"],
        )
        ```

    For full control, pass `document_mapper`:

        ```python
        def mapper(entity):
            return Document(
                page_content=entity.get("summary", ""),
                metadata={"id": entity["id"], "name": entity["name"]},
            )

        retriever = DiffbotKnowledgeGraphRetriever(client=db, document_mapper=mapper)
        ```
    """

    k: int = 10
    """Default number of results. Can be overridden per call via `invoke(..., k=N)`."""

    from_: int = 0
    """Result offset (passes through to `dql(from_=...)`)."""

    filter: str | None = None
    """DQL filter expression (passes through to `dql(filter=...)`)."""

    exportspec: str | None = None
    """Export spec for non-JSON formats (passes through to `dql(exportspec=...)`)."""

    format: str = "json"
    """Response format. Defaults to `json`.

    Other values return raw bytes (see `dql(raw=True)`).
    """

    extra: dict[str, str] | None = None
    """Extra query params merged into the DQL request.

    Passes through to `dql(extra=...)`.
    """

    fields: list[str] | None = None
    """Allowlist of top-level entity keys to keep in `metadata`.

    `None` (default) keeps every field. Set this to a small list like
    `["id", "type", "name", "homepageUri"]` to drastically shrink Document
    payloads — important when the retriever feeds an LLM tool call, since
    full Diffbot KG entities can run thousands of tokens each.

    Ignored when `document_mapper` is set.
    """

    content_fields: list[str] = Field(
        default_factory=lambda: list(DEFAULT_KG_CONTENT_FIELDS)
    )
    """Ordered priority for selecting `page_content` from an entity.

    The first key in this list with a non-empty value wins. The chosen key
    is excluded from `metadata` to avoid duplicating data.

    Ignored when `document_mapper` is set.
    """

    document_mapper: DocumentMapper | None = None
    """Optional override mapping a raw entity dict to a `Document`."""

    def _hit_to_document(self, hit: dict[str, Any]) -> Document:
        # Diffbot returns each result as
        # {"score": ..., "entity": {...}, "entity_ctx": ...}. Older shapes
        # (and our tests) sometimes embed entity fields at the top level, so
        # fall back to the hit itself when there's no nested entity.
        entity = hit.get("entity", hit)
        if self.document_mapper is not None:
            return self.document_mapper(entity)
        doc = _dict_to_document(
            entity,
            content_fields=self.content_fields,
            fields=self.fields,
        )
        if "score" in hit:
            doc.metadata["score"] = hit["score"]
        return doc

    def _dql_kwargs(self, size: int) -> dict[str, Any]:
        return {
            "size": size,
            "from_": self.from_,
            "format": self.format,
            "filter": self.filter,
            "exportspec": self.exportspec,
            "extra": self.extra,
        }

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
        **kwargs: Any,
    ) -> list[Document]:
        k = _resolve_k(self.k, kwargs)
        with self._sync_db() as db:
            body = db.dql(query, **self._dql_kwargs(k))
        if not isinstance(body, dict):
            msg = (
                "DQL returned a non-JSON body; "
                "set `format='json'` to use this retriever."
            )
            raise TypeError(msg)
        return [self._hit_to_document(h) for h in body.get("data", [])[:k]]

    async def _aget_relevant_documents(
        self,
        query: str,
        *,
        run_manager: AsyncCallbackManagerForRetrieverRun,
        **kwargs: Any,
    ) -> list[Document]:
        k = _resolve_k(self.k, kwargs)
        async with self._async_db() as db:
            body = await db.dql(query, **self._dql_kwargs(k))
        if not isinstance(body, dict):
            msg = (
                "DQL returned a non-JSON body; "
                "set `format='json'` to use this retriever."
            )
            raise TypeError(msg)
        return [self._hit_to_document(h) for h in body.get("data", [])[:k]]


class DiffbotWebSearchRetriever(_BaseDiffbotComponent, BaseRetriever):
    """Retriever backed by Diffbot's web search API.

    The `query` passed to `invoke` is a natural-language search string.
    Results come back as `Document`s whose `page_content` is the page content
    (or snippet) returned by Diffbot, with `title`, `pageUrl`, and `score` in
    `metadata` by default.

    Example:
        ```python
        from diffbot import Diffbot
        from langchain_diffbot import DiffbotWebSearchRetriever

        retriever = DiffbotWebSearchRetriever(client=Diffbot(token=...), k=5)
        retriever.invoke("diffbot knowledge graph")
        ```
    """

    k: int = 10
    """Number of results to fetch. Maps to the SDK's `num_results`."""

    max_tokens: int | None = None
    """Optional cap on total content tokens.

    Passes through to `web_search(max_tokens=...)`.
    """

    fields: list[str] | None = None
    """Allowlist of result keys to keep in `metadata`.

    `None` keeps every field. Ignored when `document_mapper` is set.
    """

    content_fields: list[str] = Field(
        default_factory=lambda: list(DEFAULT_WEB_CONTENT_FIELDS)
    )
    """Ordered priority for selecting `page_content`. First non-empty wins.

    Ignored when `document_mapper` is set.
    """

    document_mapper: DocumentMapper | None = None
    """Optional override mapping a raw search result dict to a `Document`."""

    def _hit_to_document(self, hit: dict[str, Any]) -> Document:
        if self.document_mapper is not None:
            return self.document_mapper(hit)
        return _dict_to_document(
            hit, content_fields=self.content_fields, fields=self.fields
        )

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
        **kwargs: Any,
    ) -> list[Document]:
        k = _resolve_k(self.k, kwargs)
        with self._sync_db() as db:
            body = db.web_search(query, num_results=k, max_tokens=self.max_tokens)
        return [self._hit_to_document(h) for h in body.get("search_results", [])[:k]]

    async def _aget_relevant_documents(
        self,
        query: str,
        *,
        run_manager: AsyncCallbackManagerForRetrieverRun,
        **kwargs: Any,
    ) -> list[Document]:
        k = _resolve_k(self.k, kwargs)
        async with self._async_db() as db:
            body = await db.web_search(query, num_results=k, max_tokens=self.max_tokens)
        return [self._hit_to_document(h) for h in body.get("search_results", [])[:k]]
