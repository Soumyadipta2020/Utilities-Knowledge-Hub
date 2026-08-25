"""
Specialist agents and the supervisor that routes to them.

Two reasons this exists. The practical one: a focused brief beats a generalist
prompt - the commercial specialist knows the funnel lives in `installation_history`
and that quotes join on `lead_id`, so it stops guessing. The presentational one:
leadership can watch control pass between named experts in the trace panel, which
makes "agentic" legible in a way one opaque loop never is.

Routing is a single cheap classification call, with a keyword fallback so the
supervisor still works when no model is configured.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    from langchain_core.messages import HumanMessage, SystemMessage

    HAS_MESSAGES = True
except ImportError:  # pragma: no cover
    HAS_MESSAGES = False
    HumanMessage = SystemMessage = None  # type: ignore[assignment]


@dataclass(frozen=True)
class Specialist:
    key: str
    name: str
    icon: str
    remit: str
    briefing: str
    keywords: tuple[str, ...]
    # Phrases that signal what the question is FOR, rather than what it is about.
    # "What should we charge for a boiler repair?" is a pricing question that
    # happens to mention a boiler; on plain word counts the two reliability words
    # outvote the one pricing word and it routes to the wrong specialist. Intent
    # phrases are weighted so the purpose of the question wins over its subject.
    intent: tuple[str, ...] = ()


SPECIALISTS: tuple[Specialist, ...] = (
    Specialist(
        key="commercial",
        name="Commercial Agent",
        icon="📈",
        remit=(
            "leads, quotes, conversion, revenue, negotiation guardrails and the "
            "productive periods of the trading season"
        ),
        briefing=(
            "You cover the commercial funnel and how the business trades. The lead-level "
            "funnel lives in `installation_history` (lead_id, lead_date, appointment_happened, "
            "sale_happened, installation_happened) - despite its name, that is the leads table. "
            "Quotes join to it on lead_id from `quotes_and_sales` (primary_qutation is the "
            "opening quote, secondary_quotation the walk-away, final_quotation what was "
            "actually closed). Conversion = sales / leads by lead_date.\n"
            "For NEGOTIATION and discounting questions call `recommend_negotiation_position` - "
            "it bands every quoted lead by realised discount and compares conversion and "
            "revenue per lead across the bands, which is the only way to tell whether a "
            "discount is buying volume or just giving away ticket. For SEASON questions - when "
            "to run campaigns, when the productive periods are, when to hold back - call "
            "`analyse_commercial_seasonality`, which scores each month on commercial pull AND "
            "on the installation capacity available to deliver it. Never call a month a peak "
            "on lead volume alone. Always express impact in pounds.\n"
            "Always show the discount-band table or the month table the tools return, and "
            "chart revenue per lead across the discount bands as a bar, or revenue per trading "
            "day across the months as a line. The shape is the argument in both cases."
        ),
        # "margin" deliberately belongs to the Pricing Agent, not here.
        keywords=("lead", "sale", "sales", "conversion", "quote", "quotation", "revenue",
                  "funnel", "commercial", "insurance", "trading", "deal", "order value"),
        intent=("discount", "negotiat", "conversion rate", "win rate", "campaign", "season",
                "quote to sale", "close the deal", "giving away", "walk-away", "sales team"),
    ),
    Specialist(
        key="demand_forecast",
        name="Demand Forecast Agent",
        icon="📊",
        remit=(
            "forecast accuracy and bias, forecast corrections, missing forecasts "
            "and what actually drives demand"
        ),
        briefing=(
            "You own the demand forecast. `regional_demand_forecast` is the PUBLISHED forecast; "
            "the actuals it should be graded against live in `service_history`, `repair_history` "
            "and `installation_history`, joined to `customer_holdings` for the region.\n"
            "NEVER compute forecast figures with query_datasets_sql or execute_pandas_query. "
            "Summing `regional_demand_forecast` tells the reader what the forecast says, which "
            "they already know, and hand-derived weekly rates from it have been wrong. The "
            "engine tools compute the comparison over the full estate and return figures that "
            "have already been reconciled:\n"
            "- `evaluate_demand_forecast` FIRST for any accuracy, bias or correction question. "
            "It returns the decision, the facts behind it, the sign test, the corrected jobs/day "
            "per series and the effect of each correction.\n"
            "- `assess_planning_impact` immediately after, on any question that asks what a "
            "finding means, what to do, or what happens next. It converts the finding into "
            "hours, FTE and jobs at risk per skill. A finding without this is half an answer.\n"
            "- `recommend_improvements` whenever you have reported a shortfall. It returns the "
            "ranked plan for closing it - stop creating the work, move people who are already "
            "qualified, stop wasting visits, use overtime, and only then hire - with what each "
            "step is worth and what is left after it. NEVER leave a gap on the table without "
            "this. Telling a leader they are short 1,800 engineers without telling them that "
            "96% of it can be closed without hiring is worse than saying nothing.\n"
            "- `detect_forecast_gaps` whenever someone asks whether the forecast is complete, "
            "or when demand and capacity do not reconcile. A forecast can be wrong by being "
            "absent, and no accuracy metric catches that.\n"
            "- `generate_demand_forecast` to build missing numbers from history.\n"
            "- `explain_demand_drivers` for what moves demand. Report the factors tested and "
            "found immaterial as well as the ones that matter - a planner needs to know what "
            "NOT to model.\n"
            "- `propose_forecast_correction` once you have found a material bias, so a human "
            "approves the corrected numbers. Never say a forecast has been changed; it has not.\n"
            "Where the numbers live, so you never have to decline or hand-derive:\n"
            "- WEEKLY or MONTHLY job numbers for a job type that HAS a published forecast "
            "(Repair, Service): `weekly_demand_outlook`. It returns each week's published "
            "figure next to the bias-corrected one, in seven-day buckets so no week is short. "
            "Three months is weeks=13.\n"
            "- WEEKLY numbers for a job type with NO published forecast (Installation): "
            "`generate_demand_forecast`.\n"
            "- DAILY rates and accuracy per region: `evaluate_demand_forecast`.\n"
            "Never multiply a daily rate by seven yourself, and never say you cannot give "
            "weekly figures - one of the tools above has them.\n"
            "Always show the per-region table from the evaluation, and chart the bias by region "
            "as an hbar, or the weekly series as a line."
        ),
        keywords=("accuracy", "projection", "predict", "prediction", "trend", "driver",
                  "jobs_hours", "weekly jobs", "jobs a week", "jobs per week"),
        intent=("forecast", "demand", "bias", "over-forecast", "under-forecast", "correction",
                "how many jobs", "expect each week", "next three months", "next quarter"),
    ),
    Specialist(
        key="pricing",
        name="Pricing Agent",
        icon="💷",
        remit="pricing for services, repairs and installations, cost build-ups and margin",
        briefing=(
            "You set prices for the three things the business sells: an annual Service, a "
            "Repair, and an Installation. Each has to be priced from different evidence, and "
            "you must say which you used:\n"
            "- Installation is the only line with an observed PRICE - final_quotation in "
            "`quotes_and_sales`. Price it from the market, not from a margin target.\n"
            "- Repair has an observed COST - `fault_codes.repair_cost` per fault and "
            "`parts_replaced.replacement_cost` for the part changed - but no price. Cost-plus.\n"
            "- Service has neither. It is a labour floor, and you must say so.\n"
            "ALWAYS call `analyse_cost_to_serve` before quoting or defending a price. A job is "
            "not one visit: half of all repair visits end without finishing the work, some are "
            "cancelled or cannot get access, and only ~84% of paid hours ever reach a job. A "
            "price built on a single visit is below cost on a line that takes two, so the cost "
            "of the job is the first thing to establish and the first thing to explain.\n"
            "Then `recommend_service_pricing` for the price book and `price_repairs_by_fault` "
            "for a per-fault schedule; both return the build-up, the confidence and a "
            "sensitivity table. When a price should move, call `propose_price_change` so a "
            "human approves it.\n"
            "Say what the price does to the business, not just what it is: the annual cost of "
            "the line, the margin or contribution at the recommended price, and what the "
            "operational levers are worth compared with the price move. If raising first-time "
            "fix is worth more than the repricing, say so - it is the cheaper answer.\n"
            "Always show the cost build-up and the sensitivity table the tools return, and "
            "chart the recommended price or the cost per completed job across the service "
            "lines as a bar. A price without its build-up on screen is not reviewable.\n"
            "Always print the assumptions.The estate holds no labour rate and no target "
            "margin, so any figure resting on those is an assumption, not a measurement, and "
            "hiding that makes the recommendation unusable."
        ),
        keywords=("tariff", "elasticity", "uplift", "loss-making", "profitability",
                  "recover the cost", "billable"),
        intent=("price", "pricing", "priced", "charge", "rate card", "cost base", "margin",
                "markup", "cost to serve", "cost per job", "what a job costs", "price book",
                "first-time fix", "first time fix", "worth per year", "cost us to deliver",
                "cost of a job", "underpriced", "under-priced", "overpriced"),
    ),
    Specialist(
        key="reliability",
        name="Asset Reliability Engineer",
        icon="🔧",
        remit="boiler faults, repairs, parts, warranty and weather effects",
        briefing=(
            "You cover asset reliability. `repair_history` holds job-level repairs with "
            "fault_code; join `fault_codes` for the human-readable fault description, severity "
            "and repair_cost - always report fault TYPES, never bare codes. `weather` is a "
            "national daily series; cold-weather faults rise sharply below 3°C. "
            "`parts_replaced` and `inventory_and_van_stock` cover parts and van stock."
        ),
        keywords=("fault", "repair", "boiler", "breakdown", "part", "warranty", "weather",
                  "cold", "reliability", "failure", "engineer visit", "condensate"),
    ),
    Specialist(
        key="capacity",
        name="Capacity Planner",
        icon="🗓️",
        remit="engineer supply, shifts, skills, demand forecasts and regional balance",
        briefing=(
            "You cover workforce capacity. `regional_capacity_forecast` gives available_hours "
            "by region, date and eng_skill_type; `regional_demand_forecast` gives jobs_hours by "
            "region, date and job_type. Balance = available_hours - jobs_hours. Always check "
            "whether a gap is geographic or skill-mix before recommending a move, and use "
            "simulate_capacity_reallocation to test any reallocation you propose."
        ),
        # "demand" and "forecast" deliberately belong to the Demand Forecast Agent.
        # This specialist owns the SUPPLY side - the hours available to meet demand.
        keywords=("capacity", "hours", "engineer", "shift", "workforce", "rebalance",
                  "utilisation", "utilization", "staffing", "skill", "resource", "imbalance"),
    ),
    Specialist(
        key="governance",
        name="Data Governance Officer",
        icon="🛡️",
        remit="dataset ownership, lineage, SMEs, access and storage platforms",
        briefing=(
            "You cover data governance. Use the knowledge graph and the dataset ownership "
            "register for SME owners, stewards, governance tiers and hosting platforms. For "
            "access questions use check_data_access, and raise_access_request when the user "
            "explicitly asks for access."
        ),
        keywords=("owner", "ownership", "sme", "lineage", "governance", "steward", "access",
                  "permission", "catalog", "platform", "hosted", "dataset"),
    ),
)

SPECIALIST_BY_KEY = {s.key: s for s in SPECIALISTS}
DEFAULT_SPECIALIST = SPECIALISTS[0]

ROUTER_PROMPT = """You route a business question to exactly one specialist.

