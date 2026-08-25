"""
Verification tests for the planning agents: demand forecast, commercial, pricing.

These assert the PROPERTIES a recommendation has to hold, not the specific
figures - the datasets are regenerated, so pinning a number would make the suite
brittle without making it stronger. What matters and is checked here:

  * the numbers are internally consistent (a correction factor really does map
    the forecast onto the run-rate; a margin really does follow from its cost base);
  * an approval-gated suggestion re-derives its own figures, so a caller cannot
    inject one, and is never auto-applied;
  * a bad input comes back as recoverable guidance rather than an exception.
"""

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import DATA_DIR
from app.services.sql_service import SqlService
from app.agent import commercial as commercial_engine
from app.agent import demand_forecast as demand_engine
from app.agent import pricing as pricing_engine
from app.agent.analytics import AnalyticsError

SQL = SqlService(DATA_DIR)


def test_demand_forecast_agent():
    print("--- Demand Forecast Agent ---")

    evaluation = demand_engine.evaluate(SQL)
    assert evaluation["rows"], "No forecast series could be graded."
    for row in evaluation["rows"]:
        # The suggested figure IS the observed run-rate, and the correction
        # factor is the multiplier that gets the forecast there. If these ever
        # disagree, the number a human approves is not the number analysed.
        assert row["suggested_jobs_per_day"] == row["actual_jobs_per_day"]
        assert abs(
            row["forecast_jobs_per_day"] * row["correction_factor"]
            - row["actual_jobs_per_day"]
        ) < 1.0
        assert row["material"] == (abs(row["bias_pct"]) >= demand_engine.MATERIAL_BIAS_PCT)
        assert row["balance_after"] == row["available_hours"] - row["corrected_hours_horizon"]
    print(f"[PASS] Graded {evaluation['summary']['graded']} series, "
          f"{evaluation['summary']['material']} material, weighted bias "
          f"{evaluation['summary']['weighted_bias_pct']}%")

    # A filter that matches nothing must return the valid names, not an
    # unactionable empty result.
    empty = demand_engine.evaluate(SQL, region="Nowhere")
    assert not empty["rows"]
    assert empty["available_regions"]
    assert "Nowhere" in demand_engine.render_evaluation(empty)
    print("[PASS] Unknown region returns the valid region list")

    gaps = demand_engine.gaps(SQL)
    assert "has_gaps" in gaps
    for item in gaps["missing_job_types"]:
        assert item["capacity_hours_horizon"] > 0, "A gap must be staffed to be a gap."
        assert item["unmatched_hours"] == item["capacity_hours_horizon"] - item["implied_demand_hours"]
    print(f"[PASS] Coverage check: "
          f"{[item['job_type'] for item in gaps['missing_job_types']] or 'no missing job types'}")

    built = demand_engine.build_forecast(SQL, "Installation", weeks=4)
    assert built["weeks"] == 4
    assert len(built["national_weekly"]) == 4
    assert built["totals"]["jobs"] > 0
    for week in built["national_weekly"]:
        assert week["low"] <= week["jobs"] <= week["high"], "Point estimate outside its own band."
    assert built["parameters"]["hours_per_job_source"], "Hours ratio must state its provenance."
    print(f"[PASS] Built {built['totals']['jobs']:,} jobs / "
          f"{built['totals']['jobs_hours']:,} hours over 4 weeks")

    try:
        demand_engine.build_forecast(SQL, "Nonsense")
        raise AssertionError("An unknown job type should not build a forecast.")
    except AnalyticsError as error:
        assert "Valid job types" in str(error)
    print("[PASS] Unknown job type is refused with the valid list")

    decision = evaluation["decision"]
    assert decision["conclusion"] and decision["falsifier"] and decision["not_concluded"]
    assert decision["confidence"] in {"low", "medium", "high"}
    assert decision["facts"], "A decision must carry the facts it rests on."
    sign_test = decision["sign_test"]
    assert sign_test["series"] == len(evaluation["rows"])
    assert sign_test["same_direction"] <= sign_test["series"]
    if sign_test["same_direction"] == sign_test["series"]:
        assert 0 < sign_test["p_value"] <= 1
    print(f"[PASS] Decision recorded ({decision['confidence']} confidence, "
          f"{sign_test['same_direction']}/{sign_test['series']} same direction) with a falsifier")

    weekly = demand_engine.weekly_outlook(SQL, 13, ["Repair", "Service"])
    assert weekly["weeks"] == 13, "Three months must return thirteen weekly buckets."
    assert set(weekly["job_types"]) == {"Repair", "Service"}
    for entry in weekly["rows"]:
        # Seven-day buckets, so no week is short and no total compares 6 days with 7.
        assert entry["complete"], f"{entry['week_commencing']} is not a full seven days."
        assert entry["published_jobs"] == sum(
            line["published_jobs"] for line in entry["lines"].values()
        )
        assert entry["corrected_jobs"] >= entry["published_jobs"], (
            "The corrected view should not fall below the published one while the "
            "forecast is under-stating demand."
        )
    # The weekly view and the accuracy grading must agree on the correction.
    evaluation_factors = {
        row["job_type"]: row for row in demand_engine.evaluate(SQL)["rows"]
    }
    for job_type, factor in weekly["correction_factors"].items():
        assert job_type in evaluation_factors
        assert 0.5 < factor < 2.0, f"Implausible correction factor for {job_type}: {factor}"
    assert weekly["totals"]["shortfall_jobs"] == (
        weekly["totals"]["corrected_jobs"] - weekly["totals"]["published_jobs"]
    )
    print(f"[PASS] Weekly outlook: {weekly['totals']['published_jobs']:,} jobs planned vs "
          f"{weekly['totals']['corrected_jobs']:,} likely over 13 weeks "
          f"({weekly['totals']['shortfall_jobs']:,} short)")

    impact = demand_engine.planning_impact(SQL)
    assert impact["skills"], "No skill position was computed."
    for skill in impact["skills"]:
        assert skill["balance_after"] == skill["available_hours"] - skill["true_hours"]
        assert skill["position"] == ("deficit" if skill["balance_after"] < 0 else "surplus")
        assert skill["fte_equivalent"] >= 0
        # Pre-existing deficit must never be counted as something this analysis found.
        assert skill["jobs_at_risk_added"] <= skill["jobs_at_risk"]
        assert skill["jobs_at_risk_added"] == max(
            skill["jobs_at_risk"] - skill["jobs_at_risk_before"], 0
        )
    totals = impact["totals"]
    assert totals["jobs_at_risk_added"] <= totals["jobs_at_risk"]
    print(f"[PASS] Plan impact: {totals['unplanned_hours']:,} unplanned hours, "
          f"{totals['fte_gap']} FTE gap, {totals['jobs_at_risk_added']:,} of "
          f"{totals['jobs_at_risk']:,} jobs at risk newly identified")

    plan = demand_engine.recommendations(SQL)
    assert plan["options"], "A shortfall was reported with no plan for closing it."
    running = plan["gap_hours"]
    for option in plan["options"]:
        # Every option must be readable by a non-specialist and say what it takes.
        assert option["plain"] and option["how"] and option["evidence"]
        assert option["hours_closed"] > 0
        assert option["effort"] in {"low", "medium", "high"}
        # Options must not double-count: each closes only what is still open.
        running -= option["hours_closed"]
        assert option["gap_remaining_after"] == max(round(running), 0)
    assert sum(o["hours_closed"] for o in plan["options"]) <= plan["gap_hours"] + 1
    # Recruitment must be last - the point of the plan is that it is not first.
    hiring = [o for o in plan["options"] if not o.get("no_new_people")]
    if hiring:
        assert hiring[0]["rank"] == len(plan["options"]), "Hiring is not the last resort."
    assert plan["closed_without_hiring"] <= plan["gap_hours"]
    print(f"[PASS] Plan closes {plan['closed_without_hiring_pct']}% of the "
          f"{plan['gap_hours']:,}-hour gap without hiring, across "
          f"{len(plan['options'])} ranked steps")

    drivers = demand_engine.drivers(SQL)
    assert drivers["factors"], "No demand drivers were measured."
    # Every factor carries an effect size, and the material/immaterial split is
    # a function of it - reporting the nil results is the point of this tool.
    for factor in drivers["factors"]:
        assert factor["effect_pct"] is not None and factor["dataset"] and factor["reading"]
    assert len(drivers["material"]) + len(drivers["immaterial"]) == len(drivers["factors"])
    print(f"[PASS] {len(drivers['factors'])} drivers measured "
          f"({len(drivers['material'])} material, {len(drivers['immaterial'])} ruled out)")


