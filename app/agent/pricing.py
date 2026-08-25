"""
Pricing Agent - engine.

Prices the three things the business sells: an annual Service, a Repair, and an
Installation. Each one has to be priced from different evidence, because the
estate records different things about each:

  * Installation is the only line with an OBSERVED price - `quotes_and_sales`
    holds the opening, walk-away and final quotation for every lead. So it is
    priced from what the market has already paid, adjusted by the measured price
    response from the commercial engine.
  * Repair has an observed COST - `fault_codes.repair_cost` per fault type, and
    `parts_replaced.replacement_cost` for the part actually changed - but no
    price anywhere. So it is built up cost-plus, and the recorded fault cost is
    reported alongside as a variance check on the build-up.
  * Service has neither price nor cost recorded. It is labour, so it is priced
    from job duration at the assumed labour rate, and that assumption is printed
    with the number rather than buried in it.

The distinction matters more than the arithmetic: a price built from an observed
market number and a price built from an assumed labour rate carry very different
confidence, and a recommendation that hides which is which is not usable.
"""

from __future__ import annotations

from typing import Any

from app.agent import commercial as commercial_engine
from app.agent import demand_forecast as demand_engine
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
    signed_pct,
)

SERVICE_LINES = ("Service", "Repair", "Installation")

# Price points tested around the recommendation, so the reader sees the shape of
# the margin curve rather than a single number presented as optimal.
SENSITIVITY_STEPS = (-0.10, -0.05, 0.0, 0.05, 0.10)


def _canonical_line(service_line: str) -> str:
    wanted = str(service_line or "").strip().casefold()
    aliases = {
        "service": "Service", "servicing": "Service", "maintenance": "Service",
        "annual service": "Service", "annual maintenance": "Service",
        "repair": "Repair", "repairs": "Repair", "breakdown": "Repair", "fix": "Repair",
        "installation": "Installation", "install": "Installation",
        "installs": "Installation", "installations": "Installation",
    }
    if wanted in aliases:
        return aliases[wanted]
    raise AnalyticsError(
        f"Unknown service line '{service_line}'. Valid lines: {', '.join(SERVICE_LINES)}."
    )


# ------------------------------------------------------------------ cost bases


def _annual_volume(sql_service: Any) -> dict[str, float]:
    """Annualised national job volume per service line, from the run-rate."""
    volume: dict[str, float] = {}
    for row in demand_engine.actual_run_rate(sql_service):
        volume[row["job_type"]] = volume.get(row["job_type"], 0.0) + float(row["jobs_per_day"] or 0)
    return {line: per_day * 365.0 for line, per_day in volume.items()}


def _repair_cost_base(sql_service: Any) -> dict[str, Any]:
    """Build up the cost of an average repair, and check it against the record."""

    def build() -> dict[str, Any]:
        rows = records(
            sql_service,
            """
            WITH fault AS (
                -- fault_codes carries duplicate rows for a few codes; joining it
                -- raw fans the repair table out and inflates every volume below.
                SELECT fault_code,
                       any_value(explanation_related_fault_codes) AS fault_type,
                       any_value(severity) AS severity,
                       avg(repair_cost) AS repair_cost
                FROM fault_codes GROUP BY 1
            ), job AS (
                SELECT r.fault_code, r.parts_changed,
                       f.fault_type, f.severity, f.repair_cost AS recorded_cost,
                       p.replacement_cost AS part_cost
                FROM repair_history r
                LEFT JOIN fault f USING (fault_code)
                LEFT JOIN parts_replaced p ON p.part = r.parts_changed
            )
            SELECT COALESCE(fault_type, 'Unclassified') AS fault_type,
                   any_value(severity) AS severity,
                   count(*) AS jobs,
                   round(avg(recorded_cost), 2) AS recorded_cost,
                   round(avg(part_cost), 2) AS part_cost
            FROM job GROUP BY 1 ORDER BY 3 DESC
            """,
            max_rows=60,
        )
        if not rows:
            raise AnalyticsError("repair_history holds no repairs to price.")

        total_jobs = sum(float(row["jobs"]) for row in rows) or 1.0
        weighted_recorded = sum(
            float(row["recorded_cost"] or 0) * float(row["jobs"]) for row in rows
        ) / total_jobs
        weighted_parts = sum(
            float(row["part_cost"] or 0) * float(row["jobs"]) for row in rows
        ) / total_jobs
        return {
            "faults": rows,
            "jobs": total_jobs,
            "weighted_recorded_cost": round(weighted_recorded, 2),
            "weighted_part_cost": round(weighted_parts, 2),
        }

    return cached("pricing:repair_cost", build)


