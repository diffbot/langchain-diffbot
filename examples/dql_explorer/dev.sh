#!/usr/bin/env bash
#
# One-command live-reload dev server for the DQL Explorer. Starts both halves
# in parallel in this one terminal and stops them together on Ctrl-C:
#
#   - FastAPI backend on :8000 with auto-reload (uvicorn --reload)
#   - Vite dev server on :5173 with hot module reload, proxying /api to :8000
#
# Open the http://localhost:5173 URL Vite prints — not :8000. Edits to the
# Python or the React source reload live.
#
# How the single-terminal teardown works: the shell runs this script (and
# everything it spawns) as one foreground process group, so Ctrl-C delivers
# SIGINT to both daemons at once. The trap below is the backstop — it fires
# `kill 0` (signal the whole process group) so that if one daemon dies, the
# other and any grandchildren (uvicorn's reload worker, esbuild) go with it.
#
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
examples_dir="$(dirname "$here")"

# Need the secrets the server loads from examples/.env (DIFFBOT_API_TOKEN,
# ANTHROPIC_API_KEY). Warn early rather than failing on the first query.
if [[ ! -f "$examples_dir/.env" ]]; then
  echo "warning: $examples_dir/.env not found — copy .env.example to .env and"
  echo "         fill in DIFFBOT_API_TOKEN and ANTHROPIC_API_KEY." >&2
fi

# Frontend deps (no-op once installed). Python deps are installed on the fly by
# `uv run --extra examples` below.
(cd "$here/web" && pnpm install)

# Tear both daemons down once, on Ctrl-C or if either exits. Disarm the trap
# first so `kill 0` can't re-enter it.
cleanup() {
  trap - EXIT INT TERM
  kill 0 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo
echo "  ┌─────────────────────────────────────────────────────────────┐"
echo "  │  Open the LIVE UI at  http://localhost:5173                  │"
echo "  │  (:8000 is the API only — it redirects here in dev.)         │"
echo "  └─────────────────────────────────────────────────────────────┘"
echo

# Backend with auto-reload (run from examples/ so `dql_explorer` imports).
(cd "$examples_dir" && DQL_EXPLORER_RELOAD=1 uv run --extra examples python -m dql_explorer) &

# Frontend with hot reload.
(cd "$here/web" && pnpm dev) &

# Block here while both daemons run; Ctrl-C (or either daemon exiting) trips the
# trap above, which tears the rest down.
wait
