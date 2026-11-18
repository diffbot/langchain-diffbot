"""Unit tests for the Diffbot document loaders (no network)."""

from __future__ import annotations

import httpx
import pytest
import respx
from diffbot import Diffbot, DiffbotAsync
from diffbot.crawl import CrawlEvent, CrawlEventType
from diffbot.errors import JobError

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


@respx.mock
def test_extract_loader_passes_extract_options() -> None:
    route = respx.get(ANALYZE_URL).mock(
        return_value=httpx.Response(200, json={"objects": [{"text": "x"}]})
    )
    loader = DiffbotExtractLoader(
        client=Diffbot(token="t"),
        urls=["https://example.com"],
        extract_options={"timeout": 5000, "fields": ["links", "meta"], "paging": False},
    )
    assert len(list(loader.lazy_load())) == 1
    params = route.calls.last.request.url.params
    assert params["timeout"] == "5000"
    assert params["fields"] == "links,meta"


@respx.mock
async def test_extract_loader_alazy_load_passes_extract_options() -> None:
    route = respx.get(ANALYZE_URL).mock(
        return_value=httpx.Response(200, json={"objects": [{"text": "x"}]})
    )
    loader = DiffbotExtractLoader(
        async_client=DiffbotAsync(token="t"),
        urls=["https://example.com"],
        extract_options={"timeout": 7000, "mode": "article"},
    )
    assert len([d async for d in loader.alazy_load()]) == 1
    params = route.calls.last.request.url.params
    assert params["timeout"] == "7000"
    assert params["mode"] == "article"


@respx.mock
def test_extract_loader_default_sends_no_extra_options() -> None:
    route = respx.get(ANALYZE_URL).mock(
        return_value=httpx.Response(200, json={"objects": [{"text": "x"}]})
    )
    loader = DiffbotExtractLoader(client=Diffbot(token="t"), urls=["https://e.com"])
    list(loader.lazy_load())
    assert "fields" not in route.calls.last.request.url.params


def _crawl_stubs(mocker, statuses: list[dict], records: list[dict]):  # type: ignore[no-untyped-def]
    db = Diffbot(token="t")
    started = mocker.patch.object(
        db,
        "crawl",
        return_value=iter(
            [CrawlEvent(CrawlEventType.JOB_CREATED, "now", {"job_name": "job1"})]
        ),
    )
    get_job = mocker.patch.object(db, "crawl_get_job", side_effect=statuses)
    download = mocker.patch.object(db, "crawl_download", return_value=records)
    return db, started, get_job, download


_RECORDS = [
    {"text": "Page one", "title": "One", "pageUrl": "https://example.com/1"},
    {"text": "Page two", "title": "Two", "pageUrl": "https://example.com/2"},
]


def test_crawl_loader_download_starts_polls_and_downloads(mocker) -> None:  # type: ignore[no-untyped-def]
    db, started, get_job, download = _crawl_stubs(
        mocker,
        [{"jobStatus": {"status": 0}}, {"jobStatus": {"status": 9, "message": "done"}}],
        _RECORDS,
    )
    loader = DiffbotCrawlLoader(
        client=db,
        site="https://example.com",
        download=True,
        poll_interval=0,
        download_num=5,
        crawl_kwargs={"hops": 1},
    )
    docs = list(loader.lazy_load())
    started.assert_called_once_with("https://example.com", hops=1, watch=False)
    assert get_job.call_count == 2
    download.assert_called_once_with("job1", format="json", type=None, num=5)
    assert [d.page_content for d in docs] == ["Page one", "Page two"]
    assert docs[0].metadata["url"] == "https://example.com/1"
    assert docs[0].metadata["title"] == "One"


def test_crawl_loader_download_reuses_existing_job(mocker) -> None:  # type: ignore[no-untyped-def]
    db, started, _, download = _crawl_stubs(
        mocker, [{"jobStatus": {"status": 9, "message": "done"}}], _RECORDS
    )
    loader = DiffbotCrawlLoader(
        client=db, site="https://example.com", download=True, job_name="existing"
    )
    assert len(list(loader.lazy_load())) == 2
    started.assert_not_called()
    assert download.call_args.args == ("existing",)


def test_crawl_loader_download_raises_on_failed_job(mocker) -> None:  # type: ignore[no-untyped-def]
    db, *_ = _crawl_stubs(
        mocker, [{"jobStatus": {"status": 4, "message": "Job failed"}}], []
    )
    loader = DiffbotCrawlLoader(client=db, site="https://example.com", download=True)
    with pytest.raises(JobError):
        list(loader.lazy_load())


def test_crawl_loader_download_times_out(mocker) -> None:  # type: ignore[no-untyped-def]
    db, *_ = _crawl_stubs(mocker, [{"jobStatus": {"status": 0}}] * 50, [])
    loader = DiffbotCrawlLoader(
        client=db,
        site="https://example.com",
        download=True,
        poll_interval=0,
        poll_timeout=0,
    )
    with pytest.raises(TimeoutError):
        list(loader.lazy_load())


async def test_crawl_loader_download_async(mocker) -> None:  # type: ignore[no-untyped-def]
    db = DiffbotAsync(token="t")

    async def fake_crawl(site, **kwargs):  # type: ignore[no-untyped-def]
        assert kwargs["watch"] is False
        yield CrawlEvent(CrawlEventType.JOB_CREATED, "now", {"job_name": "job1"})

    mocker.patch.object(db, "crawl", fake_crawl)
    mocker.patch.object(
        db,
        "crawl_get_job",
        side_effect=[{"jobStatus": {"status": 0}}, {"jobStatus": {"status": 9}}],
    )
    mocker.patch.object(db, "crawl_download", return_value=_RECORDS)
    loader = DiffbotCrawlLoader(
        async_client=db, site="https://example.com", download=True, poll_interval=0
    )
    docs = [d async for d in loader.alazy_load()]
    assert [d.page_content for d in docs] == ["Page one", "Page two"]


def test_crawl_loader_default_path_does_not_download(mocker) -> None:  # type: ignore[no-untyped-def]
    db = Diffbot(token="t")
    crawl = mocker.patch.object(db, "crawl", return_value=iter([]))
    download = mocker.patch.object(db, "crawl_download")
    assert list(DiffbotCrawlLoader(client=db, site="https://e.com").lazy_load()) == []
    crawl.assert_called_once_with("https://e.com", watch=True)
    download.assert_not_called()
