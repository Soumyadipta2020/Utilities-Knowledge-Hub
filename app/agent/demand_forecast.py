"""
Demand Forecast Agent - engine.

What it does, in the order a planner would do it:

  1. READ the forecast that already exists (`regional_demand_forecast`) and
     re-derive what demand actually is running at, from the job histories.
  2. GRADE the forecast against that run-rate per region and job type, and turn
     any material bias into a correction with its effect in hours, engineer-days
     and pounds - so a human is approving a number, not a vibe.
  3. FIND what is missing. A forecast can be wrong by being absent: the estate
     provisions engineer capacity for Installation work but forecasts no
     Installation demand at all, which no accuracy metric would ever surface.
  4. BUILD the missing forecast from history when asked, and say by what method.
  5. EXPLAIN what moves demand - including, importantly, the factors that were
     tested and found NOT to move it. A planner who knows weather is worth 1%
     here stops building weather adjustments.

Design note on honesty: every figure below is computed from the full datasets,
and every factor in `drivers()` reports its measured effect size even when that
effect is nil. An agent that only ever reports drivers it "found" is an agent
that will invent one.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Sequence

from app.agent.analytics import (
    AnalyticsError,
    assumption,
    cached,
    chart_block,
    declared,
    gbp,
    markdown_table,
    num,
    records,
    join_plain,
    scalar,
    signed_pct,
)

# Window of recent actuals used as the run-rate the forecast is graded against.
# Eight weeks is long enough to average out day-to-day noise and short enough to
# still reflect the level the business is actually running at.
TRAILING_DAYS = 56

# Planning horizon for effects. Matches the 13-week window the capacity
# simulation already uses, so the two agents quote comparable numbers.
HORIZON_WEEKS = 13
HORIZON_DAYS = HORIZON_WEEKS * 7

# Below this, a bias is noise in an operational forecast and correcting it would
# cost more in churn than it returns in accuracy.
MATERIAL_BIAS_PCT = 5.0

# Falls back only for a job type that has no forecast rows to read a real
# hours-per-job ratio from. Declared with any figure that depends on it.
FALLBACK_HOURS_PER_JOB = 2.0

JOB_TYPES = ("Service", "Repair", "Installation")

# Which history table is the source of truth for each job type's actuals. The
# `appointment_schedule` view carries a job_category but no customer, so a
# regional split through it needs a second 5m-row join; each history table
# carries customer_id directly and is the cheaper and more direct source.
_ACTUAL_SOURCES = {
    "Service": ("service_history", "service_date", ""),
    "Repair": ("repair_history", "repair_date", ""),
    "Installation": ("installation_history", "installation_date", "AND i.installation_happened"),
}


# --------------------------------------------------------------- base figures


def actuals_cutoff(sql_service: Any) -> date:
    """Last date on which the estate has complete actuals for every job type.

    Installation rows run a fortnight past the service and repair tables, but
    that tail thins out sharply - it is jobs already booked, not work already
    done. Grading a forecast against a partial tail would manufacture a shortfall
    that does not exist, so every job type is cut at the same complete date.
    """

    def build() -> date:
        value = scalar(
            sql_service,
            """
            SELECT least(
                (SELECT max(service_date) FROM service_history),
                (SELECT max(repair_date) FROM repair_history)
            ) AS cutoff
            """,
        )
        if value is None:
            raise AnalyticsError("No actuals found in service_history or repair_history.")
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return datetime.fromisoformat(str(value)[:10]).date()

    return cached("demand:cutoff", build)


def _forecast_window(sql_service: Any) -> dict[str, Any]:
    def build() -> dict[str, Any]:
        rows = records(
            sql_service,
            "SELECT min(date) AS start_date, max(date) AS end_date, count(*) AS rows "
            "FROM regional_demand_forecast",
        )
        if not rows or rows[0].get("start_date") is None:
            raise AnalyticsError("regional_demand_forecast holds no rows.")
        row = rows[0]
        return {
            "start": _as_date(row["start_date"]),
            "end": _as_date(row["end_date"]),
            "rows": int(row["rows"]),
        }

    return cached("demand:forecast_window", build)


def _as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)[:10]).date()


def actual_run_rate(sql_service: Any) -> list[dict[str, Any]]:
    """Jobs per day by region and job type over the trailing window.

    This is the single expensive scan in the module - three history tables joined
    to `customer_holdings` for the regional split - so it is memoised and every
    other function reads from it.
    """

    def build() -> list[dict[str, Any]]:
        cutoff = actuals_cutoff(sql_service)
        start = cutoff - timedelta(days=TRAILING_DAYS - 1)
        rows = records(
            sql_service,
            f"""
            WITH actual AS (
                SELECT 'Service' AS job_type, h.region AS region, s.service_date AS d
                FROM service_history s JOIN customer_holdings h USING (customer_id)
                WHERE s.service_date BETWEEN DATE '{start}' AND DATE '{cutoff}'
                UNION ALL
                SELECT 'Repair', h.region, r.repair_date
                FROM repair_history r JOIN customer_holdings h USING (customer_id)
                WHERE r.repair_date BETWEEN DATE '{start}' AND DATE '{cutoff}'
                UNION ALL
                SELECT 'Installation', h.region, i.installation_date
                FROM installation_history i JOIN customer_holdings h ON h.customer_id = i.customer_id
                WHERE i.installation_happened
                  AND i.installation_date BETWEEN DATE '{start}' AND DATE '{cutoff}'
            )
            SELECT job_type, region,
                   count(*) AS jobs,
                   count(DISTINCT d) AS days,
                   round(count(*) * 1.0 / NULLIF(count(DISTINCT d), 0), 2) AS jobs_per_day
            FROM actual
            GROUP BY 1, 2
            ORDER BY 1, 2
            """,
            max_rows=200,
        )
        for row in rows:
            row["window_start"] = str(start)
            row["window_end"] = str(cutoff)
        return rows

    return cached("demand:run_rate", build)


def forecast_level(sql_service: Any) -> list[dict[str, Any]]:
    """Forecast jobs per day and hours per job, over the same-length horizon."""

    def build() -> list[dict[str, Any]]:
        window = _forecast_window(sql_service)
        horizon_end = window["start"] + timedelta(days=TRAILING_DAYS - 1)
        return records(
            sql_service,
            f"""
            SELECT region, job_type,
                   round(avg(number_of_jobs), 2) AS forecast_jobs_per_day,
                   round(sum(number_of_jobs)) AS forecast_jobs,
                   round(sum(jobs_hours)) AS forecast_hours,
                   round(sum(jobs_hours) / NULLIF(sum(number_of_jobs), 0), 2) AS hours_per_job,
                   count(DISTINCT date) AS days
            FROM regional_demand_forecast
            WHERE date BETWEEN DATE '{window["start"]}' AND DATE '{horizon_end}'
            GROUP BY 1, 2
            ORDER BY 2, 1
            """,
            max_rows=200,
        )

    return cached("demand:forecast_level", build)


def capacity_by_skill(sql_service: Any) -> list[dict[str, Any]]:
    """Provisioned engineer hours over the planning horizon, by region and skill."""

    def build() -> list[dict[str, Any]]:
        window = _forecast_window(sql_service)
        end = window["start"] + timedelta(days=HORIZON_DAYS - 1)
        return records(
            sql_service,
            f"""
            SELECT region, eng_skill_type AS job_type,
                   round(sum(available_hours)) AS available_hours
            FROM regional_capacity_forecast
            WHERE date BETWEEN DATE '{window["start"]}' AND DATE '{end}'
            GROUP BY 1, 2
            ORDER BY 2, 1
            """,
            max_rows=200,
        )

    return cached("demand:capacity", build)


def engineer_day_hours(sql_service: Any) -> float:
    """Productive hours in a standard engineer day, from the shift roster."""

    def build() -> float:
        value = scalar(
            sql_service,
            """
            SELECT round(avg(
                       date_diff('minute', shift_start_time, shift_end)
                       - COALESCE(date_diff('minute', lunch_start, lunch_end), 0)
                   ) / 60.0, 2) AS productive_hours
            FROM engineer_availability_and_shifts
            """,
        )
        try:
            hours = float(value)
        except (TypeError, ValueError):
            return 7.0
        return hours if 3.0 <= hours <= 14.0 else 7.0

    return cached("demand:engineer_day_hours", build)


# ------------------------------------------------------------------ evaluation


def evaluate(sql_service: Any, region: str = "", job_type: str = "") -> dict[str, Any]:
    """Grade the published forecast against the run-rate, region by region.

    Returns the per-row detail, a national summary, and the correction each row
    would need - the numbers a human is asked to approve.
    """
    window = _forecast_window(sql_service)
    cutoff = actuals_cutoff(sql_service)
    day_hours = engineer_day_hours(sql_service)
    labour_rate = assumption("labour_cost_per_hour_gbp")

    actual_index = {
        (row["job_type"], row["region"]): row for row in actual_run_rate(sql_service)
    }
    capacity_index = {
        (row["job_type"], row["region"]): float(row["available_hours"] or 0)
        for row in capacity_by_skill(sql_service)
    }

    rows: list[dict[str, Any]] = []
    for entry in forecast_level(sql_service):
        key = (entry["job_type"], entry["region"])
        actual = actual_index.get(key)
        if actual is None:
            continue
        if region and str(entry["region"]).casefold() != region.strip().casefold():
            continue
        if job_type and str(entry["job_type"]).casefold() != job_type.strip().casefold():
            continue

        forecast_per_day = float(entry["forecast_jobs_per_day"] or 0)
        actual_per_day = float(actual["jobs_per_day"] or 0)
        if actual_per_day <= 0:
            continue

        bias_pct = (forecast_per_day - actual_per_day) / actual_per_day * 100.0
        hours_per_job = float(entry["hours_per_job"] or FALLBACK_HOURS_PER_JOB)

        # The correction is expressed as a multiplier on the published forecast,
        # which is what a planner actually applies to a forecast file.
        correction_factor = actual_per_day / forecast_per_day if forecast_per_day else 0.0
        horizon_forecast_hours = forecast_per_day * hours_per_job * HORIZON_DAYS
        horizon_corrected_hours = actual_per_day * hours_per_job * HORIZON_DAYS
        hours_delta = horizon_corrected_hours - horizon_forecast_hours

        available = capacity_index.get(key, 0.0)
        rows.append({
            "region": entry["region"],
            "job_type": entry["job_type"],
            "forecast_jobs_per_day": round(forecast_per_day, 1),
            "actual_jobs_per_day": round(actual_per_day, 1),
            "bias_pct": round(bias_pct, 1),
            "material": abs(bias_pct) >= MATERIAL_BIAS_PCT,
            "direction": "under-forecast" if bias_pct < 0 else "over-forecast",
            "hours_per_job": round(hours_per_job, 2),
            "correction_factor": round(correction_factor, 3),
            "suggested_jobs_per_day": round(actual_per_day, 1),
            "forecast_hours_horizon": round(horizon_forecast_hours),
            "corrected_hours_horizon": round(horizon_corrected_hours),
            "hours_delta": round(hours_delta),
            "engineer_days_delta": round(hours_delta / day_hours) if day_hours else 0,
            "cost_delta_gbp": round(hours_delta * labour_rate),
            "available_hours": round(available),
            "balance_before": round(available - horizon_forecast_hours),
            "balance_after": round(available - horizon_corrected_hours),
        })

    rows.sort(key=lambda item: item["bias_pct"])

    # Echoed back so a caller that filtered on a name that does not exist gets
    # the real names rather than an empty result it cannot act on.
    graded_keys = [
        (entry["job_type"], entry["region"])
        for entry in forecast_level(sql_service)
        if (entry["job_type"], entry["region"]) in actual_index
    ]

    material = [row for row in rows if row["material"]]
    total_delta = sum(row["hours_delta"] for row in rows)
    weighted_bias = (
        sum(row["bias_pct"] * row["forecast_hours_horizon"] for row in rows)
        / sum(row["forecast_hours_horizon"] for row in rows)
        if rows and sum(row["forecast_hours_horizon"] for row in rows)
        else 0.0
    )

    # A bias that points the same way everywhere is a method problem, not a
    # regional one - and it is fixed with one correction rather than nine.
    negative = sum(1 for row in rows if row["bias_pct"] < 0)
    if rows and negative == len(rows):
        pattern = "systematic under-forecast in every region and job type"
    elif rows and negative == 0:
        pattern = "systematic over-forecast in every region and job type"
    else:
        pattern = "mixed - some regions over, some under"

    return {
        "forecast_window": {"start": str(window["start"]), "end": str(window["end"])},
        "actuals_window": {
            "start": str(cutoff - timedelta(days=TRAILING_DAYS - 1)),
            "end": str(cutoff),
            "days": TRAILING_DAYS,
        },
        "decision": _decision_record(rows, pattern, weighted_bias, cutoff),
        "rows": rows,
        "filters": {"region": region or "", "job_type": job_type or ""},
        "available_regions": sorted({key[1] for key in graded_keys}),
        "available_job_types": sorted({key[0] for key in graded_keys}),
        "summary": {
            "graded": len(rows),
            "material": len(material),
            "weighted_bias_pct": round(weighted_bias, 1),
            "pattern": pattern,
            "hours_delta_horizon": round(total_delta),
            "engineer_days_delta": round(total_delta / day_hours) if day_hours else 0,
            "cost_delta_gbp": round(total_delta * labour_rate),
            "horizon_weeks": HORIZON_WEEKS,
            "worst": material[0] if material else None,
        },
        "assumptions": declared("labour_cost_per_hour_gbp"),
        "method": (
            f"Published forecast for the first {TRAILING_DAYS} days of the horizon, compared "
            f"with the actual run-rate over the trailing {TRAILING_DAYS} days to {cutoff}. "
            "Actuals come from service_history, repair_history and installation_history joined "
            "to customer_holdings for the regional split. Effects are scaled to "
            f"{HORIZON_WEEKS} weeks using each job type's own forecast hours-per-job ratio."
        ),
    }


def _decision_record(
    rows: list[dict[str, Any]], pattern: str, weighted_bias: float, cutoff: date
) -> dict[str, Any]:
    """State the conclusion, the test behind it, and what would overturn it.

    A recommendation is only as good as the reader's ability to attack it, so the
    sign test, the sample it rests on and the explicit falsifier all travel with
    the conclusion. The sign test is the load-bearing one: a forecast with no
    systematic bias should scatter either side of the run-rate, so every series
    landing on the same side is the thing that makes this a method fault rather
    than a run of bad luck.
    """
    if not rows:
        return {}

    same_direction = max(
        sum(1 for row in rows if row["bias_pct"] < 0),
        sum(1 for row in rows if row["bias_pct"] > 0),
    )
    total = len(rows)
    # Two-sided sign test against a coin-flip null. Series within a region are not
    # fully independent, so this is an indicative floor rather than a p-value to
    # quote in a paper - and it is described that way.
    p_value = min(1.0, 2.0 * (0.5 ** total)) if same_direction == total else None
    material = [row for row in rows if row["material"]]

    if same_direction == total and total >= 8:
        confidence = "high"
        conclusion = (
            f"The forecast has a systematic method fault, not a regional problem. All {total} "
            f"series miss in the same direction and the weighted bias is "
            f"{signed_pct(weighted_bias)}. One correction factor fixes the method; correcting "
            "nine regions separately would treat the symptom."
        )
    elif len(material) >= total / 2:
        confidence = "medium"
        conclusion = (
            f"{len(material)} of {total} series are outside tolerance but they do not all miss "
            "the same way, so this is a set of regional corrections rather than one method fix."
        )
    else:
        confidence = "low"
        conclusion = (
            f"Only {len(material)} of {total} series are outside the "
            f"±{MATERIAL_BIAS_PCT:.0f}% band. The forecast is broadly sound; correct the named "
            "series and leave the method alone."
        )

    facts = [
        f"Every series was graded on the same basis: published jobs/day for the first "
        f"{TRAILING_DAYS} days of the horizon against the actual run-rate over the "
        f"{TRAILING_DAYS} days to {cutoff}, region by region.",
        f"{same_direction} of {total} series miss in the same direction ({pattern}).",
        f"{len(material)} series are outside the ±{MATERIAL_BIAS_PCT:.0f}% materiality band; "
        f"{total - len(material)} are inside it and need no change.",
    ]
    if p_value is not None:
        facts.append(
            f"If the forecast were unbiased, the chance of all {total} series landing on the same "
            f"side is about {p_value * 100:.4f}%. That is what rules out random variation as the "
            "explanation. Series within a region are not fully independent, so treat this as "
            "indicative rather than exact."
        )

    return {
        "conclusion": conclusion,
        "confidence": confidence,
        "facts": facts,
        "sign_test": {
            "series": total,
            "same_direction": same_direction,
            "p_value": p_value,
        },
        "falsifier": (
            "This conclusion is wrong if the trailing "
            f"{TRAILING_DAYS} days are not representative — a promotion, a backlog catch-up or a "
            "data-loading gap in the job histories would all produce the same signature. Check "
            "the run-rate against the preceding quarter before applying the correction, and "
            "confirm the forecast was not deliberately set below run-rate as a capacity-"
            "constrained plan rather than an unconstrained demand view."
        ),
        "not_concluded": (
            "This does not say demand is rising. The forecast is being compared with the level "
            "demand is already running at, not with a trend. The measured growth trend is a "
            "separate and much smaller effect."
        ),
    }


def render_evaluation(result: dict[str, Any], limit: int = 20) -> str:
    """Markdown for the chat agent. The UI renders the same dict as a table."""
    summary = result["summary"]
    if not result["rows"]:
        filters = result.get("filters", {})
        if filters.get("region") or filters.get("job_type"):
            return (
                f"No forecast series matches region='{filters.get('region', '')}' "
                f"job_type='{filters.get('job_type', '')}'. "
                f"Regions with a gradeable forecast: {', '.join(result['available_regions'])}. "
                f"Job types: {', '.join(result['available_job_types'])}. "
                "Call the tool again with one of these exact names."
            )
        return (
            "No forecast row could be graded: the published forecast and the job "
            "histories have no region/job-type combination in common."
        )

    decision = result.get("decision") or {}
    lines = [
        f"**Decision: {decision.get('conclusion', 'see the table below.')}** "
        f"(confidence: {decision.get('confidence', 'unstated')})",
        "",
        "**The facts this rests on**",
    ]
    for fact in decision.get("facts", []):
        lines.append(f"- {fact}")
    lines += [
        f"- Weighted bias across the graded series is "
        f"**{signed_pct(summary['weighted_bias_pct'])}**; correcting every material series moves "
        f"**{num(abs(summary['hours_delta_horizon']))} engineer-hours** over "
        f"{summary['horizon_weeks']} weeks (~{num(abs(summary['engineer_days_delta']))} "
        f"engineer-days, {gbp(abs(summary['cost_delta_gbp']))} of labour at the assumed rate).",
        f"- Forecast window {result['forecast_window']['start']} → "
        f"{result['forecast_window']['end']}; graded against actuals "
        f"{result['actuals_window']['start']} → {result['actuals_window']['end']}.",
        "",
    ]
    if decision.get("not_concluded"):
        lines += [f"**What this does NOT say.** {decision['not_concluded']}", ""]
    if decision.get("falsifier"):
        lines += [f"**What would overturn it.** {decision['falsifier']}", ""]

    table_rows = []
    for row in result["rows"][:limit]:
        table_rows.append([
            row["region"],
            row["job_type"],
            num(row["forecast_jobs_per_day"], 1),
            num(row["actual_jobs_per_day"], 1),
            signed_pct(row["bias_pct"]),
            num(row["suggested_jobs_per_day"], 1),
            f"{num(row['hours_delta'])} h",
            num(row["balance_before"]) + " → " + num(row["balance_after"]),
        ])
    lines.append(markdown_table(
        ["Region", "Job type", "Forecast/day", "Actual/day", "Bias",
         "Suggested/day", "Hours effect (13w)", "Capacity balance"],
        table_rows,
    ))

    # Charted from the same rows as the table above it, so the picture and the
    # figures cannot drift apart.
    chart = chart_block({
        "type": "hbar",
        "title": "How far each area's forecast is from actual demand",
        "subtitle": "Negative means we are planning for less work than turns up",
        "x_label": "Difference from actual (%)",
        "labels": [f"{row['region']} {row['job_type']}" for row in result["rows"][:limit]],
        "series": [{
            "name": "Difference from actual",
            "values": [row["bias_pct"] for row in result["rows"][:limit]],
        }],
        "highlight": (
            f"{summary['worst']['region']} {summary['worst']['job_type']}"
            if summary.get("worst") else ""
        ),
        "value_suffix": "%",
        "note": (
            f"Every area misses the same way, which is what makes this a method "
            f"problem rather than a regional one."
            if "systematic" in summary.get("pattern", "") else summary.get("pattern", "")
        ),
        "source": "regional_demand_forecast vs service_history, repair_history, installation_history",
    })
    if chart:
        lines += ["", chart]

    worst = summary.get("worst")
    if worst:
        lines += [
            "",
            f"**Worst series:** {worst['region']} {worst['job_type']} at "
            f"{signed_pct(worst['bias_pct'])}. Correcting it to "
            f"{num(worst['suggested_jobs_per_day'], 1)} jobs/day moves its 13-week capacity "
            f"balance from {num(worst['balance_before'])} to {num(worst['balance_after'])} hours.",
        ]

    lines += ["", f"_Method:_ {result['method']}"]
    return "\n".join(lines)


# ------------------------------------------------------- forward planning impact


def planning_impact(sql_service: Any) -> dict[str, Any]:
    """What the forecast being wrong means for the plan, not just for accuracy.

    Three sources of unplanned work are added up here, because a planner has to
    carry all three and the forecast contains none of them:

      1. the bias - demand is running above the published line;
      2. the missing job types - work that is staffed but not forecast at all;
      3. the return visits implied by jobs that do not finish first time, which
         consume a slot the demand line never asked for.

    The result is expressed the way a plan is actually managed: hours, engineers,
    and whether each skill can absorb it.
    """
    evaluation = evaluate(sql_service)
    coverage = gaps(sql_service)
    day_hours = engineer_day_hours(sql_service)
    window = _forecast_window(sql_service)
    horizon_end = window["start"] + timedelta(days=HORIZON_DAYS - 1)
    working_days = HORIZON_DAYS

    capacity_index = {
        (row["job_type"], row["region"]): float(row["available_hours"] or 0)
        for row in capacity_by_skill(sql_service)
    }

    # 1. Bias, aggregated to the skill a planner actually staffs.
    by_skill: dict[str, dict[str, float]] = {}
    for row in evaluation["rows"]:
        entry = by_skill.setdefault(row["job_type"], {
            "forecast_hours": 0.0, "corrected_hours": 0.0, "bias_hours": 0.0, "available": 0.0,
        })
        entry["forecast_hours"] += row["forecast_hours_horizon"]
        entry["corrected_hours"] += row["corrected_hours_horizon"]
        entry["bias_hours"] += row["hours_delta"]
        entry["available"] += row["available_hours"]

    # 2. Job types staffed but never forecast.
    for missing in coverage["missing_job_types"]:
        entry = by_skill.setdefault(missing["job_type"], {
            "forecast_hours": 0.0, "corrected_hours": 0.0, "bias_hours": 0.0, "available": 0.0,
        })
        entry["corrected_hours"] += missing["implied_demand_hours"]
        entry["bias_hours"] += missing["implied_demand_hours"]
        entry["available"] += missing["capacity_hours_horizon"]

    # 3. Return visits. Sourced from the pricing engine's cost-to-serve model so
    #    the two agents cannot quote different first-time-fix rates.
    revisits: dict[str, dict[str, Any]] = {}
    try:
        from app.agent import pricing as pricing_engine

        for line in pricing_engine.cost_to_serve(sql_service)["lines"]:
            multiple = float(line["visits_per_completed_job"])
            if multiple <= 1.0:
                continue
            entry = by_skill.get(line["service_line"])
            if entry is None:
                continue
            extra = entry["corrected_hours"] * (multiple - 1.0)
            revisits[line["service_line"]] = {
                "first_time_fix_pct": line["first_time_fix_pct"],
                "visits_per_completed_job": multiple,
                "extra_hours": round(extra),
                "extra_engineer_days": round(extra / day_hours) if day_hours else 0,
            }
            entry["corrected_hours"] += extra
            entry["bias_hours"] += extra
    except Exception as error:  # noqa: BLE001 - a missing cost model must not block the plan
        print(f"[DemandForecast] Revisit load unavailable: {error}")

    skills: list[dict[str, Any]] = []
    for skill, entry in sorted(by_skill.items()):
        available = entry["available"] or sum(
            hours for (job_type, _), hours in capacity_index.items() if job_type == skill
        )
        balance_before = available - entry["forecast_hours"]
        balance_after = available - entry["corrected_hours"]
        hours_per_job = max(_skill_hours_per_job(sql_service, skill), 0.1)

        # One FTE delivers a rostered day for every day of the horizon. The estate
        # works seven days a week - the weekday profile is flat - so calendar days
        # and working days are the same thing here.
        fte_capacity = day_hours * working_days if day_hours and working_days else 0.0
        fte = abs(balance_after) / fte_capacity if fte_capacity else 0.0

        # Split what the plan ALREADY showed from what this analysis adds. Service
        # was in deficit before anyone looked at the forecast; claiming that
        # deficit as a finding would be taking credit for the plan's own arithmetic.
        at_risk_before = round(-balance_before / hours_per_job) if balance_before < 0 else 0
        at_risk_after = round(-balance_after / hours_per_job) if balance_after < 0 else 0
        skills.append({
            "job_type": skill,
            "available_hours": round(available),
            "planned_hours": round(entry["forecast_hours"]),
            "true_hours": round(entry["corrected_hours"]),
            "unplanned_hours": round(entry["bias_hours"]),
            "balance_before": round(balance_before),
            "balance_after": round(balance_after),
            "position": "deficit" if balance_after < 0 else "surplus",
            "position_before": "deficit" if balance_before < 0 else "surplus",
            "fte_equivalent": round(fte, 1),
            "jobs_at_risk_before": at_risk_before,
            "jobs_at_risk": at_risk_after,
            "jobs_at_risk_added": max(at_risk_after - at_risk_before, 0),
            "revisit": revisits.get(skill),
        })

    deficit = [s for s in skills if s["balance_after"] < 0]
    surplus = [s for s in skills if s["balance_after"] > 0]
    total_unplanned = sum(s["unplanned_hours"] for s in skills)
    total_at_risk = sum(s["jobs_at_risk"] for s in deficit)
    total_at_risk_before = sum(s["jobs_at_risk_before"] for s in skills)
    total_fte = sum(s["fte_equivalent"] for s in deficit)

    # Cross-skill cover: surplus in one skill only helps if engineers can be
    # retrained or re-scoped, which is a decision, not an assumption.
    transferable = sum(s["balance_after"] for s in surplus)

    return {
        "horizon": {
            "start": str(window["start"]),
            "end": str(horizon_end),
            "weeks": HORIZON_WEEKS,
        },
        "skills": skills,
        "deficit_skills": [s["job_type"] for s in deficit],
        "surplus_skills": [s["job_type"] for s in surplus],
        "totals": {
            "unplanned_hours": round(total_unplanned),
            "unplanned_engineer_days": round(total_unplanned / day_hours) if day_hours else 0,
            "jobs_at_risk": round(total_at_risk),
            "jobs_at_risk_before": round(total_at_risk_before),
            "jobs_at_risk_added": round(max(total_at_risk - total_at_risk_before, 0)),
            "fte_gap": round(total_fte, 1),
            "transferable_surplus_hours": round(transferable),
            "net_position_hours": round(sum(s["balance_after"] for s in skills)),
        },
        "assumptions": declared("labour_cost_per_hour_gbp"),
        "method": (
            "Unplanned work is the sum of three things the published plan does not carry: the "
            "bias against the actual run-rate, job types that are staffed but not forecast, and "
            "the return visits implied by jobs that do not complete first time (taken from the "
            "same cost-to-serve model the Pricing Agent uses, so the two cannot disagree). FTE "
            f"is deficit hours over {HORIZON_WEEKS} weeks at the rostered productive day."
        ),
    }


def _skill_hours_per_job(sql_service: Any, skill: str) -> float:
    try:
        return hours_per_job_ratio(sql_service, skill)[0]
    except Exception:  # noqa: BLE001
        return FALLBACK_HOURS_PER_JOB


def render_planning_impact(result: dict[str, Any]) -> str:
    totals = result["totals"]
    lines = [
        f"**What this means for the plan** — {result['horizon']['weeks']} weeks, "
        f"{result['horizon']['start']} → {result['horizon']['end']}",
        "",
        f"- **{num(totals['unplanned_hours'])} engineer-hours of work are not in the plan** "
        f"(~{num(totals['unplanned_engineer_days'])} engineer-days): the forecast bias, the job "
        "types that are staffed but never forecast, and the return visits that jobs failing "
        "first time will require.",
    ]
    if totals["jobs_at_risk"]:
        lines.append(
            f"- **{num(totals['jobs_at_risk'])} jobs cannot be served** with the capacity "
            f"currently provisioned — a gap of **{num(totals['fte_gap'], 1)} FTE** over the "
            f"horizon. Of those, {num(totals['jobs_at_risk_before'])} were already implied by "
            f"the published plan's own numbers; **{num(totals['jobs_at_risk_added'])} are added "
            "by this analysis.** Do not present the whole figure as a new discovery."
        )
    if result["surplus_skills"] and result["deficit_skills"]:
        lines.append(
            f"- {', '.join(result['surplus_skills'])} hold "
            f"{num(totals['transferable_surplus_hours'])} surplus hours while "
            f"{', '.join(result['deficit_skills'])} are short. The estate is not short of people "
            "overall — it is short of the right skill in the right place, which is a "
            "redeployment and retraining decision before it is a hiring one."
        )
    lines.append("")

    lines.append(markdown_table(
        ["Skill", "Hours available", "Hours planned", "True hours needed", "Not in plan",
         "Balance before → after", "Position", "FTE gap", "Jobs at risk (already implied → total)"],
        [
            [
                row["job_type"], num(row["available_hours"]), num(row["planned_hours"]),
                num(row["true_hours"]), num(row["unplanned_hours"]),
                f"{num(row['balance_before'])} → {num(row['balance_after'])}",
                row["position"],
                num(row["fte_equivalent"], 1) if row["position"] == "deficit"
                else f"+{num(row['fte_equivalent'], 1)} spare",
                f"{num(row['jobs_at_risk_before'])} → {num(row['jobs_at_risk'])}"
                if row["jobs_at_risk"] else "—",
            ]
            for row in result["skills"]
        ],
    ))

    chart = chart_block({
        "type": "bar",
        "title": "Hours we have against hours the work actually needs",
        "subtitle": f"Next {result['horizon']['weeks']} weeks, by skill",
        "y_label": "Engineer-hours",
        "labels": [row["job_type"] for row in result["skills"]],
        "series": [
            {"name": "Hours available",
             "values": [row["available_hours"] for row in result["skills"]]},
            {"name": "Hours the work needs",
             "values": [row["true_hours"] for row in result["skills"]]},
        ],
        "note": (
            "Where the second bar is taller, the work cannot all be done with the people "
            "currently planned for it."
        ),
        "source": "regional_capacity_forecast, regional_demand_forecast and the job histories",
    })
    if chart:
        lines += ["", chart]

    for row in result["skills"]:
        revisit = row.get("revisit")
        if revisit:
            lines += [
                "",
                f"**{row['job_type']} return visits:** only {revisit['first_time_fix_pct']}% of "
                f"{row['job_type'].lower()} visits finish the job, so each completed job takes "
                f"{revisit['visits_per_completed_job']:.2f} visits. That is "
                f"{num(revisit['extra_hours'])} hours "
                f"(~{num(revisit['extra_engineer_days'])} engineer-days) of work the demand line "
                "never asked for. Raising first-time fix is the cheapest capacity available — it "
                "needs no hiring at all.",
            ]

    lines += ["", f"_Method:_ {result['method']}"]
    return "\n".join(lines)


# ------------------------------------------------------------- weekly outlook


def weekly_outlook(
    sql_service: Any, weeks: int = HORIZON_WEEKS, job_types: Sequence[str] | None = None
) -> dict[str, Any]:
    """The published forecast week by week, next to what it should say.

    Two deliberate choices here, both about not misleading the reader:

      * Weeks are seven-day buckets counted from the first forecast date, NOT
        calendar weeks. The forecast starts mid-week, so calendar weeks would make
        the first and last bucket short and every weekly total would silently be
        comparing six days with seven.
      * Both the published number and the corrected number are shown. Giving only
        the published one answers the question asked while withholding the fact
        that it is systematically low; giving only the corrected one quotes a
        figure that is not in any system the reader can look up.
    """
    weeks = max(1, min(int(weeks or HORIZON_WEEKS), 52))
    wanted = (
        [_canonical_job_type(item) for item in job_types] if job_types else None
    )

    window = _forecast_window(sql_service)
    start = window["start"]
    end = start + timedelta(days=7 * weeks - 1)

    filter_sql = ""
    if wanted:
        names = ", ".join(f"'{name}'" for name in wanted)
        filter_sql = f"AND job_type IN ({names})"

    rows = records(
        sql_service,
        f"""
        SELECT date_diff('day', DATE '{start}', date) // 7 AS bucket,
               job_type,
               sum(number_of_jobs) AS jobs,
               sum(jobs_hours) AS hours,
               count(DISTINCT date) AS days
        FROM regional_demand_forecast
        WHERE date BETWEEN DATE '{start}' AND DATE '{end}' {filter_sql}
        GROUP BY 1, 2 ORDER BY 1, 2
        """,
        max_rows=400,
    )
    if not rows:
        raise AnalyticsError(
            "The published forecast holds no rows in that window"
            + (f" for {join_plain(wanted)}." if wanted else ".")
        )

    # National correction factor per job type, from the same grading the
    # evaluation reports - so the corrected column here and the corrected
    # jobs/day there can never tell different stories.
    evaluation = evaluate(sql_service)
    factors: dict[str, float] = {}
    for job_type in {str(row["job_type"]) for row in rows}:
        series = [r for r in evaluation["rows"] if r["job_type"] == job_type]
        forecast_total = sum(r["forecast_jobs_per_day"] for r in series)
        actual_total = sum(r["actual_jobs_per_day"] for r in series)
        factors[job_type] = round(actual_total / forecast_total, 4) if forecast_total else 1.0

    by_week: dict[str, dict[str, Any]] = {}
    for row in rows:
        bucket = int(row["bucket"])
        week_start = start + timedelta(days=7 * bucket)
        entry = by_week.setdefault(str(week_start), {
            "week_commencing": str(week_start),
            "week_ending": str(week_start + timedelta(days=6)),
            "days_covered": 0,
            "lines": {},
            "published_jobs": 0,
            "corrected_jobs": 0,
            "published_hours": 0,
            "corrected_hours": 0,
        })
        job_type = str(row["job_type"])
        factor = factors.get(job_type, 1.0)
        published = float(row["jobs"] or 0)
        hours = float(row["hours"] or 0)
        entry["lines"][job_type] = {
            "published_jobs": round(published),
            "corrected_jobs": round(published * factor),
            "published_hours": round(hours),
            "corrected_hours": round(hours * factor),
        }
        entry["days_covered"] = max(entry["days_covered"], int(row["days"]))
        entry["published_jobs"] += round(published)
        entry["corrected_jobs"] += round(published * factor)
        entry["published_hours"] += round(hours)
        entry["corrected_hours"] += round(hours * factor)

    ordered = [by_week[key] for key in sorted(by_week)]
    # A bucket short of seven days is the tail of the forecast, not a fall in
    # demand. Flag it rather than letting it read as a drop.
    for entry in ordered:
        entry["complete"] = entry["days_covered"] >= 7

    complete = [entry for entry in ordered if entry["complete"]]
    line_names = sorted({name for entry in ordered for name in entry["lines"]})

    return {
        "start": str(start),
        "end": str(end),
        "weeks": len(ordered),
        "complete_weeks": len(complete),
        "job_types": line_names,
        "correction_factors": factors,
        "rows": ordered,
        "totals": {
            "published_jobs": sum(entry["published_jobs"] for entry in ordered),
            "corrected_jobs": sum(entry["corrected_jobs"] for entry in ordered),
            "published_hours": sum(entry["published_hours"] for entry in ordered),
            "corrected_hours": sum(entry["corrected_hours"] for entry in ordered),
            "shortfall_jobs": sum(
                entry["corrected_jobs"] - entry["published_jobs"] for entry in ordered
            ),
        },
        "average_week": {
            name: {
                "published": round(
                    sum(e["lines"].get(name, {}).get("published_jobs", 0) for e in complete)
                    / len(complete)
                ) if complete else 0,
                "corrected": round(
                    sum(e["lines"].get(name, {}).get("corrected_jobs", 0) for e in complete)
                    / len(complete)
                ) if complete else 0,
            }
            for name in line_names
        },
        "method": (
            f"Weeks are seven-day buckets counted from {start}, the first day the forecast "
            "covers, so no week is short and no weekly total compares six days with seven. "
            "Published figures are summed straight from regional_demand_forecast across all "
            "nine regions. The corrected column applies the national correction factor for "
            "each job type from the forecast grading "
            + join_plain([f"{name} x{value}" for name, value in sorted(factors.items())])
            + " - it is what the plan should say, and is not in any system yet."
        ),
    }


def render_weekly_outlook(result: dict[str, Any]) -> str:
    totals = result["totals"]
    names = result["job_types"]

    lines = [
        f"**Weekly {join_plain([n.lower() for n in names])} jobs — "
        f"{result['weeks']} weeks from {result['start']}**",
        "",
    ]
    for name in names:
        average = result["average_week"].get(name, {})
        lines.append(
            f"- **{name}: about {num(average.get('published'))} jobs a week** as the plan "
            f"stands, but **{num(average.get('corrected'))} a week** on what demand is actually "
            f"running at (a factor of {result['correction_factors'].get(name, 1.0)})."
        )
    lines += [
        f"- Over the {result['weeks']} weeks that is {num(totals['published_jobs'])} jobs "
        f"planned against {num(totals['corrected_jobs'])} likely — a shortfall of "
        f"**{num(totals['shortfall_jobs'])} jobs** nobody has capacity for.",
        "",
    ]

    headers = ["Week commencing"]
    for name in names:
        headers += [f"{name} planned", f"{name} likely"]
    headers += ["Total planned", "Total likely"]

    table_rows = []
    for entry in result["rows"]:
        row = [entry["week_commencing"] + ("" if entry["complete"] else " *")]
        for name in names:
            line = entry["lines"].get(name, {})
            row += [num(line.get("published_jobs")), num(line.get("corrected_jobs"))]
        row += [num(entry["published_jobs"]), num(entry["corrected_jobs"])]
        table_rows.append(row)
    lines.append(markdown_table(headers, table_rows))

    if result["complete_weeks"] < result["weeks"]:
        lines += ["", "\\* fewer than seven days of forecast fall in this week."]

    chart = chart_block({
        "type": "line",
        "title": f"Weekly {join_plain([n.lower() for n in names])} jobs, planned against likely",
        "x_label": "Week commencing",
        "y_label": "Jobs per week",
        "labels": [entry["week_commencing"] for entry in result["rows"]],
        "series": [
            {"name": "Planned (published forecast)",
             "values": [entry["published_jobs"] for entry in result["rows"]]},
            {"name": "Likely (corrected for the bias)",
             "values": [entry["corrected_jobs"] for entry in result["rows"]]},
        ],
        "note": (
            f"The gap between the lines is {num(totals['shortfall_jobs'])} jobs over "
            f"{result['weeks']} weeks that the plan does not carry."
        ),
        "source": "regional_demand_forecast, graded against the job histories",
    })
    if chart:
        lines += ["", chart]

    lines += ["", f"_Method:_ {result['method']}"]
    return "\n".join(lines)


# -------------------------------------------------------------- what to do next

# Conservative interim target for repair first-time fix. The estate's own Service
# and Installation lines already run near 95%, so the ceiling is an internal
# benchmark rather than an invented one - but closing that whole distance in a
# quarter is not credible, so the plan is costed at a nearer target and the full
# benchmark is quoted as the prize.
INTERIM_FIX_RATE_PCT = 60.0

# Overtime policy ceiling as a share of gross hours. The estate currently runs
# around 6%; this is the level a plan can assume without a policy change.
OVERTIME_CEILING_PCT = 10.0


def recommendations(sql_service: Any) -> dict[str, Any]:
    """Turn the findings into a ranked plan for closing the gap.

    Ordered by what a manager should reach for first, which is not the same as
    what is largest: work you can stop needing beats work you can redeploy, which
    beats work you have to pay more for, which beats hiring. Each option carries
    what it closes and what is still left after it, so the list reads as a plan
    rather than a menu.
    """
    impact = planning_impact(sql_service)
    day_hours = engineer_day_hours(sql_service)
    horizon_days = HORIZON_DAYS

    deficit_hours = sum(
        -skill["balance_after"] for skill in impact["skills"] if skill["balance_after"] < 0
    )
    remaining = float(deficit_hours)
    options: list[dict[str, Any]] = []

    # ---- 1. Stop creating the work: repairs that do not finish first time.
    revisit_skills = [
        skill for skill in impact["skills"]
        if skill.get("revisit") and skill["revisit"]["visits_per_completed_job"] > 1.05
    ]
    for skill in sorted(revisit_skills, key=lambda s: -s["revisit"]["extra_hours"]):
        revisit = skill["revisit"]
        current = float(revisit["first_time_fix_pct"])
        if current >= INTERIM_FIX_RATE_PCT:
            continue
        # Hours scale with 1/fix-rate, so the saving from a given improvement is
        # largest exactly where the rate is worst.
        full_prize = float(revisit["extra_hours"])
        share = (1 / current - 1 / INTERIM_FIX_RATE_PCT) / (1 / current - 1 / 100.0)
        closed = min(full_prize * share, remaining)
        options.append({
            "name": f"Finish more {skill['job_type'].lower()} jobs on the first visit",
            "plain": (
                f"Right now only {current:.0f} out of every 100 "
                f"{skill['job_type'].lower()} visits actually finish the job — the rest have to "
                f"come back, usually because the engineer did not have the part. Every return "
                f"trip is a second appointment for work we were already paid to do once. If we "
                f"get that up to {INTERIM_FIX_RATE_PCT:.0f} out of 100, that work simply stops "
                f"existing. We are not doing it faster; we are not doing it twice."
            ),
            "hours_closed": round(closed),
            "value_note": (
                f"Our own service and installation teams already finish about 95 jobs out of "
                f"100 first time, so this is not a stretch target — it is catching up with the "
                f"rest of the business. Closing that whole distance would remove "
                f"{num(full_prize)} hours."
            ),
            "how": [
                "Find the parts that most often send an engineer back, and stock them on the van.",
                "Ask the contact centre to capture the fault code before the visit is booked, so "
                "the right parts and the right engineer are sent the first time.",
                "Report first-time fix weekly by region and by engineer, so it is visible.",
            ],
            "effort": "medium",
            "lead_time": "one to two quarters",
            "no_new_people": True,
            "evidence": (
                f"{revisit['visits_per_completed_job']:.2f} visits per completed "
                f"{skill['job_type'].lower()} job, from visit_outcome."
            ),
        })
        remaining -= closed

    # ---- 2. Move people who are already qualified.
    cross_skill = _cross_skilled_engineers(sql_service)
    surplus_skills = [s for s in impact["skills"] if s["balance_after"] > 0]
    for surplus in surplus_skills:
        movable = [
            row for row in cross_skill
            if row["primary_skill"] == surplus["job_type"]
            and row["secondary_skill"] in {s["job_type"] for s in impact["skills"]
                                           if s["balance_after"] < 0}
        ]
        engineers = sum(int(row["engineers"]) for row in movable)
        if not engineers or remaining <= 0:
            continue
        capacity = engineers * day_hours * horizon_days
        closed = min(capacity, surplus["balance_after"], remaining)
        destinations = join_plain(sorted({row["secondary_skill"] for row in movable}))
        options.append({
            "name": f"Move already-qualified {surplus['job_type'].lower()} engineers across",
            "plain": (
                f"We have {num(surplus['balance_after'])} hours of "
                f"{surplus['job_type'].lower()} time that nobody is using, while "
                f"{destinations.lower()} work goes unstaffed. {engineers} of those engineers are "
                f"ALREADY trained in {destinations.lower()} — it is their recorded second skill. "
                "They do not need a course, a certificate or a new hire. They need a different "
                "rota."
            ),
            "hours_closed": round(closed),
            "value_note": (
                f"This is the fastest capacity in the plan because it needs no recruitment and "
                f"no training. It is capped by how much {surplus['job_type'].lower()} work still "
                "has to be covered, so it cannot all be moved at once."
            ),
            "how": [
                f"Confirm the {engineers} engineers listed with a second skill are current on it.",
                "Reschedule them region by region, starting where the shortfall is worst.",
                f"Keep enough {surplus['job_type'].lower()} cover for the work that line still has.",
            ],
            "effort": "low",
            "lead_time": "weeks",
            "no_new_people": True,
            "evidence": (
                f"{engineers} engineers in engineer_skill hold {surplus['job_type']} as their "
                f"primary skill and {destinations} as a secondary skill."
            ),
        })
        remaining -= closed

    # ---- 3. Stop wasting the visits we do make.
    aborted = _aborted_visit_hours(sql_service, impact)
    if aborted["hours"] > 0 and remaining > 0:
        closed = min(aborted["hours"] * 0.5, remaining)
        options.append({
            "name": "Halve the visits where nobody is home or the job is cancelled",
            "plain": (
                f"About {aborted['share_pct']:.1f} in every 100 visits are wasted — the customer "
                "cancels, or the engineer arrives and cannot get in. The van still drove there "
                "and the slot is still gone. Cutting that in half hands back capacity we have "
                "already paid for."
            ),
            "hours_closed": round(closed),
            "value_note": (
                f"Worth about {num(aborted['hours'])} hours over the quarter if it were "
                "eliminated entirely; halving it is the realistic version."
            ),
            "how": [
                "Send a confirmation the day before and let the customer move the slot in one tap.",
                "Flag addresses that have failed access before, and agree entry arrangements up front.",
                "Give the engineer a nearby standby job to pick up when a visit falls through.",
            ],
            "effort": "low",
            "lead_time": "weeks",
            "no_new_people": True,
            "evidence": f"{num(aborted['visits'])} aborted visits in visit_outcome.",
        })
        remaining -= closed

    # ---- 4. Pay for more hours from the people we have.
    overtime = _overtime_headroom(sql_service, impact)
    if overtime["hours"] > 0 and remaining > 0:
        closed = min(overtime["hours"], remaining)
        options.append({
            "name": "Use the overtime headroom we already allow",
            "plain": (
                f"Overtime is currently running at about {overtime['current_pct']:.1f}% of paid "
                f"hours. Policy allows up to {OVERTIME_CEILING_PCT:.0f}%. Taking it to the ceiling "
                "in the regions that are short buys real hours quickly — but it costs premium "
                "rates and it burns people out, so it is a bridge, not a fix."
            ),
            "hours_closed": round(closed),
            "value_note": (
                "Use this to cover the gap while the first three options take effect, and plan "
                "to come back off it."
            ),
            "how": [
                "Target the overtime at the regions and skills in deficit, not across the board.",
                "Set an end date for it at the same time you switch it on.",
            ],
            "effort": "low",
            "lead_time": "immediate",
            "no_new_people": True,
            "evidence": (
                f"Overtime is {overtime['current_pct']:.1f}% of gross hours in "
                "regional_capacity_forecast."
            ),
        })
        remaining -= closed

    # ---- 5. Whatever is left is a hiring number.
    residual = max(remaining, 0.0)
    fte = residual / (day_hours * horizon_days) if day_hours and horizon_days else 0.0
    hire_cost = residual * assumption("labour_cost_per_hour_gbp")
    if residual > 0:
        options.append({
            "name": "Recruit for what is genuinely left",
            "plain": (
                f"After everything above, about {num(residual)} hours of work still has nobody "
                f"to do it — roughly {num(fte, 1)} full-time engineers for the quarter. This is "
                "the only part of the gap that actually needs recruitment, and it is much "
                "smaller than the headline shortfall. Doing this first, before the other four, "
                "would mean hiring people to do work we should not be creating."
            ),
            "hours_closed": round(residual),
            "value_note": (
                f"About {gbp(hire_cost)} of labour at the assumed rate. Contract or agency cover "
                "may be the right answer for a gap this shape rather than permanent heads."
            ),
            "how": [
                "Size the requirement AFTER the first four options are underway, not before.",
                "Split it by region and skill so recruitment goes where the shortfall actually is.",
            ],
            "effort": "high",
            "lead_time": "one to two quarters to productive",
            "no_new_people": False,
            "evidence": "Residual after the options above.",
        })

    for index, option in enumerate(options, start=1):
        option["rank"] = index
    running = float(deficit_hours)
    for option in options:
        running -= option["hours_closed"]
        option["gap_remaining_after"] = round(max(running, 0))

    no_hire_closed = sum(o["hours_closed"] for o in options if o.get("no_new_people"))
    return {
        "gap_hours": round(deficit_hours),
        "gap_fte": round(deficit_hours / (day_hours * horizon_days), 1)
                   if day_hours and horizon_days else 0.0,
        # What hiring for the whole gap would cost, so the "do the cheap things
        # first" saving can be stated as a number rather than asserted.
        "gap_cost_gbp": round(deficit_hours * assumption("labour_cost_per_hour_gbp")),
        "options": options,
        "closed_without_hiring": round(no_hire_closed),
        "closed_without_hiring_pct": (
            round(no_hire_closed / deficit_hours * 100.0, 1) if deficit_hours else 0.0
        ),
        "residual_hours": round(residual),
        "residual_fte": round(fte, 1),
        "residual_cost_gbp": round(hire_cost),
        "horizon": impact["horizon"],
        "assumptions": declared("labour_cost_per_hour_gbp"),
        "method": (
            "Options are ordered by what a manager should reach for first: stop creating the "
            "work, then move people who are already qualified, then stop wasting visits, then "
            "buy hours with overtime, and only then recruit. Each option is capped by what is "
            "genuinely available and by the gap still open when it is reached, so the hours do "
            "not double-count."
        ),
    }


def _cross_skilled_engineers(sql_service: Any) -> list[dict[str, Any]]:
    """Engineers who already hold a second skill, so they can move without training."""

    def build() -> list[dict[str, Any]]:
        return records(
            sql_service,
            """
            SELECT primary_skill, secondary_skill, count(*) AS engineers
            FROM engineer_skill
            WHERE secondary_skill IS NOT NULL
              AND secondary_skill NOT IN ('None', '')
              AND secondary_skill <> primary_skill
            GROUP BY 1, 2 ORDER BY 3 DESC
            """,
            max_rows=40,
        )

    return cached("demand:cross_skill", build)


def _aborted_visit_hours(sql_service: Any, impact: dict[str, Any]) -> dict[str, Any]:
    """Hours consumed by visits that achieved nothing, over the horizon."""
    try:
        from app.agent import pricing as pricing_engine

        serve_lines = pricing_engine.cost_to_serve(sql_service)["lines"]
    except Exception:  # noqa: BLE001
        return {"hours": 0.0, "visits": 0, "share_pct": 0.0}

    total_visits = sum(float(row["visits_total"]) for row in serve_lines)
    aborted = sum(float(row["visits_aborted"]) for row in serve_lines)
    if not total_visits:
        return {"hours": 0.0, "visits": 0, "share_pct": 0.0}

    share = aborted / total_visits
    horizon_hours = sum(skill["true_hours"] for skill in impact["skills"])
    return {
        "hours": horizon_hours * share,
        "visits": round(aborted),
        "share_pct": round(share * 100.0, 1),
    }


def _overtime_headroom(sql_service: Any, impact: dict[str, Any]) -> dict[str, Any]:
    """Extra hours available by taking overtime up to the policy ceiling."""

    def build() -> dict[str, Any]:
        rows = records(
            sql_service,
            """
            SELECT round(sum(gross_hours)) AS gross_hours,
                   round(sum(overtime)) AS overtime_hours
            FROM regional_capacity_forecast
            """,
            max_rows=1,
        )
        if not rows or not rows[0].get("gross_hours"):
            return {"hours": 0.0, "current_pct": 0.0}
        gross = float(rows[0]["gross_hours"])
        current = float(rows[0]["overtime_hours"] or 0)
        current_pct = current / gross * 100.0
        headroom_pct = max(OVERTIME_CEILING_PCT - current_pct, 0.0)
        return {"hours": gross * headroom_pct / 100.0, "current_pct": round(current_pct, 1)}

    return cached("demand:overtime_headroom", build)


def render_recommendations(result: dict[str, Any]) -> str:
    if not result["options"]:
        return (
            "No shortfall to close: every skill has enough capacity for the work the corrected "
            "forecast implies."
        )

    lines = [
        "**How to close the gap — in the order to do it**",
        "",
        f"We are short about **{num(result['gap_hours'])} hours of engineer time** over the next "
        f"{result['horizon']['weeks']} weeks — roughly {num(result['gap_fte'], 1)} full-time "
        "engineers. The important point is that **most of it does not need new people**: "
        f"the first steps below cover {num(result['closed_without_hiring'])} hours "
        f"({num(result['closed_without_hiring_pct'], 1)}% of the gap) without a single hire.",
        "",
    ]

    for option in result["options"]:
        lines += [
            f"**{option['rank']}. {option['name']}** — closes about "
            f"{num(option['hours_closed'])} hours"
            + (f", leaving {num(option['gap_remaining_after'])} still open."
               if option["gap_remaining_after"] else ", which closes the gap."),
            "",
            option["plain"],
            "",
            f"_{option['value_note']}_",
            "",
            "What this takes:",
        ]
        for step in option["how"]:
            lines.append(f"- {step}")
        lines += [
            "",
            f"Effort: {option['effort']} · Time to effect: {option['lead_time']} · "
            f"Evidence: {option['evidence']}",
            "",
        ]

    chart = chart_block({
        "type": "bar",
        "title": "What each step closes, in the order to do it",
        "subtitle": f"Shortfall of {num(result['gap_hours'])} engineer-hours",
        "y_label": "Engineer-hours closed",
        "labels": [f"{o['rank']}. {o['name'][:34]}" for o in result["options"]],
        "series": [{
            "name": "Hours closed",
            "values": [o["hours_closed"] for o in result["options"]],
        }],
        "note": (
            f"{num(result['closed_without_hiring_pct'], 0)}% of the shortfall closes without "
            "hiring anyone; recruitment is the last bar, not the first."
        ),
        "source": "visit_outcome, engineer_skill and regional_capacity_forecast",
    })
    if chart:
        lines += [chart, ""]

    lines += [
        f"**If we do nothing**, the work does not disappear — it turns into missed appointments, "
        f"longer waits and overtime we did not plan. The shortfall is "
        f"{num(result['gap_hours'])} hours; hiring our way out of all of it would cost about "
        f"{gbp(result['gap_hours'] * assumption('labour_cost_per_hour_gbp'))} in labour, against "
        f"{gbp(result['residual_cost_gbp'])} if we do the cheaper things first.",
        "",
        f"_Method:_ {result['method']}",
    ]
    return "\n".join(lines)


# ----------------------------------------------------------------------- gaps


def gaps(sql_service: Any) -> dict[str, Any]:
    """Where the forecast is absent rather than wrong.

    Three kinds of hole are checked: a job type the business staffs but does not
    forecast, a region missing from a job type it should cover, and calendar days
    with no forecast row inside the horizon.
    """
    window = _forecast_window(sql_service)
    day_hours = engineer_day_hours(sql_service)

    forecast_pairs = {
        (row["job_type"], row["region"]) for row in forecast_level(sql_service)
    }
    forecast_types = {job for job, _ in forecast_pairs}
    capacity_rows = capacity_by_skill(sql_service)
    run_rate = {(row["job_type"], row["region"]): row for row in actual_run_rate(sql_service)}

    missing_types: list[dict[str, Any]] = []
    for job in sorted({row["job_type"] for row in capacity_rows}):
        if job in forecast_types:
            continue
        provisioned = sum(
            float(row["available_hours"] or 0) for row in capacity_rows if row["job_type"] == job
        )
        observed_per_day = sum(
            float(row["jobs_per_day"] or 0)
            for (job_type, _), row in run_rate.items()
            if job_type == job
        )
        implied_hours = observed_per_day * FALLBACK_HOURS_PER_JOB * HORIZON_DAYS
        missing_types.append({
            "job_type": job,
            "regions_staffed": len({row["region"] for row in capacity_rows if row["job_type"] == job}),
            "capacity_hours_horizon": round(provisioned),
            "observed_jobs_per_day": round(observed_per_day, 1),
            "implied_demand_hours": round(implied_hours),
            "unmatched_hours": round(provisioned - implied_hours),
            "utilisation_pct": round(implied_hours / provisioned * 100.0, 1) if provisioned else None,
            "engineer_days_idle": round((provisioned - implied_hours) / day_hours) if day_hours else 0,
        })

    missing_regions: list[dict[str, Any]] = []
    for job in sorted(forecast_types):
        covered = {region for job_type, region in forecast_pairs if job_type == job}
        staffed = {row["region"] for row in capacity_rows if row["job_type"] == job}
        for region in sorted(staffed - covered):
            missing_regions.append({"job_type": job, "region": region})

    expected_days = (window["end"] - window["start"]).days + 1
    coverage = records(
        sql_service,
        """
        SELECT job_type, count(DISTINCT date) AS days_covered,
               count(DISTINCT region) AS regions
        FROM regional_demand_forecast GROUP BY 1 ORDER BY 1
        """,
        max_rows=50,
    )
    calendar_holes = [
        {
            "job_type": row["job_type"],
            "days_covered": int(row["days_covered"]),
            "days_expected": expected_days,
            "missing_days": expected_days - int(row["days_covered"]),
        }
        for row in coverage
        if int(row["days_covered"]) < expected_days
    ]

    return {
        "forecast_window": {"start": str(window["start"]), "end": str(window["end"])},
        "missing_job_types": missing_types,
        "missing_regions": missing_regions,
        "calendar_holes": calendar_holes,
        "has_gaps": bool(missing_types or missing_regions or calendar_holes),
        "assumptions": declared("labour_cost_per_hour_gbp"),
    }


def render_gaps(result: dict[str, Any]) -> str:
    if not result["has_gaps"]:
        return (
            "No forecast gaps found: every job type the estate staffs is forecast, "
            "in every region it staffs, for every day of the horizon."
        )

    lines = ["**Forecast coverage gaps**", ""]
    missing = result["missing_job_types"]
    if missing:
        note = (
            "The gap between the bars is capacity paid for against demand nobody forecast — "
            "invisible to any accuracy measure, because there is no forecast to be wrong."
        )
        source = (
            "regional_capacity_forecast vs regional_demand_forecast and the job histories"
        )
        # A chart needs at least two bars. With several missing job types the
        # comparison runs across them; with one, it runs between the two measures.
        if len(missing) > 1:
            spec = {
                "type": "bar",
                "labels": [item["job_type"] for item in missing],
                "series": [
                    {"name": "Hours staffed",
                     "values": [item["capacity_hours_horizon"] for item in missing]},
                    {"name": "Hours the real work needs",
                     "values": [item["implied_demand_hours"] for item in missing]},
                ],
            }
        else:
            item = missing[0]
            spec = {
                "type": "bar",
                "labels": ["Hours staffed", "Hours the real work needs"],
                "series": [{
                    "name": f"{item['job_type']} engineer-hours",
                    "values": [item["capacity_hours_horizon"], item["implied_demand_hours"]],
                }],
                "highlight": "Hours the real work needs",
            }
        chart = chart_block({
            **spec,
            "title": "Staffed hours against the work that is actually there",
            "subtitle": "Job types with engineers rostered but no forecast at all",
            "y_label": "Engineer-hours over the horizon",
            "note": note,
            "source": source,
        })
        if chart:
            lines += [chart, ""]

    for item in result["missing_job_types"]:
        lines += [
            f"- **{item['job_type']} demand is not forecast at all.** The capacity plan "
            f"provisions {num(item['capacity_hours_horizon'])} engineer-hours of "
            f"{item['job_type']} skill across {item['regions_staffed']} regions over "
            f"{HORIZON_WEEKS} weeks, against no forecast demand line. The observed run-rate "
            f"is {num(item['observed_jobs_per_day'], 1)} jobs/day nationally, which implies "
            f"about {num(item['implied_demand_hours'])} hours of real demand — "
            f"{num(item['utilisation_pct'], 1)}% utilisation, leaving "
            f"{num(item['engineer_days_idle'])} engineer-days unmatched.",
        ]
    for item in result["missing_regions"]:
        lines.append(
            f"- **{item['job_type']} has no forecast for {item['region']}**, although the "
            "region is staffed for that skill."
        )
    for item in result["calendar_holes"]:
        lines.append(
            f"- **{item['job_type']}** covers {item['days_covered']} of "
            f"{item['days_expected']} horizon days ({item['missing_days']} missing)."
        )
    lines += [
        "",
        "Call `generate_demand_forecast` for any missing job type to build the numbers "
        "from history and put them in front of a human for approval.",
    ]
    return "\n".join(lines)


# ------------------------------------------------------------ forecast builder


def _seasonal_factors(sql_service: Any, job_type: str) -> dict[int, float]:
    """Month-of-year index for a job type, normalised to 1.0 on the mean.

    Built from complete months only: a partial month reads as a collapse in
    demand and would drag a generated forecast down with it.
    """
    source, column, extra = _ACTUAL_SOURCES[job_type]
    alias = source[0]

    def build() -> dict[int, float]:
        cutoff = actuals_cutoff(sql_service)
        rows = records(
            sql_service,
            f"""
            WITH daily AS (
                SELECT {alias}.{column} AS d, count(*) AS jobs
                FROM {source} {alias}
                WHERE {alias}.{column} IS NOT NULL AND {alias}.{column} <= DATE '{cutoff}' {extra}
                GROUP BY 1
            )
            SELECT month(d) AS month, round(avg(jobs), 2) AS jobs_per_day, count(*) AS days
            FROM daily GROUP BY 1 ORDER BY 1
            """,
            max_rows=20,
        )
        # A month observed on fewer than 20 days is a partial month.
        usable = {int(r["month"]): float(r["jobs_per_day"]) for r in rows if int(r["days"]) >= 20}
        if not usable:
            return {}
        mean = sum(usable.values()) / len(usable)
        if mean <= 0:
            return {}
        return {month: round(value / mean, 4) for month, value in usable.items()}

    return cached(f"demand:season:{job_type}", build)


def _trend_per_year(sql_service: Any, job_type: str) -> float:
    """Year-on-year change in jobs per day, as a fraction (0.011 = +1.1%)."""
    source, column, extra = _ACTUAL_SOURCES[job_type]
    alias = source[0]

    def build() -> float:
        cutoff = actuals_cutoff(sql_service)
        rows = records(
            sql_service,
            f"""
            SELECT year({alias}.{column}) AS yr,
                   count(*) * 1.0 / NULLIF(count(DISTINCT {alias}.{column}), 0) AS per_day
            FROM {source} {alias}
            WHERE {alias}.{column} IS NOT NULL AND {alias}.{column} <= DATE '{cutoff}' {extra}
            GROUP BY 1 ORDER BY 1
            """,
            max_rows=20,
        )
        usable = [r for r in rows if r["per_day"]]
        if len(usable) < 2:
            return 0.0
        first, last = float(usable[0]["per_day"]), float(usable[-1]["per_day"])
        years = max(int(usable[-1]["yr"]) - int(usable[0]["yr"]), 1)
        if first <= 0:
            return 0.0
        return round(((last / first) ** (1.0 / years)) - 1.0, 4)

    return cached(f"demand:trend:{job_type}", build)


def _daily_volatility(sql_service: Any, job_type: str) -> float:
    """Coefficient of variation of daily national volume, for the uncertainty band."""
    source, column, extra = _ACTUAL_SOURCES[job_type]
    alias = source[0]

    def build() -> float:
        cutoff = actuals_cutoff(sql_service)
        start = cutoff - timedelta(days=180)
        row = records(
            sql_service,
            f"""
            WITH daily AS (
                SELECT {alias}.{column} AS d, count(*) AS jobs
                FROM {source} {alias}
                WHERE {alias}.{column} BETWEEN DATE '{start}' AND DATE '{cutoff}' {extra}
                GROUP BY 1
            )
            SELECT avg(jobs) AS mean_jobs, stddev_samp(jobs) AS sd FROM daily
            """,
            max_rows=1,
        )
        if not row or not row[0].get("mean_jobs"):
            return 0.0
        mean = float(row[0]["mean_jobs"])
        sd = float(row[0].get("sd") or 0)
        return round(sd / mean, 4) if mean > 0 else 0.0

    return cached(f"demand:volatility:{job_type}", build)


def build_forecast(sql_service: Any, job_type: str, weeks: int = HORIZON_WEEKS) -> dict[str, Any]:
    """Create a weekly demand forecast for a job type, from history.

    Method is deliberately transparent rather than clever: trailing run-rate per
    region, multiplied by a month-of-year seasonal index and a year-on-year trend
    factor. A planner can reproduce it in a spreadsheet, which is what makes it
    approvable.
    """
    canonical = _canonical_job_type(job_type)
    weeks = max(1, min(int(weeks or HORIZON_WEEKS), 52))
    window = _forecast_window(sql_service)
    start = window["start"]

    base = {
        row["region"]: float(row["jobs_per_day"] or 0)
        for row in actual_run_rate(sql_service)
        if row["job_type"] == canonical
    }
    if not base:
        raise AnalyticsError(
            f"No actuals for job type '{canonical}' in the trailing {TRAILING_DAYS} days, "
            "so a forecast cannot be built from history."
        )

    hours_per_job, hours_source = hours_per_job_ratio(sql_service, canonical)
    seasonal = _seasonal_factors(sql_service, canonical)
    trend = _trend_per_year(sql_service, canonical)
    volatility = _daily_volatility(sql_service, canonical)
    day_hours = engineer_day_hours(sql_service)

    weekly: list[dict[str, Any]] = []
    for index in range(weeks):
        week_start = start + timedelta(days=7 * index)
        factor_season = seasonal.get(week_start.month, 1.0)
        factor_trend = (1.0 + trend) ** ((7 * index + 3.5) / 365.0)
        for region, per_day in sorted(base.items()):
            jobs = per_day * factor_season * factor_trend * 7.0
            weekly.append({
                "week_commencing": str(week_start),
                "region": region,
                "job_type": canonical,
                "jobs": round(jobs),
                "jobs_hours": round(jobs * hours_per_job),
                "seasonal_factor": round(factor_season, 3),
                "trend_factor": round(factor_trend, 4),
                "low": round(jobs * (1 - volatility)),
                "high": round(jobs * (1 + volatility)),
            })

    national = [
        {
            "week_commencing": week,
            "jobs": sum(r["jobs"] for r in weekly if r["week_commencing"] == week),
            "jobs_hours": sum(r["jobs_hours"] for r in weekly if r["week_commencing"] == week),
            "low": sum(r["low"] for r in weekly if r["week_commencing"] == week),
            "high": sum(r["high"] for r in weekly if r["week_commencing"] == week),
        }
        for week in sorted({r["week_commencing"] for r in weekly})
    ]

    total_hours = sum(row["jobs_hours"] for row in weekly)
    available = sum(
        float(row["available_hours"] or 0)
        for row in capacity_by_skill(sql_service)
        if row["job_type"] == canonical
    )

    regional = [
        {
            "region": region,
            "jobs_per_day_now": round(per_day, 1),
            "jobs": sum(r["jobs"] for r in weekly if r["region"] == region),
            "jobs_hours": sum(r["jobs_hours"] for r in weekly if r["region"] == region),
        }
        for region, per_day in sorted(base.items())
    ]

    assumption_keys = ["labour_cost_per_hour_gbp"]
    return {
        "job_type": canonical,
        "weeks": weeks,
        "start": str(start),
        "end": str(start + timedelta(days=7 * weeks - 1)),
        "weekly": weekly,
        "national_weekly": national,
        "regional_totals": regional,
        "totals": {
            "jobs": sum(row["jobs"] for row in weekly),
            "jobs_hours": total_hours,
            "engineer_days": round(total_hours / day_hours) if day_hours else 0,
            "available_hours": round(available),
            "balance": round(available - total_hours),
            "utilisation_pct": round(total_hours / available * 100.0, 1) if available else None,
        },
        "parameters": {
            "base_window_days": TRAILING_DAYS,
            "hours_per_job": hours_per_job,
            "hours_per_job_source": hours_source,
            "trend_per_year_pct": round(trend * 100.0, 2),
            "volatility_pct": round(volatility * 100.0, 1),
            "seasonal_factors": seasonal,
        },
        "assumptions": declared(*assumption_keys),
        "method": (
            f"Trailing {TRAILING_DAYS}-day run-rate per region × month-of-year seasonal index × "
            f"year-on-year trend of {signed_pct(trend * 100.0, 2)}. Hours converted at "
            f"{hours_per_job} h/job ({hours_source}). The low/high band is ±{round(volatility * 100, 1)}%, "
            "the observed coefficient of variation of daily volume over the last 180 days."
        ),
    }


def _canonical_job_type(job_type: str) -> str:
    wanted = str(job_type or "").strip().casefold()
    for candidate in JOB_TYPES:
        if candidate.casefold() == wanted or candidate.casefold().startswith(wanted[:5] or "~"):
            return candidate
    raise AnalyticsError(
        f"Unknown job type '{job_type}'. Valid job types: {', '.join(JOB_TYPES)}."
    )


def hours_per_job_ratio(sql_service: Any, job_type: str) -> tuple[float, str]:
    """Hours per job for a job type, preferring the estate's own forecast ratio."""
    for row in forecast_level(sql_service):
        if row["job_type"] == job_type and row.get("hours_per_job"):
            return round(float(row["hours_per_job"]), 2), "from the published forecast for this job type"

    ratios = [
        float(row["hours_per_job"])
        for row in forecast_level(sql_service)
        if row.get("hours_per_job")
    ]
    if ratios:
        average = round(sum(ratios) / len(ratios), 2)
        return average, (
            "no published forecast exists for this job type, so the average ratio across the "
            "job types that do have one is applied - verify it against real job durations"
        )
    return FALLBACK_HOURS_PER_JOB, "default assumption - no forecast ratio available anywhere"