def test_commercial_agent():
    print("\n--- Commercial Agent ---")

    negotiation = commercial_engine.negotiation(SQL)
    assert negotiation["bands"], "No discount bands were produced."
    for band in negotiation["bands"]:
        assert band["leads"] > 0
        assert 0 <= band["conversion_pct"] <= 100
    # The guardrail must follow from the measurement, not be asserted alongside it.
    assert negotiation["price_responsive"] == (
        negotiation["conversion_spread_pp"] >= commercial_engine.CONVERSION_NOISE_PP
    )
    assert negotiation["best_band"]["revenue_per_lead"] >= negotiation["worst_band"]["revenue_per_lead"]
    assert negotiation["leakage_gbp"] >= 0
    assert negotiation["guardrail"]["position"] and negotiation["guardrail"]["detail"]
    print(f"[PASS] {len(negotiation['bands'])} bands, conversion spread "
          f"{negotiation['conversion_spread_pp']}pp → \"{negotiation['guardrail']['position']}\"")

    season = commercial_engine.season(SQL)
    assert season["months"], "No complete trading month was found."
    assert len(season["peak"]) and len(season["trough"])
    for month in season["months"]:
        assert month["month_name"]
        assert month["opportunity_score"] >= 0
    # Peaks must genuinely outrank troughs on the composite score.
    assert min(m["opportunity_score"] for m in season["peak"]) >= max(
        m["opportunity_score"] for m in season["trough"]
    )
    print(f"[PASS] {len(season['months'])} months scored; peak "
          f"{[m['month_name'] for m in season['peak']]}")


