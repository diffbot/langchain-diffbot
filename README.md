# langchain-diffbot

[![CI](https://github.com/diffbot/langchain-diffbot/actions/workflows/ci.yml/badge.svg)](https://github.com/diffbot/langchain-diffbot/actions/workflows/ci.yml)

A thin LangChain integration over the official [`diffbot-python`](https://github.com/diffbot/diffbot-python) SDK. Every Diffbot API gets the closest LangChain primitive:

| Diffbot API | LangChain class(es) |
| --- | --- |
| Knowledge Graph (DQL) | `DiffbotKnowledgeGraphRetriever`, `DiffbotKnowledgeGraphTool` |
| Web Search | `DiffbotWebSearchRetriever`, `DiffbotWebSearchTool` |
| Extract (Analyze) | `DiffbotExtractTool`, `DiffbotExtractLoader` |
| NLP entities | `DiffbotEntitiesTool` |
| Crawl | `DiffbotCrawlLoader` |
| LLM RAG (`ask`) | `ChatDiffbot` (with native streaming) |

## Installation

```bash
pip install langchain-diffbot
```

## Authentication

Get an API token at https://app.diffbot.com/get-started/ and export it:

```bash
export DIFFBOT_API_TOKEN="..."
```

Every class also accepts `diffbot_api_token=...` directly, or a pre-built `diffbot.Diffbot` client via `client=...` (see [Bring-your-own-client](#bring-your-own-client) below).

## Quickstart — Knowledge Graph retriever

```python
from langchain_diffbot import DiffbotKnowledgeGraphRetriever

retriever = DiffbotKnowledgeGraphRetriever(k=5)
docs = retriever.invoke("type:Organization industries:\"Artificial Intelligence\" location.city.name:\"Boston\"")
for d in docs:
    print(d.metadata["name"], "—", d.page_content[:120])
```

The query string is a [DQL (Diffbot Query Language)](https://docs.diffbot.com/reference/dql-quickstart) expression.

## Shaping the output

Diffbot KG entities and web-search results are large. Dumping them straight into an LLM prompt can blow past per-minute input-token limits in a single call. Both retrievers expose three shaping knobs:

```python
from langchain_core.documents import Document
from langchain_diffbot import DiffbotKnowledgeGraphRetriever

# 1. Project only the top-level fields you care about. Drops everything else
#    from `metadata`. Recommended for agent / tool-use scenarios.
retriever = DiffbotKnowledgeGraphRetriever(
    k=5,
    fields=["id", "type", "name", "homepageUri", "nbEmployees"],
)

# 2. Choose which field becomes `page_content`. First non-empty value wins.
retriever = DiffbotKnowledgeGraphRetriever(
    content_fields=["summary", "description", "name"],
)

# 3. For total control, pass a `document_mapper` that turns a raw entity
#    dict into whatever Document shape you want.
def mapper(entity: dict) -> Document:
    return Document(
        page_content=entity.get("summary", ""),
        metadata={"id": entity["id"], "name": entity["name"]},
    )

retriever = DiffbotKnowledgeGraphRetriever(document_mapper=mapper)
```

`fields` and `content_fields` are ignored when `document_mapper` is set. The same knobs work on `DiffbotWebSearchRetriever`.

## Web search

```python
from langchain_diffbot import DiffbotWebSearchRetriever

web = DiffbotWebSearchRetriever(k=5, fields=["title", "pageUrl", "score"])
docs = web.invoke("diffbot knowledge graph llm grounding")
```

## Extract a URL

```python
from langchain_diffbot import DiffbotExtractTool, DiffbotExtractLoader

# Single URL
tool = DiffbotExtractTool()
page = tool.invoke({"url": "https://www.diffbot.com/products/extract/"})

# Batch — yields one Document per URL, sync or async
loader = DiffbotExtractLoader(urls=["https://example.com", "https://diffbot.com"])
for doc in loader.lazy_load():
    print(doc.metadata["title"], doc.page_content[:200])
```

`DiffbotExtractTool` returns a structured `{"error": ..., "errorCode": ...}` dict when Diffbot reports an extraction failure (200 with `errorCode`), so agents can react and try another URL instead of catching an exception. Auth / rate-limit errors propagate as `diffbot.errors.AuthError` / `RateLimitError`.

## ChatDiffbot

```python
from langchain_core.messages import HumanMessage
from langchain_diffbot import ChatDiffbot

llm = ChatDiffbot()

for chunk in llm.stream([HumanMessage(content="What is the Diffbot Knowledge Graph?")]):
    print(chunk.content, end="", flush=True)
```

`_stream` / `_astream` are native — no thread-pool fallback. `.invoke()` aggregates the stream into a single message.

## Using a retriever in a chain

The retrievers are standard `BaseRetriever`s, so they slot into LCEL like any other:

```python
from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_diffbot import DiffbotKnowledgeGraphRetriever

retriever = DiffbotKnowledgeGraphRetriever(
    k=5,
    fields=["id", "name", "homepageUri", "nbEmployees", "industries"],
)

prompt = ChatPromptTemplate.from_template(
    "Answer using only this Diffbot KG context:\n\n{context}\n\nQuestion: {question}"
)


def _format(docs):
    return "\n---\n".join(
        f"{d.metadata.get('name')} (id={d.metadata.get('id')}): {d.page_content}"
        for d in docs
    )


chain = (
    {"context": retriever | _format, "question": RunnablePassthrough()}
    | prompt
    | ChatAnthropic(model="claude-sonnet-4-6")
    | StrOutputParser()
)

chain.invoke('type:Organization location.city.name:"Boston" industries:"Biotech"')
```

## Bring-your-own-client

Every class accepts a pre-built `diffbot.Diffbot` (or `diffbot.DiffbotAsync`) via `client` / `async_client`. The package uses it as-is and **does not close it** — you own the lifecycle. This is the escape hatch for anything the SDK supports that's not re-exposed as a field (custom URLs, `transport=`, shared connection pools, custom headers).

```python
from diffbot import Diffbot
from langchain_diffbot import DiffbotKnowledgeGraphRetriever

# One client shared across many retriever calls (no per-call httpx pool churn)
shared = Diffbot(token="...", timeout=60.0)
retriever = DiffbotKnowledgeGraphRetriever(client=shared, k=5)
```

## Examples

The [`examples/`](./examples) folder has runnable demos:

- [`examples/quickstart/`](./examples/quickstart) — full tour: every public class, output shaping, async, and a multi-tool research agent.
- [`examples/company_research/`](./examples/company_research) — the same multi-tool agent as a one-shot CLI: `cd examples && python -m company_research "your question"`. The agent combines KG search + web search + URL extract.

Both need `langchain` + `langchain-anthropic` on top of the base package — install the extra:

```bash
pip install "langchain-diffbot[examples]"
```

## Development

```bash
uv sync --all-groups
uv run pytest tests/unit_tests
```

Integration tests hit the live Diffbot API and require `DIFFBOT_API_TOKEN`:

```bash
uv run pytest tests/integration_tests
```