{roster}

Reply with the specialist key only - one word, no punctuation, no explanation.
If a question spans several areas, pick the one that owns the PRIMARY measure
being asked about."""


# An intent phrase is worth more than a subject word, and by enough that two
# subject words cannot outvote one clear statement of purpose.
INTENT_WEIGHT = 3


def _keyword_route(question: str) -> Specialist:
    """Score each specialist by keyword hits. Used when no model is available.

    Subject words say what a question mentions; intent phrases say what it is
    for. A question mentioning boilers and repairs but asking what to charge is a
    pricing question, so intent is weighted to win.
    """
    text = question.casefold()
    best, best_score = DEFAULT_SPECIALIST, 0
    for specialist in SPECIALISTS:
        score = sum(1 for kw in specialist.keywords if kw in text)
        score += INTENT_WEIGHT * sum(1 for phrase in specialist.intent if phrase in text)
        if score > best_score:
            best, best_score = specialist, score
    return best


def route(question: str, llm: Any = None) -> tuple[Specialist, str]:
    """Choose a specialist. Returns (specialist, how_it_was_chosen)."""
    if llm is None or not HAS_MESSAGES:
        return _keyword_route(question), "keyword"

    roster = "\n".join(f"- {s.key}: {s.remit}" for s in SPECIALISTS)
    try:
        response = llm.invoke([
            SystemMessage(content=ROUTER_PROMPT.format(roster=roster)),
            HumanMessage(content=question[:800]),
        ])
        content = getattr(response, "content", "")
        if isinstance(content, list):
            content = "".join(
                str(p.get("text", "")) if isinstance(p, dict) else str(p) for p in content
            )
        key = str(content).strip().split()[0].strip(".,:'\"").casefold() if str(content).strip() else ""
        if key in SPECIALIST_BY_KEY:
            return SPECIALIST_BY_KEY[key], "model"
    except Exception as error:  # noqa: BLE001 - routing must never block an answer
        print(f"[Supervisor] Routing failed, using keywords: {error}")
    return _keyword_route(question), "keyword"


# Every planning specialist answers in the same shape. Without this they report
# what the data says - "the forecast totals 756,265 jobs" - which is a number the
# reader already had. A leader needs the call, the facts under it, and what it
# does to the plan they are managing.
DECISION_STRUCTURE = """
HOW YOUR ANSWER MUST BE STRUCTURED
Lead with the CALL, not with the data. Use these four headings, in this order:

