"""ChatDiffbot — LangChain chat model wrapping Diffbot's LLM RAG `ask` endpoint."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

from langchain_diffbot._base import _BaseDiffbotComponent


def _to_diffbot_messages(messages: list[BaseMessage]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for m in messages:
        if isinstance(m, HumanMessage):
            role = "user"
        elif isinstance(m, AIMessage):
            role = "assistant"
        elif isinstance(m, SystemMessage):
            role = "system"
        else:
            # Fall back on the message's `type` attribute for anything exotic.
            role = m.type if isinstance(m.type, str) else "user"
        content = m.content if isinstance(m.content, str) else str(m.content)
        out.append({"role": role, "content": content})
    return out


class ChatDiffbot(_BaseDiffbotComponent, BaseChatModel):
    """Chat model backed by Diffbot's LLM RAG (`ask`) endpoint.

    The SDK streams tokens natively, so this class implements `_stream` and
    `_astream`. `_generate` / `_agenerate` aggregate the stream into a single
    `ChatGeneration`.

    Example:
        ```python
        from diffbot import Diffbot
        from langchain_diffbot import ChatDiffbot

        llm = ChatDiffbot(client=Diffbot(token=...))
        llm.invoke("What's the capital of France?")
        ```
    """

    @property
    def _llm_type(self) -> str:
        return "diffbot"

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        payload = _to_diffbot_messages(messages)
        with self._sync_db() as db:
            for chunk in db.ask(payload):
                if run_manager is not None:
                    run_manager.on_llm_new_token(chunk)
                yield ChatGenerationChunk(message=AIMessageChunk(content=chunk))

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        payload = _to_diffbot_messages(messages)
        async with self._async_db() as db:
            async for chunk in db.ask(payload):
                if run_manager is not None:
                    await run_manager.on_llm_new_token(chunk)
                yield ChatGenerationChunk(message=AIMessageChunk(content=chunk))

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        parts: list[str] = []
        for chunk in self._stream(
            messages, stop=stop, run_manager=run_manager, **kwargs
        ):
            content = chunk.message.content
            parts.append(content if isinstance(content, str) else str(content))
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content="".join(parts)))]
        )

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        parts: list[str] = []
        async for chunk in self._astream(
            messages, stop=stop, run_manager=run_manager, **kwargs
        ):
            content = chunk.message.content
            parts.append(content if isinstance(content, str) else str(content))
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content="".join(parts)))]
        )
