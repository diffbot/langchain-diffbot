#!/usr/bin/env bash
# PostToolUse hook: lint README.md with Vale after it is edited.
#
# Reads the hook JSON on stdin, and only acts when the edited file is README.md.
# Exit 0 = nothing to do / clean. Exit 2 = Vale found errors; its output goes to
# stderr, which Claude Code feeds back to the model so it can fix the prose.
# Skips silently if `jq` or `vale` isn't installed (don't block edits).

set -u

command -v jq >/dev/null 2>&1 || exit 0
command -v vale >/dev/null 2>&1 || exit 0

input=$(cat)
file=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty')

case "$file" in
  */README.md | README.md) ;;
  *) exit 0 ;;
esac

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
[ -f README.md ] || exit 0

if ! out=$(vale README.md 2>&1); then
  {
    echo "Vale found prose issues in README.md (LangChain docs house style):"
    echo "$out"
    echo "Fix these in README.md so it stays publishable (see 'make lint_prose')."
  } >&2
  exit 2
fi

exit 0
