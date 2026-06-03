# Company Research CLI

A one-shot command-line agent for company research over the Diffbot Knowledge
Graph and the live web. Ask a question in plain English; the agent picks its own
approach, may iterate, and cites the entity IDs / URLs it used. Useful for shell
scripting or quick spot checks.

It's the same multi-tool agent as the [`quickstart` notebook](../quickstart),
packaged as a CLI.

## Prerequisites

- `DIFFBOT_API_TOKEN` and `ANTHROPIC_API_KEY` in the environment. Copy
  `../.env.example` to `../.env` and fill them in (the CLI loads `examples/.env`).
- Python deps: from the repo root, `uv sync --extra examples`.

## Run it

Run from `examples/` (so the `company_research` package is importable):

```bash
cd examples
uv run --extra examples python -m company_research "What companies in Austin work on robotics?"
uv run --extra examples python -m company_research --quiet "Who are the executives at Diffbot?"
uv run --extra examples python -m company_research "What did Diffbot announce most recently?"
```

By default the agent prints its tool calls and intermediate responses as it
works. Pass `--quiet` to print only the final answer.

## Tools

The agent has five tools backed by Diffbot, and chooses which to use per
question:

- `inspect_ontology(op, name?, search?)` — look up the KG schema (entity types,
  a type's fields, taxonomy/enum values) so it writes DQL with real field paths.
- `probe_dql(queries)` — get hit counts for several DQL variants at once, to
  check a query is well-shaped before committing.
- `search_kg(dql_query)` — Knowledge Graph search via DQL.
- `web_search(query)` — natural-language web search, for current/news-y info or
  when the KG comes up short.
- `extract_url(url)` — fetch and read a single web page.

The intended loop is **introspect (ontology) → probe → search → refine**, with
`web_search` + `extract_url` as the fallback when the KG doesn't have it.

## Model

Defaults to `anthropic:claude-haiku-4-5` because a multi-step agent loop on a
fresh Anthropic account can blow past Sonnet's 30k input-tokens-per-minute Tier
1 limit. Override with any `provider:model` string:

```bash
COMPANY_RESEARCH_MODEL=anthropic:claude-sonnet-4-6 \
  uv run --extra examples python -m company_research "..."
```

## Layout

```
company_research/
├── agent.py      # create_agent + system prompt + model selection
├── tools.py      # the five Diffbot-backed tools
├── cli.py        # argparse, runs one question, renders the trace
└── __main__.py   # `python -m company_research` → cli.main()
```
