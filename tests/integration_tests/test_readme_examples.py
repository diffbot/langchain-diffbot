"""Execute the README's python code blocks against the live Diffbot API.

The mocked unit suite (`unit_tests/test_readme_examples.py`) proves the examples
*parse and run*; this proves they still work against the real service — catching
drift in query semantics or response shapes that a canned mock can't.

Credential gating, so CI never spends non-Diffbot quota:
  - The whole module is skipped without `DIFFBOT_API_TOKEN`.
  - Diffbot-only blocks run live (CI has the token).
  - The LCEL example imports `langchain_anthropic`; it runs only when
    `ANTHROPIC_API_KEY` is set (i.e. locally). CI does not provide that key — and
    doesn't install `langchain_anthropic` — so the block is skipped there and no
    Anthropic tokens are consumed.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os

import pytest

from tests.readme import (
    DIFFBOT_ONLY_IMPORTS,
    extract_blocks,
    import_roots,
    is_executable,
)

pytestmark = pytest.mark.skipif(
    not os.environ.get("DIFFBOT_API_TOKEN"),
    reason="DIFFBOT_API_TOKEN not set",
)

_BLOCKS = extract_blocks()


def _skip_reason(source: str) -> str | None:
    """Return why a block can't run live, or None if it's runnable."""
    if not is_executable(source):
        # The crawl example drives a real, slow crawl job; documented, not run.
        return "illustrative block (e.g. crawl) — not executed by the suite"
    extra = import_roots(source) - DIFFBOT_ONLY_IMPORTS
    if not extra:
        return None
    # The only non-Diffbot example we support running is the Anthropic LCEL one.
    if extra == {"langchain_anthropic"}:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return "ANTHROPIC_API_KEY not set (CI never runs the Anthropic example)"
        if importlib.util.find_spec("langchain_anthropic") is None:
            return "langchain_anthropic not installed"
        return None
    return f"needs un-runnable imports {sorted(extra)}"


@pytest.mark.parametrize("source", [b for _, b in _BLOCKS], ids=[i for i, _ in _BLOCKS])
def test_readme_example_runs_live(source: str) -> None:
    reason = _skip_reason(source)
    if reason:
        pytest.skip(reason)

    # Examples print for illustration; swallow it to keep test output clean.
    with contextlib.redirect_stdout(io.StringIO()):
        exec(
            compile(source, f"README.md:{id(source)}", "exec"), {"__name__": "__main__"}
        )
