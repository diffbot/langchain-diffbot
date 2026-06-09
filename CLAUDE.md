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

### Client-only: the SDK client is the single configuration surface

`_BaseDiffbotComponent` (in `_base.py`) gives every class exactly two fields: `client` (a `diffbot.Diffbot`) and `async_client` (a `diffbot.DiffbotAsync`). The caller builds the SDK client and passes it in; `_sync_db` / `_async_db` yield it as-is and **never close it** (the caller owns the lifecycle), and raise a clear error if the matching client is missing. There is no `diffbot_api_token` / `timeout` on components and no per-call client construction — the component never builds a client itself.

This is deliberate: there is one way to give a component HTTP access (hand it a client), and one place to configure the SDK (the client you build). Everything the SDK supports — token, `timeout`, custom URLs (`analyze_url`, `web_search_url`, …), `transport=` (logging/retries/headers, or `httpx.MockTransport(...)` in tests) — is set on that client, not mirrored as component fields. Share one client across many components to reuse a single connection pool. Pick the execution mode by which client you build: `Diffbot` for the sync surface, `DiffbotAsync` for the async surface, both if a component is used both ways. Unit tests still mock at the httpx layer with `respx`, so they construct a `Diffbot(token="t")` and pass `client=`/`async_client=` without needing a real transport.

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

## Documentation

`README.md` is the **single source of truth** for this package's docs. The Diffbot provider page on the LangChain docs site (`src/oss/python/integrations/providers/diffbot.mdx` in `langchain-ai/docs`) is **generated from it** by the `sync-langchain-docs` skill — never hand-edit that page; edit `README.md` and sync on request. The skill resolves the local docs checkout (sibling `../langchain-docs` by default, overridable via `$LANGCHAIN_DOCS_REPO`) and converts the README to MDX (frontmatter, `<CodeGroup>` install block, absolute links, dropping the CI badge + Development section).

**After any change to `README.md`, lint its prose** against the LangChain docs house style:

```
make lint_prose      # Vale on README.md (errors only — the same gate the docs-repo CI enforces)
```

The Vale config (`.vale.ini` + `.github/vale/styles/`) is copied from `langchain-ai/docs`, so the README passes the same gate its generated page faces; fenced code blocks and frontmatter are skipped. It is a point-in-time copy — re-copy both if LangChain updates their styles. (Needs the `vale` binary: `brew install vale`.)

Two unit suites keep the README in lockstep with the package: `tests/unit_tests/test_readme_parity.py` (the `## Components reference` table matches `__all__`, every class is documented, every example builds a client) and `tests/unit_tests/test_readme_examples.py` (every executable example runs under `respx` mocks; the crawl example is documented but not executed — flagged via `tests/readme.py`'s `is_executable`). `tests/integration_tests/test_readme_examples.py` runs the same blocks live.

## Commands

```
make format          # ruff format + ruff check --fix
make lint            # ruff check + ruff format --check
make lint_prose      # Vale prose lint on README.md (needs `vale`)
make typing          # mypy on the package
make test            # unit tests
make test_integration  # integration tests (needs DIFFBOT_API_TOKEN)
```

## Continuous integration

`.github/workflows/ci.yml` runs on every push to `main` and every PR: `make lint` + `make typing` (Python 3.12) and `make test` (Python 3.10 and 3.13). `.github/workflows/integration.yml` runs `make test_integration` nightly and on-demand (`workflow_dispatch`), reading the repo-level `DIFFBOT_API_TOKEN` secret. It is kept off the per-PR path on purpose: neither `schedule` nor `workflow_dispatch` can be triggered by a fork PR, so the token is never exposed to untrusted code.

CI cannot use the `[tool.uv.sources]` table, which pins `langchain-core` / `langchain-tests` to the sibling `../langchain/` checkout that only exists locally. Every CI install is `uv sync --no-sources` (resolves those from PyPI, the same path release builds take) and sets `UV_NO_SYNC=true` so the `make` targets' `uv run` reuse the synced env instead of re-resolving against the sources table. `--no-sources` re-resolves, so `uv.lock` is not used in CI.

## Releasing

PyPI / TestPyPI tokens live in the macOS Keychain so the Makefile pulls them automatically — no plaintext on disk, no shell-history leaks. First-time (or post-rotation) setup:

```
make set-token-testpypi    # prompts; input hidden as you paste (bash read -rsp)
make set-token-pypi        # same, for real PyPI
```

Each target reads with hidden input, overwrites any existing entry, and keeps the token out of `make` output and shell history. Per-version flow:

```
make bump-patch            # 0.1.0 → 0.1.1  (or bump-minor / bump-major)
make release-test          # publish to TestPyPI
make verify-release-test   # install from TestPyPI in a throwaway venv
make release               # publish to real PyPI (prompts to type the version)
make verify-release        # install from PyPI in a throwaway venv
```

`release-test` / `release` refuse to publish if the current `pyproject.toml` version is already on the target index, so the loop is always "bump → release-test → verify → release → verify". PyPI never allows re-uploading a version. To rotate a token, revoke the old one at https://pypi.org/manage/account/token/ (or the TestPyPI equivalent) and re-run the matching `set-token-*` target — it overwrites the Keychain entry.

## Layout

```
langchain_diffbot/
├── __init__.py            # public re-exports — every user-facing class listed in __all__
├── _base.py               # _BaseDiffbotComponent — holds client / async_client; yields them per call (never closes)
├── chat_models.py         # ChatDiffbot (wraps `ask`)
├── document_loaders.py    # DiffbotExtractLoader, DiffbotCrawlLoader
├── retrievers.py          # DiffbotKnowledgeGraphRetriever, DiffbotWebSearchRetriever
├── tools.py               # DiffbotExtractTool, DiffbotWebSearchTool, DiffbotEntitiesTool, DiffbotKnowledgeGraphTool, DiffbotAskTool, DiffbotOntologyTool, DiffbotDQLProbeTool
└── py.typed               # PEP 561 marker
tests/
├── unit_tests/            # no network — use respx to mock the SDK's httpx calls
└── integration_tests/     # hit real Diffbot; require DIFFBOT_API_TOKEN
```

New public surfaces go in their own top-level module and get re-exported from `__init__.py`. `tests/unit_tests/test_imports.py` asserts the public surface.
