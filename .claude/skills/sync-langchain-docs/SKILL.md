---
name: sync-langchain-docs
description: "Keep all Diffbot docs in sync: README.md in this repo and the three LangChain docs pages (providers, tools, retrievers). Use when code changes, when any doc page drifts, or when the user says: sync langchain docs, update the diffbot docs, sync the integration pages."
allowed-tools: Bash(python3:*), Bash(git:*), Bash(gh:*), Bash(make:*), Read, Edit, Write
---

# Sync Diffbot docs across all pages

## What this skill does

Four documents describe the `langchain-diffbot` package. Keep them all accurate and consistent — update whichever ones need it, not just one.

| File | Audience | Owns |
|------|----------|------|
| `README.md` (this repo) | GitHub / PyPI readers | Complete package reference — install, auth, all classes, examples |
| `providers/diffbot.mdx` (langchain-docs) | Docs site visitors landing on Diffbot | Overview only: install, auth, components table, links to detail pages |
| `tools/diffbot.mdx` (langchain-docs) | Docs site visitors looking for tools | Full tool documentation with examples |
| `retrievers/diffbot.mdx` (langchain-docs) | Docs site visitors looking for retrievers | Full retriever documentation with examples |

**Link, don't duplicate within langchain-docs.** The provider hub names every class and links to the tools/retrievers pages; the detail pages don't repeat install/auth. The README is for a different audience and channel (GitHub/PyPI) — it can be complete without violating this rule.

## Where the docs repo lives

A local `langchain-ai/docs` checkout is expected at the sibling **`../langchain-docs`** by default (override with `$LANGCHAIN_DOCS_REPO`). Verify it:

```bash
python3 .claude/skills/sync-langchain-docs/sync.py --path
```

If that errors, ask the user for its path or to clone `git@github.com:langchain-ai/docs.git` next to this repo.

## Steps

<Steps>

### Read all four files

Read every file before touching any of them:

- `README.md`
- `$(python3 .claude/skills/sync-langchain-docs/sync.py --repo)/src/oss/python/integrations/providers/diffbot.mdx`
- `$(python3 .claude/skills/sync-langchain-docs/sync.py --repo)/src/oss/python/integrations/tools/diffbot.mdx`
- `$(python3 .claude/skills/sync-langchain-docs/sync.py --repo)/src/oss/python/integrations/retrievers/diffbot.mdx`

Also check what triggered the sync — git diff, the user's description, or a specific change — so you know what actually changed and can limit edits to what's necessary.

### Identify what needs updating

For each of the four files, decide independently whether it needs a change. Common triggers:

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
2. Sync comment (keep it — see current file for wording)
3. Short intro + API → class mapping table
4. `## Installation` as `<CodeGroup>` with `pip` and `uv` tabs
5. `## Authentication` — prose + `db = Diffbot(...)` snippet only; no usage examples
6. One short section per class group (Retrievers, Tools, Chat model, Document loaders) — one sentence + import snippet + link to the detail page; no examples
7. `## Components reference` table

**tools/diffbot.mdx** — full tool docs. Include every tool class, usage examples, and any agent patterns. Link back to the provider hub for install/auth. Do not repeat retriever content.

**retrievers/diffbot.mdx** — full retriever docs. Include both retriever classes, output shaping, LCEL chain usage. Link back to the provider hub for install/auth. Do not repeat tool content.

MDX formatting rules (Vale enforces these — violations block the docs CI):
- Em dashes: no surrounding spaces (`word—word`, not `word — word`)
- `prebuilt` not `pre-built`
- Install blocks: `<CodeGroup>` with `pip` and `uv` tabs
- Relative links to this repo become absolute `https://github.com/diffbot/langchain-diffbot/...` URLs

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