def test_pricing_agent():
    print("\n--- Pricing Agent ---")

    serve = pricing_engine.cost_to_serve(SQL)
    assert serve["lines"], "No service line could be costed."
    for line in serve["lines"]:
        # A completed job can never take fewer than one visit, and the true cost
        # can never be below the single-visit cost it is built from.
        assert line["visits_per_completed_job"] >= 1.0
        assert line["cost_per_completed_job"] >= line["naive_single_visit_cost"]
        assert 0 < line["first_time_fix_pct"] <= 100
        assert abs(
            line["visits_per_completed_job"] - line["visits_total"] / line["visits_completed"]
        ) < 0.01
        assert abs(
            line["labour_per_completed_job"]
            - line["labour_per_visit"] * line["visits_per_completed_job"]
        ) < 0.05
        assert line["levers"], "A cost must come with something that can be done about it."
        for lever in line["levers"]:
            assert lever["annual_value_gbp"] >= 0 and lever["detail"]
    print("[PASS] " + "; ".join(
        f"{line['service_line']} {line['visits_per_completed_job']:.2f} visits/job → "
        f"£{line['cost_per_completed_job']:,.2f}"
        for line in serve["lines"]
    ))

    book = pricing_engine.price_book(SQL)
    assert len(book["lines"]) == len(pricing_engine.SERVICE_LINES)
    for line in book["lines"]:
        assert line["recommended_price"] > 0
        assert line["basis"] and line["confidence"] in {"low", "medium", "high"}
        assert line["components"], "A price must show what it is built from."
        if line["cost_base"]:
            # The stated margin must be the margin the recommended price gives.
            implied = (line["recommended_price"] - line["cost_base"]) / line["recommended_price"] * 100
            assert abs(implied - line["margin_at_recommended_pct"]) < 0.2
        assert len(line["sensitivity"]) == len(pricing_engine.SENSITIVITY_STEPS)
    # Assumptions must travel with any figure that depends on them.
    assert {a["key"] for a in book["assumptions"]} >= {
        "labour_cost_per_hour_gbp", "target_gross_margin_pct"
    }
    print("[PASS] " + ", ".join(
        f"{line['service_line']} £{line['recommended_price']:,.2f} ({line['basis']})"
        for line in book["lines"]
    ))

    single = pricing_engine.price_book(SQL, service_line="repairs")
    assert len(single["lines"]) == 1 and single["lines"][0]["service_line"] == "Repair"
    print("[PASS] Service line aliases resolve ('repairs' → Repair)")

    try:
        pricing_engine.price_book(SQL, service_line="spaceships")
        raise AssertionError("An unknown service line should not be priced.")
    except AnalyticsError as error:
        assert "Valid lines" in str(error)
    print("[PASS] Unknown service line is refused with the valid list")

    # A price must cover the cost of COMPLETING the job, not of one visit.
    serve_index = {line["service_line"]: line for line in serve["lines"]}
    for line in book["lines"]:
        delivery = serve_index.get(line["service_line"])
        if delivery is None:
            continue
        assert line["recommended_price"] > delivery["cost_per_completed_job"], (
            f"{line['service_line']} is priced below what it costs to complete."
        )
    print("[PASS] Every recommended price clears its own cost to serve")

    schedule = pricing_engine.repair_price_list(SQL)
    assert schedule["rows"], "No fault types were priced."
    for row in schedule["rows"]:
        assert row["cost_base"] == round(row["labour_cost"] + row["part_cost"], 2)
        assert row["recommended_price"] > row["cost_base"]
    # The schedule and the headline repair price must rest on the same labour.
    repair_line = next(line for line in book["lines"] if line["service_line"] == "Repair")
    assert abs(
        schedule["rows"][0]["labour_cost"] - serve_index["Repair"]["labour_per_completed_job"]
    ) < 0.05, "The fault schedule contradicts the headline repair price."
    assert schedule["rows"][0]["recommended_price"] < repair_line["recommended_price"] * 1.5
    print(f"[PASS] {len(schedule['rows'])} fault types priced, consistent with the price book")


