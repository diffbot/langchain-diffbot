"""Regenerate examples/quickstart.ipynb from cell definitions in this file.

Run once whenever you change a cell. Run with:
    uv run python examples/_build_notebook.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

NB_PATH = Path(__file__).with_name("quickstart.ipynb")

# (cell_type, source_str)
CELLS: list[tuple[str, str]] = []


def md(src: str) -> None:
    CELLS.append(("markdown", src))


def code(src: str) -> None:
    CELLS.append(("code", src))


# ---------------------------------------------------------------------------
md("""\
# `langchain-diffbot` quickstart

This notebook walks through every public surface in `langchain-diffbot`:

1. Install + authenticate
2. **Knowledge Graph retriever** with [DQL](https://docs.diffbot.com/reference/dql-quickstart)
3. **Output shaping** so KG entities don't blow past LLM input-token limits
4. **Native async** — `ainvoke` runs on a real event loop, not a thread pool
5. **Web Search retriever** — natural-language web search backed by Diffbot
6. **Extract tool + loader** — fetch and read individual URLs
7. **Entities tool** — NLP entity / sentiment extraction
8. **ChatDiffbot** — Diffbot's own LLM RAG endpoint, with native streaming
9. **Bring-your-own-client** — pre-built SDK clients for full transport control
10. A **multi-tool research agent** that combines KG + web search + extract

You'll need:

- A **Diffbot API token** — [app.diffbot.com/get-started](https://app.diffbot.com/get-started/)
- An **Anthropic API key** (for the agent section only) — [console.anthropic.com](https://console.anthropic.com/)
""")

md("""## 1. Install

Until `diffbot-python` is published to PyPI, install it from GitHub alongside the LangChain extras.""")

code("""%pip install --quiet \\
    "diffbot-python @ git+https://github.com/diffbot/diffbot-python" \\
    langchain-diffbot \\
    langchain langchain-anthropic python-dotenv""")

md("""## 2. Authenticate

Put your keys in a `.env` next to this notebook, or paste them inline below. `getpass` keeps them out of the notebook output.""")

code("""import getpass
import os

from dotenv import load_dotenv

load_dotenv()

if not os.getenv("DIFFBOT_API_TOKEN"):
    os.environ["DIFFBOT_API_TOKEN"] = getpass.getpass("DIFFBOT_API_TOKEN: ")

if not os.getenv("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = getpass.getpass("ANTHROPIC_API_KEY: ")""")

md("""## 3. Knowledge Graph retrieval

`DiffbotKnowledgeGraphRetriever` is a standard LangChain `BaseRetriever`. The `query` you pass to `.invoke()` is a [DQL](https://docs.diffbot.com/reference/dql-quickstart) expression — not natural language. A few patterns you'll use a lot:

| What you want | DQL |
| --- | --- |
| Filter by entity type | `type:Organization`, `type:Person`, `type:Article` |
| Exact match | `name:"Diffbot"` |
| Nested fields | `location.city.name:"Austin"` |
| AND (combine with spaces) | `type:Organization industries:"Robotics"` |
| Sort ascending | `sortBy:nbEmployees` |
| Sort descending | `revSortBy:nbEmployees` (no `desc` keyword) |""")

code("""from langchain_diffbot import DiffbotKnowledgeGraphRetriever

retriever = DiffbotKnowledgeGraphRetriever(k=5)

docs = retriever.invoke(
    'type:Organization industries:"Artificial Intelligence" location.city.name:"Boston"'
)

for d in docs:
    print(d.metadata.get("name"), "—", d.page_content[:120])""")

md("""## 4. Shaping the output

Diffbot KG entities can be huge — nested `suppliers`, `employments`, `articles`, `tags`, etc. One unshaped `invoke()` can drop tens of thousands of tokens into a prompt and blow past per-minute input-token limits. The retriever gives you three knobs:

1. `fields=[...]` — allowlist of top-level metadata keys to keep
2. `content_fields=[...]` — ordered priority for which field becomes `page_content` (first non-empty value wins)
3. `document_mapper=fn` — full override; ignores the other two

The same three knobs are available on `DiffbotWebSearchRetriever` (section 5) — they're the canonical way to keep tool responses agent-sized.

### 4a. Field projection (recommended for agent / tool-use)""")

code("""retriever = DiffbotKnowledgeGraphRetriever(
    k=3,
    fields=["id", "type", "name", "homepageUri", "nbEmployees", "industries"],
)

docs = retriever.invoke('type:Organization location.city.name:"Austin" industries:"Robotics"')

for d in docs:
    print(d.metadata)
    print("  content:", d.page_content[:200], "\\n")""")

md("""### 4b. Pick which field becomes `page_content`""")

code("""retriever = DiffbotKnowledgeGraphRetriever(
    k=3,
    fields=["id", "name"],
    content_fields=["summary", "description", "name"],
)

for d in retriever.invoke('type:Organization name:"Anthropic"'):
    print(d.metadata["name"], "—", d.page_content[:160])""")

md("""### 4c. Full control with `document_mapper`

Use this when you need a custom Document shape — nested-field projection, formatted strings, derived metadata, etc.""")

code("""from langchain_core.documents import Document


def mapper(entity: dict) -> Document:
    city = (entity.get("location") or {}).get("city", {}).get("name")
    return Document(
        page_content=entity.get("summary") or entity.get("description", ""),
        metadata={
            "id": entity.get("id"),
            "name": entity.get("name"),
            "city": city,
            "employees": entity.get("nbEmployees"),
        },
    )


retriever = DiffbotKnowledgeGraphRetriever(k=3, document_mapper=mapper)

for d in retriever.invoke('type:Organization industries:"Biotechnology" revSortBy:nbEmployees'):
    print(d.metadata, "—", d.page_content[:120])""")

md("""## 5. Async is native

Every retriever / tool / loader / chat model in this package implements both sync and async surfaces. `ainvoke` runs on a real `httpx.AsyncClient` — not the thread-pool fallback LangChain falls back to when only one side is implemented. That matters when you fan out many KG queries from one event loop.""")

code("""import asyncio

retriever = DiffbotKnowledgeGraphRetriever(k=3, fields=["id", "name", "industries"])

queries = [
    'type:Organization location.city.name:"Austin" industries:"Robotics"',
    'type:Organization location.city.name:"Boston" industries:"Biotechnology"',
    'type:Organization location.city.name:"San Francisco" industries:"Artificial Intelligence"',
]

results = await asyncio.gather(*(retriever.ainvoke(q) for q in queries))

for q, docs in zip(queries, results, strict=True):
    print(q)
    for d in docs:
        print("  •", d.metadata.get("name"))""")

md("""## 6. Web Search retriever

`DiffbotWebSearchRetriever` wraps Diffbot's natural-language web search. Same shape as the KG retriever — pass `k`, optionally `fields` / `content_fields` / `document_mapper`. Results come back as `Document`s whose `page_content` is the page content (or snippet) returned by Diffbot.""")

code("""from langchain_diffbot import DiffbotWebSearchRetriever

web = DiffbotWebSearchRetriever(k=3, fields=["title", "pageUrl", "score"])

for d in web.invoke("diffbot knowledge graph llm grounding"):
    print(d.metadata)
    print("  content:", d.page_content[:200], "\\n")""")

md("""## 7. Extract tool + loader

Diffbot's Analyze API turns a URL into structured markdown. The package exposes two surfaces over it:

- **`DiffbotExtractTool`** — single-call BaseTool. Hand it to an agent.
- **`DiffbotExtractLoader`** — DocumentLoader. Hand it a list of URLs and iterate.

### 7a. Extract tool (one URL at a time)""")

code("""from langchain_diffbot import DiffbotExtractTool

extract = DiffbotExtractTool()
result = extract.invoke({"url": "https://www.diffbot.com/products/extract/"})

print("title:", result["title"])
print("type :", result["type"])
print("content (first 400 chars):\\n", (result["content"] or "")[:400])""")

md("""### 7b. Extract loader (batch URLs into Documents)

`alazy_load` runs concurrently on a single event loop — useful when ingesting many URLs.""")

code("""from langchain_diffbot import DiffbotExtractLoader

loader = DiffbotExtractLoader(
    urls=[
        "https://www.diffbot.com/products/extract/",
        "https://www.diffbot.com/products/kg/",
    ],
)

for doc in loader.lazy_load():
    print(doc.metadata["title"], "—", doc.metadata["url"])
    print("  ", (doc.page_content or "")[:200], "\\n")""")

md("""### 7c. Extract tool handles extraction errors gracefully

When Diffbot returns a 200 with an `errorCode` body (e.g. it couldn't fetch the page), `DiffbotExtractTool` returns a structured `{"error": ..., "errorCode": ...}` dict instead of raising — so agents can react and try a different URL.""")

code("""result = extract.invoke({"url": "https://example.com/this-page-does-not-exist-XYZ"})
print(result)""")

md("""## 8. Entities tool

`DiffbotEntitiesTool` wraps Diffbot's NLP API. Hand it a chunk of text; it returns entities (people, orgs, places, …), each with a stable `id` that you can look up in the KG via DQL (`id:or("E1","E2",...)`).""")

code("""from langchain_diffbot import DiffbotEntitiesTool

entities = DiffbotEntitiesTool()
result = entities.invoke({
    "text": "Anthropic, founded by Dario Amodei and Daniela Amodei in 2021, released Claude in 2023."
})

for e in result.get("entities", [])[:5]:
    print(f"  {e.get('name'):30s} {e.get('type', '?'):20s} {e.get('id', '?')}")
print("sentiment:", result.get("sentiment"))""")

md("""## 9. ChatDiffbot

`ChatDiffbot` wraps Diffbot's own LLM RAG endpoint as a LangChain `BaseChatModel`. It streams tokens natively, so both `.stream()` and `.astream()` work out of the box — and `.invoke()` aggregates the stream for you.""")

code("""from langchain_diffbot import ChatDiffbot
from langchain_core.messages import HumanMessage

llm = ChatDiffbot()

# Streaming
print("streaming: ", end="", flush=True)
for chunk in llm.stream([HumanMessage(content="In one sentence, what is the Diffbot Knowledge Graph?")]):
    print(chunk.content, end="", flush=True)
print()""")

code("""# Or invoke to get a single message back
msg = llm.invoke([HumanMessage(content="Who founded Anthropic?")])
print(msg.content)""")

md("""## 10. Bring-your-own-client

Every class in the package accepts a pre-built `diffbot.Diffbot` (or `diffbot.DiffbotAsync`) via the `client` / `async_client` fields. When you supply one, the package uses it as-is and **does not close it** — you own the lifecycle. This is the escape hatch for anything the SDK supports that we don't re-expose: custom URLs, `transport=`, shared connection pools, custom headers.""")

code("""from diffbot import Diffbot

# Share one Diffbot client across many retriever calls instead of opening a
# fresh httpx pool per call. Useful in long-running services.
shared = Diffbot(token=os.environ["DIFFBOT_API_TOKEN"], timeout=60.0)

retriever = DiffbotKnowledgeGraphRetriever(client=shared, k=3, fields=["id", "name"])
print(retriever.invoke('type:Organization name:"Diffbot"'))

shared.close()""")

md("""## 11. Multi-tool research agent

A more realistic agent setup: hand it three tools — KG search, web search, and URL extract — and let it pick its own approach. The agent below mirrors the `examples/company_research/` CLI in this repo, which uses the same shaping pattern in all three tools to keep responses agent-sized.""")

code("""from functools import lru_cache
from typing import Any

from diffbot.errors import APIError
from langchain.agents import create_agent
from langchain_core.tools import tool

from langchain_diffbot import (
    DiffbotExtractTool,
    DiffbotKnowledgeGraphRetriever,
    DiffbotWebSearchRetriever,
)

_KG_FIELDS = [
    "id", "type", "name", "homepageUri", "nbEmployees",
    "industries", "location", "employments", "date",
]


@lru_cache(maxsize=1)
def _kg() -> DiffbotKnowledgeGraphRetriever:
    return DiffbotKnowledgeGraphRetriever(k=5, fields=_KG_FIELDS)


@lru_cache(maxsize=1)
def _web() -> DiffbotWebSearchRetriever:
    return DiffbotWebSearchRetriever(k=5, fields=["title", "pageUrl", "score"])


@lru_cache(maxsize=1)
def _extract() -> DiffbotExtractTool:
    return DiffbotExtractTool()


@tool
def search_kg(dql_query: str) -> list[dict]:
    \"\"\"Search the Diffbot Knowledge Graph with a DQL query.

    DQL: `type:Organization`, `name:"Diffbot"`, `location.city.name:"Austin"`,
    `revSortBy:nbEmployees` (descending; use `sortBy:` for ascending). AND with
    spaces. Combine for filtered lookup.
    \"\"\"
    try:
        docs = _kg().invoke(dql_query)
    except APIError as exc:
        return [{"error": f"Diffbot rejected the query ({exc.status_code}): {exc.message}. Refine and retry."}]
    return [{"summary": d.page_content, **d.metadata} for d in docs]


@tool
def web_search(query: str) -> list[dict]:
    \"\"\"Search the web via Diffbot. Use when the KG comes up short.\"\"\"
    docs = _web().invoke(query)
    return [{**d.metadata, "content": d.page_content[:800]} for d in docs]


@tool
def extract_url(url: str) -> dict[str, Any]:
    \"\"\"Fetch and read a single web page (markdown + title + type).\"\"\"
    raw = _extract().invoke({"url": url})
    if "error" in raw:
        return raw
    return {**raw, "content": (raw.get("content") or "")[:4000]}


SYSTEM_PROMPT = \"\"\"\\
You are a research assistant with three Diffbot-backed tools:

- `search_kg(dql_query)` — Knowledge Graph search via DQL. Prefer for known
  entities and filtered queries.
- `web_search(query)` — natural-language web search. Use when the KG is
  empty or you need current info.
- `extract_url(url)` — read a single web page in full.

Iterate: if KG is empty, web-search; if a web result looks promising, extract it.
Cite the entity IDs or URLs you used in your answer.\"\"\"

# Default to Haiku — a multi-step trace on a fresh Anthropic account can
# blow past Sonnet's 30k input-tokens-per-minute Tier 1 limit.
agent = create_agent(
    model="anthropic:claude-haiku-4-5",
    tools=[search_kg, web_search, extract_url],
    system_prompt=SYSTEM_PROMPT,
)""")

md(
    """Ask it a research question. The agent will pick its own tools, may iterate, and cites its sources."""
)

code("""result = agent.invoke(
    {"messages": [{"role": "user", "content": "What companies in Austin work on robotics?"}]}
)
print(result["messages"][-1].content)""")

md("""Inspect the trace to see which tools the agent reached for:""")

code("""for m in result["messages"]:
    print(f"[{m.type}]", getattr(m, "content", "") or getattr(m, "tool_calls", ""))""")

md("""## Where to go next

- [DQL reference](https://docs.diffbot.com/reference/dql-quickstart) — full query language
- [Diffbot KG entity schema](https://docs.diffbot.com/reference/knowledge-graph-overview) — what fields exist on each entity type
- [`langchain-diffbot` README](https://github.com/shixish/langchain-diffbot) — reference docs for all the classes
- [`diffbot-python` SDK](https://github.com/diffbot/diffbot-python) — the underlying client; everything you can pass to `Diffbot(...)` works via the `client=` field
- [`create_agent` docs](https://docs.langchain.com/oss/python/langchain/agents) — customize the agent loop (memory, structured output, middleware)
""")


def main() -> None:
    nb = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python"},
        },
        "cells": [],
    }
    for i, (ctype, src) in enumerate(CELLS):
        cell: dict = {
            "cell_type": ctype,
            "id": f"cell-{i:02d}",
            "metadata": {},
            "source": src.splitlines(keepends=True),
        }
        if ctype == "code":
            cell["execution_count"] = None
            cell["outputs"] = []
        nb["cells"].append(cell)
    NB_PATH.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {NB_PATH} ({len(CELLS)} cells)", file=sys.stderr)


if __name__ == "__main__":
    main()
