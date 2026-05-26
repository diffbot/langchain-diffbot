"""Unit tests for `DiffbotKnowledgeGraphRetriever` (no network)."""

from __future__ import annotations

import httpx
import pytest
import respx
from diffbot import Diffbot
from langchain_core.documents import Document

from langchain_diffbot import DiffbotKnowledgeGraphRetriever

# Diffbot SDK hardcodes the KG endpoint here (see diffbot/kg.py).
DQL_URL = "https://kg.diffbot.com/kg/v3/dql"

SAMPLE_BODY = {
    "data": [
        {
            "score": 1000.0,
            "entity": {
                "id": "E1",
                "type": "Organization",
                "name": "Acme AI",
                "description": "Boston-based AI company.",
                "homepageUri": "https://acme.example",
            },
            "entity_ctx": {},
        },
        {
            "score": 500.0,
            "entity": {
                "id": "E2",
                "type": "Organization",
                "name": "Beta Labs",
                "summary": "Robotics startup.",
            },
            "entity_ctx": {},
        },
    ]
}


def test_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DIFFBOT_API_TOKEN", raising=False)
    with pytest.raises(ValueError, match="Diffbot API token"):
        DiffbotKnowledgeGraphRetriever()


def test_reads_token_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DIFFBOT_API_TOKEN", "env-token")
    r = DiffbotKnowledgeGraphRetriever()
    assert r.diffbot_api_token.get_secret_value() == "env-token"


@respx.mock
def test_invoke_maps_entities_to_documents() -> None:
    respx.get(f"{DQL_URL}").mock(return_value=httpx.Response(200, json=SAMPLE_BODY))
    r = DiffbotKnowledgeGraphRetriever(diffbot_api_token="t", k=2)
    docs = r.invoke("type:Organization")
    assert len(docs) == 2
    assert all(isinstance(d, Document) for d in docs)
    assert docs[0].page_content == "Boston-based AI company."
    assert docs[0].metadata["name"] == "Acme AI"
    # `description` should not leak into metadata (it's the page_content).
    assert "description" not in docs[0].metadata
    # Score from the outer hit rides along on metadata.
    assert docs[0].metadata["score"] == 1000.0
    # Fallback path: no description, uses summary.
    assert docs[1].page_content == "Robotics startup."


@respx.mock
def test_invoke_handles_flat_entity_shape() -> None:
    # Backwards-compat: some endpoints / mocks return entity fields at the
    # top level instead of nested under `entity`. The retriever should still
    # produce a usable Document.
    flat_body = {
        "data": [
            {"id": "E9", "type": "Organization", "name": "Flat Co", "description": "x"}
        ]
    }
    respx.get(f"{DQL_URL}").mock(return_value=httpx.Response(200, json=flat_body))
    r = DiffbotKnowledgeGraphRetriever(diffbot_api_token="t")
    [doc] = r.invoke("type:Organization")
    assert doc.page_content == "x"
    assert doc.metadata["name"] == "Flat Co"


@respx.mock
def test_invoke_k_kwarg_overrides_default() -> None:
    route = respx.get(f"{DQL_URL}").mock(
        return_value=httpx.Response(200, json=SAMPLE_BODY)
    )
    r = DiffbotKnowledgeGraphRetriever(diffbot_api_token="t", k=10)
    r.invoke("type:Organization", k=3)
    assert route.calls.last.request.url.params["size"] == "3"


@respx.mock
def test_invoke_rejects_invalid_k() -> None:
    respx.get(f"{DQL_URL}").mock(return_value=httpx.Response(200, json=SAMPLE_BODY))
    r = DiffbotKnowledgeGraphRetriever(diffbot_api_token="t")
    with pytest.raises(ValueError, match="positive integer"):
        r.invoke("type:Organization", k=0)


@respx.mock
async def test_ainvoke_maps_entities_to_documents() -> None:
    respx.get(f"{DQL_URL}").mock(return_value=httpx.Response(200, json=SAMPLE_BODY))
    r = DiffbotKnowledgeGraphRetriever(diffbot_api_token="t", k=2)
    docs = await r.ainvoke("type:Organization")
    assert [d.metadata["id"] for d in docs] == ["E1", "E2"]


FAT_BODY = {
    "data": [
        {
            "score": 1234.5,
            "entity": {
                "id": "E1",
                "type": "Organization",
                "name": "Acme AI",
                "description": "Boston-based AI company.",
                "homepageUri": "https://acme.example",
                "nbEmployees": 42,
                "suppliers": [{"name": "X"}, {"name": "Y"}],
                "industries": ["AI", "Robotics"],
                "tags": [{"label": "ML"}] * 100,
            },
            "entity_ctx": {},
        }
    ]
}


