"""Build the M&A / IPO dashboard: run two DQL queries, aggregate the entities.

The Explorer tab lets an agent author one-off queries. This dashboard is the
opposite shape: two *fixed* DQL templates (recent acquisitions, recent IPOs)
parameterized by a minimum employee count and a date window, run against the KG,
then reduced in Python into chart-ready breakdowns (by industry, month, country,
exchange) plus the underlying events. No model is involved — it's a deterministic
roll-up of real KG data, so the numbers always trace back to the shown queries.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from langsmith.run_helpers import tracing_context

from langchain_diffbot import DiffbotKnowledgeGraphTool

# Per-query fetch cap. Counts at the 4k-employee default are tiny (tens), but a
# user can drag the size limit to 0 and pull thousands; cap the sample so the
# roll-up stays fast. `totals.fetched` vs `hits` tells the UI when it's a sample.
MAX_FETCH = 400

# Default window: the trailing three months ending today.
DEFAULT_WINDOW_DAYS = 92


def default_range() -> tuple[str, str]:
    """Return (date_from, date_to) ISO strings for the default 3-month window."""
    today = date.today()
    return (today - timedelta(days=DEFAULT_WINDOW_DAYS)).isoformat(), today.isoformat()


def _ddate_str(ddate: Any) -> str | None:
    """Pull a clean ISO-ish date string from a Diffbot DDate composite.

    DDate strings carry a leading precision marker (`d2026-03-02`, `d2026-03`,
    `d2026`); the marker is dropped, the already-present precision is kept.
    """
    if not isinstance(ddate, dict):
        return None
    raw = ddate.get("str")
    if not isinstance(raw, str) or not raw:
        return None
    if len(raw) > 1 and raw[0].isalpha() and (raw[1].isdigit() or raw[1] == "-"):
        raw = raw[1:]
    return raw


def _primary_industry(entity: dict[str, Any]) -> str:
    """Best broad-industry label for an org: the lowest-level primary category."""
    cats = entity.get("categories") or []
    named = [c for c in cats if isinstance(c, dict) and c.get("name")]
    if not named:
        return "Uncategorized"
    primary = [c for c in named if c.get("isPrimary")] or named
    # Level 1 is the broadest bucket (e.g. "Technology Companies"); prefer it.
    primary.sort(key=lambda c: c.get("level") or 99)
    return str(primary[0]["name"])


def _country(entity: dict[str, Any]) -> str:
    """Country name from the org's location composite, or 'Unknown'."""
    loc = entity.get("location")
    if isinstance(loc, dict):
        country = loc.get("country")
        if isinstance(country, dict) and country.get("name"):
            return str(country["name"])
    return "Unknown"


def _amount_usd(amount: Any) -> float | None:
    """Numeric value from a Diffbot Amount composite (currency ignored)."""
    if isinstance(amount, dict) and isinstance(amount.get("value"), (int, float)):
        return float(amount["value"])
    return None


def _pick_deal(deals: Any, date_from: str, date_to: str) -> dict[str, Any]:
    """Choose the acquisition that put the org in the window.

    An org's `acquiredBy` can list several deals across its history; the DQL
    matches if *any* falls in range. Prefer the latest deal whose date is inside
    [date_from, date_to] (ISO strings compare correctly); fall back to the latest
    deal overall so a precision-trimmed date never blanks the event.
    """
    if not isinstance(deals, list):
        return {}
    dated = [d for d in deals if isinstance(d, dict)]
    if not dated:
        return {}
    in_window = [
        d
        for d in dated
        if (s := _ddate_str(d.get("date"))) and date_from <= s <= date_to
    ]
    pool = in_window or dated
    return max(pool, key=lambda d: _ddate_str(d.get("date")) or "")


def _ma_event(entity: dict[str, Any], date_from: str, date_to: str) -> dict[str, Any]:
    """Normalize an acquired org into one M&A event (its in-window acquisition)."""
    deal = _pick_deal(entity.get("acquiredBy"), date_from, date_to)
    return {
        "type": "M&A",
        "name": entity.get("name"),
        "date": _ddate_str(deal.get("date")),
        "industry": _primary_industry(entity),
        "country": _country(entity),
        "employees": entity.get("nbEmployees"),
        "amount_usd": _amount_usd(deal.get("amount")),
        "exchange": None,
        "counterparty": deal.get("name"),  # acquirer
    }


def _ipo_event(entity: dict[str, Any]) -> dict[str, Any]:
    """Normalize a newly-public org into one IPO event."""
    ipo = entity.get("ipo") if isinstance(entity.get("ipo"), dict) else {}
    return {
        "type": "IPO",
        "name": entity.get("name"),
        "date": _ddate_str(ipo.get("date")),
        "industry": _primary_industry(entity),
        "country": _country(entity),
        "employees": entity.get("nbEmployees"),
        "amount_usd": None,
        "exchange": ipo.get("stockExchange"),
        "counterparty": None,
    }


