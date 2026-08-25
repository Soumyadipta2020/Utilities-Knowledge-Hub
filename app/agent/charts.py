"""
Chart specs: the contract the model writes and the browser renders.

The model never writes rendering code. It emits a small JSON spec in a ```chart
fence, this module validates it, and the browser draws it with Chart.js. Three
reasons it works this way:

  * safety - a spec is data, so nothing the model emits is ever executed;
  * honesty - a spec carries only figures, which means the numbers in the picture
    are the numbers in the answer, and both can be checked against the tool output;
  * one contract, both arms - the RAG baseline and the agent chart identically, so
    a side-by-side difference in the picture is a difference in the *data*, not in
    the plotting.

The schema deliberately has no second y-axis and no pie/donut type. A dual axis
invents a correlation from the arbitrary alignment of two scales, and a donut is
unreadable for the close values these questions produce.
"""

from __future__ import annotations

from typing import Any
import json
import re

CHART_BLOCK = re.compile(r"```chart\s*(\{.*?\})\s*```", re.DOTALL)

# Catches a chart fence whose body never parsed as an object at all - truncated
# output, a stray comment, a fence the model never closed. Without this sweep the
# reader would be shown the raw fence contents as a code block.
CHART_FENCE_ANY = re.compile(r"```chart\b[\s\S]*?(?:```|$)")

CHART_TYPES = {"line", "bar", "hbar", "stacked_bar", "stat"}

MAX_SERIES = 5          # the categorical palette is validated to 5 slots
MAX_POINTS = 60         # a weekly year fits; past this a table is the right form
MAX_STATS = 4


# Written once and injected into BOTH system prompts, so the two arms of the
# comparison cannot drift apart in how they chart.
CHART_INSTRUCTIONS = """
## Charts

When your answer contains a series, a ranking or a part-to-whole split, add ONE
chart (at most two) as a fenced ```chart block containing only JSON:

```chart
{"type":"line","title":"Net weekly appointments","x_label":"Week commencing",
 "y_label":"Net appointments","labels":["2026-05-18","2026-05-25"],
 "series":[{"name":"Net appointments","values":[62222,59648]}],
 "highlight":"2026-05-25","note":"What the reader should take away in one line.",
 "source":"appointment_schedule joined to visit_outcome"}
```

Fields: `type` (required), `title` (required), `labels` + `series` (required
except for `stat`), and optionally `subtitle`, `x_label`, `y_label`, `highlight`
(one label to emphasise - use it for the anomaly the answer is about), `note`
(one-line takeaway), `source` (which datasets the figures came from),
`value_prefix`, `value_suffix`.

Pick the type by what the reader has to do:
- `line` - a trend over time. This is the default for anything weekly/monthly.
- `bar` - compare magnitude across a few named categories.
- `hbar` - same, but for more than ~6 categories or long names.
- `stacked_bar` - part-to-whole across categories.
- `stat` - ONE headline number, or up to four. Use
  `{"type":"stat","title":"...","stats":[{"label":"Appointments lost","value":"17,360","note":"week of 6 Jul"}]}`
  instead of drawing a one-bar chart.

Rules - these matter more than having a chart at all:
1. Every value must be a figure you actually retrieved or computed in this turn.
   Never invent, smooth, round-trip or extrapolate a point to fill a chart. If you
   do not have a series, do not draw one.
2. `labels` and every series' `values` must be the same length, and values must be
   plain numbers (no units, no commas, no strings).
3. At most 5 series. If you have more, chart the top ones and say so.
4. Never chart two measures with different scales together (e.g. counts and
   percentages) - chart the one the question asked about.
5. Keep the surrounding prose and any table intact: the chart supplements the
   answer, it never replaces the figures in the text.
6. `note` should say what the picture shows, not describe the chart type.
""".strip()


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        # Models slip commas, currency and percent signs into "numbers".
        cleaned = re.sub(r"[,\s£$€%]", "", value.strip())
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _clean_text(value: Any, limit: int = 160) -> str:
    return str(value or "").strip()[:limit]


