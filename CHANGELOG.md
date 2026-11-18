# Changelog

## Unreleased

Internal: removed the pre-publish `make dev-sdk` target and the SDK relock TODOs now that `diffbot` 3.4.0 is on PyPI. No package changes.

## 0.3.0 - 2026-11-17

Require `diffbot>=3.4.0,<4`. 0.2.0 is already on PyPI, so this release is 0.3.0.

DQL follows the SDK: POST `https://kg.diffbot.com/kg/v3/dql` with a JSON body; the token stays the `token` query parameter. GET remains the low-level escape hatch.

`uv.lock` resolves `diffbot` 3.4.0 from PyPI (`uv lock --no-sources`).

Publishing is PyPI trusted publishing from `.github/workflows/release.yml` (no token, no GitHub environment). Tag `v0.3.0`. The SDK still has no `py.typed` marker, so the mypy override stays.
