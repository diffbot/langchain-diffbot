# Changelog

## 0.3.0 - 2026-11-17

Require `diffbot>=3.4.0rc0,<4` so CI can verify the SDK release candidate. Switch to `>=3.4.0,<4` for the unison publish. 0.2.0 is already on PyPI, so this release is 0.3.0.

DQL follows the SDK: POST `https://kg.diffbot.com/kg/v3/dql` with a JSON body; the token stays the `token` query parameter. GET remains the low-level escape hatch.

Relock with `uv lock --upgrade-package diffbot` once 3.4.0 is on PyPI. That command needs the sibling `../langchain` checkout so the editable `langchain-core` / `langchain-tests` sources stay in `uv.lock`. `make dev-sdk` is only a pre-publish local install; do not commit it.

Publishing is PyPI trusted publishing from `.github/workflows/release.yml` (no token, no GitHub environment). Tag `v0.3.0`. The SDK still has no `py.typed` marker, so the mypy override stays.
