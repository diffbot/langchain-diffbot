"""Live integration tests. Requires DIFFBOT_API_TOKEN."""

from __future__ import annotations

import os

import pytest
from diffbot import Diffbot, DiffbotAsync
from langchain_core.documents import Document

from langchain_diffbot import DiffbotKnowledgeGraphRetriever

pytestmark = pytest.mark.skipif(
    not os.environ.get("DIFFBOT_API_TOKEN"),
    reason="DIFFBOT_API_TOKEN not set",
)


def test_live_basic_query() -> None:
    client = Diffbot(token=os.environ["DIFFBOT_API_TOKEN"])
    retriever = DiffbotKnowledgeGraphRetriever(client=client, k=3)
    docs = retriever.invoke('type:Organization name:"Diffbot"')
    assert isinstance(docs, list)
    assert all(isinstance(d, Document) for d in docs)
    assert len(docs) <= 3
    client.close()


async def test_live_async_query() -> None:
    async with DiffbotAsync(token=os.environ["DIFFBOT_API_TOKEN"]) as client:
        retriever = DiffbotKnowledgeGraphRetriever(async_client=client, k=2)
        docs = await retriever.ainvoke('type:Organization name:"Diffbot"')
    assert isinstance(docs, list)
    assert all(isinstance(d, Document) for d in docs)
