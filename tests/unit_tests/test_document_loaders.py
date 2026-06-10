"""Unit tests for the Diffbot document loaders (no network)."""

from __future__ import annotations

import httpx
import respx
from diffbot import Diffbot, DiffbotAsync
from diffbot.crawl import CrawlEvent, CrawlEventType

from langchain_diffbot import DiffbotCrawlLoader, DiffbotExtractLoader

ANALYZE_URL = "https://api.diffbot.com/v3/analyze"


@respx.mock
def test_extract_loader_yields_one_document_per_url() -> None:
    respx.get(ANALYZE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "objects": [
                    {
                        "text": "Hello",
                        "title": "Ex",
                        "type": "article",
                        "pageUrl": "https://example.com",
                    }
                ]
            },
        )
    )
    loader = DiffbotExtractLoader(
        client=Diffbot(token="t"),
        urls=["https://example.com", "https://example.com/2"],
    )
    docs = list(loader.lazy_load())
    assert len(docs) == 2
    assert docs[0].page_content == "Hello"
    assert docs[0].metadata["url"] == "https://example.com"
    assert docs[1].metadata["url"] == "https://example.com/2"


@respx.mock
async def test_extract_loader_alazy_load() -> None:
    respx.get(ANALYZE_URL).mock(
        return_value=httpx.Response(
            200, json={"objects": [{"text": "x", "title": "t"}]}
        )
    )
    loader = DiffbotExtractLoader(
        async_client=DiffbotAsync(token="t"), urls=["https://example.com"]
    )
    docs = [d async for d in loader.alazy_load()]
    assert len(docs) == 1
    assert docs[0].page_content == "x"


def test_crawl_loader_default_mapper_filters_to_url_events() -> None:
    # Bypass the SDK by stubbing `_kwargs` and feeding events through the mapper
    # directly — the crawl SDK path is integration-tested upstream.
    loader = DiffbotCrawlLoader(client=Diffbot(token="t"), site="https://example.com")
    job_event = CrawlEvent(
        event_type=CrawlEventType.JOB_CREATED,
        timestamp="now",
        details={"job_name": "j1"},
    )
    url_event = CrawlEvent(
        event_type=CrawlEventType.URL_PROCESSED,
        timestamp="2026-01-01T00:00:00",
        details={"url": "https://example.com/page", "status": "ok"},
    )
    assert loader._map_event(job_event) is None
    doc = loader._map_event(url_event)
    assert doc is not None
    assert doc.page_content == "https://example.com/page"
    assert doc.metadata == {
        "url": "https://example.com/page",
        "status": "ok",
        "crawl_timestamp": "2026-01-01T00:00:00",
    }


def test_crawl_loader_custom_event_mapper() -> None:
    def mapper(event: CrawlEvent):
        # Pass-through both event types as a single-string Document.
        from langchain_core.documents import Document

        return Document(
            page_content=event.event_type.value,
            metadata=dict(event.details),
        )

    loader = DiffbotCrawlLoader(
        client=Diffbot(token="t"), site="https://example.com", event_mapper=mapper
    )
    job_event = CrawlEvent(
        event_type=CrawlEventType.JOB_CREATED,
        timestamp="now",
        details={"job_name": "j1"},
    )
    doc = loader._map_event(job_event)
    assert doc is not None
    assert doc.page_content == "job_created"
    assert doc.metadata == {"job_name": "j1"}


def test_crawl_loader_defaults_watch_true() -> None:
    loader = DiffbotCrawlLoader(client=Diffbot(token="t"), site="https://example.com")
    assert loader._kwargs() == {"watch": True}


def test_crawl_loader_user_can_override_watch() -> None:
    loader = DiffbotCrawlLoader(
        client=Diffbot(token="t"),
        site="https://example.com",
        crawl_kwargs={"watch": False, "hops": 3},
    )
    assert loader._kwargs() == {"watch": False, "hops": 3}
