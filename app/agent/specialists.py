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


SPECIALISTS: tuple[Specialist, ...] = (
    Specialist(
        key="commercial",
        name="Commercial Analyst",
        icon="📈",
        remit="leads, quotes, sales, conversion, revenue and pricing",
        briefing=(
            "You cover the commercial funnel. The lead-level funnel lives in "
            "`installation_history` (lead_id, lead_date, appointment_happened, sale_happened, "
            "installation_happened) - despite its name, that is the leads table. Quotes join "
            "to it on lead_id from `quotes_and_sales` (primary_qutation, secondary_quotation, "
            "final_quotation). Conversion = sales / leads by lead_date week. Always express "
            "impact in pounds using final_quotation."
        ),
        keywords=("lead", "sale", "sales", "conversion", "quote", "quotation", "revenue",
                  "price", "pricing", "funnel", "commercial", "insurance"),
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
        keywords=("capacity", "hours", "engineer", "shift", "workforce", "demand", "forecast",
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


def _keyword_route(question: str) -> Specialist:
    """Score each specialist by keyword hits. Used when no model is available."""
    text = question.casefold()
    best, best_score = DEFAULT_SPECIALIST, 0
    for specialist in SPECIALISTS:
        score = sum(1 for kw in specialist.keywords if kw in text)
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


def specialist_directive(specialist: Specialist) -> str:
    """The block appended to the agent's system prompt for this specialist."""
    return (
        f"\n\nYOU ARE THE {specialist.name.upper()} ({specialist.icon}).\n"
        f"Remit: {specialist.remit}.\n{specialist.briefing}\n"
        "If the question falls outside your remit, answer what you can and say plainly "
        "which specialist should take the rest."
    )


def roster() -> list[dict[str, str]]:
    return [
        {"key": s.key, "name": s.name, "icon": s.icon, "remit": s.remit}
        for s in SPECIALISTS
    ]
