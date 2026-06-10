"""Diffbot document loaders — batch ingestion via Extract and Crawl."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Iterator
from typing import Any

from diffbot.crawl import CrawlEvent, CrawlEventType
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document
from pydantic import Field

from langchain_diffbot._base import _BaseDiffbotComponent

ExtractDocumentMapper = Callable[[str, dict[str, Any]], Document]
"""`(url, raw_response) -> Document`."""

CrawlEventMapper = Callable[[CrawlEvent], Document | None]
"""`(event) -> Document | None`. Return None to skip the event."""


def _default_extract_mapper(url: str, raw: dict[str, Any]) -> Document:
    objects = raw.get("objects") or []
    first = objects[0] if objects else {}
    page_content = first.get("text") or raw.get("markdown") or ""
    metadata = {
        "url": url,
        "title": first.get("title") or raw.get("title"),
        "pageUrl": first.get("pageUrl") or raw.get("url"),
        "resolvedPageUrl": first.get("resolvedPageUrl"),
        "type": first.get("type") or raw.get("type"),
    }
    return Document(page_content=page_content, metadata=metadata)


def _default_crawl_mapper(event: CrawlEvent) -> Document | None:
    # Non-URL events (e.g. JOB_CREATED) are skipped by default. The Document's
    # page_content is the URL itself — the crawl SDK only surfaces URLs, not
    # page contents. Chain with `DiffbotExtractLoader` to fetch content.
    if event.event_type != CrawlEventType.URL_PROCESSED:
        return None
    url = event.details.get("url", "")
    return Document(
        page_content=url,
        metadata={
            "url": url,
            "status": event.details.get("status"),
            "crawl_timestamp": event.timestamp,
        },
    )


class DiffbotExtractLoader(_BaseDiffbotComponent, BaseLoader):
    """Loader that calls `extract` on each of `urls` and yields a `Document`.

    Example:
        ```python
        from diffbot import Diffbot
        from langchain_diffbot import DiffbotExtractLoader

        docs = DiffbotExtractLoader(
            client=Diffbot(token=...),
            urls=["https://example.com", "https://diffbot.com"],
        ).load()
        ```
    """

    urls: list[str]
    """URLs to extract."""

    api: str = "analyze"
    """Diffbot extract API. Defaults to `analyze`."""

    fmt: str = "markdown"
    """Output format. `markdown` uses Diffbot's LLM-optimized mode."""

    document_mapper: ExtractDocumentMapper | None = None
    """Optional `(url, raw_response) -> Document` override."""

    def _to_doc(self, url: str, raw: dict[str, Any]) -> Document:
        mapper = self.document_mapper or _default_extract_mapper
        return mapper(url, raw)

    def lazy_load(self) -> Iterator[Document]:
        """Yield one `Document` per URL, calling `extract` synchronously."""
        with self._sync_db() as db:
            for url in self.urls:
                raw = db.extract(url, api=self.api, fmt=self.fmt)
                yield self._to_doc(url, raw)

    async def alazy_load(self) -> AsyncIterator[Document]:
        """Yield one `Document` per URL, calling `extract` asynchronously."""
        async with self._async_db() as db:
            for url in self.urls:
                raw = await db.extract(url, api=self.api, fmt=self.fmt)
                yield self._to_doc(url, raw)


class DiffbotCrawlLoader(_BaseDiffbotComponent, BaseLoader):
    """Loader that drives a Diffbot crawl and yields a `Document` per URL.

    By default `page_content` is the crawled URL itself (the crawl SDK only
    yields URL events, not page contents). To fetch content per URL, chain
    this with `DiffbotExtractLoader`.

    Defaults `watch=True` so URL events are actually emitted — with
    `watch=False` the SDK only yields a single JOB_CREATED event, which the
    default mapper skips.
    """

    site: str
    """Seed URL for the crawl."""

    crawl_kwargs: dict[str, Any] = Field(default_factory=dict)
    """Extra kwargs passed to `Diffbot.crawl(site, **crawl_kwargs)`.

    Defaults to `{"watch": True}` if not overridden.
    """

    event_mapper: CrawlEventMapper | None = None
    """Optional `(event) -> Document | None` override. Return None to skip."""

    def _kwargs(self) -> dict[str, Any]:
        kw = dict(self.crawl_kwargs)
        kw.setdefault("watch", True)
        return kw

    def _map_event(self, event: CrawlEvent) -> Document | None:
        mapper = self.event_mapper or _default_crawl_mapper
        return mapper(event)

    def lazy_load(self) -> Iterator[Document]:
        """Drive a crawl synchronously and yield a `Document` per mapped event."""
        with self._sync_db() as db:
            for event in db.crawl(self.site, **self._kwargs()):
                doc = self._map_event(event)
                if doc is not None:
                    yield doc

    async def alazy_load(self) -> AsyncIterator[Document]:
        """Drive a crawl asynchronously and yield a `Document` per mapped event."""
        async with self._async_db() as db:
            async for event in db.crawl(self.site, **self._kwargs()):
                doc = self._map_event(event)
                if doc is not None:
                    yield doc
