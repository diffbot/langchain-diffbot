#!/usr/bin/env python3
"""Resolve the Diffbot provider page inside a local langchain-ai/docs checkout.

README.md in this repo is the single source of truth for the Diffbot provider
page on the LangChain docs site; the `sync-langchain-docs` skill *generates* the
page (`.mdx`) from it. The generation itself is agent-driven (prose → house
style), so this script does not copy anything — it just resolves where the page
lives, so the skill never hardcodes the path:

    # Resolve the docs repo from --docs-repo, $LANGCHAIN_DOCS_REPO, or the
    # sibling ../langchain-docs, then print:
    python3 sync.py --path    # absolute path of the target .mdx page
    python3 sync.py --repo    # absolute path of the docs repo root

The target path inside the docs repo is fixed:
    src/oss/python/integrations/providers/diffbot.mdx
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

# This file lives at <repo>/.claude/skills/sync-langchain-docs/sync.py.
_REPO_ROOT = Path(__file__).resolve().parents[3]
TARGET_RELPATH = "src/oss/python/integrations/providers/diffbot.mdx"


def resolve_docs_repo(arg: str | None) -> Path:
    """Find the langchain-ai/docs checkout from the arg, env, or sibling dir."""
    candidate = arg or os.environ.get("LANGCHAIN_DOCS_REPO")
    if candidate:
        path = Path(candidate).expanduser().resolve()
    else:
        path = (_REPO_ROOT.parent / "langchain-docs").resolve()
    if not (path / TARGET_RELPATH).exists():
        msg = (
            f"langchain-ai/docs checkout not found at {path} "
            f"(no {TARGET_RELPATH}). Pass --docs-repo or set LANGCHAIN_DOCS_REPO."
        )
        raise SystemExit(msg)
    return path


def main() -> int:
    """Print the resolved docs repo root or target page path."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        action="store_true",
        help="Print the docs repo root instead of the target page path.",
    )
    parser.add_argument(
        "--path",
        action="store_true",
        help="Print the absolute path of the target page (default).",
    )
    parser.add_argument(
        "--docs-repo", default=None, help="Path to a local langchain-ai/docs checkout."
    )
    args = parser.parse_args()

    repo = resolve_docs_repo(args.docs_repo)
    # Default to the page path so a bare invocation is useful too.
    print(repo if args.repo else repo / TARGET_RELPATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
