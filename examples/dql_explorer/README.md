# DQL Explorer

A small web app: type a question in plain English, and a LangChain agent turns it
into a valid [DQL](https://docs.diffbot.com/reference/dql-quickstart) query, runs
it against the Diffbot Knowledge Graph, and shows the results as a table.

It demonstrates the package's **DQL-authoring loop** end to end:
`DiffbotOntologyTool` (look up real field paths) → `DiffbotDQLProbeTool` (check
hit counts) → the agent commits to a query, and the server runs it with
`DiffbotKnowledgeGraphTool`.

The agent only *authors* the query and picks the columns (a structured
`DQLPlan`); the **server** runs the DQL and builds the table, so the rows are
always real KG data — and the exact query is shown in the UI.

## Prerequisites

- `DIFFBOT_API_TOKEN` and `ANTHROPIC_API_KEY` in the environment. Copy
  `../.env.example` to `../.env` and fill them in (the server loads
  `examples/.env`).
- Python deps: from the repo root, `uv sync --extra examples`.
- [pnpm](https://pnpm.io/) and Node for the frontend.

## Run it (single port)

Build the React app once, then run the server — it serves both the API and the
built SPA on one port:

```bash
cd examples/dql_explorer/web
pnpm install
pnpm build
cd ..
uv run --extra examples python -m dql_explorer
# open http://127.0.0.1:8000
```

Override host/port with `DQL_EXPLORER_HOST` / `DQL_EXPLORER_PORT`.

## Develop (hot reload)

Run the backend and the Vite dev server side by side. Vite serves the UI on
:5173 and proxies `/api` to the backend on :8000:

```bash
# terminal 1 — backend
uv run --extra examples python -m dql_explorer

# terminal 2 — frontend with hot reload
cd examples/dql_explorer/web
pnpm dev
# open the URL Vite prints (http://localhost:5173)
```

## Model

Defaults to `anthropic:claude-haiku-4-5` (a fast, cheap authoring loop). Override:

```bash
DQL_EXPLORER_MODEL=anthropic:claude-sonnet-4-6 uv run --extra examples python -m dql_explorer
```

**Rate limits:** the authoring loop re-sends the growing message history (ontology
results, probe counts) on each step, so a few queries in quick succession can hit
a low Anthropic input-tokens-per-minute tier and surface as a slow request (the
SDK backs off and retries the 429) or an error. The agent caps large ontology
results to keep each turn small; if you still hit limits, space out queries or
raise your tier. A 429 is reported in the UI as an "agent failed" message.

## Optional: LangSmith tracing

Set these before starting the server and each query is traced; the UI shows a
"View trace in LangSmith" link:

```bash
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY=ls-...
# optional: export LANGSMITH_PROJECT=dql-explorer
```

When unset, the app works exactly the same — just no trace link.

## Layout

```
dql_explorer/
├── agent.py        # create_agent + DQLPlan structured output + ontology/probe tools
├── server.py       # FastAPI: POST /api/query, serves the built SPA
├── projection.py   # dot-path projection of KG entities into table rows
├── __main__.py     # `python -m dql_explorer` → uvicorn
└── web/            # React + TypeScript + Vite frontend (pnpm)
```