def cost_to_serve(sql_service: Any) -> dict[str, Any]:
    """What a COMPLETED job actually costs, not what one visit costs.

    Three things separate the two, and all three are measurable here:

      1. Visits that do not finish the job. Half of all repair visits end
         'Parts Required', so a completed repair consumes roughly two visits, not
         one. A cost base built on one visit understates repair economics by
         about the same factor.
      2. Visits that never happen. No-access and cancellations burn a slot and
         still leave the job to do.
      3. Non-productive time. The capacity plan buys gross hours and only ~84% of
         them survive to be available for jobs, so an hour of work costs more
         than an hour of pay.

    The revisit itself is NOT recorded anywhere in the estate - there is one
    outcome row per job and no follow-up job. So this is the visit requirement
    the outcomes IMPLY, and it is reported as such. That same implication is what
    the demand forecast is missing, which is why this figure matters twice.
    """

    def build() -> dict[str, Any]:
        outcomes = records(
            sql_service,
            """
            SELECT a.job_category AS service_line, v.visit_status, count(*) AS visits
            FROM visit_outcome v JOIN appointment_schedule a USING (job_id)
            GROUP BY 1, 2
            """,
            max_rows=60,
        )
        if not outcomes:
            raise AnalyticsError("No visit outcomes found, so cost to serve cannot be built.")

        productivity = records(
            sql_service,
            """
            SELECT eng_skill_type AS service_line,
                   round(sum(gross_hours)) AS gross_hours,
                   round(sum(available_hours)) AS available_hours,
                   round(sum(available_hours) * 1.0 / NULLIF(sum(gross_hours), 0), 4)
                       AS productive_ratio
            FROM regional_capacity_forecast GROUP BY 1
            """,
            max_rows=20,
        )
        productive_index = {
            str(row["service_line"]): float(row["productive_ratio"] or 1.0) for row in productivity
        }

        labour_rate = assumption("labour_cost_per_hour_gbp")
        repair_costs = _repair_cost_base(sql_service)
        volumes = _annual_volume(sql_service)

        lines: list[dict[str, Any]] = []
        for line in SERVICE_LINES:
            rows_for = [row for row in outcomes if str(row["service_line"]) == line]
            if not rows_for:
                continue
            by_status = {str(row["visit_status"]): float(row["visits"]) for row in rows_for}
            total_visits = sum(by_status.values())
            completed = by_status.get("Completed", 0.0)
            if not completed:
                continue

            incomplete = by_status.get("Parts Required", 0.0)
            aborted = sum(
                value for status, value in by_status.items()
                if status == "No Access" or status.startswith("Cancelled")
            )
            visits_per_job = total_visits / completed
            first_time_fix = completed / total_visits * 100.0

            hours_per_visit, hours_source = demand_engine.hours_per_job_ratio(sql_service, line)
            productive_ratio = productive_index.get(line, 1.0)
            # An hour of work has to carry the hours that were paid for but never
            # became available, so the effective rate is the rate divided by the
            # share of gross hours that survives.
            loaded_rate = labour_rate / productive_ratio if productive_ratio else labour_rate
            labour_per_visit = hours_per_visit * loaded_rate
            labour_per_job = labour_per_visit * visits_per_job

            parts_per_job = repair_costs["weighted_part_cost"] if line == "Repair" else 0.0
            cost = labour_per_job + parts_per_job
            naive_cost = hours_per_visit * labour_rate + parts_per_job

            annual_jobs = volumes.get(line, 0.0)
            lines.append({
                "service_line": line,
                "visits_total": round(total_visits),
                "visits_completed": round(completed),
                "visits_incomplete": round(incomplete),
                "visits_aborted": round(aborted),
                "first_time_fix_pct": round(first_time_fix, 1),
                "visits_per_completed_job": round(visits_per_job, 3),
                "hours_per_visit": hours_per_visit,
                "hours_per_visit_source": hours_source,
                "productive_ratio_pct": round(productive_ratio * 100.0, 1),
                "labour_rate_loaded": round(loaded_rate, 2),
                "labour_per_visit": round(labour_per_visit, 2),
                "labour_per_completed_job": round(labour_per_job, 2),
                "parts_per_completed_job": round(parts_per_job, 2),
                "cost_per_completed_job": round(cost, 2),
                "naive_single_visit_cost": round(naive_cost, 2),
                "understatement_pct": round((cost / naive_cost - 1) * 100.0, 1) if naive_cost else 0.0,
                "annual_completed_jobs": round(annual_jobs),
                "annual_cost_gbp": round(cost * annual_jobs),
                "levers": _cost_levers(
                    line, completed, total_visits, visits_per_job, labour_per_visit,
                    annual_jobs, aborted, productive_ratio, hours_per_visit, labour_rate,
                ),
            })

        return {
            "lines": lines,
            "assumptions": declared("labour_cost_per_hour_gbp"),
            "method": (
                "Visits per completed job = all visits for that line in visit_outcome divided by "
                "the ones that completed. Labour is charged at the assumed rate grossed up by the "
                "productive share of hours in regional_capacity_forecast (paid gross hours vs "
                "hours actually available for jobs). Parts are the volume-weighted replacement "
                "cost of the part changed. The return visit implied by an incomplete job is not "
                "recorded in the estate, so this is the visit requirement the outcomes imply."
            ),
        }

    return cached("pricing:cost_to_serve", build)


