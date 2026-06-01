"""Unit tests for the Diffbot tools (no network)."""

from __future__ import annotations

import httpx
import respx

from langchain_diffbot import (
    DiffbotDQLProbeTool,
    DiffbotEntitiesTool,
    DiffbotExtractTool,
    DiffbotKnowledgeGraphTool,
    DiffbotOntologyTool,
    DiffbotWebSearchTool,
)

ANALYZE_URL = "https://api.diffbot.com/v3/analyze"
WEB_SEARCH_URL = "https://llm.diffbot.com/api/v1/web_search"
NLP_URL = "https://nl.diffbot.com/v1/"
DQL_URL = "https://kg.diffbot.com/kg/v3/dql"
ONTOLOGY_URL = "https://kg.diffbot.com/kg/ontology"

_FIXTURE_ONTOLOGY = {
    "types": {
        "Organization": {
            "fields": {
                "name": {"type": "String"},
                "location": {"type": "Location", "isComposite": True},
            }
        },
        "Person": {"fields": {"name": {"type": "String"}}},
    },
    "composites": {
        "Location": {"fields": {"city": {"type": "City", "isComposite": True}}}
    },
    "enums": {"Language": {"values": ["EN", "FR"]}},
    "taxonomies": {
        "OrganizationCategory": {
            "categories": [
                {
                    "name": "Technology",
                    "children": [{"name": "Semiconductor Companies"}],
                }
            ]
        }
    },
}


def _mock_ontology() -> respx.Route:
    return respx.get(ONTOLOGY_URL).mock(
        return_value=httpx.Response(200, json=_FIXTURE_ONTOLOGY)
    )


@respx.mock
def test_extract_tool_shapes_response() -> None:
    raw = {
        "objects": [
            {
                "text": "Hello world",
                "title": "Example",
                "type": "article",
                "pageUrl": "https://example.com",
                "resolvedPageUrl": "https://example.com/",
            }
        ]
    }
    respx.get(ANALYZE_URL).mock(return_value=httpx.Response(200, json=raw))
    tool = DiffbotExtractTool(diffbot_api_token="t")
    out = tool.invoke({"url": "https://example.com"})
    assert out["content"] == "Hello world"
    assert out["title"] == "Example"
    assert out["type"] == "article"
    assert out["resolvedPageUrl"] == "https://example.com/"


@respx.mock
def test_extract_tool_returns_structured_error_on_extraction_failure() -> None:
    # `extract` returns 200 with an `errorCode` body → SDK raises ExtractionError →
    # tool maps to a dict instead of bubbling the exception to the agent.
    respx.get(ANALYZE_URL).mock(
        return_value=httpx.Response(
            200, json={"errorCode": 500, "error": "could not fetch"}
        )
    )
    tool = DiffbotExtractTool(diffbot_api_token="t")
    out = tool.invoke({"url": "https://example.com"})
    assert out["errorCode"] == 500
    assert "could not fetch" in out["error"]


@respx.mock
def test_extract_tool_propagates_auth_error() -> None:
    respx.get(ANALYZE_URL).mock(
        return_value=httpx.Response(401, text='{"message": "bad token"}')
    )
    tool = DiffbotExtractTool(diffbot_api_token="t")
    try:
        tool.invoke({"url": "https://example.com"})
    except Exception as e:  # diffbot.errors.AuthError
        assert "401" in str(e)
    else:
        raise AssertionError("expected AuthError to propagate")


@respx.mock
def test_web_search_tool_returns_results_list() -> None:
    body = {
        "search_results": [
            {
                "score": 1.0,
                "title": "A",
                "pageUrl": "https://a.example",
                "content": "hi",
            }
        ]
    }
    respx.get(WEB_SEARCH_URL).mock(return_value=httpx.Response(200, json=body))
    tool = DiffbotWebSearchTool(diffbot_api_token="t")
    out = tool.invoke({"text": "anything", "num_results": 1})
    assert isinstance(out, list)
    assert out[0]["title"] == "A"


@respx.mock
def test_entities_tool_returns_response_dict() -> None:
    body = [
        {
            "entities": [{"name": "Apple", "type": "Organization", "id": "E1"}],
            "sentiment": 0.4,
        }
    ]
    respx.post(NLP_URL).mock(return_value=httpx.Response(200, json=body))
    tool = DiffbotEntitiesTool(diffbot_api_token="t")
    out = tool.invoke({"text": "Apple CEO ..."})
    assert out["entities"][0]["id"] == "E1"
    assert out["sentiment"] == 0.4


@respx.mock
def test_kg_tool_returns_raw_body() -> None:
    body = {"data": [{"score": 1.0, "entity": {"id": "E1", "name": "Acme"}}]}
    respx.get(DQL_URL).mock(return_value=httpx.Response(200, json=body))
    tool = DiffbotKnowledgeGraphTool(diffbot_api_token="t")
    out = tool.invoke({"query": "type:Organization", "size": 1})
    assert out["data"][0]["entity"]["id"] == "E1"


@respx.mock
def test_ontology_tool_lists_and_caches() -> None:
    route = _mock_ontology()
    tool = DiffbotOntologyTool(diffbot_api_token="t")
    assert tool.invoke({"op": "types"}) == ["Organization", "Person"]
    # Second call is served from the in-memory cache — no second HTTP fetch.
    assert tool.invoke({"op": "enums"}) == ["Language"]
    assert route.call_count == 1


@respx.mock
def test_ontology_tool_fields_and_taxonomy() -> None:
    _mock_ontology()
    tool = DiffbotOntologyTool(diffbot_api_token="t")
    fields = tool.invoke({"op": "fields", "name": "Organization"})
    assert "location: [Location] [isComposite]" in fields
    tax = tool.invoke(
        {"op": "taxonomy", "name": "OrganizationCategory", "search": "semi"}
    )
    assert tax == ["Semiconductor Companies"]


@respx.mock
def test_ontology_tool_returns_error_dict_on_unknown_type() -> None:
    _mock_ontology()
    tool = DiffbotOntologyTool(diffbot_api_token="t")
    out = tool.invoke({"op": "fields", "name": "Nope"})
    assert isinstance(out, dict)
    assert "error" in out
    out = tool.invoke({"op": "fields"})  # missing required name
    assert "error" in out


@respx.mock
def test_dql_probe_tool_returns_hit_counts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["size"] == "0"
        hits = 5 if "Diffbot" in request.url.params["query"] else 100
        return httpx.Response(200, json={"hits": hits, "results": 0})

    respx.get(DQL_URL).mock(side_effect=handler)
    tool = DiffbotDQLProbeTool(diffbot_api_token="t")
    out = tool.invoke(
        {"queries": ['type:Organization name:"Diffbot"', "type:Organization"]}
    )
    assert out == [
        {"query": 'type:Organization name:"Diffbot"', "hits": 5},
        {"query": "type:Organization", "hits": 100},
    ]