def _validate_stat(spec: dict[str, Any]) -> dict[str, Any] | None:
    tiles = []
    for raw in (spec.get("stats") or [])[:MAX_STATS]:
        if not isinstance(raw, dict):
            continue
        value = raw.get("value")
        if value is None or str(value).strip() == "":
            continue
        tiles.append({
            "label": _clean_text(raw.get("label"), 80),
            # Stat values stay strings: they are display text ("17,360", "5.1%"),
            # not plotted magnitudes.
            "value": _clean_text(value, 24),
            "note": _clean_text(raw.get("note"), 90),
        })
    if not tiles:
        return None
    return {
        "type": "stat",
        "title": _clean_text(spec.get("title")) or "Key figures",
        "subtitle": _clean_text(spec.get("subtitle")),
        "stats": tiles,
        "note": _clean_text(spec.get("note"), 240),
        "source": _clean_text(spec.get("source"), 200),
    }


def validate_spec(spec: Any) -> dict[str, Any] | None:
    """Return a canonical spec, or None if it is not renderable.

    Anything malformed is dropped rather than repaired: a chart built from a spec
    the model got wrong is worse than no chart, because it looks authoritative.
    """
    if not isinstance(spec, dict):
        return None

    chart_type = str(spec.get("type", "")).strip().lower()
    if chart_type not in CHART_TYPES:
        return None
    if chart_type == "stat":
        return _validate_stat(spec)

    labels = [_clean_text(label, 60) for label in (spec.get("labels") or [])]
    labels = labels[:MAX_POINTS]
    if len(labels) < 2:
        return None

    series: list[dict[str, Any]] = []
    for raw in (spec.get("series") or [])[:MAX_SERIES]:
        if not isinstance(raw, dict):
            continue
        values = [_as_number(value) for value in (raw.get("values") or [])][: len(labels)]
        if len(values) != len(labels) or any(value is None for value in values):
            continue
        if not any(value for value in values):
            continue  # an all-zero series is a rendering artefact, not data
        series.append({
            "name": _clean_text(raw.get("name"), 60) or f"Series {len(series) + 1}",
            "values": values,
        })

    if not series:
        return None

    highlight = _clean_text(spec.get("highlight"), 60)
    return {
        "type": chart_type,
        "title": _clean_text(spec.get("title")) or "Chart",
        "subtitle": _clean_text(spec.get("subtitle")),
        "x_label": _clean_text(spec.get("x_label"), 60),
        "y_label": _clean_text(spec.get("y_label"), 60),
        "labels": labels,
        "series": series,
        "highlight": highlight if highlight in labels else "",
        "value_prefix": _clean_text(spec.get("value_prefix"), 4),
        "value_suffix": _clean_text(spec.get("value_suffix"), 8),
        "note": _clean_text(spec.get("note"), 240),
        "source": _clean_text(spec.get("source"), 200),
    }


def sanitize_answer(answer: str) -> tuple[str, list[dict[str, Any]]]:
    """Validate every ```chart block in an answer.

    Valid specs are rewritten in canonical form and left in place, so the client
    renders exactly what was checked here. Invalid ones are removed - the reader
    sees the prose without a broken chart, never a wall of raw JSON.
    """
    if not answer or "```chart" not in answer:
        return answer, []

    kept: list[dict[str, Any]] = []

    def replace(match: re.Match[str]) -> str:
        try:
            parsed = json.loads(match.group(1))
        except (ValueError, TypeError):
            return ""
        spec = validate_spec(parsed)
        if spec is None:
            return ""
        kept.append(spec)
        # A sentinel, not the final fence: the next step deletes every remaining
        # chart fence, and a validated block must not be caught by that sweep.
        return f"\x00CHART{len(kept) - 1}\x00"

    cleaned = CHART_BLOCK.sub(replace, answer)
    cleaned = CHART_FENCE_ANY.sub("", cleaned)
    for index, spec in enumerate(kept):
        cleaned = cleaned.replace(
            f"\x00CHART{index}\x00", "```chart\n" + json.dumps(spec) + "\n```"
        )
    # Dropping a block can leave a run of blank lines behind it.
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, kept


def strip_chart_blocks(answer: str) -> str:
    """The prose alone, for consumers that should never see a spec.

    Conversation history, the answer verifier, decision memory and graph keyword
    extraction all work on the words. Feeding them a block of chart JSON wastes
    context at best and, in the verifier's case, invites it to re-check a spec
    instead of the claim.
    """
    if not answer or "```chart" not in answer:
        return answer
    return re.sub(r"\n{3,}", "\n\n", CHART_FENCE_ANY.sub("", answer)).strip()
