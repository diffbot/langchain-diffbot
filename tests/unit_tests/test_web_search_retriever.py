"""Unit tests for `DiffbotWebSearchRetriever` (no network)."""

from __future__ import annotations

import httpx
import respx
from langchain_core.documents import Document

from langchain_diffbot import DiffbotWebSearchRetriever

WEB_SEARCH_URL = "https://llm.diffbot.com/api/v1/web_search"

SAMPLE_BODY = {
    "search_results": [
        {
            "score": 0.91,
            "title": "Diffbot Knowledge Graph",
            "pageUrl": "https://www.diffbot.com/kg/",
            "content": "Diffbot KG is the largest commercial knowledge graph...",
        },
        {
            "score": 0.42,
            "title": "About Diffbot",
            "pageUrl": "https://www.diffbot.com/about",
            "snippet": "Diffbot uses AI to extract structured data from web pages.",
        },
    ]
}


@respx.mock
def test_invoke_maps_results_to_documents() -> None:
    respx.get(WEB_SEARCH_URL).mock(return_value=httpx.Response(200, json=SAMPLE_BODY))
    r = DiffbotWebSearchRetriever(diffbot_api_token="t", k=2)
    docs = r.invoke("diffbot knowledge graph")
    assert len(docs) == 2
    assert all(isinstance(d, Document) for d in docs)
    # Default content_fields priority: content first.
    assert docs[0].page_content.startswith("Diffbot KG is")
    assert docs[0].metadata["title"] == "Diffbot Knowledge Graph"
    assert docs[0].metadata["score"] == 0.91
    # `content` was promoted to page_content — should not leak into metadata.
    assert "content" not in docs[0].metadata
    # Falls back to `snippet` when `content` is missing.
    assert docs[1].page_content.startswith("Diffbot uses AI")


@respx.mock
def test_num_results_and_max_tokens_pass_through() -> None:
    route = respx.get(WEB_SEARCH_URL).mock(
        return_value=httpx.Response(200, json=SAMPLE_BODY)
    )
    r = DiffbotWebSearchRetriever(diffbot_api_token="t", k=5, max_tokens=2000)
    r.invoke("diffbot")
    params = route.calls.last.request.url.params
    # diffbot-python sends the `num_results` kwarg as the `size` wire param.
    assert params["size"] == "5"
    assert params["maxTokens"] == "2000"


@respx.mock
def test_fields_allowlist() -> None:
    respx.get(WEB_SEARCH_URL).mock(return_value=httpx.Response(200, json=SAMPLE_BODY))
    r = DiffbotWebSearchRetriever(
        diffbot_api_token="t", k=1, fields=["title", "pageUrl"]
    )
    [doc] = r.invoke("diffbot")
    assert set(doc.metadata) == {"title", "pageUrl"}


@respx.mock
def test_document_mapper_overrides_default() -> None:
    respx.get(WEB_SEARCH_URL).mock(return_value=httpx.Response(200, json=SAMPLE_BODY))

    def mapper(hit: dict) -> Document:
        return Document(page_content=hit["title"], metadata={"url": hit["pageUrl"]})

    r = DiffbotWebSearchRetriever(diffbot_api_token="t", k=1, document_mapper=mapper)
    [doc] = r.invoke("diffbot")
    assert doc.page_content == "Diffbot Knowledge Graph"
    assert doc.metadata == {"url": "https://www.diffbot.com/kg/"}


@respx.mock
async def test_ainvoke_works() -> None:
    respx.get(WEB_SEARCH_URL).mock(return_value=httpx.Response(200, json=SAMPLE_BODY))
    r = DiffbotWebSearchRetriever(diffbot_api_token="t", k=2)
    docs = await r.ainvoke("diffbot")
    assert [d.metadata["title"] for d in docs] == [
        "Diffbot Knowledge Graph",
        "About Diffbot",
    ]
