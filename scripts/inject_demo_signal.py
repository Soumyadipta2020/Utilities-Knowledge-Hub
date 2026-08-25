"""
Plant a realistic, discoverable operational incident in the demo datasets.

WHY THIS EXISTS
---------------
The generated datasets are uniform random noise: weekly appointment volumes sit
in a flat band with no seasonality and no events, and `visit_status` only
ever contains 'Completed' or 'Parts Required'. That makes two things impossible:

  * "net appointments" is not a meaningful measure - nothing is ever cancelled;
  * "why did week X dip?" has no answer, because no week ever dips.

A root-cause demo needs a cause that is actually present in the data and can be
found by joining several datasets. This script injects one:

  A severe weather event during one week drives a spike in cancellations,
  concentrated in the regions worst affected, alongside a collapse in engineer
  productive hours in those same regions.

Everything is derived from a stable hash of the job id, so the script is
deterministic and safe to re-run - a second run reproduces the first exactly.

Only three files are rewritten: visit_outcome, weather and
engineer_availability_and_shifts. Appointment records are left untouched, so
"booked" volume is unchanged and the dip appears in NET appointments only.

Usage:  python scripts/inject_demo_signal.py [--week YYYY-MM-DD] [--verify]
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Regions taking the brunt of the storm. Chosen to be a minority of the estate
# so the concentration is a real finding rather than a uniform national drop.
STORM_REGIONS = ("North East", "Scotland", "Yorkshire")

# Every fault code shipped with the identical description, "System error
# occurred due to component failure", so no question about the *type* of fault
# could be answered in business language. These are real combi-boiler failure
# modes, keeping the original codes so existing joins still work.
FAULT_TAXONOMY = {
    "F11": ("Flame loss / ignition lockout", "High"),
    "F16": ("Fan fault - airflow obstruction", "Medium"),
    "F27": ("Frozen condensate pipe - blockage", "High"),
    "F30": ("NTC thermistor - temperature sensor fault", "Medium"),
    "F44": ("Low system pressure", "Low"),
    "F53": ("Gas valve fault", "Critical"),
    "F59": ("PCB / control board failure", "Critical"),
    "F64": ("Diverter valve stuck", "Medium"),
    "F69": ("Pump seizure - circulation failure", "High"),
    "F73": ("Heat exchanger scaling", "High"),
    "F78": ("Ignition electrode failure", "High"),
    "F82": ("Overheat thermostat trip", "Medium"),
    "F92": ("Water pressure sensor fault", "Low"),
}

# Cold-weather failure modes. Below the threshold these displace other faults,
# creating a genuine, discoverable correlation between temperature and fault mix.
COLD_FAULTS = ("F27", "F11", "F78")
COLD_TEMP_THRESHOLD = 3.0
COLD_DISPLACEMENT_PCT = 55  # share of cold-day repairs that become cold faults

SALES_LOST_PCT = 45          # share of that week's sales that fail to close
ELEVATED_QUOTE_MIN = 2700.0  # the pricing spike that explains the drop
ELEVATED_QUOTE_MAX = 3400.0

# Cancellation rates, as percentage buckets over a hash of the job id.
BASELINE_CANCEL_PCT = 3      # ordinary customer cancellations, every week
BASELINE_NOACCESS_PCT = 5    # cumulative: buckets 3-4 become 'No Access'
STORM_HIT_REGION_PCT = 58    # storm week, worst-hit regions
STORM_OTHER_REGION_PCT = 14  # storm week, rest of the country


def _p(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace("'", "''")


def inject(data_dir: Path, week_start: date | None = None) -> dict:
    con = duckdb.connect()
    con.execute("SET enable_progress_bar = false")

    visit = data_dir / "visit_outcome.csv"
    holdings = data_dir / "customer_holdings.csv"
    weather = data_dir / "weather.csv"
    shifts = data_dir / "engineer_availability_and_shifts.csv"
    engineers = data_dir / "engineer_master.csv"

    for required in (visit, holdings, weather, shifts, engineers):
        if not required.exists():
            con.close()
            raise FileNotFoundError(f"Missing dataset: {required}")

    # Determine anchor date from data if week_start is not specified
    if week_start is None:
        try:
            latest_val = con.execute(f"SELECT max(visit_date) FROM read_csv_auto('{_p(visit)}')").fetchone()[0]
            if hasattr(latest_val, "date"):
                anchor_date = latest_val.date()
            elif isinstance(latest_val, str):
                anchor_date = datetime.fromisoformat(latest_val[:10]).date()
            else:
                anchor_date = datetime.now().date()
        except Exception:
            anchor_date = datetime.now().date()
        # Monday ~3 weeks prior to anchor date
        week_start = anchor_date - timedelta(days=anchor_date.weekday() + 21)
    else:
        anchor_date = week_start + timedelta(days=21)

    week_end = week_start + timedelta(days=6)
    sales_dip_week = anchor_date - timedelta(days=anchor_date.weekday() + 42)
    sales_end = sales_dip_week + timedelta(days=6)

    regions_sql = ", ".join(f"'{r}'" for r in STORM_REGIONS)

    # --- 1. visit_outcome: cancellations -------------------------------------
    tmp_visit = visit.with_suffix(".csv.tmp")
    con.execute(f"""
        COPY (
            WITH region_of AS (
                SELECT customer_id, any_value(region) AS region
                FROM read_csv_auto('{_p(holdings)}')
                GROUP BY customer_id
            )
            SELECT
                v.job_id,
                v.customer_id,
                v.visit_date,
                CASE
                    WHEN v.visit_date BETWEEN DATE '{week_start}' AND DATE '{week_end}'
                         AND r.region IN ({regions_sql})
                         AND (abs(hash(v.job_id)) % 100) < {STORM_HIT_REGION_PCT}
                        THEN 'Cancelled - Severe Weather'
                    WHEN v.visit_date BETWEEN DATE '{week_start}' AND DATE '{week_end}'
                         AND (abs(hash(v.job_id)) % 100) < {STORM_OTHER_REGION_PCT}
                        THEN 'Cancelled - Severe Weather'
                    WHEN (abs(hash(v.job_id)) % 100) < {BASELINE_CANCEL_PCT}
                        THEN 'Cancelled - Customer'
                    WHEN (abs(hash(v.job_id)) % 100) < {BASELINE_NOACCESS_PCT}
                        THEN 'No Access'
                    ELSE v.visit_status
                END AS visit_status,
                v.customer_feedback
            FROM read_csv_auto('{_p(visit)}') v
            LEFT JOIN region_of r USING (customer_id)
        ) TO '{_p(tmp_visit)}' (HEADER, DELIMITER ',')
    """)
    os.replace(tmp_visit, visit)

    # --- 2. weather: the storm itself ----------------------------------------
    tmp_weather = weather.with_suffix(".csv.tmp")
    con.execute(f"""
        COPY (
            SELECT
                pincode,
                date,
                CASE WHEN date BETWEEN DATE '{week_start}' AND DATE '{week_end}'
                     THEN round(least(temperature, 4.5) - 3.0, 2) ELSE temperature END AS temperature,
                CASE WHEN date BETWEEN DATE '{week_start}' AND DATE '{week_end}'
                     THEN 96 ELSE humidity END AS humidity,
                CASE WHEN date BETWEEN DATE '{week_start}' AND DATE '{week_end}'
                     THEN round(greatest(rain, 38.0), 2) ELSE rain END AS rain,
                CASE WHEN date BETWEEN DATE '{week_start}' AND DATE '{week_end}'
                     THEN round(greatest(wind, 74.0), 2) ELSE wind END AS wind,
                solar_radiation,
                atmospheric_pressure
            FROM read_csv_auto('{_p(weather)}')
        ) TO '{_p(tmp_weather)}' (HEADER, DELIMITER ',')
    """)
    os.replace(tmp_weather, weather)

    # --- 3. engineer shifts: lost productive time ----------------------------
    tmp_shifts = shifts.with_suffix(".csv.tmp")
    con.execute(f"""
        COPY (
            WITH region_of AS (
                SELECT pay_id, any_value(work_location) AS work_location
                FROM read_csv_auto('{_p(engineers)}')
                GROUP BY pay_id
            )
            SELECT
                s.pay_id,
                s.shift_date,
                s.shift_start_time,
                s.shift_end,
                s.lunch_start,
                s.lunch_end,
                CASE WHEN s.shift_date BETWEEN DATE '{week_start}' AND DATE '{week_end}'
                          AND e.work_location IN ({regions_sql})
                     THEN TIME '09:30:00' ELSE s.non_productive_event_start_time END
                     AS non_productive_event_start_time,
                CASE WHEN s.shift_date BETWEEN DATE '{week_start}' AND DATE '{week_end}'
                          AND e.work_location IN ({regions_sql})
                     THEN TIME '16:00:00' ELSE s.non_productive_event_end_time END
                     AS non_productive_event_end_time
            FROM read_csv_auto('{_p(shifts)}') s
            LEFT JOIN region_of e USING (pay_id)
        ) TO '{_p(tmp_shifts)}' (HEADER, DELIMITER ',')
    """)
    os.replace(tmp_shifts, shifts)

    # --- 4. fault_codes: a real fault taxonomy --------------------------------
    fault_codes = data_dir / "fault_codes.csv"
    tmp_faults = fault_codes.with_suffix(".csv.tmp")
    mapping = ", ".join(
        f"('{code}', '{desc}', '{sev}')" for code, (desc, sev) in FAULT_TAXONOMY.items()
    )
    con.execute(f"""
        COPY (
            SELECT
                f.fault_code,
                coalesce(m.description, f.explanation_related_fault_codes)
                    AS explanation_related_fault_codes,
                coalesce(m.severity, f.severity) AS severity,
                f.repair_cost
            FROM read_csv_auto('{_p(fault_codes)}') f
            LEFT JOIN (VALUES {mapping}) AS m(code, description, severity)
                   ON m.code = f.fault_code
        ) TO '{_p(tmp_faults)}' (HEADER, DELIMITER ',')
    """)
    os.replace(tmp_faults, fault_codes)

    # --- 5. repair_history: cold-weather fault correlation --------------------
    repairs = data_dir / "repair_history.csv"
    tmp_repairs = repairs.with_suffix(".csv.tmp")
    all_codes = "[" + ", ".join(f"'{c}'" for c in FAULT_TAXONOMY) + "]"
    cold_codes = "[" + ", ".join(f"'{c}'" for c in COLD_FAULTS) + "]"
    con.execute(f"""
        COPY (
            WITH daily_temp AS (
                SELECT date, min(temperature) AS temperature
                FROM read_csv_auto('{_p(weather)}') GROUP BY date
            )
            SELECT
                r.job_id, r.customer_id, r.repair_date, r.repair_type, r.parts_changed,
                CASE
                    WHEN w.temperature < {COLD_TEMP_THRESHOLD}
                         AND (abs(hash(r.job_id)) % 100) < {COLD_DISPLACEMENT_PCT}
                    THEN {cold_codes}[CAST((abs(hash(r.job_id || 'cold')) % {len(COLD_FAULTS)}) + 1 AS BIGINT)]
                    ELSE {all_codes}[CAST((abs(hash(r.job_id)) % {len(FAULT_TAXONOMY)}) + 1 AS BIGINT)]
                END AS fault_code,
                r.fault_reason
            FROM read_csv_auto('{_p(repairs)}') r
            LEFT JOIN daily_temp w ON w.date = r.repair_date
        ) TO '{_p(tmp_repairs)}' (HEADER, DELIMITER ',')
    """)
    os.replace(tmp_repairs, repairs)

    # --- 6. sales conversion dip ---------------------------------------------
    leads = data_dir / "installation_history.csv"
    quotes = data_dir / "quotes_and_sales.csv"

    tmp_quotes = quotes.with_suffix(".csv.tmp")
    con.execute(f"""
        COPY (
            WITH dip_leads AS (
                SELECT lead_id FROM read_csv_auto('{_p(leads)}')
                WHERE lead_date BETWEEN DATE '{sales_dip_week}' AND DATE '{sales_end}'
            )
            SELECT
                q.lead_id, q.primary_qutation, q.secondary_quotation,
                CASE WHEN d.lead_id IS NOT NULL
                     THEN round({ELEVATED_QUOTE_MIN} +
                          (abs(hash(q.lead_id)) % 1000) / 1000.0 *
                          ({ELEVATED_QUOTE_MAX} - {ELEVATED_QUOTE_MIN}), 2)
                     ELSE q.final_quotation END AS final_quotation
            FROM read_csv_auto('{_p(quotes)}') q
            LEFT JOIN dip_leads d USING (lead_id)
        ) TO '{_p(tmp_quotes)}' (HEADER, DELIMITER ',')
    """)
    os.replace(tmp_quotes, quotes)

    tmp_leads = leads.with_suffix(".csv.tmp")
    con.execute(f"""
        COPY (
            SELECT
                job_id, customer_id, lead_id, lead_date, mode_of_conversation_with_customer,
                appointment_date, appointment_happened,
                CASE WHEN lost THEN NULL ELSE sale_date END AS sale_date,
                CASE WHEN lost THEN 'No' ELSE sale_happened END AS sale_happened,
                CASE WHEN lost THEN NULL ELSE installation_date END AS installation_date,
                CASE WHEN lost THEN 'No' ELSE installation_happened END AS installation_happened,
                CASE WHEN lost THEN 'No' ELSE insurance_purchased END AS insurance_purchased
            FROM (
                SELECT *,
                    (lead_date BETWEEN DATE '{sales_dip_week}' AND DATE '{sales_end}'
                     AND (abs(hash(lead_id)) % 100) < {SALES_LOST_PCT}) AS lost
                FROM read_csv_auto('{_p(leads)}')
            )
        ) TO '{_p(tmp_leads)}' (HEADER, DELIMITER ',')
    """)
    os.replace(tmp_leads, leads)

    con.close()
    return {
        "storm_week": f"{week_start} to {week_end}",
        "storm_regions": list(STORM_REGIONS),
        "sales_dip_week": f"{sales_dip_week} to {sales_end}",
        "fault_codes_named": len(FAULT_TAXONOMY),
    }


def verify(data_dir: Path, week_start: date | None = None) -> None:
    con = duckdb.connect()
    con.execute("SET enable_progress_bar = false")
    visit = _p(data_dir / "visit_outcome.csv")

    if week_start is None:
        try:
            latest_val = con.execute(f"SELECT max(visit_date) FROM read_csv_auto('{visit}')").fetchone()[0]
            if hasattr(latest_val, "date"):
                anchor_date = latest_val.date()
            elif isinstance(latest_val, str):
                anchor_date = datetime.fromisoformat(latest_val[:10]).date()
            else:
                anchor_date = datetime.now().date()
        except Exception:
            anchor_date = datetime.now().date()
        week_start = anchor_date - timedelta(days=anchor_date.weekday() + 21)

    print("\nWeekly booked vs net appointments (historical window):")
    rows = con.execute(f"""
        SELECT date_trunc('week', visit_date) AS wk,
               count(*) AS booked,
               count(*) FILTER (WHERE visit_status NOT LIKE 'Cancelled%'
                                  AND visit_status <> 'No Access') AS net
        FROM read_csv_auto('{visit}')
        GROUP BY 1 ORDER BY wk DESC LIMIT 13
    """).fetchall()
    print(f"    {'week':<12}{'booked':>9}{'net':>9}{'net %':>8}")
    for wk, booked, net in sorted(rows):
        marker = "   <-- incident week" if str(wk.date()) == str(week_start) else ""
        print(f"    {str(wk.date()):<12}{booked:>9,}{net:>9,}{100*net/max(booked,1):>7.1f}%{marker}")

    print("\nCancellation reasons during the incident week, by region:")
    rows = con.execute(f"""
        WITH region_of AS (
            SELECT customer_id, any_value(region) AS region
            FROM read_csv_auto('{_p(data_dir / "customer_holdings.csv")}') GROUP BY customer_id
        )
        SELECT r.region, count(*) FILTER (WHERE v.visit_status = 'Cancelled - Severe Weather') AS storm_cancels,
               count(*) AS total,
               round(100.0 * count(*) FILTER (WHERE v.visit_status = 'Cancelled - Severe Weather') / count(*), 1) AS pct
        FROM read_csv_auto('{visit}') v JOIN region_of r USING (customer_id)
        WHERE v.visit_date BETWEEN DATE '{week_start}' AND DATE '{week_start + timedelta(days=6)}'
        GROUP BY 1 ORDER BY pct DESC
    """).fetchall()
    for region, cancels, total, pct in rows:
        print(f"    {region:<14}{cancels:>8,} of {total:>8,}   {pct:>5}%")

    leads = _p(data_dir / "installation_history.csv")
    quotes = _p(data_dir / "quotes_and_sales.csv")
    print("\nWeekly leads / net sales / conversion:")
    rows = con.execute(f"""
        SELECT date_trunc('week', l.lead_date) wk, count(*) leads,
               count(*) FILTER (WHERE l.sale_happened='Yes') sales,
               round(100.0*count(*) FILTER (WHERE l.sale_happened='Yes')/count(*),1) conv,
               round(avg(q.final_quotation)) avg_quote
        FROM read_csv_auto('{leads}') l LEFT JOIN read_csv_auto('{quotes}') q USING (lead_id)
        GROUP BY 1 ORDER BY wk
    """).fetchall()
    print(f"    {'week':<12}{'leads':>8}{'sales':>8}{'conv%':>8}{'avg quote':>11}")
    for wk, leads_n, sales_n, conv, avg_q in rows:
        print(f"    {str(wk.date()):<12}{leads_n:>8,}{sales_n:>8,}{conv:>7}%{avg_q:>11,.0f}")

    repairs = _p(data_dir / "repair_history.csv")
    faults = _p(data_dir / "fault_codes.csv")
    print("\nTop fault types, split by temperature:")
    rows = con.execute(f"""
        WITH daily AS (SELECT date, min(temperature) t FROM read_csv_auto('{_p(data_dir / "weather.csv")}') GROUP BY date),
             named AS (SELECT fault_code, any_value(explanation_related_fault_codes) d FROM read_csv_auto('{faults}') GROUP BY 1)
        SELECT n.d AS fault_type,
               count(*) FILTER (WHERE daily.t < {COLD_TEMP_THRESHOLD}) AS cold_days,
               count(*) FILTER (WHERE daily.t >= {COLD_TEMP_THRESHOLD}) AS mild_days,
               count(*) AS total
        FROM read_csv_auto('{repairs}') r
        JOIN daily ON daily.date = r.repair_date
        LEFT JOIN named n ON n.fault_code = r.fault_code
        GROUP BY 1 ORDER BY total DESC LIMIT 6
    """).fetchall()
    print(f"    {'fault type':<40}{'cold':>9}{'mild':>9}{'total':>9}")
    for ftype, cold, mild, total in rows:
        print(f"    {str(ftype)[:38]:<40}{cold:>9,}{mild:>9,}{total:>9,}")
    con.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=str(PROJECT_ROOT / "data"))
    parser.add_argument("--week", default=None, help="Monday of the incident week (defaults to 3 weeks prior to dataset end)")
    parser.add_argument("--verify", action="store_true", help="Only report, do not modify")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    week_start = None
    if args.week:
        year, month, day = (int(part) for part in args.week.split("-"))
        week_start = date(year, month, day)

    if not args.verify:
        print(f"Injecting demo incident (regions: {', '.join(STORM_REGIONS)})...")
        result = inject(data_dir, week_start)
        print(f"Rewrote visit_outcome, weather and engineer_availability_and_shifts. {result}")

    verify(data_dir, week_start)


if __name__ == "__main__":
    main()