def _cost_levers(
    line: str,
    completed: float,
    total_visits: float,
    visits_per_job: float,
    labour_per_visit: float,
    annual_jobs: float,
    aborted: float,
    productive_ratio: float,
    hours_per_visit: float,
    labour_rate: float,
) -> list[dict[str, Any]]:
    """What each percentage point of operational improvement is worth a year.

    Sized against the same annual volume the cost base uses, so a lever and the
    cost it attacks are always directly comparable.
    """
    levers: list[dict[str, Any]] = []

    # First-time fix. Visits per completed job is 1/fix-rate, so the saving from
    # a point of fix-rate is non-linear and largest where the rate is worst -
    # which is exactly why repair is the place to spend.
    fix_rate = completed / total_visits
    improved = min(fix_rate + 0.01, 0.999)
    visits_saved = (1 / fix_rate - 1 / improved) * annual_jobs
    levers.append({
        "name": "First-time fix +1 percentage point",
        "detail": (
            f"Moves the fix rate from {fix_rate * 100:.1f}% to {improved * 100:.1f}%, cutting "
            f"visits per completed job from {1 / fix_rate:.3f} to {1 / improved:.3f} — "
            f"{visits_saved:,.0f} fewer visits a year. Van stock and diagnostic quality are the "
            "usual levers."
        ),
        "annual_value_gbp": round(visits_saved * labour_per_visit),
    })

    # Aborted visits: a slot consumed with no job done.
    aborted_share = aborted / total_visits
    aborted_annual = aborted_share * annual_jobs * visits_per_job
    levers.append({
        "name": "Cut aborted visits by a tenth",
        "detail": (
            f"{aborted_share * 100:.1f}% of {line.lower()} visits are no-access or cancelled — "
            f"about {aborted_annual:,.0f} wasted slots a year. Removing a tenth of them frees "
            "capacity without hiring. Confirmation calls and access arrangements are the lever."
        ),
        "annual_value_gbp": round(aborted_annual * 0.10 * labour_per_visit),
    })

    # Non-productive time.
    if productive_ratio and productive_ratio < 1:
        recovered = annual_jobs * visits_per_job * hours_per_visit * 0.01 / productive_ratio
        levers.append({
            "name": "Recover 1 point of non-productive time",
            "detail": (
                f"Only {productive_ratio * 100:.1f}% of paid gross hours reach the job. One point "
                f"back is about {recovered:,.0f} productive hours a year across this line."
            ),
            "annual_value_gbp": round(recovered * labour_rate),
        })

    levers.sort(key=lambda item: item["annual_value_gbp"], reverse=True)
    return levers


