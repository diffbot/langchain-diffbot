"""Keep README.md in lockstep with the package surface.

README.md is the single source of truth for this package's docs; the LangChain
provider page is generated from it by the `sync-langchain-docs` skill. These
tests fail if the README drifts from `__all__`, so a class added, renamed, or
removed cannot silently miss the docs (and therefore the published page).
"""

from __future__ import annotations

import re

from langchain_diffbot import __all__
from tests.readme import components_table_classes, extract_blocks

# Exported classes that take a `client` (every public component does today).
_COMPONENTS = set(__all__)


def test_components_table_matches_all() -> None:
    """The Components reference table lists exactly the exported classes."""
    assert sorted(components_table_classes()) == sorted(__all__)


def test_every_class_is_documented() -> None:
    """Every exported class appears in an import line in a README example."""
    text = "\n".join(src for _, src in extract_blocks())
    for name in __all__:
        assert re.search(rf"\b{name}\b", text), f"{name} is not used in any example"


def test_examples_build_a_client() -> None:
    """No component is constructed without a client (the package is client-only).

    Catches the most damaging regression: an example that omits `client=` and
    therefore raises `ValueError` at call time.
    """
    for block_id, src in extract_blocks():
        constructs_component = any(
            re.search(rf"\b{name}\s*\(", src) for name in _COMPONENTS
        )
        if constructs_component:
            assert "client=" in src or "async_client=" in src, (
                f"example {block_id} constructs a component without a client"
            )
