# `langchain-diffbot` examples

Two ways to see the package in action. Both expect `DIFFBOT_API_TOKEN` and (for the agent code) `ANTHROPIC_API_KEY` in the environment — copy `.env.example` to `.env` and fill in the values, or `export` them in your shell.

## Install

From inside this repo (the common case — `[tool.uv.sources]` already points `diffbot-python` at its GitHub source):

```bash
uv sync --extra examples
```

From outside the repo (e.g. after `langchain-diffbot` is published to PyPI) you'd install both explicitly since `diffbot-python` isn't on PyPI yet:

```bash
python3 -m pip install diffbot-python langchain-diffbot[examples]
```

## Notebook

[`quickstart.ipynb`](./quickstart.ipynb) is a full tour of the package:

1. Knowledge Graph retriever + output shaping
2. Native async
3. Web Search retriever
4. Extract tool + extract loader
5. Entities tool
6. ChatDiffbot (Diffbot's own LLM with native streaming)
7. Bring-your-own SDK client
8. A multi-tool research agent that uses KG search + web search + URL extract

```bash
# uv-managed (recommended — handles PATH automatically):
uv run --with jupyter jupyter lab examples/quickstart.ipynb

# Or plain pip (use `python -m jupyter`, not `jupyter`, to avoid PATH issues):
pip install jupyter
python -m jupyter lab examples/quickstart.ipynb
```

The notebook is regenerated from [`_build_notebook.py`](./_build_notebook.py) — edit that file (cell sources are inline) and re-run `uv run python examples/_build_notebook.py` rather than editing the `.ipynb` directly.

## CLI

[`company_research/`](./company_research) is the same multi-tool agent packaged as a one-shot CLI. Useful for shell scripting or quick spot checks.

```bash
cd examples
python -m company_research "What companies in Austin work on robotics?"
python -m company_research --quiet "Who are the executives at Diffbot?"
python -m company_research "What did Diffbot announce most recently?"
```

The agent has three tools:

- `search_kg(dql_query)` — Knowledge Graph search
- `web_search(query)` — natural-language web search
- `extract_url(url)` — fetch and read a single page

It picks its own approach, may iterate, and cites the entity IDs / URLs it used. Drop `--quiet` to see the tool calls and intermediate responses.

### Model

Defaults to `anthropic:claude-haiku-4-5` because a multi-step agent loop on a fresh Anthropic account can blow past Sonnet's 30k input-tokens-per-minute Tier 1 limit. Override with:

```bash
COMPANY_RESEARCH_MODEL=anthropic:claude-sonnet-4-6 python -m company_research "..."
```

## Web app

[`dql_explorer/`](./dql_explorer) is a browser UI for the DQL-authoring loop:
type a question in plain English, and an agent inspects the ontology, probes
query variants, writes the DQL, and the results come back as a table. It's a
FastAPI backend serving a React + TypeScript (Vite) frontend, with optional
LangSmith tracing. See [`dql_explorer/README.md`](./dql_explorer/README.md) for
setup — in short:

```bash
cd dql_explorer/web && pnpm install && pnpm build && cd ..
uv run --extra examples python -m dql_explorer   # then open http://127.0.0.1:8000
```
