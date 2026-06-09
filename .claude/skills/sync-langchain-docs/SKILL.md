---
name: sync-langchain-docs
description: "Generate the Diffbot provider page on the LangChain docs site from this repo's canonical README.md, then open a PR against langchain-ai/docs. Use after changing the public API, docstrings, or README.md, or when the user says: sync langchain docs, update the diffbot provider page, push docs to langchain, regenerate the integration page."
allowed-tools: Bash(python3:*), Bash(git:*), Bash(gh:*), Bash(make:*), Bash(cd:*)
---

# Sync the LangChain docs provider page

This repo owns the Diffbot integration page published on the LangChain docs site. The **single source of truth is [`README.md`](../../../README.md)**; the published page is `src/oss/python/integrations/providers/diffbot.mdx` in [`langchain-ai/docs`](https://github.com/langchain-ai/docs). This skill **generates** the `.mdx` page *from the README* (the README is GitHub-flavored Markdown; the page needs frontmatter and LangChain docs house style), writes it into a local `langchain-ai/docs` checkout, and opens a PR.

Edit the content in `README.md` only — never hand-edit the page in `langchain-ai/docs`. The generated page is a derived artifact.

## Where the docs repo lives

A local `langchain-ai/docs` checkout is expected at the sibling **`../langchain-docs`** by default (override with `$LANGCHAIN_DOCS_REPO` or `--docs-repo`). `sync.py` resolves and validates it and prints the target page path so you never hardcode it:

```bash
TARGET="$(python3 .claude/skills/sync-langchain-docs/sync.py --path)"
```

If that errors, the checkout is missing — ask the user for its path (or to clone `git@github.com:langchain-ai/docs.git` next to this repo).

## When to run

Run after anything that changes what the page should say:

- A public class is added, renamed, or removed (`langchain_diffbot.__all__`).
- An example, constructor argument, or behavior described in the README changes.
- `README.md` itself was edited.

## Steps

<Steps>

### Confirm the README is correct and current

The page is only as good as the README. Update `README.md` first if needed, then verify the parity guard passes (it asserts the Components reference table matches `__all__`, every class is documented, and every example builds a client) and that the examples still run:

```bash
uv run pytest tests/unit_tests/test_readme_parity.py tests/unit_tests/test_readme_examples.py -q
```

Also check prose against the LangChain docs house style **locally**, before touching the docs repo — `make lint_prose` runs Vale with `.vale.ini` + `.github/vale/styles/` copied from `langchain-ai/docs`, so the README faces the same gate its generated page will:

```bash
make lint_prose
```

Fix `README.md` until these are green before generating the page.

### Resolve the target page path

```bash
TARGET="$(python3 .claude/skills/sync-langchain-docs/sync.py --path)"
```

### Generate the page from the README

Read `README.md` and write the LangChain `.mdx` to `$TARGET`, applying these conversions (this is a content transform, not a copy):

- **Frontmatter** — prepend:
  ```mdx
  ---
  title: "Diffbot integrations"
  description: "Integrate with Diffbot using LangChain Python."
  ---
  ```
- **Source-of-truth note** — immediately after the frontmatter, add an MDX comment so reviewers know not to hand-edit the page:
  ```mdx
  {/* Generated from README.md in diffbot/langchain-diffbot by the
      sync-langchain-docs skill. Edit there, not here. */}
  ```
- **Drop repo-only content** — omit the CI badge (top of the README) and the entire `## Development` section; they don't belong on the published page.
- **Install block** — convert the single ` ```bash ` install fence into a `<CodeGroup>` with a `pip` and a `uv` tab:
  ```mdx
  <CodeGroup>
  ```bash pip
  pip install langchain-diffbot
  ```

  ```bash uv
  uv add langchain-diffbot
  ```
  </CodeGroup>
  ```
- **Rewrite relative repo links** — turn `./examples`, `(./examples/...)`, and any other repo-relative link into an absolute `https://github.com/diffbot/langchain-diffbot/...` URL.
- **Pass through unchanged** — all prose, ` ```python ` example blocks, and the Markdown tables (the API→class table and the `## Components reference` table) carry over as-is.

### Lint the page with the docs repo's tooling

House style is enforced by Vale in `langchain-ai/docs`. Run it against the generated page and fix any violations **in `README.md`**, then re-generate (previous step):

```bash
make -C "$(python3 .claude/skills/sync-langchain-docs/sync.py --repo)" \
  lint_prose FILES="src/oss/python/integrations/providers/diffbot.mdx"
```

### Open the PR

Branch, commit, and open the PR from inside the docs repo. Summarize what changed in the page:

```bash
cd "${LANGCHAIN_DOCS_REPO:-../langchain-docs}"
git checkout -b docs/sync-diffbot-provider
git add src/oss/python/integrations/providers/diffbot.mdx
git commit -m "docs: regenerate Diffbot provider page from langchain-diffbot README"
git push -u origin docs/sync-diffbot-provider
gh pr create --base main \
  --title "docs: update Diffbot provider page" \
  --body "Regenerates the Diffbot integration page from the canonical README.md in diffbot/langchain-diffbot. <summary of the change>. Generated with help from Claude Code."
```

</Steps>

## Notes

- The published page carries an MDX comment naming this repo's `README.md` as the source of truth, so reviewers know not to hand-edit it.
- Keep the PR body focused on the "why": which API/README change drove the docs update.
- If `langchain-ai/docs` already has an open Diffbot branch (for example `integration/diffbot`), reuse it instead of creating a new one — ask the user which branch to target.