@respx.mock
def test_fields_projection_narrows_metadata() -> None:
    respx.get(f"{DQL_URL}").mock(return_value=httpx.Response(200, json=FAT_BODY))
    r = DiffbotKnowledgeGraphRetriever(
        diffbot_api_token="t",
        fields=["id", "name", "homepageUri", "nbEmployees"],
    )
    [doc] = r.invoke("type:Organization")
    assert doc.page_content == "Boston-based AI company."
    # `score` always rides along (it's an outer hit field, not part of the
    # projection allowlist).
    assert set(doc.metadata) == {"id", "name", "homepageUri", "nbEmployees", "score"}
    # Confirm noisy fields were dropped.
    assert "suppliers" not in doc.metadata
    assert "tags" not in doc.metadata


@respx.mock
def test_fields_excludes_chosen_content_field() -> None:
    # If `description` is in `fields` it should still be excluded from metadata
    # because it was promoted to `page_content`.
    respx.get(f"{DQL_URL}").mock(return_value=httpx.Response(200, json=FAT_BODY))
    r = DiffbotKnowledgeGraphRetriever(
        diffbot_api_token="t",
        fields=["id", "name", "description"],
    )
    [doc] = r.invoke("type:Organization")
    assert doc.page_content == "Boston-based AI company."
    assert "description" not in doc.metadata


@respx.mock
def test_content_fields_priority_is_configurable() -> None:
    body = {
        "data": [
            {
                "id": "E1",
                "name": "Acme",
                "description": "Long description.",
                "summary": "Short summary.",
            }
        ]
    }
    respx.get(f"{DQL_URL}").mock(return_value=httpx.Response(200, json=body))
    r = DiffbotKnowledgeGraphRetriever(
        diffbot_api_token="t",
        content_fields=["summary", "description", "name"],
    )
    [doc] = r.invoke("type:Organization")
    assert doc.page_content == "Short summary."
    # `summary` was consumed; `description` rides along in metadata.
    assert doc.metadata.get("description") == "Long description."
    assert "summary" not in doc.metadata


@respx.mock
def test_document_mapper_overrides_default() -> None:
    respx.get(f"{DQL_URL}").mock(return_value=httpx.Response(200, json=FAT_BODY))

    def mapper(entity: dict) -> Document:
        return Document(
            page_content=f"{entity['name']} ({entity['id']})",
            metadata={"id": entity["id"]},
        )

    r = DiffbotKnowledgeGraphRetriever(
        diffbot_api_token="t",
        # These should be ignored when document_mapper is set.
        fields=["nbEmployees"],
        content_fields=["description"],
        document_mapper=mapper,
    )
    [doc] = r.invoke("type:Organization")
    assert doc.page_content == "Acme AI (E1)"
    assert doc.metadata == {"id": "E1"}


@respx.mock
def test_sdk_kwargs_pass_through() -> None:
    # The SDK serializes from_, filter, format, exportspec onto the request URL.
    # We don't want to assert the SDK's wire format byte-for-byte (that's its
    # job to test), but the params should at least show up.
    route = respx.get(DQL_URL).mock(return_value=httpx.Response(200, json=SAMPLE_BODY))
    r = DiffbotKnowledgeGraphRetriever(
        diffbot_api_token="t",
        k=5,
        from_=10,
        filter="type:Organization",
        exportspec="csv-spec",
    )
    r.invoke("name:Acme")
    params = route.calls.last.request.url.params
    assert params["size"] == "5"
    assert params["from"] == "10"
    assert params["filter"] == "type:Organization"
    assert params["exportspec"] == "csv-spec"


@respx.mock
def test_client_passthrough_uses_provided_diffbot() -> None:
    # If the user supplies a pre-built client, we use it as-is and don't close
    # it. After two retrieve calls the client should still be usable, proving
    # it wasn't closed between calls.
    respx.get(DQL_URL).mock(return_value=httpx.Response(200, json=SAMPLE_BODY))
    db = Diffbot(token="t", timeout=5.0)
    r = DiffbotKnowledgeGraphRetriever(client=db, k=1)
    r.invoke("name:Acme")
    r.invoke("name:Beta")
    # Direct SDK call still works — confirms we didn't close the user's client.
    assert isinstance(db.dql("name:Charlie", size=1), dict)
    db.close()


def test_client_passthrough_skips_token_requirement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # When a client is supplied, no token is needed at construction time.
    monkeypatch.delenv("DIFFBOT_API_TOKEN", raising=False)
    db = Diffbot(token="t")
    r = DiffbotKnowledgeGraphRetriever(client=db)
    # No exception even though there's no token field set.
    assert r.diffbot_api_token is None
    db.close()