def render_cost_to_serve(result: dict[str, Any]) -> str:
    lines = [
        "**Cost to serve — what a completed job actually costs**",
        "",
        markdown_table(
            ["Service line", "First-time fix", "Visits per completed job", "Labour per visit",
             "Labour per job", "Parts", "True cost per job", "Single-visit cost", "Understated by"],
            [
                [
                    row["service_line"], f"{row['first_time_fix_pct']}%",
                    num(row["visits_per_completed_job"], 2), gbp(row["labour_per_visit"], 2),
                    gbp(row["labour_per_completed_job"], 2), gbp(row["parts_per_completed_job"], 2),
                    f"**{gbp(row['cost_per_completed_job'], 2)}**",
                    gbp(row["naive_single_visit_cost"], 2),
                    signed_pct(row["understatement_pct"]),
                ]
                for row in result["lines"]
            ],
        ),
        "",
    ]

    chart = chart_block({
        "type": "bar",
        "title": "What a job really costs against what one visit costs",
        "subtitle": "The gap is the visits that do not finish the job",
        "y_label": "Cost per completed job (£)",
        "labels": [row["service_line"] for row in result["lines"]],
        "series": [
            {"name": "Cost of a single visit",
             "values": [row["naive_single_visit_cost"] for row in result["lines"]]},
            {"name": "True cost to complete",
             "values": [row["cost_per_completed_job"] for row in result["lines"]]},
        ],
        "value_prefix": "£",
        "note": (
            "Price a line off the shorter bar and every job loses money, because the taller "
            "bar is what it actually costs to finish."
        ),
        "source": "visit_outcome, appointment_schedule, parts_replaced and regional_capacity_forecast",
    })
    if chart:
        lines += [chart, ""]

    for row in result["lines"]:
        lines.append(
            f"**{row['service_line']}** — {num(row['visits_total'])} visits produced "
            f"{num(row['visits_completed'])} completed jobs. "
            + (
                f"{num(row['visits_incomplete'])} ended needing parts and "
                if row["visits_incomplete"]
                else ""
            )
            + f"{num(row['visits_aborted'])} were no-access or cancelled. At "
            f"{num(row['annual_completed_jobs'])} completed jobs a year the line costs "
            f"**{gbp(row['annual_cost_gbp'])}** to serve."
        )
        for lever in row["levers"]:
            lines.append(
                f"  - {lever['name']}: **{gbp(lever['annual_value_gbp'])}/yr** — {lever['detail']}"
            )
        lines.append("")

    lines.append(f"_Method:_ {result['method']}")
    return "\n".join(lines)


def _installation_price(sql_service: Any) -> dict[str, Any]:
    """The observed installation market: what customers have actually paid."""

    def build() -> dict[str, Any]:
        rows = records(
            sql_service,
            """
            SELECT count(*) AS sales,
                   round(avg(q.final_quotation), 2) AS avg_final,
                   round(median(q.final_quotation), 2) AS median_final,
                   round(quantile_cont(q.final_quotation, 0.25), 2) AS p25,
                   round(quantile_cont(q.final_quotation, 0.75), 2) AS p75,
                   round(avg(q.primary_qutation), 2) AS avg_opening,
                   round(avg(q.secondary_quotation), 2) AS avg_walkaway
            FROM quotes_and_sales q
            JOIN installation_history i USING (lead_id)
            WHERE i.sale_happened
            """,
            max_rows=1,
        )
        if not rows or not rows[0].get("sales"):
            raise AnalyticsError("No completed sales found to price installations from.")

        regional = records(
            sql_service,
            """
            SELECT h.region,
                   count(*) AS sales,
                   round(median(q.final_quotation)) AS median_final,
                   round(avg(q.final_quotation)) AS avg_final
            FROM quotes_and_sales q
            JOIN installation_history i USING (lead_id)
            JOIN customer_holdings h ON h.customer_id = i.customer_id
            WHERE i.sale_happened
            GROUP BY 1 ORDER BY 3 DESC
            """,
            max_rows=30,
        )
        result = dict(rows[0])
        result["regional"] = regional
        medians = [float(row["median_final"]) for row in regional if row["median_final"]]
        result["regional_spread_pct"] = (
            round((max(medians) - min(medians)) / min(medians) * 100.0, 1) if medians else 0.0
        )
        return result

    return cached("pricing:installation_price", build)


# ------------------------------------------------------------------ price book


