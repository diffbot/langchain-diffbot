"""LangChain integration for Diffbot.

Thin layer over the official `diffbot-python` SDK. Every public class takes a
pre-built `diffbot.Diffbot` (sync) and/or `diffbot.DiffbotAsync` (async) client
via the `client` / `async_client` fields — build the client yourself (token,
`timeout`, `transport=`, custom URLs), pass it in, and share one across many
components. Anything the SDK can do, you configure on the client.
"""

from langchain_diffbot.chat_models import ChatDiffbot
from langchain_diffbot.document_loaders import (
    DiffbotCrawlLoader,
    DiffbotExtractLoader,
)
from langchain_diffbot.retrievers import (
    DiffbotKnowledgeGraphRetriever,
    DiffbotWebSearchRetriever,
)
from langchain_diffbot.tools import (
    DiffbotAskTool,
    DiffbotDQLProbeTool,
    DiffbotEntitiesTool,
    DiffbotExtractTool,
    DiffbotKnowledgeGraphTool,
    DiffbotOntologyTool,
    DiffbotWebSearchTool,
)

__all__ = [
    "ChatDiffbot",
    "DiffbotAskTool",
    "DiffbotCrawlLoader",
    "DiffbotDQLProbeTool",
    "DiffbotEntitiesTool",
    "DiffbotExtractLoader",
    "DiffbotExtractTool",
    "DiffbotKnowledgeGraphRetriever",
    "DiffbotKnowledgeGraphTool",
    "DiffbotOntologyTool",
    "DiffbotWebSearchRetriever",
    "DiffbotWebSearchTool",
]
