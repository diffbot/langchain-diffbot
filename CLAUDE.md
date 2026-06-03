# langchain-diffbot

LangChain integration package for the Diffbot APIs (Knowledge Graph, Extract, Web Search, NLP entities, Crawl, and the Diffbot LLM RAG endpoint).

## Stack

- **Build/deps**: `uv` (not Poetry/pip). `pyproject.toml` is PEP 621 with `hatchling` as the build backend. Dependency groups (`test`, `lint`, `typing`) are declared under `[dependency-groups]` and invoked via `uv run --group <name> ...`.
- **HTTP / Diffbot transport**: the official [`diffbot-python`](https://github.com/diffbot/diffbot-python) SDK. It wraps `httpx` under the hood, so `respx` continues to work for unit tests — mocks target the real upstream URLs (KG: `https://kg.diffbot.com/kg/v3/dql`, web search: `https://llm.diffbot.com/api/v1/web_search`, extract: `https://api.diffbot.com/v3/analyze`, ask: `https://llm.diffbot.com/rag/v1/chat/completions`, NLP: `https://nl.diffbot.com/v1/`, crawl: `https://api.diffbot.com/v3/crawl`, ontology: `https://kg.diffbot.com/kg/ontology`). `diffbot-python` is published on PyPI and resolved from there as a normal dependency (`diffbot-python>=0.1.0`); `langchain-core` / `langchain-tests` are still resolved during local dev from the sibling `../langchain/` checkout via `[tool.uv.sources]` — release builds use the published versions.
- **Models**: `pydantic` v2.
- **LangChain**: targets `langchain-core >=1.0,<2.0`. During local dev `langchain-core` and `langchain-tests` are resolved from a sibling `../langchain/` checkout via `[tool.uv.sources]` — release builds use the published versions.
- **Test runner**: `pytest` with `asyncio_mode = "auto"`.

## Architectural decisions

### Thin layer over diffbot-python

Every public class calls `diffbot.Diffbot` / `diffbot.DiffbotAsync` methods directly inside a small context-managed lifecycle helper. We do **not** maintain a wrapper that mirrors every SDK method — adding a thin LangChain surface for a new SDK method should be a ~30-line change, no plumbing edits required.

Each class accepts the SDK's kwargs by name. The only renames are LangChain-convention: `size` → `k` on the KG retriever, `num_results` → `k` on the web-search retriever. Everything else (`from_`, `filter`, `format`, `exportspec`, `extra`, `max_tokens`, `api`, `fmt`, `lang`) keeps its SDK name.

### Bring-your-own-client

`_BaseDiffbotComponent` (in `_base.py`) gives every class four optional fields: `diffbot_api_token`, `timeout`, `client`, `async_client`. The `client` / `async_client` fields take a pre-built `diffbot.Diffbot` / `diffbot.DiffbotAsync`. When supplied, we use it as-is and **do not close it** — the user owns the lifecycle. When not supplied, we construct a fresh SDK client per call (matching the legacy per-call lifecycle).

This is the escape hatch for anything the SDK supports that we don't re-expose: custom URLs (`analyze_url`, `web_search_url`, …), `transport=httpx.MockTransport(...)` for tests, shared connection pools, custom headers. We don't have to mirror each knob — the user just passes a configured client.

### Both sync and async are implemented natively

Every retriever/tool/loader/chat-model defines both the sync and async surface (`_get_relevant_documents`/`_aget_relevant_documents`, `_run`/`_arun`, `lazy_load`/`alazy_load`, `_stream`/`_astream`), each delegating to the matching method on `Diffbot` / `DiffbotAsync`.

LangChain would let us implement only one and inherit a thread-pool fallback for the other, but for HTTP-bound integrations that fallback caps concurrency at the default executor size (~12 workers) and breaks cancellation propagation. Native async lets a single event loop hold hundreds of in-flight Diffbot calls.

### No `_async`/`_sync` codegen split

The methods are short enough (typically one SDK call inside a context manager) that hand-mirroring is cheaper than maintaining a codegen script and a CI drift check. Revisit if any single feature area grows past ~100 lines of non-trivial async logic that needs a sync twin.

### Output shaping on the retrievers

`DiffbotKnowledgeGraphRetriever` and `DiffbotWebSearchRetriever` accept `fields` (metadata allowlist), `content_fields` (priority list for `page_content`), and `document_mapper` (full override). Diffbot KG entities and web-search results can run thousands of tokens each — without shaping, a single retrieval can blow past LLM input limits when fed into a tool call. Defaults preserve everything; agent-style users are expected to pass `fields=[...]`.

### DQL authoring tools: ontology + probe

To let an agent build valid DQL on the fly (rather than guessing field names), two tools wrap the SDK's DQL-authoring helpers:

- `DiffbotOntologyTool` — navigates the KG ontology (`Diffbot.dql_fetch_ontology()` → `diffbot.Ontology`). It fetches the ontology once over HTTP and caches the `Ontology` in memory on the tool instance (a `PrivateAttr`) for the rest of its lifetime — the caching policy is the consumer's, not the SDK's. Ops mirror the `db dql ontology` CLI: `types`/`composites`/`enums`/`taxonomies`/`fields`/`taxonomy`/`enum`/`search`.
- `DiffbotDQLProbeTool` — wraps `Diffbot.dql_parallel()` to probe query variants at `size=0` (hit counts only), so an agent can check selectivity before committing.

The intended agent loop is **introspect (ontology) → probe → run (`DiffbotKnowledgeGraphTool`) → refine**; `examples/company_research` demonstrates it end to end.

### Admin / utility SDK methods are not wrapped

Methods like `crawl_list_jobs`, `crawl_get_job`, `crawl_delete_job`, and `dql_refresh_ontology` don't fit cleanly as LangChain primitives. We don't wrap them, but since every component exposes `.client` / `.async_client`, users can reach them directly.

## Commands

```
make format          # ruff format + ruff check --fix
make lint            # ruff check + ruff format --check
make typing          # mypy on the package
make test            # unit tests
make test_integration  # integration tests (needs DIFFBOT_API_TOKEN)
```

## Layout

```
langchain_diffbot/
├── __init__.py            # public re-exports — every user-facing class listed in __all__
├── _base.py               # _BaseDiffbotComponent — token / timeout / client lifecycle helper
├── chat_models.py         # ChatDiffbot (wraps `ask`)
├── document_loaders.py    # DiffbotExtractLoader, DiffbotCrawlLoader
├── retrievers.py          # DiffbotKnowledgeGraphRetriever, DiffbotWebSearchRetriever
├── tools.py               # DiffbotExtractTool, DiffbotWebSearchTool, DiffbotEntitiesTool, DiffbotKnowledgeGraphTool, DiffbotOntologyTool, DiffbotDQLProbeTool
└── py.typed               # PEP 561 marker
tests/
├── unit_tests/            # no network — use respx to mock the SDK's httpx calls
└── integration_tests/     # hit real Diffbot; require DIFFBOT_API_TOKEN
```

New public surfaces go in their own top-level module and get re-exported from `__init__.py`. `tests/unit_tests/test_imports.py` asserts the public surface.
