"""Project KG entities onto the agent-chosen columns to build table rows.

The agent returns dot-path columns (e.g. `location.city.name`). KG entities are
nested dicts that sometimes branch into lists (e.g. `employments`, `industries`),
so plucking a path can fan out to several values. We keep this forgiving: a bad
or missing path yields an empty cell rather than an error, so one wrong column
never blanks the whole table.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from datetime import datetime, timezone
from typing import Any

# Values longer than this are truncated so a stray long field can't wreck the
# table layout. Generous enough for names, URLs, short descriptions.
_MAX_CELL_CHARS = 200


def _walk(node: Any, parts: Sequence[str]) -> list[Any]:
    """Walk `parts` into `node`, fanning out across any lists encountered.

    Returns a flat list of leaf values (so `employments.employer.name` over an
    entity with several employments yields one entry per employer).
    """
    if not parts:
        # Expand a terminal list one level so a list of scalars/composites
        # becomes several cells joined later, not a raw "[...]" repr.
        return list(node) if isinstance(node, list) else [node]
    if isinstance(node, list):
        out: list[Any] = []
        for item in node:
            out.extend(_walk(item, parts))
        return out
    if isinstance(node, dict):
        key = parts[0]
        if key in node:
            return _walk(node[key], parts[1:])
        return []
    return []


def _format_date(value: dict[str, Any]) -> str | None:
    """Render a Diffbot date composite ({str, precision, timestamp}) as a date.

    Diffbot date strings carry a leading precision marker, e.g. `d2013-02-02`
    (day), `d2013-02` (month), `d2013` (year); the amount of date present already
    reflects the precision, so we just drop the marker. Falls back to the epoch-ms
    `timestamp` if no usable `str` is present.
    """
    raw = value.get("str")
    if isinstance(raw, str) and raw:
        if len(raw) > 1 and raw[0].isalpha() and (raw[1].isdigit() or raw[1] == "-"):
            raw = raw[1:]
        return raw
    ts = value.get("timestamp")
    if isinstance(ts, (int, float)):
        try:
            return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).date().isoformat()
        except (ValueError, OverflowError, OSError):
            return None
    return None


def _format_leaf(value: Any) -> str:
    """Render a single leaf value as a compact display string."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (str, int, float)):
        return str(value)
    if isinstance(value, dict):
        # Diffbot date composites carry `timestamp`/`precision` instead of a name.
        if "timestamp" in value or ("str" in value and "precision" in value):
            formatted = _format_date(value)
            if formatted is not None:
                return formatted
        # Prefer a human label if the composite carries one.
        for key in ("name", "label", "title"):
            if value.get(key):
                return str(value[key])
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def pluck(entity: dict[str, Any], path: str) -> str:
    """Pluck a dot-path out of an entity and format it for a table cell.

    Multiple matches (from list fan-out) are de-duplicated, joined with `, `,
    and truncated. Missing paths return an empty string.
    """
    leaves = _walk(entity, path.split("."))
    seen: list[str] = []
    for leaf in leaves:
        rendered = _format_leaf(leaf)
        if rendered and rendered not in seen:
            seen.append(rendered)
    cell = ", ".join(seen)
    if len(cell) > _MAX_CELL_CHARS:
        cell = cell[: _MAX_CELL_CHARS - 1] + "…"
    return cell


def build_rows(
    data: Iterable[dict[str, Any]], paths: Sequence[str]
) -> list[dict[str, str]]:
    """Project each DQL hit onto `paths`, keyed by path.

    `data` is the `data` array from a DQL response. Each hit is
    `{"score": ..., "entity": {...}}`; older shapes embed the entity at the top
    level, so fall back to the hit itself (matches the KG retriever's behavior).
    """
    rows: list[dict[str, str]] = []
    for hit in data:
        entity = hit.get("entity", hit) if isinstance(hit, dict) else {}
        rows.append({path: pluck(entity, path) for path in paths})
    return rows
