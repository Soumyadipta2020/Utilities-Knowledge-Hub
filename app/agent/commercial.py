"""
Commercial Agent - engine.

Two questions a commercial lead actually has:

  * "Where should I be negotiating, and how hard?" - answered by measuring what
    discounting has bought historically. The estate holds the primary quote, the
    final quote and whether the lead converted, which is enough to test the
    assumption every sales floor runs on: that a bigger discount wins more work.
  * "When is our productive season?" - answered by combining when demand converts
    with when the business can actually deliver it. A month with high conversion
    and no engineer capacity is not a good month; a quiet month with idle
    installation capacity is where a campaign pays.

The negotiation analysis deliberately reports revenue PER LEAD rather than total
revenue by band. Total revenue by band mostly measures how many deals landed in
that band, which tells a negotiator nothing. Revenue per lead is conversion and
price in one number, and it is the quantity a discount policy actually moves.
"""

from __future__ import annotations

from typing import Any

from app.agent.analytics import (
    AnalyticsError,
    cached,
    chart_block,
    gbp,
    markdown_table,
    num,
    records,
)

# Discount bands, as a share off the primary quotation. The first band is
# negative on purpose: a large share of quotes are negotiated UP from the
# opening number, and folding those in with "no discount" would hide it.
DISCOUNT_BANDS = (
    ("Negotiated up", None, 0.0),
    ("0-5% off", 0.0, 0.05),
    ("5-15% off", 0.05, 0.15),
    ("15-25% off", 0.15, 0.25),
    ("25%+ off", 0.25, None),
)

# Below this, a difference in conversion across discount bands is noise rather
# than price response.
CONVERSION_NOISE_PP = 2.0

