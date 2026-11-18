"""Diffbot document loaders — batch ingestion via Extract and Crawl."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Callable, Iterator
from typing import Any

from diffbot.crawl import CrawlEvent, CrawlEventType
from diffbot.errors import JobError
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document
from pydantic import Field, field_validator

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


CrawlRecordMapper = Callable[[dict[str, Any]], Document | None]
"""`(record) -> Document | None` for `crawl_download` records. None skips."""

# Crawler job status codes that mean "still running" (matches the SDK's own
# watch loop); anything else is terminal.
_CRAWL_RUNNING_STATUSES = (0, 7)


def _default_record_mapper(record: dict[str, Any]) -> Document | None:
    url = record.get("pageUrl") or record.get("resolvedPageUrl") or ""
    return _default_extract_mapper(url, {"objects": [record]})


def _check_job_done(job_name: str, job: dict[str, Any]) -> bool:
    """Return True when the job is terminal; raise `JobError` if it failed.

    `crawl_get_job` returns `{}` for an unknown job; that is an error, not a
    job that is "still running" (otherwise we'd poll until `poll_timeout`).
    """
    if not job:
        raise JobError(job_name, f"Crawler job {job_name!r} not found")
    status = job.get("jobStatus") or {}
    if status.get("status", 0) in _CRAWL_RUNNING_STATUSES:
        return False
    message = status.get("message", "")
    if "fail" in message.lower() or "error" in message.lower():
        raise JobError(job_name, f"Crawler job failed: {message}")
    return True


def _poll_timeout_error(job_name: str, timeout: float) -> TimeoutError:
    return TimeoutError(f"Crawl job {job_name!r} not finished after {timeout}s")


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

    extract_options: dict[str, Any] = Field(default_factory=dict)
    """Keyword options forwarded to `Diffbot.extract` for every URL.

    Any of the SDK's extract options (`timeout`, `mode`, `fields`, `fallback`,
    `discussion`, `paging`, `max_pages`, `natural_language`,
    `summary_num_sentences`, `max_tags`, `tag_confidence`,
    `category_confidence`, `use_proxy`, `extra`). Empty by default.
    """

    document_mapper: ExtractDocumentMapper | None = None
    """Optional `(url, raw_response) -> Document` override."""

    def _to_doc(self, url: str, raw: dict[str, Any]) -> Document:
        mapper = self.document_mapper or _default_extract_mapper
        return mapper(url, raw)

    def lazy_load(self) -> Iterator[Document]:
        """Yield one `Document` per URL, calling `extract` synchronously."""
        with self._sync_db() as db:
            for url in self.urls:
                raw = db.extract(
                    url, api=self.api, fmt=self.fmt, **self.extract_options
                )
                yield self._to_doc(url, raw)

    async def alazy_load(self) -> AsyncIterator[Document]:
        """Yield one `Document` per URL, calling `extract` asynchronously."""
        async with self._async_db() as db:
            for url in self.urls:
                raw = await db.extract(
                    url, api=self.api, fmt=self.fmt, **self.extract_options
                )
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

    download: bool = False
    """Opt in to the start / poll / download path instead of watching.

    When True the loader starts a job (or reuses `job_name`), polls
    `crawl_get_job` until it finishes, then calls `crawl_download` and yields a
    `Document` per extracted record with real page content. `watch` and
    `event_mapper` are not used in this mode. Default False keeps the
    URL-per-event watch behavior.
    """

    job_name: str | None = None
    """Existing crawl job to poll and download (only with `download=True`).

    If unset, a new job is started for `site` (using `crawl_kwargs`, with
    `watch=False`; set `job_name` inside `crawl_kwargs` to choose its name).
    """

    poll_interval: float = 2.0
    """Seconds between job-status polls (only with `download=True`)."""

    poll_timeout: float | None = 600.0
    """Max seconds to wait for the job to finish; None waits forever."""

    download_type: str | None = None
    """Report passed to `crawl_download(type=...)`.

    `"urls"` is rejected: that report is CSV text, not records. Use the default
    watch mode (`download=False`) for a URL-per-`Document` crawl.
    """

    download_num: int | None = None
    """Cap on records passed to `crawl_download(num=...)`."""

    record_mapper: CrawlRecordMapper | None = None
    """Optional `(record) -> Document | None` override for downloaded records."""

    @field_validator("download_type")
    @classmethod
    def _reject_urls_report(cls, v: str | None) -> str | None:
        if v == "urls":
            raise ValueError(
                'download_type="urls" returns CSV text, not records; use the '
                "default watch mode (download=False) to get one Document per URL"
            )
        return v

    def _kwargs(self) -> dict[str, Any]:
        kw = dict(self.crawl_kwargs)
        kw.setdefault("watch", True)
        return kw

    def _map_event(self, event: CrawlEvent) -> Document | None:
        mapper = self.event_mapper or _default_crawl_mapper
        return mapper(event)

    def _records_to_docs(self, records: list[dict[str, Any]]) -> Iterator[Document]:
        mapper = self.record_mapper or _default_record_mapper
        for record in records:
            doc = mapper(record)
            if doc is not None:
                yield doc

    def _deadline(self) -> float | None:
        if self.poll_timeout is None:
            return None
        return time.monotonic() + self.poll_timeout

    def _start_kwargs(self) -> dict[str, Any]:
        kw = dict(self.crawl_kwargs)
        kw["watch"] = False
        return kw

    def lazy_load(self) -> Iterator[Document]:
        """Drive a crawl synchronously and yield a `Document` per mapped event.

        With `download=True`, start (or reuse) a job, poll until it finishes,
        and yield a `Document` per downloaded record instead.
        """
        if self.download:
            yield from self._download_sync()
            return
        with self._sync_db() as db:
            for event in db.crawl(self.site, **self._kwargs()):
                doc = self._map_event(event)
                if doc is not None:
                    yield doc

    async def alazy_load(self) -> AsyncIterator[Document]:
        """Drive a crawl asynchronously and yield a `Document` per mapped event.

        With `download=True`, start (or reuse) a job, poll until it finishes,
        and yield a `Document` per downloaded record instead.
        """
        if self.download:
            async for downloaded in self._download_async():
                yield downloaded
            return
        async with self._async_db() as db:
            async for event in db.crawl(self.site, **self._kwargs()):
                doc = self._map_event(event)
                if doc is not None:
                    yield doc

    def _download_sync(self) -> Iterator[Document]:
        with self._sync_db() as db:
            name = self.job_name
            if name is None:
                for event in db.crawl(self.site, **self._start_kwargs()):
                    if event.event_type == CrawlEventType.JOB_CREATED:
                        name = event.details["job_name"]
            if name is None:
                raise RuntimeError("Diffbot crawl did not report a job name")
            deadline = self._deadline()
            while not _check_job_done(name, db.crawl_get_job(name)):
                if deadline is not None and time.monotonic() >= deadline:
                    raise _poll_timeout_error(name, self.poll_timeout or 0)
                time.sleep(self.poll_interval)
            records = db.crawl_download(
                name, format="json", type=self.download_type, num=self.download_num
            )
        yield from self._records_to_docs(records)

    async def _download_async(self) -> AsyncIterator[Document]:
        async with self._async_db() as db:
            name = self.job_name
            if name is None:
                async for event in db.crawl(self.site, **self._start_kwargs()):
                    if event.event_type == CrawlEventType.JOB_CREATED:
                        name = event.details["job_name"]
            if name is None:
                raise RuntimeError("Diffbot crawl did not report a job name")
            deadline = self._deadline()
            while not _check_job_done(name, await db.crawl_get_job(name)):
                if deadline is not None and time.monotonic() >= deadline:
                    raise _poll_timeout_error(name, self.poll_timeout or 0)
                await asyncio.sleep(self.poll_interval)
            records = await db.crawl_download(
                name, format="json", type=self.download_type, num=self.download_num
            )
        for rec_doc in self._records_to_docs(records):
            yield rec_doc