def price_book(sql_service: Any, service_line: str = "") -> dict[str, Any]:
    """Recommend a price for each service line, with its basis and confidence."""
    wanted = _canonical_line(service_line) if str(service_line or "").strip() else ""

    labour_rate = assumption("labour_cost_per_hour_gbp")
    target_margin = assumption("target_gross_margin_pct") / 100.0
    volumes = _annual_volume(sql_service)
    serve_index = {row["service_line"]: row for row in cost_to_serve(sql_service)["lines"]}
    lines: list[dict[str, Any]] = []

    for line in SERVICE_LINES:
        if wanted and line != wanted:
            continue

        hours_per_job, hours_source = demand_engine.hours_per_job_ratio(sql_service, line)
        labour_cost = round(hours_per_job * labour_rate, 2)
        annual_volume = round(volumes.get(line, 0.0))
        serve = serve_index.get(line)

        # The cost base is the cost of a COMPLETED job. Pricing a repair off one
        # visit when it takes two is the single most expensive mistake available
        # here, so the visit multiple is carried into the cost base and shown.
        serve_component = None
        if serve:
            serve_component = {
                "name": "Delivery reality",
                "value": round(
                    serve["cost_per_completed_job"] - serve["naive_single_visit_cost"], 2
                ),
                "detail": (
                    f"{serve['first_time_fix_pct']}% of {line.lower()} visits finish the job, so a "
                    f"completed job consumes {serve['visits_per_completed_job']:.2f} visits, and "
                    f"only {serve['productive_ratio_pct']}% of paid hours reach the job. Together "
                    f"these add {gbp(serve['cost_per_completed_job'] - serve['naive_single_visit_cost'], 2)} "
                    f"to the cost of every completed job — "
                    f"{signed_pct(serve['understatement_pct'])} on a single-visit build-up."
                ),
            }

        if line == "Repair":
            costs = _repair_cost_base(sql_service)
            parts_cost = costs["weighted_part_cost"]
            cost_base = round(
                serve["cost_per_completed_job"] if serve else labour_cost + parts_cost, 2
            )
            recommended = round(cost_base / (1 - target_margin), 2)
            entry = {
                "service_line": line,
                "basis": "cost-plus on cost to serve",
                "confidence": "medium",
                "components": [
                    {"name": "Labour", "value": labour_cost,
                     "detail": f"{hours_per_job} h/visit ({hours_source}) at "
                               f"{gbp(labour_rate, 2)}/h (assumed)"},
                    {"name": "Parts", "value": parts_cost,
                     "detail": "volume-weighted replacement cost of the part actually changed, "
                               "from parts_replaced joined to repair_history"},
                ] + ([serve_component] if serve_component else []),
                "cost_base": cost_base,
                "realised_price": None,
                "recommended_price": recommended,
                "cross_check": {
                    "name": "Recorded cost per fault",
                    "value": costs["weighted_recorded_cost"],
                    "detail": (
                        "fault_codes.repair_cost weighted by the observed fault mix. This is "
                        "what the estate records a repair as costing; the build-up above is "
                        "labour plus the part across every visit the job takes. A large "
                        "divergence means one of the two is wrong and should be reconciled "
                        "before the price is published."
                    ),
                },
                "evidence": [
                    f"{num(costs['jobs'])} repairs analysed across "
                    f"{len(costs['faults'])} fault types",
                ] + ([
                    f"Pricing this line off a single visit would set it at "
                    f"{gbp(serve['naive_single_visit_cost'] / (1 - target_margin), 2)} — below the "
                    f"{gbp(serve['cost_per_completed_job'], 2)} it costs to complete, so every job "
                    "would lose money at the target margin."
                ] if serve else []),
            }
        elif line == "Service":
            cost_base = round(serve["cost_per_completed_job"] if serve else labour_cost, 2)
            recommended = round(cost_base / (1 - target_margin), 2)
            entry = {
                "service_line": line,
                "basis": "cost-plus on cost to serve (labour only)",
                "confidence": "low",
                "components": [
                    {"name": "Labour", "value": labour_cost,
                     "detail": f"{hours_per_job} h/visit ({hours_source}) at "
                               f"{gbp(labour_rate, 2)}/h (assumed)"},
                ] + ([serve_component] if serve_component else []),
                "cost_base": cost_base,
                "realised_price": None,
                "recommended_price": recommended,
                "cross_check": None,
                "evidence": [
                    "The estate records no price and no consumable cost for an annual service, "
                    "so this is a labour floor, not a market price. Treat it as the minimum a "
                    "service plan must recover, and validate against the service-plan billing "
                    "system before publishing.",
                ],
            }
        else:
            market = _installation_price(sql_service)
            realised = float(market["median_final"])
            negotiation = None
            try:
                negotiation = commercial_engine.negotiation(sql_service)
            except AnalyticsError:
                negotiation = None

            # Price to the band that has historically produced the most revenue
            # per lead, rather than to a margin target - installation is the one
            # line where the market's own answer is observable.
            if negotiation and not negotiation["price_responsive"]:
                target_price = float(negotiation["best_band"]["avg_final"])
                rationale = (
                    f"Conversion varies only {negotiation['conversion_spread_pp']} points across "
                    f"the whole discount range, so the market is not visibly price-sensitive in "
                    f"the range already tested. The '{negotiation['best_band']['band']}' band "
                    f"closes at {gbp(negotiation['best_band']['avg_final'])} on the same "
                    f"conversion, so that is the level to hold."
                )
                confidence = "high"
            else:
                target_price = realised
                rationale = (
                    "Conversion does move with discount, so the current realised median is the "
                    "safe position until a controlled price test is run."
                )
                confidence = "medium"

            entry = {
                "service_line": line,
                "basis": "observed market price",
                "confidence": confidence,
                "components": [
                    {"name": "Labour (informational)", "value": labour_cost,
                     "detail": f"{hours_per_job} h/job ({hours_source}) at "
                               f"{gbp(labour_rate, 2)}/h (assumed). Materials and appliance cost "
                               "are not recorded anywhere in the estate, so this is NOT a full "
                               "cost base and no margin is claimed from it."},
                ] + ([serve_component] if serve_component else []),
                # Deliberately None: the appliance is the dominant cost of an
                # installation and the estate does not hold it, so any "margin"
                # computed here would be fiction. What CAN be stated is the
                # contribution over the delivery cost, and it is stated as that.
                "cost_base": None,
                "delivery_cost": serve["cost_per_completed_job"] if serve else None,
                "contribution_over_delivery": (
                    round(target_price - serve["cost_per_completed_job"], 2) if serve else None
                ),
                "realised_price": realised,
                "recommended_price": round(target_price, 2),
                "cross_check": {
                    "name": "Quote ladder",
                    "value": round(float(market["avg_opening"]), 2),
                    "detail": (
                        f"Opening {gbp(market['avg_opening'])} → walk-away "
                        f"{gbp(market['avg_walkaway'])} → final {gbp(market['avg_final'])}. "
                        f"Interquartile range {gbp(market['p25'])}–{gbp(market['p75'])}."
                    ),
                },
                "evidence": [
                    f"{num(market['sales'])} completed sales priced",
                    f"Regional median spread {market['regional_spread_pct']}% — "
                    + ("no case for regional price differentiation"
                       if market["regional_spread_pct"] < 5
                       else "large enough to justify regional price points"),
                    rationale,
                ] + ([
                    f"Delivery costs {gbp(serve['cost_per_completed_job'], 2)} per completed "
                    f"installation, leaving {gbp(target_price - serve['cost_per_completed_job'], 2)} "
                    "of contribution towards the appliance, materials and overhead the estate does "
                    "not record. That is a contribution, not a margin — do not report it as one."
                ] if serve else []),
                "regional": market["regional"],
            }

        reference = entry["recommended_price"]
        entry["annual_volume"] = annual_volume
        entry["hours_per_job"] = hours_per_job
        entry["sensitivity"] = _sensitivity(entry, annual_volume)
        if entry.get("cost_base"):
            entry["margin_at_recommended_pct"] = round(
                (reference - entry["cost_base"]) / reference * 100.0, 1
            )
        else:
            entry["margin_at_recommended_pct"] = None
        if entry.get("realised_price"):
            entry["price_change_pct"] = round(
                (reference - entry["realised_price"]) / entry["realised_price"] * 100.0, 1
            )
            entry["annual_revenue_effect_gbp"] = round(
                (reference - entry["realised_price"]) * annual_volume
            )
        else:
            entry["price_change_pct"] = None
            entry["annual_revenue_effect_gbp"] = round(reference * annual_volume)
        lines.append(entry)

    return {
        "lines": lines,
        "assumptions": declared("labour_cost_per_hour_gbp", "target_gross_margin_pct"),
        "method": (
            "Installation is priced from observed final quotations in quotes_and_sales; "
            "Repair is built up from the part actually changed in parts_replaced plus labour, "
            "and cross-checked against fault_codes.repair_cost; Service is labour-only because "
            "the estate records neither a price nor a consumable cost for it. Volumes are the "
            "trailing run-rate from the job histories, annualised."
        ),
    }