def _entities(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull entity dicts out of a DQL response (`data: [{entity: {...}}]`)."""
    out: list[dict[str, Any]] = []
    for hit in body.get("data", []):
        if isinstance(hit, dict):
            out.append(hit.get("entity", hit))
    return out


def _count_breakdown(
    events: list[dict[str, Any]], key: str, types: tuple[str, ...] = ("M&A", "IPO")
) -> list[dict[str, Any]]:
    """Group events by `event[key]`, counting per type and total, sorted desc."""
    buckets: dict[str, dict[str, int]] = defaultdict(lambda: {t: 0 for t in types})
    for ev in events:
        label = ev.get(key) or "Unknown"
        buckets[label][ev["type"]] += 1
    rows = [
        {key: label, **counts, "total": sum(counts.values())}
        for label, counts in buckets.items()
    ]
    rows.sort(key=lambda r: r["total"], reverse=True)
    return rows


def _month_series(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Count M&A/IPO per calendar month (YYYY-MM), chronological."""
    buckets: dict[str, dict[str, int]] = defaultdict(lambda: {"M&A": 0, "IPO": 0})
    for ev in events:
        d = ev.get("date")
        month = d[:7] if isinstance(d, str) and len(d) >= 7 else "unknown"
        buckets[month][ev["type"]] += 1
    rows = [
        {"month": m, "ma": c["M&A"], "ipo": c["IPO"], "total": c["M&A"] + c["IPO"]}
        for m, c in buckets.items()
    ]
    rows.sort(key=lambda r: r["month"])
    return rows


async def _build(min_employees: int, date_from: str, date_to: str) -> dict[str, Any]:
    """Run both queries (concurrently), aggregate, and shape the response."""
    # Omit the headcount clause entirely at 0 — DQL has no "any value" wildcard.
    emp = f" nbEmployees>{min_employees}" if min_employees > 0 else ""
    ma_query = (
        f'type:Organization isAcquired:true acquiredBy.date>="{date_from}" '
        f'acquiredBy.date<="{date_to}"{emp}'
    )
    ipo_query = f'type:Organization ipo.date>="{date_from}" ipo.date<="{date_to}"{emp}'

    kg = DiffbotKnowledgeGraphTool()
    # The dashboard is deterministic (no model), and each KG call returns up to
    # MAX_FETCH full entities — tracing those to LangSmith serializes tens of MB
    # per call (and trips its 26 MB ingest cap with a 422). There's nothing worth
    # tracing here, so turn it off for these two calls; the Explorer agent run in
    # server.py stays traced.
    with tracing_context(enabled=False):
        ma_body, ipo_body = await asyncio.gather(
            kg.ainvoke({"query": ma_query, "size": MAX_FETCH}),
            kg.ainvoke({"query": ipo_query, "size": MAX_FETCH}),
        )

    ma_entities = _entities(ma_body)
    ipo_entities = _entities(ipo_body)
    events: list[dict[str, Any]] = [
        _ma_event(e, date_from, date_to) for e in ma_entities
    ]
    events += [_ipo_event(e) for e in ipo_entities]
    # Most recent first for the events table / top-deals list.
    events.sort(key=lambda e: e.get("date") or "", reverse=True)

    ma_hits = int(ma_body.get("hits", 0))
    ipo_hits = int(ipo_body.get("hits", 0))
    deal_value = sum(e["amount_usd"] for e in events if e.get("amount_usd"))

    top_deals = sorted(
        (e for e in events if e["type"] == "M&A" and e.get("amount_usd")),
        key=lambda e: e["amount_usd"],
        reverse=True,
    )[:8]

    return {
        "min_employees": min_employees,
        "date_from": date_from,
        "date_to": date_to,
        "totals": {
            "events": len(events),
            "ma": ma_hits,
            "ipo": ipo_hits,
            "deal_value_usd": deal_value,
            "fetched": len(events),
            "is_sample": ma_hits > len(ma_entities) or ipo_hits > len(ipo_entities),
        },
        "by_industry": _count_breakdown(events, "industry")[:12],
        "by_month": _month_series(events),
        "by_country": _count_breakdown(events, "country")[:10],
        "by_exchange": _count_breakdown(
            [e for e in events if e["type"] == "IPO"], "exchange"
        )[:10],
        "top_deals": top_deals,
        "events": events,
        "queries": {"ma": ma_query, "ipo": ipo_query},
        "error": None,
    }


async def build_dashboard(
    min_employees: int, date_from: str, date_to: str
) -> dict[str, Any]:
    """Build the dashboard payload, surfacing any failure as an `error` field."""
    try:
        return await _build(min_employees, date_from, date_to)
    except Exception as exc:  # surface to the UI instead of a 500
        return {
            "min_employees": min_employees,
            "date_from": date_from,
            "date_to": date_to,
            "totals": {
                "events": 0,
                "ma": 0,
                "ipo": 0,
                "deal_value_usd": 0,
                "fetched": 0,
                "is_sample": False,
            },
            "by_industry": [],
            "by_month": [],
            "by_country": [],
            "by_exchange": [],
            "top_deals": [],
            "events": [],
            "queries": {},
            "error": f"Failed to build the dashboard: {exc}",
        }
