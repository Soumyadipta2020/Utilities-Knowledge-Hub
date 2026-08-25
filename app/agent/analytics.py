"""
Shared plumbing for the planning agents (demand forecast, commercial, pricing).

These three agents differ from the existing tools in one important way: they do
not answer a question, they produce a *position* - a corrected forecast, a
negotiation guardrail, a price. That position has to be reproducible, so each
engine here computes it from SQL over the full estate rather than letting the
model estimate it, and returns a structured dict that both the chat tool and the
REST endpoint render from. One computation, two surfaces, no drift.

Two things live here because all three engines need them:

  * a TTL cache - the run-rate scan joins several million-row history tables to
    `customer_holdings`, which costs 5-15 seconds. Paying that on every chat turn
    would blow the agent's time budget, so results are memoised and warmed at
    boot on a background thread.
  * an explicit assumptions ledger - a price or a capacity conversion needs a
    labour rate, and the estate holds no labour cost anywhere. Rather than let a
    number of unknown provenance leak into a recommendation, every assumption is
    declared here, carried through the result, and printed with the answer.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Sequence


class AnalyticsError(RuntimeError):
    """Raised when an engine cannot compute a result it was asked for."""


# --------------------------------------------------------------- assumptions

# Values the estate does not record. Each one is surfaced with any figure that
# depends on it, so a reader can see exactly which part of a recommendation is
# measured and which part is assumed.
ASSUMPTIONS: dict[str, dict[str, Any]] = {
    "labour_cost_per_hour_gbp": {
        "value": 42.0,
        "note": "Fully-loaded engineer cost per productive hour. Not held anywhere in the "
                "estate - replace with the finance rate before quoting externally.",
    },
    "target_gross_margin_pct": {
        "value": 35.0,
        "note": "Target gross margin used to convert a cost base into a price. "
                "Set by commercial policy, not derived from data.",
    },
    "parts_attach_rate": {
        "value": 0.65,
        "note": "Share of repair jobs consuming a chargeable part, inferred from the "
                "'Parts Required' share of visit outcomes; refine with a parts-issue feed.",
    },
}


def assumption(key: str) -> float:
    return float(ASSUMPTIONS[key]["value"])


def declared(*keys: str) -> list[dict[str, Any]]:
    """The assumption entries behind a result, ready to print alongside it."""
    return [
        {"key": key, "value": ASSUMPTIONS[key]["value"], "note": ASSUMPTIONS[key]["note"]}
        for key in keys
        if key in ASSUMPTIONS
    ]


# --------------------------------------------------------------------- cache

CACHE_TTL_SECONDS = float(15 * 60)

_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_LOCK = threading.Lock()


def cached(key: str, builder: Callable[[], Any], ttl: float = CACHE_TTL_SECONDS) -> Any:
    """Memoise an expensive scan.

    The builder runs OUTSIDE the lock deliberately. These scans take seconds, and
    holding the lock across one would serialise every other engine behind it. Two
    concurrent misses compute twice and the second write wins, which costs one
    duplicate scan and never a wrong answer.
    """
    now = time.time()
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit is not None and (now - hit[0]) < ttl:
            return hit[1]

    value = builder()
    with _CACHE_LOCK:
        _CACHE[key] = (time.time(), value)
    return value


def clear_cache() -> None:
    with _CACHE_LOCK:
        _CACHE.clear()


# ----------------------------------------------------------------- SQL access


def records(sql_service: Any, sql: str, max_rows: int = 1000) -> list[dict[str, Any]]:
    """Run a query and return rows as dicts keyed by column name."""
    if sql_service is None or not getattr(sql_service, "available", False):
        raise AnalyticsError(
            "The SQL engine is unavailable, so this analysis cannot be computed. "
            "Install duckdb or ask a question that does not need full-estate figures."
        )

    result = sql_service.query(sql, max_rows=max_rows)
    if not result.get("success"):
        raise AnalyticsError(str(result.get("error", "unknown SQL error")))

    columns = list(result["columns"])
    return [dict(zip(columns, row)) for row in result["rows"]]


def scalar(sql_service: Any, sql: str, default: Any = None) -> Any:
    """First column of the first row, or `default` when nothing came back."""
    rows = records(sql_service, sql, max_rows=1)
    if not rows:
        return default
    value = next(iter(rows[0].values()), default)
    return default if value is None else value


# ------------------------------------------------------------------ formatting


def gbp(value: Any, decimals: int = 0) -> str:
    try:
        return f"£{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return "n/a"


def num(value: Any, decimals: int = 0) -> str:
    try:
        return f"{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return "n/a"


def signed_pct(value: Any, decimals: int = 1) -> str:
    try:
        return f"{float(value):+.{decimals}f}%"
    except (TypeError, ValueError):
        return "n/a"


def join_plain(items: Sequence[str], conjunction: str = "and") -> str:
    """Join a list the way a person writes it: "a, b and c", not "a, b, c"."""
    values = [str(item) for item in items if str(item).strip()]
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    return f"{', '.join(values[:-1])} {conjunction} {values[-1]}"


def markdown_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    """Render a markdown table. Empty input returns an empty string, not a stub."""
    if not rows:
        return ""
    lines = [
        "| " + " | ".join(str(header) for header in headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join("" if cell is None else str(cell) for cell in row) + " |")
    return "\n".join(lines)


def chart_block(spec: dict[str, Any]) -> str:
    """Render a chart spec as the fenced block the browser draws.

    The engines emit their own charts rather than leaving it to the model. Two
    reasons: the values come from the same computation as the table beside them,
    so a picture can never disagree with the figures it sits under; and a chart
    appears whether or not the model remembers to draw one. The spec is still
    validated downstream by `charts.sanitize_answer`, so a malformed one is
    dropped rather than shown.
    """
    import json as _json

    from app.agent.charts import validate_spec

    checked = validate_spec(spec)
    if checked is None:
        return ""
    return "```chart\n" + _json.dumps(checked) + "\n```"


def assumptions_block(entries: Sequence[dict[str, Any]]) -> str:
    """One line per assumption, so no figure travels without its caveat."""
    if not entries:
        return ""
    lines = ["**Assumptions used** (not measured in the estate):"]
    for entry in entries:
        lines.append(f"- `{entry['key']}` = {entry['value']} — {entry['note']}")
    return "\n".join(lines)
