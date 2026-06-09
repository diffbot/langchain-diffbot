"""Shared base for langchain-diffbot components.

Every public class in this package inherits from `_BaseDiffbotComponent`. The
mixin holds the pre-built SDK clients and exposes two context managers
(`_sync_db`, `_async_db`) that the components use to acquire a
`diffbot.Diffbot` / `diffbot.DiffbotAsync` for a single call.

Client-only by design: there is exactly one way to give a component HTTP
access — hand it a client you built. Customize the client however the SDK
allows (token, `timeout`, `transport=`, custom URLs); share a connection pool
by passing the same client to several components; pick your execution mode by
passing the matching class (`Diffbot` for sync, `DiffbotAsync` for async). The
component never closes a client — you own its lifecycle (use `with`/`async
with`, or call `.close()` / `.aclose()`).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager

from diffbot import Diffbot, DiffbotAsync
from pydantic import BaseModel, ConfigDict, Field


class _BaseDiffbotComponent(BaseModel):
    """Mixin holding the pre-built SDK clients.

    Concrete classes inherit from this *and* a LangChain base
    (`BaseRetriever`, `BaseTool`, `BaseDocumentLoader`, `BaseChatModel`).
    Both are Pydantic models, so their fields merge.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    client: Diffbot | None = Field(default=None, exclude=True, repr=False)
    """Pre-built sync SDK client. Required for the sync surface.

    Build it yourself — `Diffbot(token=..., timeout=..., transport=...)` — and
    pass it here. Used as-is and never closed; you own its lifecycle.
    """

    async_client: DiffbotAsync | None = Field(default=None, exclude=True, repr=False)
    """Pre-built async SDK client. Required for the async surface.

    Build it yourself — `DiffbotAsync(token=...)` — and pass it here. Used
    as-is and never closed; you own its lifecycle.
    """

    @contextmanager
    def _sync_db(self) -> Iterator[Diffbot]:
        """Yield the sync client. Raises if none was supplied. Never closes it."""
        if self.client is None:
            msg = (
                "This component has no sync client. Pass "
                "`client=Diffbot(token=...)` (build it from the `diffbot` SDK)."
            )
            raise ValueError(msg)
        yield self.client

    @asynccontextmanager
    async def _async_db(self) -> AsyncIterator[DiffbotAsync]:
        """Yield the async client. Raises if none was supplied. Never closes it."""
        if self.async_client is None:
            msg = (
                "This component has no async client. Pass "
                "`async_client=DiffbotAsync(token=...)` (build it from the "
                "`diffbot` SDK)."
            )
            raise ValueError(msg)
        yield self.async_client