def render_forecast(result: dict[str, Any], limit: int = 13) -> str:
    totals = result["totals"]
    lines = [
        f"**Generated {result['job_type']} demand forecast** — {result['weeks']} weeks from "
        f"{result['start']}, {len(result['regional_totals'])} regions.",
        "",
        f"- Total demand: **{num(totals['jobs'])} jobs / {num(totals['jobs_hours'])} engineer-hours** "
        f"(~{num(totals['engineer_days'])} engineer-days).",
    ]
    if totals.get("available_hours"):
        lines.append(
            f"- Against {num(totals['available_hours'])} provisioned hours for this skill: "
            f"balance {num(totals['balance'])} hours, "
            f"**{num(totals['utilisation_pct'], 1)}% utilisation**."
        )
    lines.append("")

    lines.append(markdown_table(
        ["Week commencing", "Jobs", "Hours", "Low", "High"],
        [
            [row["week_commencing"], num(row["jobs"]), num(row["jobs_hours"]),
             num(row["low"]), num(row["high"])]
            for row in result["national_weekly"][:limit]
        ],
    ))
    chart = chart_block({
        "type": "line",
        "title": f"Forecast {result['job_type'].lower()} jobs per week",
        "x_label": "Week commencing",
        "y_label": "Jobs",
        "labels": [row["week_commencing"] for row in result["national_weekly"]],
        "series": [{
            "name": "Forecast jobs",
            "values": [row["jobs"] for row in result["national_weekly"]],
        }],
        "note": result["parameters"].get("hours_per_job_source", ""),
        "source": "built from the job histories",
    })
    if chart:
        lines += ["", chart]

    lines += ["", "Regional split (whole horizon):", ""]
    lines.append(markdown_table(
        ["Region", "Jobs/day now", "Forecast jobs", "Forecast hours"],
        [
            [row["region"], num(row["jobs_per_day_now"], 1), num(row["jobs"]), num(row["jobs_hours"])]
            for row in result["regional_totals"]
        ],
    ))
    lines += ["", f"_Method:_ {result['method']}"]
    return "\n".join(lines)


