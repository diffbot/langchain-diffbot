"""Shared helpers for testing the python code blocks in README.md.

README.md is the single source of truth for this package's docs: the LangChain
provider page is *generated from it* by the `sync-langchain-docs` skill. Three
suites consume these helpers: `unit_tests/test_readme_examples.py` runs the
blocks against respx mocks (deterministic, no token),
`integration_tests/test_readme_examples.py` runs them against the live Diffbot
API, and `unit_tests/test_readme_parity.py` checks the page stays in lockstep
with the package surface (`__all__`). The execution suites decide which blocks
to run by inspecting each block's imports and whether it is executable.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

README = Path(__file__).parents[1] / "README.md"

# A block whose top-level imports all fall in this set needs only Diffbot to run:
# it is mockable with respx in the unit suite, and safe to execute live in CI
# with just a DIFFBOT_API_TOKEN — no Anthropic or other third-party calls (so CI
# never consumes non-Diffbot quota). `os` is stdlib (blocks read the token from
# the environment). The LCEL example imports `langchain_anthropic` and is
# therefore skipped by both suites.
DIFFBOT_ONLY_IMPORTS = {
    "langchain_diffbot",
    "langchain_core",
    "langchain",
    "diffbot",
    "os",
}

# Components that construct one of these are documented but not executed by the
# README suites. `DiffbotCrawlLoader` drives a real crawl job, which is slow and
# costly live and isn't mockable with the per-call respx pattern the rest of the
# suite uses (the crawl SDK path is integration-tested upstream — see
# `unit_tests/test_document_loaders.py`).
_NON_EXECUTABLE_CONSTRUCTORS = ("DiffbotCrawlLoader",)

_PYTHON_BLOCK = re.compile(r"```python\n(.*?)```", re.DOTALL)
_TABLE_ROW = re.compile(r"^\|\s*`([A-Za-z_][A-Za-z0-9_]*)`\s*\|", re.MULTILINE)


def read() -> str:
    """Return the raw text of README.md."""
    return README.read_text()


def extract_blocks() -> list[tuple[str, str]]:
    """Return (id, source) for each ```python block, id'd by README line number."""
    text = read()
    blocks = []
    for match in _PYTHON_BLOCK.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        blocks.append((f"L{line}", match.group(1)))
    return blocks


def is_executable(source: str) -> bool:
    """Whether the README suites should `exec` this block (vs. illustrate only)."""
    return not any(
        re.search(rf"\b{name}\s*\(", source) for name in _NON_EXECUTABLE_CONSTRUCTORS
    )


def components_table_classes() -> list[str]:
    """Return the class names listed in the `## Components reference` table.

    Reads the first backtick-wrapped cell of each row under that heading.
    """
    text = read()
    start = text.index("## Components reference")
    section = text[start:]
    # Stop at the next H2 if any, so we don't pick up later backticked cells.
    next_h2 = re.search(r"\n## ", section[3:])
    if next_h2:
        section = section[: next_h2.start() + 3]
    return _TABLE_ROW.findall(section)


def import_roots(source: str) -> set[str]:
    """Top-level module names imported by a code block (e.g. ``langchain_core``)."""
    roots: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots
