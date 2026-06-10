---
name: sync-langchain-docs
description: "Keep all Diffbot docs in sync: README.md in this repo and the LangChain docs pages (providers, tools, retrievers, chat, document loaders). Use when code changes, when any doc page drifts, or when the user says: sync langchain docs, update the diffbot docs, sync the integration pages."
allowed-tools: Bash(python3:*), Bash(git:*), Bash(gh:*), Bash(make:*), Read, Edit, Write
---

# Sync Diffbot docs across all pages

## What this skill does

Six documents describe the `langchain-diffbot` package. Keep them all accurate and consistent — update whichever ones need it, not just one.

| File | Audience | Owns |
|------|----------|------|
| `README.md` (this repo) | GitHub / PyPI readers | Complete package reference — install, auth, all classes, examples |
| `providers/diffbot.mdx` (langchain-docs) | Docs site visitors landing on Diffbot | Overview only: install, auth, components table, links to detail pages |
| `tools/diffbot.mdx` (langchain-docs) | Docs site visitors looking for tools | Full tool documentation with examples |
| `retrievers/diffbot.mdx` (langchain-docs) | Docs site visitors looking for retrievers | Full retriever documentation with examples |
| `chat/diffbot.mdx` (langchain-docs) | Docs site visitors looking for chat models | `ChatDiffbot` instantiation, invocation, streaming, chaining |
| `document_loaders/diffbot.mdx` (langchain-docs) | Docs site visitors looking for loaders | `DiffbotExtractLoader`, `DiffbotCrawlLoader` |

**Link, don't duplicate within langchain-docs.** The provider hub names every class and links to detail pages; detail pages don't repeat install/auth. The README is for a different audience and channel (GitHub/PyPI) — it can be complete without violating this rule.

## LangChain import rules (LangChain 1.x)

Assume readers use current `langchain` and `langchain-core` releases. The slim `langchain` package (1.3+) only ships `agents`, `chat_models`, `embeddings`, `messages`, `rate_limiters`, and `tools`. Paths like `langchain.documents` or `langchain.prompts` do not exist and will fail if copied.

Use this split in **every** README and MDX example:

| Symbol | Import from |
|--------|-------------|
| `HumanMessage`, `AIMessage`, `ToolMessage`, other message types | `langchain.messages` |
| `create_agent`, `tool`, `init_chat_model`, agent middleware | `langchain.agents`, `langchain.tools`, `langchain.chat_models` |
| `Document`, `ChatPromptTemplate`, `StrOutputParser`, `RunnablePassthrough`, LCEL primitives | `langchain_core.*` |

Examples:

```python
from langchain.messages import HumanMessage
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
```

**Docs CI note:** The langchain-docs **Check PR Imports** job only flags `langchain_core` imports that `langchain` actually re-exports (mostly `messages` and `tools`). `langchain_core.documents` and `langchain_core.prompts` are allowed and correct — do not "fix" them to nonexistent `langchain.*` paths.

**Package source code** (`langchain_diffbot/*.py`) continues to import from `langchain_core` directly; these rules apply to user-facing documentation and examples only.

## Where the docs repo lives

A local `langchain-ai/docs` checkout is expected at the sibling **`../langchain-docs`** by default (override with `$LANGCHAIN_DOCS_REPO`). Verify it:

```bash
python3 .claude/skills/sync-langchain-docs/sync.py --path
```

If that errors, ask the user for its path or to clone `git@github.com:langchain-ai/docs.git` next to this repo.

## Steps

<Steps>

### Read all six files

Read every file before touching any of them:

- `README.md`
- `$(python3 .claude/skills/sync-langchain-docs/sync.py --repo)/src/oss/python/integrations/providers/diffbot.mdx`
- `$(python3 .claude/skills/sync-langchain-docs/sync.py --repo)/src/oss/python/integrations/tools/diffbot.mdx`
- `$(python3 .claude/skills/sync-langchain-docs/sync.py --repo)/src/oss/python/integrations/retrievers/diffbot.mdx`
- `$(python3 .claude/skills/sync-langchain-docs/sync.py --repo)/src/oss/python/integrations/chat/diffbot.mdx`
- `$(python3 .claude/skills/sync-langchain-docs/sync.py --repo)/src/oss/python/integrations/document_loaders/diffbot.mdx`

