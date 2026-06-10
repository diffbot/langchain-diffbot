"""Execute the Python code blocks in README.md against mocked Diffbot endpoints.

README.md is maintained alongside the LangChain docs pages. This guards against
the README drifting from the package: a renamed class, a changed kwarg, or a
wrong import surfaces here as a failing exec rather than as a user copy-pasting
a broken snippet.

The blocks are run under `respx` mocks of every Diffbot endpoint — the same
canned-response style the rest of `unit_tests/` uses — so the suite stays
deterministic and needs no token or network. Blocks importing anything outside
`DIFFBOT_ONLY_IMPORTS` (e.g. the LCEL example's `langchain_anthropic`, which
would hit a real third-party API) are skipped, as are non-executable blocks
(`tests.readme.is_executable` — the crawl example drives a real job); the live
integration suite handles the former. See `tests/readme.py` for the shared
extraction helpers, and `tests/integration_tests/test_readme_examples.py` for
the live counterpart.
"""

from __future__ import annotations

import contextlib
import io

import httpx
import pytest
import respx

from tests.readme import (
    DIFFBOT_ONLY_IMPORTS,
    extract_blocks,
    import_roots,
    is_executable,
)

# Endpoint fixtures, mirroring the per-component unit tests.
DQL_URL = "https://kg.diffbot.com/kg/v3/dql"
WEB_SEARCH_URL = "https://llm.diffbot.com/api/v1/web_search"
ANALYZE_URL = "https://api.diffbot.com/v3/analyze"
ASK_URL = "https://llm.diffbot.com/rag/v1/chat/completions"
NLP_URL = "https://nl.diffbot.com/v1/"
ONTOLOGY_URL = "https://kg.diffbot.com/kg/ontology"

DQL_BODY = {
    # `hits` lets the DQL-probe example (size=0) shape a real count.
    "hits": 42,
    "data": [
        {
            "score": 1000.0,
            "entity": {
                "id": "E1",
                "type": "Organization",
                "name": "Acme AI",
                "description": "Boston-based AI company.",
                "homepageUri": "https://acme.example",
                "nbEmployees": 42,
                "industries": ["Artificial Intelligence"],
            },
        }
    ],
}

NLP_BODY = [
    {
        "entities": [{"name": "Diffbot", "type": "Organization", "id": "E1"}],
        "sentiment": 0.4,
    }
]

ONTOLOGY_BODY = {
    "types": {
        "Organization": {"fields": {"name": {"type": "String"}}},
        "Person": {"fields": {"name": {"type": "String"}}},
    },
    "composites": {},
    "enums": {},
    "taxonomies": {},
}

WEB_SEARCH_BODY = {
    "search_results": [
        {
            "score": 0.91,
            "title": "Diffbot Knowledge Graph",
            "pageUrl": "https://www.diffbot.com/kg/",
            "content": "Diffbot KG is the largest commercial knowledge graph...",
        }
    ]
}

ANALYZE_BODY = {
    "objects": [
        {
            "text": "Hello world",
            "title": "Example",
            "type": "article",
            "pageUrl": "https://example.com",
        }
    ]
}

SSE_BODY = (
    b'data: {"choices": [{"delta": {"content": "Hello"}}]}\n'
    b'data: {"choices": [{"delta": {"content": ", world"}}]}\n'
    b"data: [DONE]\n"
)

_BLOCKS = extract_blocks()


def test_readme_has_python_examples() -> None:
    # Guard against the extraction silently matching nothing (e.g. fence style
    # changes), which would make every parametrized case vanish.
    assert len(_BLOCKS) >= 12


@pytest.mark.parametrize("source", [b for _, b in _BLOCKS], ids=[i for i, _ in _BLOCKS])
def test_readme_example_runs(
    source: str,
    respx_mock: respx.MockRouter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not is_executable(source):
        pytest.skip("illustrative block (e.g. crawl) — not executed by the suite")

    unmockable = import_roots(source) - DIFFBOT_ONLY_IMPORTS
    if unmockable:
        pytest.skip(f"imports {sorted(unmockable)} — covered by the live suite")

    monkeypatch.setenv("DIFFBOT_API_TOKEN", "test-token")
    respx_mock.get(DQL_URL).mock(return_value=httpx.Response(200, json=DQL_BODY))
    respx_mock.get(WEB_SEARCH_URL).mock(
        return_value=httpx.Response(200, json=WEB_SEARCH_BODY)
    )
    respx_mock.get(ANALYZE_URL).mock(
        return_value=httpx.Response(200, json=ANALYZE_BODY)
    )
    respx_mock.post(ASK_URL).mock(return_value=httpx.Response(200, content=SSE_BODY))
    respx_mock.post(NLP_URL).mock(return_value=httpx.Response(200, json=NLP_BODY))
    respx_mock.get(ONTOLOGY_URL).mock(
        return_value=httpx.Response(200, json=ONTOLOGY_BODY)
    )

    # Examples print for illustration; swallow it to keep test output clean.
    with contextlib.redirect_stdout(io.StringIO()):
        exec(
            compile(source, f"README.md:{id(source)}", "exec"), {"__name__": "__main__"}
        )