def _sensitivity(entry: dict[str, Any], annual_volume: float) -> list[dict[str, Any]]:
    """Margin and revenue at price points either side of the recommendation."""
    base = float(entry["recommended_price"])
    cost = entry.get("cost_base")
    out = []
    for step in SENSITIVITY_STEPS:
        price = round(base * (1 + step), 2)
        out.append({
            "step_pct": round(step * 100),
            "price": price,
            "margin_pct": round((price - float(cost)) / price * 100.0, 1) if cost else None,
            "annual_revenue": round(price * annual_volume),
        })
    return out


def render_price_book(result: dict[str, Any]) -> str:
    lines = ["**Service pricing recommendation**", ""]
    lines.append(markdown_table(
        ["Service line", "Basis", "Confidence", "Cost base", "Realised price",
         "Recommended", "Margin", "Annual volume"],
        [
            [
                entry["service_line"], entry["basis"], entry["confidence"],
                gbp(entry["cost_base"], 2) if entry["cost_base"] else "not recorded",
                gbp(entry["realised_price"], 2) if entry["realised_price"] else "not recorded",
                gbp(entry["recommended_price"], 2),
                f"{entry['margin_at_recommended_pct']}%"
                if entry["margin_at_recommended_pct"] is not None else "n/a",
                num(entry["annual_volume"]),
            ]
            for entry in result["lines"]
        ],
    ))
    lines.append("")

    for entry in result["lines"]:
        lines.append(f"**{entry['service_line']} — {gbp(entry['recommended_price'], 2)}**")
        for component in entry["components"]:
            lines.append(f"- {component['name']}: {gbp(component['value'], 2)} — {component['detail']}")
        if entry.get("cross_check"):
            check = entry["cross_check"]
            lines.append(
                f"- Cross-check · {check['name']}: {gbp(check['value'], 2)} — {check['detail']}"
            )
        for note in entry.get("evidence", []):
            lines.append(f"- {note}")
        if entry.get("price_change_pct") is not None:
            lines.append(
                f"- Moving from the realised {gbp(entry['realised_price'], 2)} to "
                f"{gbp(entry['recommended_price'], 2)} is "
                f"{signed_pct(entry['price_change_pct'])}, worth "
                f"{gbp(entry['annual_revenue_effect_gbp'])} a year at the current run-rate "
                f"of {num(entry['annual_volume'])} jobs — if volume holds."
            )
        sensitivity = entry.get("sensitivity") or []
        if sensitivity:
            lines.append("")
            lines.append(markdown_table(
                ["Price move", "Price", "Margin", "Annual revenue"],
                [
                    [
                        f"{row['step_pct']:+d}%", gbp(row["price"], 2),
                        f"{row['margin_pct']}%" if row["margin_pct"] is not None else "n/a",
                        gbp(row["annual_revenue"]),
                    ]
                    for row in sensitivity
                ],
            ))
        lines.append("")

    # With one line requested, the useful picture is how its revenue responds to
    # moving the price. Across all three, it is where the prices sit relative to
    # each other - and hbar copes with installation being an order of magnitude
    # larger without squashing the other two into nothing.
    if len(result["lines"]) == 1:
        entry = result["lines"][0]
        chart = chart_block({
            "type": "line",
            "title": f"{entry['service_line']} revenue at each price point",
            "x_label": "Price move",
            "y_label": "Revenue a year (£)",
            "labels": [f"{row['step_pct']:+d}%" for row in entry["sensitivity"]],
            "series": [{
                "name": "Annual revenue",
                "values": [row["annual_revenue"] for row in entry["sensitivity"]],
            }],
            "highlight": "+0%",
            "value_prefix": "£",
            "note": (
                f"At {num(entry['annual_volume'])} jobs a year — assumes volume holds at every "
                "price, which is the part to test."
            ),
            "source": "cost to serve and the trailing job run-rate",
        })
    else:
        chart = chart_block({
            "type": "hbar",
            "title": "Recommended price by service line",
            "y_label": "Price (£)",
            "labels": [entry["service_line"] for entry in result["lines"]],
            "series": [{
                "name": "Recommended price",
                "values": [entry["recommended_price"] for entry in result["lines"]],
            }],
            "value_prefix": "£",
            "note": "Each line is priced from different evidence — see the basis column.",
            "source": "quotes_and_sales, parts_replaced and visit_outcome",
        })
    if chart:
        lines += [chart, ""]

    from app.agent.analytics import assumptions_block

    lines += [assumptions_block(result["assumptions"]), "", f"_Method:_ {result['method']}"]
    return "\n".join(line for line in lines if line is not None)