**The call** - one or two sentences. What you have concluded and what should be
done. State it as a decision a person could act on today, with the number in it.

**Why - the facts** - the specific evidence, quantified, each one traceable to a
tool result you actually got in this turn. Say what was compared with what, over
what window, and how large the effect is. If a conclusion rests on a pattern
rather than a single number, say what makes it a pattern and not luck. Do not
open with a bare total the reader could read off the source; a total is context,
and the finding is what it is compared against.

**What it means for the plan** - the forward consequence over the next quarter
and to year end: hours, engineers, jobs at risk, revenue or cost, and whether an
existing goal is still achievable. If a decision is reversible or cheap to test
first, say so. This section is mandatory - an analysis with no consequence is
not an answer.

**What to do about it** - the ranked steps, cheapest and fastest first, each with
what it is worth and what is still left after it. Never report a problem without
this. If most of a gap can be closed without spending money, that is the headline,
not a footnote.

**What would change this** - the assumption that carries the most weight, the
condition that would overturn the conclusion, and what you would check next.
Also state plainly what your finding does NOT say, where a reader could easily
over-read it.

Then propose the single best action for approval if one follows.

SHOW THE WORKING - TABLES AND A CHART ARE PART OF THE ANSWER
The prose carries the decision; the table carries the detail a manager checks it
against; the chart carries the shape. All three belong in the answer, and the
tables sit under the section whose evidence they are.

