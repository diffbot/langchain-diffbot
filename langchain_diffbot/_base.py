"""Shared base for langchain-diffbot components.

Every public class in this package inherits from `_BaseDiffbotComponent`. The
mixin holds the token / timeout / optional pre-built SDK clients and exposes
two context managers (`_sync_db`, `_async_db`) that the components use to
acquire a `diffbot.Diffbot` / `diffbot.DiffbotAsync` for a single call.

Bring-your-own-client: if the user supplies `client=...` or
`async_client=...`, we use it as-is and **do not close it** — the user owns
the lifecycle. Otherwise we construct a fresh SDK client per call and close
it on exit (same per-call lifecycle as the previous hand-rolled httpx
wrapper).
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager

from diffbot import Diffbot, DiffbotAsync
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator


class _BaseDiffbotComponent(BaseModel):
    """Mixin holding token, timeout, and optional pre-built SDK clients.

    Concrete classes inherit from this *and* a LangChain base
    (`BaseRetriever`, `BaseTool`, `BaseDocumentLoader`, `BaseChatModel`).
    Both are Pydantic models, so their fields merge.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    diffbot_api_token: SecretStr | None = Field(default=None)
    """Diffbot API token. Falls back to `DIFFBOT_API_TOKEN`.

    Not required when both `client` and `async_client` are supplied.
    """

    timeout: float = 30.0
    """HTTP timeout (seconds) for SDK clients we construct ourselves.

    Ignored when `client` / `async_client` are supplied.
    """

    client: Diffbot | None = Field(default=None, exclude=True, repr=False)
    """Optional pre-built sync SDK client.

    If set, we use it as-is and do not close it.
    """

    async_client: DiffbotAsync | None = Field(default=None, exclude=True, repr=False)
    """Optional pre-built async SDK client.

    If set, we use it as-is and do not close it.
    """

    @model_validator(mode="after")
    def _resolve_token(self) -> _BaseDiffbotComponent:
        # If the user gave us a client (for either side), we can't be sure
        # they'll use the other side — but token resolution shouldn't block
        # construction in that case. Defer the missing-token error to call time.
        if self.client is not None or self.async_client is not None:
            return self
        if (
            self.diffbot_api_token is None
            or not self.diffbot_api_token.get_secret_value()
        ):
            env_token = os.environ.get("DIFFBOT_API_TOKEN", "")
            if not env_token:
                msg = (
                    "A Diffbot API token is required. Pass `diffbot_api_token=...`, "
                    "set the `DIFFBOT_API_TOKEN` environment variable, or supply a "
                    "pre-built `client` / `async_client`."
                )
                raise ValueError(msg)
            self.diffbot_api_token = SecretStr(env_token)
        return self

    def _token(self) -> str:
        if (
            self.diffbot_api_token is None
            or not self.diffbot_api_token.get_secret_value()
        ):
            msg = (
                "A Diffbot API token is required for this call. Pass "
                "`diffbot_api_token=...`, set `DIFFBOT_API_TOKEN`, or supply a "
                "pre-built client."
            )
            raise ValueError(msg)
        return self.diffbot_api_token.get_secret_value()

    @contextmanager
    def _sync_db(self) -> Iterator[Diffbot]:
        """Yield a `Diffbot` for one call. Closes only clients we constructed."""
        if self.client is not None:
            yield self.client
            return
        with Diffbot(token=self._token(), timeout=self.timeout) as db:
            yield db

    @asynccontextmanager
    async def _async_db(self) -> AsyncIterator[DiffbotAsync]:
        """Yield a `DiffbotAsync` for one call. Closes only clients we constructed."""
        if self.async_client is not None:
            yield self.async_client
            return
        async with DiffbotAsync(token=self._token(), timeout=self.timeout) as db:
            yield db
