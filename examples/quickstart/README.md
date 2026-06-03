# Quickstart notebook

[`quickstart.ipynb`](./quickstart.ipynb) is a full guided tour of
`langchain-diffbot` — every public surface, in order:

1. Knowledge Graph retriever + output shaping
2. Native async
3. Web Search retriever
4. Extract tool + extract loader
5. Entities tool
6. ChatDiffbot (Diffbot's own LLM with native streaming)
7. Bring-your-own SDK client
8. A multi-tool research agent that uses KG search + web search + URL extract

## Prerequisites

- `DIFFBOT_API_TOKEN` and `ANTHROPIC_API_KEY` in the environment. Copy
  `../.env.example` to `../.env` and fill them in.
- Python deps: from the repo root, `uv sync --extra examples`.

## Run it

```bash
# uv-managed (recommended — handles PATH automatically):
uv run --with jupyter jupyter lab examples/quickstart/quickstart.ipynb

# Or plain pip (use `python -m jupyter`, not `jupyter`, to avoid PATH issues):
pip install jupyter
python -m jupyter lab examples/quickstart/quickstart.ipynb
```

Then run the cells top to bottom.

## Installing outside this repo

Inside the repo, `uv sync --extra examples` is all you need. From outside the
repo, install the package with its examples extra (`diffbot-python` comes in as
a dependency from PyPI):

```bash
pip install "langchain-diffbot[examples]"
```

## Editing the notebook

The notebook is regenerated from [`_build_notebook.py`](./_build_notebook.py) —
edit that file (cell sources are inline) and re-run it rather than editing the
`.ipynb` directly:

```bash
uv run python examples/quickstart/_build_notebook.py
```