# ------------------------------------------------------------- repair schedule


def repair_price_list(sql_service: Any, limit: int = 15) -> dict[str, Any]:
    """A per-fault-type repair price schedule, ranked by volume."""
    costs = _repair_cost_base(sql_service)
    labour_rate = assumption("labour_cost_per_hour_gbp")
    target_margin = assumption("target_gross_margin_pct") / 100.0
    hours_per_job, hours_source = demand_engine.hours_per_job_ratio(sql_service, "Repair")
    total_jobs = costs["jobs"] or 1.0

    # Labour must carry the same visit multiple and productive-hour loading the
    # price book uses, or this schedule would quietly contradict the headline
    # repair price sitting directly above it on the same screen.
    serve = next(
        (row for row in cost_to_serve(sql_service)["lines"] if row["service_line"] == "Repair"),
        None,
    )
    labour_cost = (
        serve["labour_per_completed_job"] if serve else hours_per_job * labour_rate
    )
    visits_per_job = serve["visits_per_completed_job"] if serve else 1.0

    rows = []
    for fault in costs["faults"][:limit]:
        part_cost = float(fault["part_cost"] or 0)
        cost_base = labour_cost + part_cost
        recommended = cost_base / (1 - target_margin)
        share = float(fault["jobs"]) / total_jobs
        rows.append({
            "fault_type": fault["fault_type"],
            "severity": fault["severity"],
            "jobs": int(fault["jobs"]),
            "share_pct": round(share * 100, 1),
            "recorded_cost": float(fault["recorded_cost"] or 0),
            "part_cost": round(part_cost, 2),
            "labour_cost": round(labour_cost, 2),
            "cost_base": round(cost_base, 2),
            "recommended_price": round(recommended, 2),
            "margin_pct": round((recommended - cost_base) / recommended * 100, 1),
        })

    return {
        "rows": rows,
        "hours_per_job": hours_per_job,
        "hours_source": hours_source,
        "visits_per_completed_job": round(visits_per_job, 3),
        "assumptions": declared("labour_cost_per_hour_gbp", "target_gross_margin_pct"),
        "method": (
            "Cost base per fault type = labour for every visit the job takes "
            f"({visits_per_job:.2f} visits at {hours_per_job} h, grossed up for non-productive "
            "time) plus the replacement cost of the part actually changed. `recorded_cost` is "
            "what fault_codes says the same repair costs; where the two diverge, reconcile "
            "before publishing. Fault-level part costs vary little here, so the differences "
            "between rows are small — the volume column is what should drive attention."
        ),
    }


