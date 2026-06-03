"""FastAPI app: author DQL with the agent, run it, return a table.

`POST /api/query` runs the structured DQL-authoring agent, then runs the DQL it
produced against the Diffbot KG and projects the chosen columns into rows. The
built React SPA (in `web/dist`) is served from `/` so the whole thing runs on a
single port: build once, run the server, open the browser.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from diffbot.errors import APIError
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tracers.context import collect_runs
from pydantic import BaseModel, Field

from dql_explorer.agent import DQLPlan, build_dql_agent
from dql_explorer.dashboard import build_dashboard, default_range
from dql_explorer.projection import build_rows
from langchain_diffbot import DiffbotKnowledgeGraphTool

# Read examples/.env (DIFFBOT_API_TOKEN, ANTHROPIC_API_KEY, optional LANGSMITH_*).
load_dotenv()

# Default number of result rows to fetch and render.
DEFAULT_K = 25
# Truncate tool outputs shown in the collapsible "steps" panel.
_STEP_OUTPUT_CHARS = 300

_DIST_DIR = Path(__file__).parent / "web" / "dist"

app = FastAPI(title="Diffbot DQL Explorer")


@lru_cache(maxsize=1)
def _agent():
    return build_dql_agent()


@lru_cache(maxsize=1)
def _kg_tool() -> DiffbotKnowledgeGraphTool:
    return DiffbotKnowledgeGraphTool()


class QueryRequest(BaseModel):
    """Body for `POST /api/query`."""

    question: str = Field(description="Plain-English question.")
    k: int = Field(default=DEFAULT_K, ge=1, le=100, description="Max rows to fetch.")


class DashboardRequest(BaseModel):
    """Body for `POST /api/dashboard`. Omitted fields fall back to defaults."""

    min_employees: int = Field(
        default=4000, ge=0, le=1_000_000, description="Minimum company headcount."
    )
    date_from: str | None = Field(
        default=None, description="ISO start date (defaults to 3 months ago)."
    )
    date_to: str | None = Field(
        default=None, description="ISO end date (defaults to today)."
    )


def _extract_steps(messages: list[Any]) -> list[dict[str, Any]]:
    """Flatten the agent's message trace into tool-call/result steps for the UI."""
    # Map tool_call_id -> truncated output so each call shows its result.
    outputs: dict[str, str] = {}
    for msg in messages:
        if isinstance(msg, ToolMessage):
            outputs[msg.tool_call_id] = str(msg.content)[:_STEP_OUTPUT_CHARS]

    steps: list[dict[str, Any]] = []
    for msg in messages:
        if isinstance(msg, AIMessage):
            for call in msg.tool_calls:
                steps.append(
                    {
                        "tool": call["name"],
                        "args": call["args"],
                        "output": outputs.get(call["id"], ""),
                    }
                )
    return steps


def _trace_url(traced_runs: list[Any]) -> str | None:
    """Build a LangSmith run URL when tracing is enabled. Never raises."""
    if not (os.environ.get("LANGSMITH_TRACING") and traced_runs):
        return None
    try:
        from langsmith import Client

        return Client().get_run_url(run=traced_runs[0])
    except Exception:
        # Tracing is a nice-to-have; a hiccup here must not fail the query.
        return None


@app.post("/api/query")
async def query(req: QueryRequest) -> dict[str, Any]:
    """Author a DQL query for `question`, run it, and return rows + metadata."""
    try:
        with collect_runs() as cb:
            result = await _agent().ainvoke(
                {"messages": [HumanMessage(content=req.question)]}
            )
    except Exception as exc:  # surface any agent failure to the UI
        return {
            "question": req.question,
            "entity_type": "",
            "dql": "",
            "notes": None,
            "columns": [],
            "rows": [],
            "hits": 0,
            "steps": [],
            "trace_url": None,
            "error": f"The agent failed to build a query: {exc}",
        }

    plan: DQLPlan = result["structured_response"]
    steps = _extract_steps(result["messages"])
    trace_url = _trace_url(cb.traced_runs)

    base = {
        "question": req.question,
        "entity_type": plan.entity_type,
        "dql": plan.dql,
        "notes": plan.notes,
        "columns": [c.model_dump() for c in plan.columns],
        "steps": steps,
        "trace_url": trace_url,
    }

    paths = [c.path for c in plan.columns]
    try:
        body = await _kg_tool().ainvoke({"query": plan.dql, "size": req.k})
    except APIError as exc:
        # Surface DQL errors to the UI alongside the query that failed.
        return {
            **base,
            "rows": [],
            "hits": 0,
            "error": (
                f"Diffbot rejected the query ({exc.status_code}): "
                f"{exc.message or 'see body'}."
            ),
        }

    return {
        **base,
        "rows": build_rows(body.get("data", []), paths),
        "hits": body.get("hits", 0),
        "error": None,
    }


@app.post("/api/dashboard")
async def dashboard(req: DashboardRequest) -> dict[str, Any]:
    """Build the M&A / IPO dashboard for a headcount floor and date window."""
    default_from, default_to = default_range()
    return await build_dashboard(
        min_employees=req.min_employees,
        date_from=req.date_from or default_from,
        date_to=req.date_to or default_to,
    )


# In dev (`./dev.sh` sets DQL_EXPLORER_RELOAD=1) the live UI is the Vite server
# on :5173 — the `dist/` this backend would serve is the last `pnpm build` and is
# stale the moment you edit any frontend file. Bounce :8000 over to Vite so an
# accidental reload of :8000 doesn't show old code.
_DEV = os.environ.get("DQL_EXPLORER_RELOAD") == "1"
_VITE_URL = os.environ.get("DQL_EXPLORER_VITE_URL", "http://localhost:5173/")

# Serve the built SPA from `/` when it exists; otherwise a build reminder. Mount
# last so the /api route above takes precedence.
if _DEV:

    @app.get("/", response_class=HTMLResponse)
    def _dev_redirect() -> str:
        return (
            f'<!doctype html><meta http-equiv="refresh" content="0; url={_VITE_URL}">'
            f"<p>Dev mode: the live UI is the Vite dev server. Redirecting to "
            f'<a href="{_VITE_URL}">{_VITE_URL}</a> — open that, not :8000 '
            f"(:8000 serves the last <code>pnpm build</code>, which is stale during dev).</p>"
        )

elif _DIST_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_DIST_DIR), html=True), name="spa")
else:

    @app.get("/", response_class=HTMLResponse)
    def _build_reminder() -> str:
        return (
            "<h1>Diffbot DQL Explorer</h1>"
            "<p>The frontend hasn't been built yet. From "
            "<code>examples/dql_explorer/web</code> run:</p>"
            "<pre>pnpm install\npnpm build</pre>"
            "<p>then restart the server.</p>"
        )
