---
name: audit-langchain-docs
description: "Audit all Diffbot documentation in langchain-ai/docs for drift against this repo's public API. Runs Vale and other docs-repo validators, then applies any prose fixes found back to README.md. Use when the user says: audit docs, check docs are up to date, review langchain docs, docs drift."
allowed-tools: Bash(python3:*), Bash(grep:*), Bash(find:*), Bash(make:*), Read, Edit
---

# Audit Diffbot docs in langchain-ai/docs

This skill checks every Diffbot documentation file on the LangChain docs site against this repo's public API, runs the docs repo's own validators (Vale, etc.), and propagates any findings back into this repo — `README.md` and Python source files (docstrings, comments). The docs repo's validation standards apply repo-wide here.

## Package authority (this repo)

| Artifact | What it defines |
|----------|----------------|
| `langchain_diffbot/__init__.py` (`__all__`) | The complete public API — every class that should be documented |
| `langchain_diffbot/tools/` | Tool class signatures, input schemas, return types |
| `langchain_diffbot/retrievers/` | Retriever constructor parameters, return types |
| `langchain_diffbot/chat_models/` | Chat model constructor parameters |
| `langchain_diffbot/document_loaders/` | Loader constructor parameters |
| `README.md` | GitHub/PyPI package reference — prose, API table, auth model, examples |

## Documentation files to audit (langchain-ai/docs)

A local `langchain-ai/docs` checkout is expected at the sibling **`../langchain-docs`** by default (override with `$LANGCHAIN_DOCS_REPO`).

| File | What it should reflect |
|------|----------------------|
| `src/oss/python/integrations/providers/diffbot.mdx` | Overview hub: API table, install, auth, component table, links to detail pages |
| `src/oss/python/integrations/tools/diffbot.mdx` | All 7 tools: `DiffbotExtractTool`, `DiffbotWebSearchTool`, `DiffbotKnowledgeGraphTool`, `DiffbotEntitiesTool`, `DiffbotAskTool`, `DiffbotOntologyTool`, `DiffbotDQLProbeTool` |
| `src/oss/python/integrations/retrievers/diffbot.mdx` | Both retrievers: `DiffbotKnowledgeGraphRetriever`, `DiffbotWebSearchRetriever` |
| `src/oss/python/integrations/chat/diffbot.mdx` | `ChatDiffbot` usage |
| `src/oss/python/integrations/document_loaders/diffbot.mdx` | `DiffbotExtractLoader`, `DiffbotCrawlLoader` |
| `src/oss/python/integrations/providers/all_providers.mdx` | Card entry for Diffbot |
| `src/oss/python/integrations/tools/index.mdx` | Row in Search table + card in All tools and toolkits |
| `src/oss/python/integrations/retrievers/index.mdx` | Rows in External index table + card in All retrievers |

## Steps

<Steps>

### Locate the docs repo

```bash
DOCS_REPO="${LANGCHAIN_DOCS_REPO:-../langchain-docs}"
if [ ! -d "$DOCS_REPO/src" ]; then
  echo "ERROR: docs repo not found at $DOCS_REPO"
  exit 1
fi
echo "Docs repo: $DOCS_REPO"
```

### Read the public API surface

Read `langchain_diffbot/__init__.py` and extract every name from `__all__`. This is the canonical list of classes that must appear in the docs.

Also read the source files to extract key constructor parameters and return types for each class:
- Tools: what input schema does each tool accept? What does it return?
- Retrievers: what constructor parameters does each take (`client`, `k`, `fields`, `content_fields`, `document_mapper`)?
- Chat model: what parameters does `ChatDiffbot` take?
- Loaders: what parameters do `DiffbotExtractLoader` and `DiffbotCrawlLoader` take?

### Read every documentation file

Read all 6 files listed in the table above. Use the file paths relative to `$DOCS_REPO/src/`.

### Run Vale on the three Diffbot content pages

Run the docs repo's own Vale validation against the three Diffbot content pages. The docs repo's `make lint_prose` accepts a space-separated `FILES=` argument:

```bash
make -C "${LANGCHAIN_DOCS_REPO:-../langchain-docs}" lint_prose \
  FILES="src/oss/python/integrations/providers/diffbot.mdx \
         src/oss/python/integrations/tools/diffbot.mdx \
         src/oss/python/integrations/retrievers/diffbot.mdx"
```

Capture the full output. Any errors or warnings Vale reports are **definitive** — they are exactly what would fail the docs repo's CI. Include every Vale finding verbatim in the report under a **Vale violations** category. If Vale reports clean, note that explicitly.

### Compare and report

For each issue found, report: the file path, the line or section, and the specific discrepancy. Organize the report into these categories:

**Missing coverage** — Classes in `__all__` not mentioned anywhere in the docs:
- Check `tools/diffbot.mdx` covers all 7 tool classes
- Check `retrievers/diffbot.mdx` covers both retriever classes
- Check `providers/diffbot.mdx` component table has all 12 classes

**Stale class names** — Class names in docs that no longer exist in `__all__`:
- Search docs files for any class name starting with `Diffbot` or `ChatDiffbot` and verify each is still in `__all__`

**Missing constructor parameters** — Key parameters documented in docs but removed from source, or present in source but undocumented:
- Retrievers: `k`, `fields`, `content_fields`, `document_mapper` — verify docs mention all four
- Tools: verify each tool's documented input fields match the actual input schema

**Stale prose** — Description in docs contradicts current behavior:
- The authentication model (client-based, not token-based env var pattern)
- Error handling behavior of `DiffbotExtractTool` (returns `{"error": ..., "errorCode": ...}` dict on failure, does not raise)
- `DiffbotCrawlLoader` page_content behavior (URL only, not page content)

**Broken cross-links** — Internal links in docs files that point to non-existent pages:
- `providers/diffbot.mdx` links to `/oss/integrations/tools/diffbot` and `/oss/integrations/retrievers/diffbot` — verify both pages exist
- `tools/diffbot.mdx` links to `/oss/integrations/providers/diffbot` — verify it exists
- `retrievers/diffbot.mdx` links to `/oss/integrations/providers/diffbot` — verify it exists

**Missing index entries** — Diffbot entries absent from listing pages:
- `all_providers.mdx` has a card for Diffbot
- `tools/index.mdx` has a row in the Search table and a card in All tools and toolkits
- `retrievers/index.mdx` has rows in the External index table and a card in All retrievers

**Vale violations** — Prose issues caught by the docs repo's Vale CI (terminology, dash spacing, etc.). These are definitive: any error here would block a PR merge. Include the raw Vale output line for each finding.

**README/hub drift** — The provider hub page (`providers/diffbot.mdx`) is kept in sync with README.md. Check:
- The API table in the hub matches the API table in README.md
- The component reference table in the hub matches README.md and `__all__`
- The install instructions are consistent

### Output a summary

Produce a concise report:

```
DIFFBOT DOCS AUDIT — <date>

VALE — <pass/fail>
  <raw Vale output, or "✔ 0 errors, 0 warnings in 3 files">

✅ PASSING
  - All 12 classes in __all__ appear in docs
  - ...

⚠️  ISSUES (<count>)
  1. [VALE] providers/diffbot.mdx:39 — Remove whitespace around ' —'. (LangChain.DashesSpaces)
  2. [MISSING COVERAGE] tools/diffbot.mdx: DiffbotFooTool added to __all__ but not documented
  3. [STALE IMPORTS] retrievers/diffbot.mdx:55 — legacy langchain.schema.* import path
  4. [MISSING INDEX ENTRY] tools/index.mdx: Diffbot missing from Search table
  ...

FIXED IN THIS REPO
  - README.md:48 — "pre-built" → "prebuilt"
  - langchain_diffbot/tools.py:43 — docstring: "pre-built" → "prebuilt"

STILL NEEDS ATTENTION IN langchain-docs
  - retrievers/diffbot.mdx:55 — legacy langchain.schema.* import (edit directly in langchain-docs)
```

### Propagate findings back into this repo

For every issue found — Vale violations, stale prose, outdated import patterns — apply the same fix throughout this repo:

1. **README.md** — fix any matching prose, terminology, or example code.
2. **Python source files** (`langchain_diffbot/*.py`) — fix matching issues in docstrings and inline comments. Do not change logic or signatures.

Use `grep` to find occurrences before editing:

```bash
grep -rn "pre-built\| — " langchain_diffbot/ README.md
```

After applying fixes, run the parity tests to confirm nothing broke:

```bash
uv run pytest tests/unit_tests/test_readme_parity.py tests/unit_tests/test_readme_examples.py -q
```

</Steps>

## Notes

- Fixes to `README.md` and Python source are applied directly by this skill. Fixes to `langchain-docs` files must be made there separately (this repo has no write access to the remote).
- To align langchain-docs pages with README.md after fixes here: run `/sync-langchain-docs`.
- To fix detail pages: edit them directly in `langchain-ai/docs`.
- **LangChain 1.x imports:** Flag `langchain.documents`, `langchain.prompts`, `langchain.runnables`, or `langchain.output_parsers` as stale — those modules do not exist. Use `langchain.messages` for message types and `langchain_core` for `Document`, prompts, parsers, and runnables. See the `sync-langchain-docs` skill for the full table.