MONTH_NAMES = (
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


# ------------------------------------------------------------------ negotiation


def negotiation(sql_service: Any, segment: str = "") -> dict[str, Any]:
    """Measure what discounting has actually bought, and set guardrails from it.

    `segment` optionally restricts the analysis to one region.
    """
    region_filter = ""
    segment = str(segment or "").strip()
    if segment:
        safe = segment.replace("'", "''")
        region_filter = f"AND h.region = '{safe}'"

    def build() -> dict[str, Any]:
        band_sql = "\n".join(
            f"WHEN {_band_predicate(low, high)} THEN '{label}'"
            for label, low, high in DISCOUNT_BANDS
        )
        rows = records(
            sql_service,
            f"""
            WITH deal AS (
                SELECT q.lead_id,
                       q.primary_qutation AS opening,
                       q.secondary_quotation AS secondary,
                       q.final_quotation AS final,
                       (q.primary_qutation - q.final_quotation)
                           / NULLIF(q.primary_qutation, 0) AS discount,
                       i.sale_happened, i.installation_happened, i.insurance_purchased
                FROM quotes_and_sales q
                JOIN installation_history i USING (lead_id)
                JOIN customer_holdings h ON h.customer_id = i.customer_id
                WHERE q.primary_qutation > 0 {region_filter}
            )
            SELECT CASE {band_sql} END AS band,
                   count(*) AS leads,
                   round(100.0 * avg(CASE WHEN sale_happened THEN 1.0 ELSE 0 END), 2) AS conversion_pct,
                   round(avg(discount) * 100, 1) AS avg_discount_pct,
                   round(avg(opening)) AS avg_opening,
                   round(avg(final)) AS avg_final,
                   round(sum(CASE WHEN sale_happened THEN final ELSE 0 END)) AS revenue,
                   round(sum(CASE WHEN sale_happened THEN final ELSE 0 END) / count(*), 2)
                       AS revenue_per_lead,
                   round(100.0 * avg(CASE WHEN insurance_purchased THEN 1.0 ELSE 0 END), 1)
                       AS insurance_attach_pct
            FROM deal
            GROUP BY 1
            """,
            max_rows=20,
        )
        if not rows:
            raise AnalyticsError("No quoted leads matched, so no negotiation position can be set.")

        order = {label: index for index, (label, _, _) in enumerate(DISCOUNT_BANDS)}
        rows.sort(key=lambda row: order.get(str(row["band"]), 99))
        for row in rows:
            row["revenue_per_lead"] = float(row["revenue_per_lead"] or 0)
            row["conversion_pct"] = float(row["conversion_pct"] or 0)

        conversions = [row["conversion_pct"] for row in rows]
        conversion_spread_pp = round(max(conversions) - min(conversions), 2)
        price_responsive = conversion_spread_pp >= CONVERSION_NOISE_PP

        best = max(rows, key=lambda row: row["revenue_per_lead"])
        worst = min(rows, key=lambda row: row["revenue_per_lead"])

        # Value of moving every deal that is discounted past the best-performing
        # band up to that band's revenue per lead. Stated as an upper bound,
        # because it holds conversion constant - which is exactly what the
        # conversion spread above is evidence for, and exactly what a controlled
        # test has to confirm before the policy is rolled out.
        leakage = 0.0
        leaking_bands: list[dict[str, Any]] = []
        for row in rows:
            if row["revenue_per_lead"] >= best["revenue_per_lead"]:
                continue
            gap = (best["revenue_per_lead"] - row["revenue_per_lead"]) * float(row["leads"])
            leakage += gap
            leaking_bands.append({
                "band": row["band"],
                "leads": int(row["leads"]),
                "revenue_per_lead": round(row["revenue_per_lead"], 2),
                "gap_per_lead": round(best["revenue_per_lead"] - row["revenue_per_lead"], 2),
                "value_gbp": round(gap),
            })

        # How often the opening number is beaten upward, and by how much: the
        # single most transferable negotiation fact in the estate.
        uplift = records(
            sql_service,
            f"""
            WITH deal AS (
                SELECT q.primary_qutation AS opening, q.secondary_quotation AS secondary,
                       q.final_quotation AS final, i.sale_happened
                FROM quotes_and_sales q
                JOIN installation_history i USING (lead_id)
                JOIN customer_holdings h ON h.customer_id = i.customer_id
                WHERE q.primary_qutation > 0 {region_filter}
            )
            SELECT count(*) AS deals,
                   count(*) FILTER (WHERE final > opening) AS closed_above_opening,
                   count(*) FILTER (WHERE final < secondary) AS closed_below_walkaway,
                   round(avg(opening)) AS avg_opening,
                   round(avg(secondary)) AS avg_secondary,
                   round(avg(final)) AS avg_final,
                   round(avg(CASE WHEN final > opening THEN final - opening END)) AS avg_uplift
            FROM deal
            """,
            max_rows=1,
        )
        shape = uplift[0] if uplift else {}

        guardrail = _guardrail(rows, best, price_responsive)
        return {
            "segment": segment or "All regions",
            "bands": rows,
            "conversion_spread_pp": conversion_spread_pp,
            "price_responsive": price_responsive,
            "best_band": best,
            "worst_band": worst,
            "leakage_gbp": round(leakage),
            "leaking_bands": leaking_bands,
            "deal_shape": shape,
            "guardrail": guardrail,
            "method": (
                "Every quoted lead in quotes_and_sales joined to installation_history on "
                "lead_id, banded by the discount from the primary quotation to the final "
                "quotation, then scored on conversion and revenue per lead. Revenue per lead "
                "is the metric a discount policy moves; total revenue per band only measures "
                "how many deals happened to land there."
            ),
        }

    return cached(f"commercial:negotiation:{segment.casefold()}", build)


def _band_predicate(low: float | None, high: float | None) -> str:
    if low is None:
        return f"discount < {high}"
    if high is None:
        return f"discount >= {low}"
    return f"discount >= {low} AND discount < {high}"


def _band_cap_pct(label: str) -> float:
    """The most a deal in this band is discounted - the cap it implies."""
    for name, _low, high in DISCOUNT_BANDS:
        if name == label:
            return 0.0 if high is None else round(high * 100.0, 1)
    return 0.0


def _guardrail(
    rows: list[dict[str, Any]], best: dict[str, Any], price_responsive: bool
) -> dict[str, Any]:
    """Turn the measured price response into an instruction a negotiator can use."""
    cap_pct = _band_cap_pct(str(best["band"]))
    cap_text = (
        "no discount off the opening quotation without a named approver"
        if cap_pct <= 0
        else f"discount authority at {cap_pct:.0f}% off the opening quotation"
    )

    if price_responsive:
        return {
            "position": "Discount selectively",
            "cap_band": best["band"],
            "cap_pct": cap_pct,
            "detail": (
                "Conversion does vary materially across discount bands, so price is buying "
                "volume. Set the cap where the marginal conversion gain stops covering the "
                "price given up, and review it by segment rather than nationally."
            ),
        }
    return {
        "position": "Hold price; trade value, not price",
        "cap_band": best["band"],
        "cap_pct": cap_pct,
        "detail": (
            f"Conversion is effectively flat across every discount band, so discount is not "
            f"buying volume - it is only reducing the ticket. Set {cap_text}, and give "
            "negotiators non-price levers (extended warranty, insurance bundling, scheduling "
            "priority) to close instead. Anything deeper needs a reason on the record, because "
            "on this evidence it buys nothing."
        ),
    }


def render_negotiation(result: dict[str, Any]) -> str:
    lines = [
        f"**Negotiation position — {result['segment']}**",
        "",
        markdown_table(
            ["Discount band", "Leads", "Conversion", "Avg opening", "Avg final",
             "Revenue per lead", "Insurance attach"],
            [
                [
                    row["band"], num(row["leads"]), f"{row['conversion_pct']:.1f}%",
                    gbp(row["avg_opening"]), gbp(row["avg_final"]),
                    gbp(row["revenue_per_lead"], 2), f"{num(row['insurance_attach_pct'], 1)}%",
                ]
                for row in result["bands"]
            ],
        ),
        "",
    ]

    # Two series on one chart because they share no scale problem: both are read
    # against the bands, and the whole argument is that one falls while the other
    # does not move. Splitting them would hide exactly that.
    chart = chart_block({
        "type": "bar",
        "title": "What we earn per lead at each discount level",
        "subtitle": "Conversion barely moves; the money does",
        "y_label": "Revenue per lead (£)",
        "labels": [str(band["band"]) for band in result["bands"]],
        "series": [{
            "name": "Revenue per lead",
            "values": [round(band["revenue_per_lead"], 2) for band in result["bands"]],
        }],
        "highlight": str(result["best_band"]["band"]),
        "value_prefix": "£",
        "note": (
            f"Conversion varies only {result['conversion_spread_pp']} points across all of "
            "these bands, so the falling bars are money given away, not volume bought."
        ),
        "source": "quotes_and_sales joined to installation_history",
    })
    if chart:
        lines += [chart, ""]

    verdict = (
        "price IS buying volume"
        if result["price_responsive"]
        else "discount is NOT buying volume"
    )
    lines += [
        f"**Read:** conversion varies by only {result['conversion_spread_pp']} percentage points "
        f"across the whole discount range, so {verdict}. Revenue per lead falls from "
        f"{gbp(result['best_band']['revenue_per_lead'], 2)} in the "
        f"'{result['best_band']['band']}' band to "
        f"{gbp(result['worst_band']['revenue_per_lead'], 2)} in the "
        f"'{result['worst_band']['band']}' band, on essentially identical conversion.",
        "",
        f"**Value at stake:** up to **{gbp(result['leakage_gbp'])}** across the leads already "
        f"quoted, if discounting were held at the '{result['best_band']['band']}' level. That is "
        "an upper bound - it holds conversion constant, which the evidence above supports but "
        "only a controlled trial confirms.",
        "",
        f"**Recommended position: {result['guardrail']['position']}.** "
        f"{result['guardrail']['detail']}",
    ]

    shape = result.get("deal_shape") or {}
    if shape.get("deals"):
        above = float(shape.get("closed_above_opening") or 0) / float(shape["deals"]) * 100.0
        below = float(shape.get("closed_below_walkaway") or 0) / float(shape["deals"]) * 100.0
        lines += [
            "",
            f"**Deal shape:** {num(above, 1)}% of quotes close ABOVE the opening number "
            f"(average uplift {gbp(shape.get('avg_uplift'))}), so the opening quote is not a "
            f"ceiling. {num(below, 1)}% close below the secondary quotation — that is the "
            "walk-away line being crossed, and it is where approval discipline should sit.",
        ]

    lines += ["", f"_Method:_ {result['method']}"]
    return "\n".join(lines)


# --------------------------------------------------------------------- season


def season(sql_service: Any) -> dict[str, Any]:
    """Rank the trading months on what converts AND on what can be delivered."""

    def build() -> dict[str, Any]:
        commercial_rows = records(
            sql_service,
            """
            WITH monthly AS (
                SELECT month(i.lead_date) AS month,
                       count(*) AS leads,
                       count(DISTINCT i.lead_date) AS days,
                       sum(CASE WHEN i.sale_happened THEN 1 ELSE 0 END) AS sales,
                       sum(CASE WHEN i.installation_happened THEN 1 ELSE 0 END) AS installs,
                       sum(CASE WHEN i.insurance_purchased THEN 1 ELSE 0 END) AS insured,
                       sum(CASE WHEN i.sale_happened THEN q.final_quotation ELSE 0 END) AS revenue
                FROM installation_history i
                LEFT JOIN quotes_and_sales q USING (lead_id)
                WHERE i.lead_date IS NOT NULL
                GROUP BY 1
            )
            SELECT month, leads, days, sales, installs, revenue,
                   round(leads * 1.0 / NULLIF(days, 0), 1) AS leads_per_day,
                   round(100.0 * sales / NULLIF(leads, 0), 1) AS conversion_pct,
                   round(100.0 * insured / NULLIF(sales, 0), 1) AS insurance_attach_pct,
                   round(revenue / NULLIF(days, 0)) AS revenue_per_day,
                   round(revenue / NULLIF(sales, 0)) AS avg_order_value
            FROM monthly
            WHERE days >= 20
            ORDER BY month
            """,
            max_rows=20,
        )
        if not commercial_rows:
            raise AnalyticsError("installation_history holds no complete trading month.")

        # Delivery side: how much installation capacity each calendar month of
        # the forward plan actually has. A month that converts well but cannot be
        # delivered is not a month to push.
        capacity_rows = records(
            sql_service,
            """
            SELECT month(date) AS month,
                   round(sum(CASE WHEN eng_skill_type = 'Installation' THEN available_hours END))
                       AS installation_hours,
                   round(sum(available_hours)) AS total_hours,
                   count(DISTINCT date) AS days
            FROM regional_capacity_forecast
            GROUP BY 1 ORDER BY 1
            """,
            max_rows=20,
        )
        capacity_index = {
            int(row["month"]): float(row["installation_hours"] or 0)
                                 / max(float(row["days"] or 1), 1.0)
            for row in capacity_rows
        }

        revenue_values = [float(row["revenue_per_day"] or 0) for row in commercial_rows]
        mean_revenue = sum(revenue_values) / len(revenue_values) if revenue_values else 0.0
        capacity_values = [v for v in capacity_index.values() if v]
        mean_capacity = sum(capacity_values) / len(capacity_values) if capacity_values else 0.0

        for row in commercial_rows:
            month = int(row["month"])
            row["month_name"] = MONTH_NAMES[month]
            revenue_index = (
                float(row["revenue_per_day"] or 0) / mean_revenue if mean_revenue else 0.0
            )
            capacity_index_value = (
                capacity_index.get(month, 0.0) / mean_capacity if mean_capacity else 0.0
            )
            row["revenue_index"] = round(revenue_index, 3)
            row["capacity_index"] = round(capacity_index_value, 3)
            row["install_hours_per_day"] = round(capacity_index.get(month, 0.0))
            # Sell what can be delivered: a month scores on commercial pull and
            # delivery headroom together, not on either alone.
            row["opportunity_score"] = round(revenue_index * (0.5 + 0.5 * capacity_index_value), 3)

        by_score = sorted(commercial_rows, key=lambda row: row["opportunity_score"], reverse=True)
        by_conversion = sorted(
            commercial_rows, key=lambda row: float(row["conversion_pct"] or 0), reverse=True
        )
        conversion_spread = round(
            float(by_conversion[0]["conversion_pct"]) - float(by_conversion[-1]["conversion_pct"]), 1
        )
        revenue_spread = round(
            (max(revenue_values) - min(revenue_values)) / min(revenue_values) * 100.0, 1
        ) if min(revenue_values) > 0 else 0.0

        k = min(3, max(1, len(by_score) // 2))
        return {
            "months": commercial_rows,
            "ranked": by_score,
            "peak": by_score[:k],
            "trough": by_score[-k:],
            "best_conversion": by_conversion[0],
            "worst_conversion": by_conversion[-1],
            "conversion_spread_pp": conversion_spread,
            "revenue_spread_pct": revenue_spread,
            "seasonal": revenue_spread >= 15.0 or conversion_spread >= 5.0,
            "method": (
                "Every complete trading month in installation_history, valued through "
                "quotes_and_sales on lead_id, then scored against the installation capacity "
                "the plan provisions for that calendar month in regional_capacity_forecast. "
                "The opportunity score is the revenue index weighted by delivery headroom, so "
                "a month that converts well but cannot be staffed does not rank as a peak."
            ),
        }

    return cached("commercial:season", build)


def render_season(result: dict[str, Any]) -> str:
    lines = [
        "**Trading season — where the productive periods are**",
        "",
        markdown_table(
            ["Month", "Leads/day", "Conversion", "Avg order value", "Revenue/day",
             "Install hrs/day available", "Opportunity score"],
            [
                [
                    row["month_name"], num(row["leads_per_day"], 1),
                    f"{num(row['conversion_pct'], 1)}%", gbp(row["avg_order_value"]),
                    gbp(row["revenue_per_day"]), num(row["install_hours_per_day"]),
                    f"{row['opportunity_score']:.2f}",
                ]
                for row in result["months"]
            ],
        ),
        "",
    ]

    chart = chart_block({
        "type": "line",
        "title": "Revenue per trading day through the year",
        "x_label": "Month",
        "y_label": "Revenue per trading day (£)",
        "labels": [row["month_name"] for row in result["months"]],
        "series": [{
            "name": "Revenue per trading day",
            "values": [row["revenue_per_day"] for row in result["months"]],
        }],
        "highlight": result["peak"][0]["month_name"] if result["peak"] else "",
        "value_prefix": "£",
        "note": (
            f"Revenue per trading day varies {result['revenue_spread_pct']}% peak to trough — "
            + ("a genuinely seasonal year." if result["seasonal"]
               else "close to flat, so delivery capacity decides the season, not demand.")
        ),
        "source": "installation_history valued through quotes_and_sales",
    })
    if chart:
        lines += [chart, ""]

    peak = ", ".join(row["month_name"] for row in result["peak"])
    trough = ", ".join(row["month_name"] for row in result["trough"])

    if result["seasonal"]:
        lines.append(
            f"**Read:** the year is genuinely seasonal — revenue per trading day varies "
            f"{result['revenue_spread_pct']}% peak to trough and conversion swings "
            f"{result['conversion_spread_pp']} points. Concentrate acquisition spend and "
            f"installer recruitment on **{peak}**, and use **{trough}** for maintenance "
            "campaigns, service-plan renewals and training."
        )
    else:
        lines.append(
            f"**Read:** demand is close to flat across the year — revenue per trading day "
            f"varies only {result['revenue_spread_pct']}% and conversion "
            f"{result['conversion_spread_pp']} points. The productive period is therefore set "
            f"by DELIVERY, not by demand: **{peak}** rank highest because that is where the "
            f"installation capacity sits, and **{trough}** are the months to avoid committing "
            "campaign volume the estate cannot install."
        )

    lines += [
        "",
        f"- Best converting month: **{result['best_conversion']['month_name']}** at "
        f"{num(result['best_conversion']['conversion_pct'], 1)}%; weakest: "
        f"**{result['worst_conversion']['month_name']}** at "
        f"{num(result['worst_conversion']['conversion_pct'], 1)}%.",
        f"- Insurance attaches on "
        f"{num(min(float(r['insurance_attach_pct'] or 0) for r in result['months']), 1)}%–"
        f"{num(max(float(r['insurance_attach_pct'] or 0) for r in result['months']), 1)}% of "
        "sales through the year — a lever available in every month, unlike price.",
        "",
        f"_Method:_ {result['method']}",
    ]
    return "\n".join(lines)


def warm(sql_service: Any) -> None:
    try:
        negotiation(sql_service)
        season(sql_service)
    except Exception as error:  # noqa: BLE001 - warming must never block boot
        print(f"[Commercial] Warm-up skipped: {error}")
