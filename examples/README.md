# `langchain-diffbot` examples

A few ways to see the package in action, from a guided notebook to a CLI and a
browser app. Each talks to the live Diffbot APIs (and the agent-based examples
also use an Anthropic model). Every example below has its own README covering
setup and how to run it.

## Notebook

[`quickstart/`](./quickstart) is a full guided tour of the package:

1. Knowledge Graph retriever + output shaping
2. Native async
3. Web Search retriever
4. Extract tool + extract loader
5. Entities tool
6. ChatDiffbot (Diffbot's own LLM with native streaming)
7. Bring-your-own SDK client
8. A multi-tool research agent that uses KG search + web search + URL extract

## CLI

[`company_research/`](./company_research) is a multi-tool agent packaged as a
one-shot command-line tool: ask a company-research question in plain English and
the agent searches the Knowledge Graph and the live web, then cites the entity
IDs / URLs it used. Useful for shell scripting or quick spot checks.

## Web app

[`dql_explorer/`](./dql_explorer) is a browser UI for the DQL-authoring loop:
type a question in plain English, and an agent inspects the ontology, probes
query variants, writes the DQL, and the results come back as a table. It also
has an M&A / IPO dashboard. It's a FastAPI backend serving a React + TypeScript
frontend, with optional LangSmith tracing.
