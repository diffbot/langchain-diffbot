# DQL Explorer

A small web app with three tabs over the Diffbot Knowledge Graph:

- **M&A / IPO Dashboard** — a parameterized view of recent acquisitions and IPOs,
  broken down by industry, geography, and time with donut/bar charts.
- **DQL Builder** — type a question in plain English, and a LangChain agent turns
  it into a valid [DQL](https://docs.diffbot.com/reference/dql-quickstart) query,
  runs it, and shows the results as a table.
- **Ask Diffbot** — type a question and Diffbot's own RAG LLM answers it directly,
  streaming the response token by token.

## DQL Builder

It demonstrates the package's **DQL-authoring loop** end to end:
`DiffbotOntologyTool` (look up real field paths) → `DiffbotDQLProbeTool` (check
hit counts) → the agent commits to a query, and the server runs it with
`DiffbotKnowledgeGraphTool`.

The agent only *authors* the query and picks the columns (a structured
`DQLPlan`); the **server** runs the DQL and builds the table, so the rows are
always real KG data — and the exact query is shown in the UI.

## M&A / IPO Dashboard

The opposite shape from the DQL Builder: instead of an agent authoring one-off
queries, the server runs **two fixed DQL templates** — recent acquisitions
(`isAcquired:true acquiredBy.date>=…`) and recent IPOs (`ipo.date>=…`) —
parameterized by a minimum-headcount floor (4,000 by default) and a date window
(the trailing 3 months by default). It then reduces the returned `Organization`
entities in Python (`dashboard.py`) into chart-ready breakdowns by industry,
month, country, and stock exchange, plus a largest-acquisitions table.

No model is involved — it's a deterministic roll-up of real KG data, and the two
queries are shown in the UI ("DQL behind this dashboard"). Tune the size floor
and date range, then **Refresh** to re-query. The charts are dependency-free SVG
(`charts.tsx`), so the example pulls in no charting library.

## Ask Diffbot

The package's `ChatDiffbot` — a LangChain `BaseChatModel` wrapping Diffbot's own
LLM RAG endpoint. Where the DQL Builder *authors* a precise query (and so needs a
tool-calling model like Claude), this tab just asks Diffbot's LLM, which is
grounded in the Knowledge Graph and the live web. `ChatDiffbot.astream` streams
tokens natively, so the backend (`POST /api/ask`) forwards each chunk to the
browser as a [Server-Sent Event](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)
and the answer renders as it arrives — no buffering, no extra LLM provider, no API
key beyond `DIFFBOT_API_TOKEN`.

## Prerequisites

- `DIFFBOT_API_TOKEN` and `ANTHROPIC_API_KEY` in the environment. Copy
  `../.env.example` to `../.env` and fill them in (the server loads
  `examples/.env`).
- Python deps: from the repo root, `uv sync --extra examples`.
- [pnpm](https://pnpm.io/) and Node for the frontend.

## Run it

One script does everything — installs frontend deps, starts the FastAPI backend
(:8000) and the Vite dev server (:5173) in parallel, with live reload on both.
Run it from anywhere; Ctrl-C stops both:

```bash
examples/dql_explorer/dev.sh
# then open the URL Vite prints (http://localhost:5173)
```

Open **:5173**, not :8000 — Vite serves the live-reloading UI and proxies `/api`
to the backend. Edits to the Python or the React source reload live.

Override the backend host/port with `DQL_EXPLORER_HOST` / `DQL_EXPLORER_PORT`.

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
├── dashboard.py    # M&A/IPO DQL templates + Python roll-up into chart breakdowns
├── server.py       # FastAPI: POST /api/query, /api/dashboard, /api/ask; serves the SPA
├── projection.py   # dot-path projection of KG entities into table rows
├── __main__.py     # `python -m dql_explorer` → uvicorn
├── dev.sh          # one-command live-reload dev (backend + Vite together)
└── web/            # React + TypeScript + Vite frontend (pnpm)
    └── src/
        ├── App.tsx        # tab shell (Dashboard / DQL Builder / Ask Diffbot)
        ├── Explorer.tsx   # DQL Builder: plain-English → DQL table
        ├── Ask.tsx        # Ask Diffbot: ChatDiffbot answer, streamed via SSE
        ├── Dashboard.tsx  # M&A/IPO controls + charts
        └── charts.tsx     # dependency-free SVG donut / bar charts
```
