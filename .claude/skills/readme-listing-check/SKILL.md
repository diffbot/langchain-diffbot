---
name: readme-listing-check
description: "Check that README.md matches the package's public API and that LangChain's external listing of langchain-diffbot is still accurate. Use when the user says: check docs, README drift, listing check, audit docs, update LangChain listing."
allowed-tools: Bash(grep:*), Bash(gh:*), Bash(curl:*), Read, Edit
---

# README + listing check

`README.md` is the canonical documentation. LangChain does not host Diffbot pages; it lists us externally (a table row and a provider card that link to this repo). Never open a manual PR on `langchain-ai/docs`; listing changes go through its **Integration listing** issue form and are filed by a human.

## 1. README vs. package

| Source of truth | README must match |
|---|---|
| `langchain_diffbot/__init__.py` (`__all__`) | the `## Components reference` table; every class documented |
| constructor signatures in `tools/`, `retrievers/`, `chat_models/`, `document_loaders/` | the examples and parameter prose |

`tests/unit_tests/test_readme_parity.py` and `test_readme_examples.py` enforce this in CI. Fix drift in `README.md` first.

## 2. Listing check

1. Fetch `scripts/data/integration_external_docs.yaml` from `langchain-ai/docs` and look at the `langchain-diffbot` rows (`gh api repos/langchain-ai/docs/contents/scripts/data/integration_external_docs.yaml --jq .content | base64 -d`).
2. Confirm: every class in `__all__` that should be listed has a row; each `docs_url` resolves (README anchors are fine); descriptions match the README (e.g. loaders default to Markdown, `extract_options`, crawl download mode); web search says "Free tier (100K searches/month)".
3. Confirm the README's "Listed on LangChain" links still return 200.
4. If anything is stale, draft an Integration listing issue (form: `.github/ISSUE_TEMPLATE/06-integration-submission.yml`) for the user to file. Disclose AI help with "Prepared with Claude Code" only.

## Notes

- Use `langchain.messages` for message types and `langchain_core` for `Document`, prompts, output parsers and runnables in README examples.
- Re-read LangChain's "Publish an integration" guide before proposing a listing change; the policy has changed twice in 2026.