# --------------------------------------------------------------------- drivers


def drivers(sql_service: Any, job_type: str = "") -> dict[str, Any]:
    """Rank what actually moves demand, including what demonstrably does not.

    Each factor reports a spread: how far apart the highest and lowest bands of
    that factor are, as a percentage of the lower. Reporting the nil results is
    the point - it stops a planner spending a quarter building a weather model
    for a one-percent effect.
    """

    def build() -> dict[str, Any]:
        cutoff = actuals_cutoff(sql_service)
        factors: list[dict[str, Any]] = []

        def spread(values: list[float]) -> float:
            usable = [v for v in values if v and v > 0]
            if len(usable) < 2:
                return 0.0
            return round((max(usable) - min(usable)) / min(usable) * 100.0, 1)

        # 1. Installed base per region - the reason regional demand differs at all.
        base_rows = records(
            sql_service,
            "SELECT region, count(*) AS customers FROM customer_holdings GROUP BY 1 ORDER BY 2 DESC",
            max_rows=50,
        )
        base_spread = spread([float(r["customers"]) for r in base_rows])
        factors.append({
            "factor": "Regional installed base",
            "measure": f"{num(base_rows[0]['customers'])} customers in "
                       f"{base_rows[0]['region']} vs {num(base_rows[-1]['customers'])} in "
                       f"{base_rows[-1]['region']}",
            "effect_pct": base_spread,
            "dataset": "customer_holdings",
            "reading": (
                "Region-level demand scales with the installed base. The base is evenly "
                "distributed here, so regional demand should be too - a forecast that "
                "differs materially by region needs a reason that is not the base."
            ),
        })

        # 2. Underlying trend.
        trend_service = _trend_per_year(sql_service, "Service") * 100.0
        trend_repair = _trend_per_year(sql_service, "Repair") * 100.0
        factors.append({
            "factor": "Underlying growth trend",
            "measure": f"Service {signed_pct(trend_service, 2)}/yr, Repair "
                       f"{signed_pct(trend_repair, 2)}/yr in jobs per day",
            "effect_pct": round(max(abs(trend_service), abs(trend_repair)), 1),
            "dataset": "service_history, repair_history",
            "reading": (
                "Small but persistent, and it compounds across a 13-week horizon. A forecast "
                "held flat at last year's level drifts low by roughly this much per year."
            ),
        })

        # 3. First-visit failure - the largest real driver of *hours*, not jobs.
        outcome_rows = records(
            sql_service,
            """
            SELECT visit_status, count(*) AS visits FROM visit_outcome GROUP BY 1 ORDER BY 2 DESC
            """,
            max_rows=20,
        )
        total_visits = sum(float(r["visits"]) for r in outcome_rows) or 1.0
        by_status = {str(r["visit_status"]): float(r["visits"]) for r in outcome_rows}
        revisit = by_status.get("Parts Required", 0.0)
        lost = sum(
            value for status, value in by_status.items()
            if status.startswith("Cancelled") or status == "No Access"
        )
        factors.append({
            "factor": "First-visit failure and revisits",
            "measure": f"{num(revisit / total_visits * 100, 1)}% of visits end 'Parts Required' "
                       f"and {num(lost / total_visits * 100, 1)}% are cancelled or no-access",
            "effect_pct": round(revisit / total_visits * 100.0, 1),
            "dataset": "visit_outcome",
            "reading": (
                "This is the biggest measured effect on hours. A forecast built on job counts "
                "understates the visits required by the revisit rate: every 'Parts Required' "
                "job consumes a second appointment slot the demand line never asked for."
            ),
        })

        # 4. Repair severity mix. Scored on how much the mix has DRIFTED, not on
        #    how concentrated it is - a stable mix, however skewed, is already
        #    priced into the run-rate and creates no forecast error.
        severity_rows = records(
            sql_service,
            f"""
            SELECT CASE
                       WHEN appointment_date BETWEEN DATE '{cutoff}' - INTERVAL {TRAILING_DAYS - 1} DAY
                                                 AND DATE '{cutoff}' THEN 'recent'
                       WHEN appointment_date BETWEEN DATE '{cutoff}' - INTERVAL {364 + TRAILING_DAYS - 1} DAY
                                                 AND DATE '{cutoff}' - INTERVAL 364 DAY THEN 'prior'
                   END AS period,
                   severity, count(*) AS jobs
            FROM appointment_schedule
            WHERE job_category = 'Repair'
            GROUP BY 1, 2 HAVING period IS NOT NULL ORDER BY 1, 3 DESC
            """,
            max_rows=40,
        )

        def critical_share(period: str) -> float:
            rows_for = [r for r in severity_rows if str(r["period"]) == period]
            total = sum(float(r["jobs"]) for r in rows_for)
            if total <= 0:
                return 0.0
            critical = sum(
                float(r["jobs"]) for r in rows_for if str(r["severity"]) == "Critical"
            )
            return critical / total * 100.0

        recent_share = critical_share("recent")
        prior_share = critical_share("prior")
        drift_pct = (
            round(abs(recent_share - prior_share) / prior_share * 100.0, 1) if prior_share else 0.0
        )
        factors.append({
            "factor": "Repair severity mix drift",
            "measure": f"Critical repairs {num(recent_share, 1)}% of the mix now vs "
                       f"{num(prior_share, 1)}% a year ago",
            "effect_pct": drift_pct,
            "dataset": "appointment_schedule",
            "reading": (
                f"Severity governs how long a repair takes and how fast it must be attended, so "
                f"a drifting mix changes the hours needed without changing the job count. The "
                f"mix has moved {drift_pct}% year on year"
                + (
                    " - stable enough that the run-rate already carries it."
                    if drift_pct < MATERIAL_BIAS_PCT
                    else " - enough that a jobs-only forecast will miss the hours effect."
                )
            ),
        })

        # 5. Weather. Tested because everyone expects it to matter.
        weather_rows = records(
            sql_service,
            """
            WITH r AS (SELECT repair_date AS d, count(*) AS repairs FROM repair_history GROUP BY 1),
                 w AS (SELECT date AS d, avg(temperature) AS temp FROM weather GROUP BY 1)
            SELECT CASE WHEN temp < 3 THEN 'Below 3C'
                        WHEN temp < 8 THEN '3-8C'
                        WHEN temp < 14 THEN '8-14C' ELSE 'Above 14C' END AS band,
                   count(*) AS days, round(avg(repairs)) AS repairs_per_day
            FROM r JOIN w USING (d) GROUP BY 1 ORDER BY 3 DESC
            """,
            max_rows=10,
        )
        weather_spread = spread([float(r["repairs_per_day"]) for r in weather_rows])
        factors.append({
            "factor": "Temperature",
            "measure": " · ".join(
                f"{r['band']}: {num(r['repairs_per_day'])}/day" for r in weather_rows
            ),
            "effect_pct": weather_spread,
            "dataset": "weather, repair_history",
            "reading": (
                "Tested and immaterial in this estate: the coldest and warmest bands differ by "
                f"{weather_spread}%. Do not build a weather adjustment into the forecast on "
                "this evidence - a cold-snap contingency is a capacity question, not a "
                "baseline demand one."
            ) if weather_spread < 5 else (
                f"Material: repair volume varies {weather_spread}% across temperature bands. "
                "The forecast should carry a weather term."
            ),
        })

        # 6. Seasonality.
        season_rows = records(
            sql_service,
            f"""
            WITH a AS (
                SELECT service_date AS d FROM service_history WHERE service_date <= DATE '{cutoff}'
                UNION ALL
                SELECT repair_date FROM repair_history WHERE repair_date <= DATE '{cutoff}'
            ), daily AS (SELECT d, count(*) AS jobs FROM a GROUP BY 1)
            SELECT month(d) AS month, round(avg(jobs)) AS jobs_per_day, count(*) AS days
            FROM daily GROUP BY 1 HAVING count(*) >= 20 ORDER BY 2 DESC
            """,
            max_rows=20,
        )
        season_spread = spread([float(r["jobs_per_day"]) for r in season_rows])
        factors.append({
            "factor": "Month-of-year seasonality",
            "measure": (
                f"Peak month {int(season_rows[0]['month'])} at {num(season_rows[0]['jobs_per_day'])}/day "
                f"vs trough month {int(season_rows[-1]['month'])} at "
                f"{num(season_rows[-1]['jobs_per_day'])}/day"
            ) if season_rows else "not computable",
            "effect_pct": season_spread,
            "dataset": "service_history, repair_history",
            "reading": (
                f"A {season_spread}% peak-to-trough spread. "
                + ("Small enough that a flat forecast is defensible, but it is free to apply."
                   if season_spread < 10 else
                   "Large enough that a flat forecast will be wrong in both the peak and the trough.")
            ),
        })

        # 7. Day of week.
        weekday_rows = records(
            sql_service,
            f"""
            WITH a AS (
                SELECT service_date AS d FROM service_history WHERE service_date <= DATE '{cutoff}'
                UNION ALL
                SELECT repair_date FROM repair_history WHERE repair_date <= DATE '{cutoff}'
            )
            SELECT dayname(d) AS day, round(count(*) * 1.0 / count(DISTINCT d)) AS jobs_per_day
            FROM a GROUP BY 1 ORDER BY 2 DESC
            """,
            max_rows=10,
        )
        weekday_spread = spread([float(r["jobs_per_day"]) for r in weekday_rows])
        factors.append({
            "factor": "Day of week",
            "measure": (
                f"{weekday_rows[0]['day']} {num(weekday_rows[0]['jobs_per_day'])}/day vs "
                f"{weekday_rows[-1]['day']} {num(weekday_rows[-1]['jobs_per_day'])}/day"
            ) if weekday_rows else "not computable",
            "effect_pct": weekday_spread,
            "dataset": "service_history, repair_history",
            "reading": (
                f"A {weekday_spread}% spread across the week, and the published forecast is "
                "already flat across weekdays. No correction needed here."
            ) if weekday_spread < 5 else (
                f"A {weekday_spread}% spread. The forecast is flat across weekdays and should "
                "not be."
            ),
        })

        # 8. Asset age. Tested because it is the standard reliability assumption.
        age_rows = records(
            sql_service,
            f"""
            WITH r AS (SELECT customer_id, count(*) AS repairs FROM repair_history GROUP BY 1)
            SELECT CASE WHEN date_diff('year', b.installation_date, DATE '{cutoff}') < 5 THEN 'Under 5y'
                        WHEN date_diff('year', b.installation_date, DATE '{cutoff}') < 10 THEN '5-10y'
                        WHEN date_diff('year', b.installation_date, DATE '{cutoff}') < 15 THEN '10-15y'
                        ELSE '15y+' END AS age_band,
                   count(*) AS boilers,
                   round(sum(COALESCE(r.repairs, 0)) * 1.0 / count(*), 3) AS repairs_per_boiler
            FROM boiler_master b LEFT JOIN r USING (customer_id)
            GROUP BY 1 ORDER BY 3 DESC
            """,
            max_rows=10,
        )
        age_spread = spread([float(r["repairs_per_boiler"]) for r in age_rows])
        factors.append({
            "factor": "Boiler age",
            "measure": " · ".join(
                f"{r['age_band']}: {num(r['repairs_per_boiler'], 3)} repairs/boiler" for r in age_rows
            ),
            "effect_pct": age_spread,
            "dataset": "boiler_master, repair_history",
            "reading": (
                f"Only a {age_spread}% difference between age bands - repair demand in this "
                "estate does not rise with asset age the way it normally would. Worth "
                "confirming the installation dates are real before relying on that."
            ) if age_spread < 10 else (
                f"Repair rate differs {age_spread}% across age bands - ageing stock is a "
                "genuine driver and the forecast should track it."
            ),
        })

        factors.sort(key=lambda item: item["effect_pct"], reverse=True)
        material = [f for f in factors if f["effect_pct"] >= MATERIAL_BIAS_PCT]
        immaterial = [f for f in factors if f["effect_pct"] < MATERIAL_BIAS_PCT]
        return {
            "job_type": job_type or "all",
            "as_of": str(cutoff),
            "factors": factors,
            "material": material,
            "immaterial": immaterial,
            "materiality_threshold_pct": MATERIAL_BIAS_PCT,
        }

    return cached(f"demand:drivers:{job_type or 'all'}", build)