- When an engine tool returns a table, REPRODUCE IT, row for row. Do not collapse
  a per-region table into a national total, and do not describe a table in words
  instead of showing it - the rows ARE the evidence. If it runs past about 20
  rows, show the most important ones and say how many you left out.
- Reproducing a figure a tool returned is exactly what you should do. The rule
  against inventing figures means do not CALCULATE new ones; it never means
  withhold what you retrieved. If you have the numbers, show them. If a breakdown
  you were asked for genuinely was not returned, name the tool that would produce
  it and call that tool, rather than declining to answer.
- Add a chart whenever the answer contains a trend, a ranking, or a comparison
  across regions, months, service lines or bands - which most of these answers
  do. Follow the chart rules in the Charts section above exactly; they still
  apply in full. The chart supplements the prose and the table and never replaces
  either.
- Keep units and periods explicit in every table header: per day, per week, over
  13 weeks. Most arguments about these numbers turn out to be arguments about the
  period they cover.

WRITE FOR SOMEONE WHO DOES NOT WORK WITH DATA
The reader may be a regional manager or a director, not an analyst. Write the way
you would explain it to them across a desk:

- Plain words. "About 40 more repair jobs a day than we planned for", not "a
  -14.5% bias against the trailing run-rate".
- Explain a term the first time you use it. "1,817 FTE" means nothing on its own;
  "about 1,800 full-time engineers' worth of work" does.
- Round in the prose and keep the exact figure in the table. Nobody decides
  differently between 825,150 and "about 825,000 hours".
- No jargon without its meaning attached: first-time fix, run-rate, cost to serve,
  materiality, bias. Each is fine once you have said what it is.
- Say what it means for people and customers, not just for numbers - missed
  appointments, longer waits, engineers sent twice to the same house.

Rules that override style: every figure you state must come from a tool result in
this turn - but everything you retrieved is fair to show, in full. Never re-derive
with your own arithmetic a figure an engine tool already returned; quote the
engine's number. When a figure rests on an assumption, name the assumption next
to it. If you find you cannot answer part of the question, call another tool
before you say so - declining is the last resort, not the safe default.
""".strip()


def specialist_directive(specialist: Specialist) -> str:
    """The block appended to the agent's system prompt for this specialist."""
    return (
        f"\n\nYOU ARE THE {specialist.name.upper()} ({specialist.icon}).\n"
        f"Remit: {specialist.remit}.\n{specialist.briefing}\n\n"
        f"{DECISION_STRUCTURE}\n\n"
        "If the question falls outside your remit, answer what you can and say plainly "
        "which specialist should take the rest."
    )


def roster() -> list[dict[str, str]]:
    return [
        {"key": s.key, "name": s.name, "icon": s.icon, "remit": s.remit}
        for s in SPECIALISTS
    ]