Also check what triggered the sync — git diff, the user's description, or a specific change — so you know what actually changed and can limit edits to what's necessary.

### Identify what needs updating

For each file, decide independently whether it needs a change. Common triggers:

- **New or renamed class** → update the components table in README + provider hub; add documentation to the appropriate detail page (tools or retrievers); update any import examples.
- **Behavior change to a tool or retriever** → update README + the matching detail page.
- **Auth model change** → update README + provider hub (both cover auth); check if detail pages reference auth.
- **Install instructions change** → update README + provider hub.
- **Example improvement** → update README; mirror to the matching detail page if it's more illustrative.
- **Detail page drifted from the code** → update just that page.

If only one file needs a change, only edit that file.

### Apply the updates

Edit each file that needs it. Rules per file:

**README.md** — complete reference, no format restrictions. Run the parity guard after any change to ensure the components table and examples stay in sync with the package:

```bash
uv run pytest tests/unit_tests/test_readme_parity.py tests/unit_tests/test_readme_examples.py -q
```

**providers/diffbot.mdx** — hub only. Structure:
1. Frontmatter (`title`, `description`)
2. Maintenance comment (keep it — see current file for wording; README and MDX pages are peers, not source/derived)
3. Short intro + API → class mapping table
4. `## Installation` as `<CodeGroup>` with `pip` and `uv` tabs
5. `## Authentication` — prose + `db = Diffbot(...)` snippet only; no usage examples
6. One short section per class group (Retrievers, Tools, Chat model, Document loaders) — one sentence + import snippet + link to the detail page; no examples
7. `## Components reference` table

**tools/diffbot.mdx** — full tool docs. Include every tool class, usage examples, and any agent patterns. Link back to the provider hub for install/auth. Do not repeat retriever content.

**retrievers/diffbot.mdx** — full retriever docs. Include both retriever classes, output shaping, LCEL chain usage. Link back to the provider hub for install/auth. Do not repeat tool content.

**chat/diffbot.mdx** — `ChatDiffbot` only. Instantiation, invocation, streaming, chaining. Follow the LangChain import rules above (`langchain.messages`, `langchain_core.prompts`).

**document_loaders/diffbot.mdx** — `DiffbotExtractLoader` and `DiffbotCrawlLoader` only. Link back to the provider hub for install/auth.

MDX formatting rules (Vale enforces these — violations block the docs CI):
- Em dashes: no surrounding spaces (`word—word`, not `word — word`)
- `prebuilt` not `pre-built`
- Install blocks: `<CodeGroup>` with `pip` and `uv` tabs
- Relative links to this repo become absolute `https://github.com/diffbot/langchain-diffbot/...` URLs

### Validate imports and prose in langchain-docs

If you changed any MDX in the docs repo, run the import checker (flags only `langchain_core` imports that should be `langchain.*` re-exports) and Vale:

```bash
DOCS="$(python3 .claude/skills/sync-langchain-docs/sync.py --repo)"
cd "$DOCS"
uv run scripts/check_pr_imports.py
make lint_prose FILES="<space-separated changed .mdx paths>"
```

### Lint every changed MDX file

The docs repo has its own Vale setup. Run it against each changed MDX:

```bash
make -C "$(python3 .claude/skills/sync-langchain-docs/sync.py --repo)" \
  lint_prose FILES="src/oss/python/integrations/providers/diffbot.mdx"
```

**If Vale or any other docs-repo validation catches a prose issue, fix it in `README.md` too** — the docs repo leads on prose quality and the README should follow. Fix violations and re-run until clean.

### Commit and push

Work from inside the docs repo. Reuse the existing `integration/diffbot` branch if it exists; otherwise create `docs/sync-diffbot-<topic>`.

```bash
DOCS="${LANGCHAIN_DOCS_REPO:-../langchain-docs}"
cd "$DOCS"
git add <changed files>
git commit -m "docs: <short summary of what changed and why>"
git push
```

Stage only the files you changed. If the branch already has an open PR, the push updates it automatically — no need to open a new one unless the user asks.

</Steps>