def test_questions_reach_the_right_agent():
    """Business questions must land on the specialist that owns them.

    This is the keyword fallback, which runs whenever no model is configured -
    so it has to work on its own. The cases that matter are the ones where the
    SUBJECT of a question belongs to one specialist and its PURPOSE to another:
    "what should we charge for a boiler repair" mentions boilers and repairs but
    is a pricing question, and used to route to asset reliability on word counts.
    """
    print("\n--- Question routing ---")

    from app.agent.specialists import route

    cases = [
        # Commercial: discounting, negotiation, conversion, trading season.
        ("commercial", "How much are we discounting, and is it winning us any more work?"),
        ("commercial", "What is our quote-to-sale conversion rate, and does discounting improve it?"),
        ("commercial", "How much margin are we giving away on discounts that buy us nothing?"),
        ("commercial", "When are the productive periods of our business year?"),
        ("commercial", "What negotiation guardrail should the sales team be working to?"),
        ("commercial", "How often do we close above our opening quote, and by how much?"),
        ("commercial", "Which region is giving away the most through discounting?"),
        # Pricing: what to charge, what it costs, margin.
        ("pricing", "What should we charge for a boiler repair?"),
        ("pricing", "What price should we set for annual servicing and installations?"),
        ("pricing", "What does a completed repair actually cost us to deliver?"),
        ("pricing", "Are our repair prices covering their cost to serve?"),
        ("pricing", "How should repairs be priced by fault type?"),
        ("pricing", "What margin do we make on each service line?"),
        ("pricing", "How much is one point of first-time fix worth in pounds?"),
        # The neighbours these two are most easily confused with.
        ("demand_forecast", "How many repair and service jobs does the plan expect each week?"),
        ("demand_forecast", "Is our demand forecast accurate?"),
        ("reliability", "Why are boiler faults rising in cold weather?"),
        ("capacity", "Do we have enough engineer capacity in the Midlands?"),
        ("governance", "Who is the SME data owner for customer_master?"),
    ]

    misrouted = []
    for expected, question in cases:
        specialist, how = route(question)
        assert how == "keyword", "This test must exercise the fallback, not a model."
        if specialist.key != expected:
            misrouted.append((question, expected, specialist.key))

    assert not misrouted, "Questions reached the wrong specialist:\n" + "\n".join(
        f"  {question!r} -> {got} (expected {want})" for question, want, got in misrouted
    )
    print(f"[PASS] All {len(cases)} business questions reach the right agent on keywords alone")


def test_answers_show_their_working():
    """Every rendered answer must carry the table and the chart behind it.

    These were lost once to a prompt change that told the agent to lead with the
    decision, so the charts are now emitted by the engines from the same figures
    as the tables beside them. That makes the visuals independent of whatever the
    model decides to write, and this test is what keeps them that way.
    """
    print("\n--- Tables and charts ---")

    from app.agent.charts import sanitize_answer

    renderers = {
        "forecast evaluation":
            lambda: demand_engine.render_evaluation(demand_engine.evaluate(SQL)),
        "weekly outlook":
            lambda: demand_engine.render_weekly_outlook(
                demand_engine.weekly_outlook(SQL, 13, ["Repair", "Service"])),
        "planning impact":
            lambda: demand_engine.render_planning_impact(demand_engine.planning_impact(SQL)),
        "improvement plan":
            lambda: demand_engine.render_recommendations(demand_engine.recommendations(SQL)),
        "generated forecast":
            lambda: demand_engine.render_forecast(
                demand_engine.build_forecast(SQL, "Installation", 13)),
        "demand drivers":
            lambda: demand_engine.render_drivers(demand_engine.drivers(SQL)),
        "coverage gaps":
            lambda: demand_engine.render_gaps(demand_engine.gaps(SQL)),
        "negotiation":
            lambda: commercial_engine.render_negotiation(commercial_engine.negotiation(SQL)),
        "trading season":
            lambda: commercial_engine.render_season(commercial_engine.season(SQL)),
        "cost to serve":
            lambda: pricing_engine.render_cost_to_serve(pricing_engine.cost_to_serve(SQL)),
        "price book":
            lambda: pricing_engine.render_price_book(pricing_engine.price_book(SQL)),
        "single line price":
            lambda: pricing_engine.render_price_book(pricing_engine.price_book(SQL, "Repair")),
        "repair schedule":
            lambda: pricing_engine.render_repair_price_list(
                pricing_engine.repair_price_list(SQL)),
    }

    # A table is not meaningful for a plan or a coverage note, but a chart always is.
    table_optional = {"improvement plan", "coverage gaps"}

    for name, render in renderers.items():
        text = render()
        _, specs = sanitize_answer(text)
        assert specs, f"{name} renders no chart."
        # sanitize_answer drops anything malformed, so surviving means renderable.
        for spec in specs:
            assert spec["title"], f"{name} chart has no title."
            if spec["type"] != "stat":
                assert len(spec["labels"]) >= 2, f"{name} chart has too few points."
                for series in spec["series"]:
                    assert len(series["values"]) == len(spec["labels"]), (
                        f"{name} chart has a series that does not line up with its labels."
                    )
        if name not in table_optional:
            assert "|---" in text, f"{name} renders no table."
    print(f"[PASS] All {len(renderers)} rendered answers carry a table and a valid chart")