def render_repair_price_list(result: dict[str, Any]) -> str:
    lines = [
        f"**Repair price schedule by fault type** "
        f"({result['hours_per_job']} h/visit, {result['hours_source']}; "
        f"{result['visits_per_completed_job']:.2f} visits per completed job)",
        "",
        markdown_table(
            ["Fault type", "Severity", "Jobs", "Share", "Part", "Labour",
             "Cost base", "Recorded cost", "Recommended price", "Margin"],
            [
                [
                    row["fault_type"], row["severity"], num(row["jobs"]), f"{row['share_pct']}%",
                    gbp(row["part_cost"], 2), gbp(row["labour_cost"], 2),
                    gbp(row["cost_base"], 2), gbp(row["recorded_cost"], 2),
                    gbp(row["recommended_price"], 2), f"{row['margin_pct']}%",
                ]
                for row in result["rows"]
            ],
        ),
        "",
    ]

    # Recommended prices barely differ between faults, because part costs barely
    # differ. Volume is what should decide where attention goes, so volume is
    # what gets charted.
    chart = chart_block({
        "type": "hbar",
        "title": "Repair volume by fault type",
        "y_label": "Repairs",
        "labels": [row["fault_type"] for row in result["rows"]],
        "series": [{
            "name": "Repairs",
            "values": [row["jobs"] for row in result["rows"]],
        }],
        "note": (
            "Prices come out close together because part costs do. Volume is what decides "
            "which fault is worth engineering out."
        ),
        "source": "repair_history joined to fault_codes and parts_replaced",
    })
    if chart:
        lines += [chart, ""]

    lines.append(f"_Method:_ {result['method']}")
    return "\n".join(lines)


def warm(sql_service: Any) -> None:
    try:
        _repair_cost_base(sql_service)
        _installation_price(sql_service)
    except Exception as error:  # noqa: BLE001 - warming must never block boot
        print(f"[Pricing] Warm-up skipped: {error}")