def render_drivers(result: dict[str, Any]) -> str:
    lines = [
        f"**What actually drives demand** (measured to {result['as_of']}, "
        f"materiality threshold {result['materiality_threshold_pct']:.0f}%)",
        "",
        markdown_table(
            ["Factor", "Measured effect", "Evidence", "Datasets"],
            [
                [
                    factor["factor"],
                    f"{factor['effect_pct']}%",
                    factor["measure"],
                    factor["dataset"],
                ]
                for factor in result["factors"]
            ],
        ),
        "",
    ]
    chart = chart_block({
        "type": "hbar",
        "title": "How much each factor actually moves demand",
        "subtitle": f"Anything under {result['materiality_threshold_pct']:.0f}% is not worth modelling",
        "y_label": "Measured effect (%)",
        "labels": [factor["factor"] for factor in result["factors"]],
        "series": [{
            "name": "Measured effect",
            "values": [factor["effect_pct"] for factor in result["factors"]],
        }],
        "highlight": result["factors"][0]["factor"] if result["factors"] else "",
        "value_suffix": "%",
        "note": (
            f"{len(result['material'])} factors matter and {len(result['immaterial'])} were "
            "tested and ruled out — the short bars are the useful result, not a gap."
        ),
        "source": "visit_outcome, weather, boiler_master and the job histories",
    })
    if chart:
        lines += [chart, ""]

    for factor in result["material"]:
        lines.append(f"- **{factor['factor']}** — {factor['reading']}")
    if result["immaterial"]:
        lines += ["", "**Tested and found immaterial** (do not build these into the model):"]
        for factor in result["immaterial"]:
            lines.append(f"- {factor['factor']} ({factor['effect_pct']}%) — {factor['reading']}")
    return "\n".join(lines)


def warm(sql_service: Any) -> None:
    """Pre-compute the expensive scans at boot so the first question is fast."""
    try:
        actual_run_rate(sql_service)
        forecast_level(sql_service)
        capacity_by_skill(sql_service)
    except Exception as error:  # noqa: BLE001 - warming must never block boot
        print(f"[DemandForecast] Warm-up skipped: {error}")