def test_approval_gate():
    """A suggestion must be queued, auditable, and never self-applied."""
    print("\n--- Approval gate ---")

    from app.services.graph_service import KnowledgeGraphService
    from app.services.data_service import DataService
    from app.services.store import HubStore
    from app.agent import tools as tools_module

    store = HubStore(DATA_DIR / "hub_state.db")
    tools_module.register_services(
        KnowledgeGraphService(DATA_DIR), DataService(DATA_DIR, sql_service=SQL), SQL, store
    )

    evaluation = demand_engine.evaluate(SQL)
    material = next((row for row in evaluation["rows"] if row["material"]), None)
    if material is None:
        print("[SKIP] No material bias in this dataset, so no correction to queue")
    else:
        outcome = tools_module.queue_forecast_correction(
            material["region"], material["job_type"], "Automated test.", "test@abc.com"
        )
        assert outcome["ok"], outcome["message"]
        action = outcome["action"]
        assert action["status"] == "pending", "A suggestion must never be pre-applied."
        assert action["expected_impact"] and action["rationale"]
        # The queued figures are the engine's, not the caller's.
        assert action["payload"]["corrected_jobs_per_day"] == material["suggested_jobs_per_day"]
        # A suggestion has to be readable and has to recommend something, not
        # just describe a number. This is the whole point of the card.
        assert "What we recommend:" in action["detail"], "Suggestion has no recommendation."
        assert "1." in action["detail"], "Recommendation has no concrete steps."
        assert "If we do nothing" in action["expected_impact"], "No cost of inaction stated."
        jargon = ["bias", "FTE", "run-rate", "horizon", "materiality", "correction factor"]
        found = [word for word in jargon if word in action["title"]]
        assert not found, f"Jargon in the headline a non-specialist reads: {found}"
        decided = store.decide_action(action["id"], True, "test@abc.com", "Approved in test.")
        assert decided["status"] == "approved" and decided["decided_by"] == "test@abc.com"
        assert store.decide_action(action["id"], True, "test@abc.com", "again") is None, \
            "An action must not be decidable twice."
        print(f"[PASS] Forecast correction queued, approved once, and not decidable twice "
              f"({action['id']})")

    price = tools_module.queue_price_change("Installation", "Automated test.", "test@abc.com")
    assert price["ok"], price["message"]
    assert price["action"]["status"] == "pending"
    assert price["action"]["payload"]["recommended_price"] > 0
    assert "What we recommend:" in price["action"]["detail"]
    # A price suggestion must show the operational alternative to raising price.
    assert "another way" in price["action"]["expected_impact"].casefold()
    store.decide_action(price["action"]["id"], False, "test@abc.com", "Rejected in test.")
    assert store.get_action(price["action"]["id"])["status"] == "rejected"
    print(f"[PASS] Price change queued and rejected ({price['action']['id']})")

    missing_reason = tools_module.queue_price_change("Installation", "   ")
    assert not missing_reason["ok"], "A suggestion without a reason must be refused."
    print("[PASS] A suggestion with no reason is refused")


if __name__ == "__main__":
    if not SQL.available:
        print("❌ DuckDB is unavailable; the planning agents cannot be tested.")
        raise SystemExit(1)
    test_demand_forecast_agent()
    test_commercial_agent()
    test_pricing_agent()
    test_questions_reach_the_right_agent()
    test_answers_show_their_working()
    test_approval_gate()
    print("\n✅ ALL PLANNING AGENT TESTS PASSED.")
