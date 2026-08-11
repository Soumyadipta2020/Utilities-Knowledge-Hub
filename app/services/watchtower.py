"""
Watchtower: an agent that reports without being asked.

Everything else in this app is pull - it answers when someone types. Watchtower
sweeps the business KPIs on a schedule, finds the weeks that break pattern, and
asks the agent to explain each one. Leaders get told; they do not have to think
of the question.

DETECTION IS DATA-DRIVEN, NOT HARDCODED. Anomalies are found with a robust
median/MAD outlier test over each KPI's own trailing history, so the sweep keeps
working if the datasets are regenerated, extended, or if a completely different
incident appears. Nothing here knows which weeks are "supposed" to be anomalous.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any, Callable

# A week must deviate by more than this many robust standard deviations, AND by
# more than the relative floor, before it is reported. The floor stops trivial
# wobble on a very stable series being dressed up as an incident.
Z_THRESHOLD = 3.5
MIN_RELATIVE_DEVIATION = 0.08
MIN_HISTORY_POINTS = 6


@dataclass
class KpiSpec:
    """One monitored business measure."""

    key: str
    label: str
    sql: str                       # must return (period, value, volume) ordered by period
    direction: str                 # "down" = only drops matter, "both" = either
    unit: str = ""
    impact_per_unit: float | None = None   # £ per unit shortfall, if quantifiable
    impact_note: str = ""
    drill: Callable[[Any, str], dict] | None = field(default=None, repr=False)


def _robust_stats(values: list[float]) -> tuple[float, float]:
    """Return (median, robust sigma) using median absolute deviation.

    MAD is used rather than the mean and standard deviation because a large
    anomaly inflates its own baseline when you use the mean - the incident
    partially hides itself.
    """
    median = statistics.median(values)
    deviations = [abs(v - median) for v in values]
    mad = statistics.median(deviations)
    # 1.4826 scales MAD to be comparable with the standard deviation of a normal.
    sigma = mad * 1.4826
    if sigma <= 0:
        sigma = statistics.pstdev(values) or 1e-9
    return median, sigma


class Watchtower:
    """Scans KPI series for outliers and asks the agent to explain them."""

    def __init__(self, sql_service: Any, store: Any) -> None:
        self.sql = sql_service
        self.store = store
        self.kpis = self._build_kpis()

    # ------------------------------------------------------------------ config

    def _build_kpis(self) -> list[KpiSpec]:
        return [
            KpiSpec(
                key="net_appointments",
                label="Weekly net completed appointments",
                sql="""
                    SELECT strftime(date_trunc('week', visit_date), '%Y-%m-%d') AS period,
                           count(*) FILTER (
                               WHERE visit_status NOT LIKE 'Cancelled%' AND visit_status <> 'No Access'
                           ) AS value,
                           count(*) AS volume
                    FROM visit_outcome
                    WHERE date_trunc('week', visit_date) + INTERVAL 6 DAY <= (SELECT max(visit_date) FROM visit_outcome)
                    GROUP BY 1 ORDER BY 1
                """,
                direction="down",
                unit="appointments",
                impact_per_unit=180.0,
                impact_note="assumes £180 average revenue per completed visit",
            ),
            KpiSpec(
                key="sales_conversion",
                label="Weekly lead-to-sale conversion rate",
                sql="""
                    SELECT strftime(date_trunc('week', lead_date), '%Y-%m-%d') AS period,
                           100.0 * count(*) FILTER (WHERE sale_happened = 'Yes') / count(*) AS value,
                           count(*) AS volume
                    FROM installation_history
                    WHERE date_trunc('week', lead_date) + INTERVAL 6 DAY <= (SELECT max(lead_date) FROM installation_history)
                    GROUP BY 1 HAVING count(*) > 100 ORDER BY 1
                """,
                direction="down",
                unit="% conversion",
            ),
            KpiSpec(
                key="net_sales",
                label="Weekly net sales",
                sql="""
                    SELECT strftime(date_trunc('week', lead_date), '%Y-%m-%d') AS period,
                           count(*) FILTER (WHERE sale_happened = 'Yes') AS value,
                           count(*) AS volume
                    FROM installation_history
                    WHERE date_trunc('week', lead_date) + INTERVAL 6 DAY <= (SELECT max(lead_date) FROM installation_history)
                    GROUP BY 1 ORDER BY 1
                """,
                direction="down",
                unit="sales",
                impact_per_unit=2100.0,
                impact_note="assumes £2,100 average final quotation per sale",
            ),
            KpiSpec(
                key="emergency_repairs",
                label="Weekly emergency repair volume",
                sql="""
                    SELECT strftime(date_trunc('week', repair_date), '%Y-%m-%d') AS period,
                           count(*) AS value,
                           count(*) AS volume
                    FROM repair_history
                    WHERE date_trunc('week', repair_date) + INTERVAL 6 DAY <= (SELECT max(repair_date) FROM repair_history)
                    GROUP BY 1 ORDER BY 1
                """,
                direction="both",
                unit="repairs",
            ),
        ]

    # ------------------------------------------------------------------- scan

    def _series(self, spec: KpiSpec) -> list[tuple[str, float, float]]:
        res = self.sql.query(spec.sql, max_rows=500)
        if not res.get("success"):
            print(f"[Watchtower] KPI '{spec.key}' query failed: {res.get('error')}")
            return []
        return [
            (str(row[0]), float(row[1]), float(row[2]))
            for row in res["rows"]
            if row[1] is not None and row[2] is not None
        ]

    @staticmethod
    def _trim_incomplete_tail(series: list[tuple[str, float, float]]) -> list[tuple[str, float, float]]:
        """Drop trailing weeks whose underlying record volume never arrived.

        A dataset that stops mid-generation leaves a sparse tail. Judged only on
        the metric, that tail looks like a catastrophic collapse - the first
        version of this reported a fictitious 97% drop. Volume is the honest
        signal for "the data is not all here yet", and only the TRAILING edge is
        trimmed, so a genuine mid-series collapse is still reported.
        """
        if len(series) < MIN_HISTORY_POINTS:
            return series
        volumes = [vol for _, _, vol in series]
        volume_median = statistics.median(volumes)
        if volume_median <= 0:
            return series

        cutoff = len(series)
        for index in range(len(series) - 1, -1, -1):
            if series[index][2] < 0.5 * volume_median:
                cutoff = index
            else:
                break
        if cutoff < len(series):
            dropped = [p for p, _, _ in series[cutoff:]]
            print(f"[Watchtower] Ignoring {len(dropped)} incomplete trailing week(s): {', '.join(dropped)}")
        return series[:cutoff]

    def scan(self, lookback_weeks: int = 26) -> list[dict[str, Any]]:
        """Run every KPI check and persist whatever breaks pattern."""
        findings: list[dict[str, Any]] = []

        for spec in self.kpis:
            series = self._trim_incomplete_tail(self._series(spec))[-lookback_weeks:]
            if len(series) < MIN_HISTORY_POINTS:
                continue

            values = [v for _, v, _ in series]
            median, sigma = _robust_stats(values)

            for period, value, _volume in series:
                deviation = value - median
                if spec.direction == "down" and deviation >= 0:
                    continue
                z = abs(deviation) / sigma if sigma else 0.0
                relative = abs(deviation) / median if median else 0.0
                if z < Z_THRESHOLD or relative < MIN_RELATIVE_DEVIATION:
                    continue

                shortfall = abs(deviation)
                impact = shortfall * spec.impact_per_unit if spec.impact_per_unit else None
                direction_word = "below" if deviation < 0 else "above"
                findings.append({
                    "kpi": spec.key,
                    "label": spec.label,
                    "period": period,
                    "severity": "high" if z >= 6 else "medium",
                    "headline": (
                        f"{spec.label} for week commencing {period} was "
                        f"{value:,.0f} {spec.unit}".rstrip() +
                        f" - {relative * 100:.0f}% {direction_word} the {median:,.0f} norm."
                    ),
                    "observed": round(value, 2),
                    "expected": round(median, 2),
                    "deviation_pct": round(-relative * 100 if deviation < 0 else relative * 100, 1),
                    "impact_gbp": round(impact, 2) if impact else None,
                    "evidence": {
                        "robust_z_score": round(z, 2),
                        "baseline_median": round(median, 2),
                        "robust_sigma": round(sigma, 2),
                        "weeks_compared": len(series),
                        "impact_basis": spec.impact_note,
                        "detection": "median/MAD outlier test over the KPI's own history",
                    },
                })

        for finding in findings:
            finding["id"] = self.store.upsert_finding(finding)
        return findings

    # ------------------------------------------------------- agent explanation

    def explain(self, finding: dict[str, Any], runtime: Any, user_email: str = "watchtower@system") -> str:
        """Ask the agent to root-cause one finding using the live data."""
        if runtime is None or not getattr(runtime, "available", False):
            return ""

        prompt = (
            f"An automated KPI monitor flagged an anomaly. Investigate the root cause using the data.\n\n"
            f"KPI: {finding.get('label', finding['kpi'])}\n"
            f"Week commencing: {finding['period']}\n"
            f"Observed: {finding.get('observed')} against a {finding.get('expected')} baseline "
            f"({finding.get('deviation_pct')}%).\n\n"
            "Determine WHY. Check related datasets - weather, engineer shifts, regions, quotes, "
            "cancellation reasons - before concluding, and rule out alternatives explicitly. "
            "Reply in under 180 words: the cause, the evidence, the regions or segments affected, "
            "and one concrete recommendation. Do not restate the numbers above."
        )
        answer = runtime.run(prompt, user_email, None)
        if answer:
            self.store.set_finding_explanation(finding["id"], answer)
        return answer

    def scan_and_explain(self, runtime: Any, max_explanations: int = 3) -> list[dict[str, Any]]:
        """Full sweep: detect, then explain the most severe findings."""
        findings = self.scan()
        ranked = sorted(findings, key=lambda f: abs(f.get("deviation_pct") or 0), reverse=True)
        for finding in ranked[:max_explanations]:
            try:
                finding["explanation"] = self.explain(finding, runtime)
            except Exception as error:  # noqa: BLE001 - one failure must not stop the sweep
                print(f"[Watchtower] Explanation failed for {finding['kpi']}: {error}")
        return ranked
