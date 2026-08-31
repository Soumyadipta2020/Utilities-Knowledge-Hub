"""
Custom Tools for Utilities Knowledge Hub Chatbot.
"""

import random
from pathlib import Path
from typing import Dict, Any, Callable

from app.agent import commercial as commercial_engine
from app.agent import demand_forecast as demand_engine
from app.agent import evidence
from app.agent import pricing as pricing_engine
from app.agent.analytics import gbp, join_plain, num, signed_pct
from app.agent.business_tools import get_business_tools

try:
    from langchain_core.tools import tool
except ImportError:
    # Graceful fallback decorator if langchain_core is not present
    def tool(func: Callable) -> Callable:
        setattr(func, "is_tool", True)
        setattr(func, "name", func.__name__)
        setattr(func, "description", func.__doc__ or "")
        setattr(func, "invoke", lambda args: func(**args) if isinstance(args, dict) else func(args))
        return func

from mcp_server.engine.metric_engine import metric_engine


# Global references to services (injected via register_services)
_GRAPH_SERVICE = None
_DATA_SERVICE = None
_SQL_SERVICE = None
_STORE = None

# Set per-request so a proposed action is attributed to the person who asked.
_CURRENT_USER = "user@abc.com"


def register_services(graph_service, data_service, sql_service=None, store=None) -> None:
    """Inject service dependencies into the tools module."""
    global _GRAPH_SERVICE, _DATA_SERVICE, _SQL_SERVICE, _STORE
    _GRAPH_SERVICE = graph_service
    _DATA_SERVICE = data_service
    _SQL_SERVICE = sql_service
    _STORE = store


def set_current_user(user_email: str) -> None:
    """Attribute subsequent tool calls to this user."""
    global _CURRENT_USER
    _CURRENT_USER = user_email or "user@abc.com"


@tool
def query_knowledge_graph(entity_name: str) -> str:
    """
    Query the NetworkX knowledge graph for boiler models, error codes, components, or diagnostic remedies.
    Use this tool when answering troubleshooting, error code, appliance model, or maintenance questions.
    Input should be an entity name like 'Worcester Bosch 4000', 'EA_Error', 'Ignition Electrode', or 'F2_Error'.
    """
    if _GRAPH_SERVICE is None:
        return "Error: Knowledge Graph Service is not initialized."

    res = _GRAPH_SERVICE.traverse_graph(entity_name)
    if not res.get("found"):
        evidence.record_failure()
        return (
            f"No direct knowledge graph match for '{entity_name}'. "
            f"Available entities: {', '.join(res.get('available_entities', []))}"
        )

    evidence.record_graph_lookup([str(res.get("matched_entity", entity_name))])
    paths = res.get("formatted_paths", [])
    if not paths:
        return f"Entity '{res['matched_entity']}' found, but no explicit relationship paths exist."

    output = f"Knowledge Graph Traversal for '{res['matched_entity']}':\n" + "\n".join(paths)
    return output


@tool
def query_live_metrics(metric_name: str) -> str:
    """
    Query live system metrics and telemetry from Live_Metrics.xlsx.
    MUST check data access permissions using check_data_access tool BEFORE executing this tool.
    Input should be a metric name like 'grid_pressure_psi', 'boiler_flame_current_ua', 'pump_flow_rate_lpm', or 'all'.
    """
    if _DATA_SERVICE is None:
        return "Error: Data Service is not initialized."

    res = _DATA_SERVICE.get_live_metrics(metric_name)
    if not res.get("success"):
        return f"Metric query failed: {res.get('error', 'Unknown error')} Available: {res.get('available_metrics')}"

    metrics = res.get("metrics", [])
    if not metrics:
        return "No live metric readings are currently available."

    # Render whatever columns the dataset actually has. The previous version
    # assumed the retired Live_Metrics.xlsx schema and raised KeyError on the
    # CSV rows, which aborted the whole agent run.
    formatted = []
    for record in metrics:
        fields = ", ".join(f"{key}: {value}" for key, value in record.items())
        formatted.append(f"• {fields}")
    return "Live Telemetry Metrics:\n" + "\n".join(formatted)


@tool
def check_data_access(user_role: str, data_source: str) -> str:
    """
    Check if the user with role user_role has permission to access the requested data_source.
    Roles: 'Customer', 'Employee', 'Admin'.
    Data Sources: 'Knowledge_Base', 'Live_Metrics', 'System_Logs'.
    Returns 'Access Granted' or 'Access Denied' with policy details.
    """
    if _DATA_SERVICE is None:
        return "Error: Data Service is not initialized."

    res = _DATA_SERVICE.check_access_permission(user_role, data_source)
    if res.get("access_granted"):
        return f"STATUS: Access Granted. Role '{res['user_role']}' is authorized for '{res['data_source']}' ({res['description']})."
    else:
        return f"STATUS: Access Denied. {res.get('reason')}"


@tool
def raise_access_request(user_email: str, data_source: str) -> str:
    """
    Generate an IT Access Ticket (ServiceNow) for a user requesting dataset access.
    Returns the generated ticket number and approval details.
    """
    ticket_num = f"TICK-{random.randint(1000, 9999)}"
    return (
        f"✅ **IT Access Ticket Created Successfully!**\n\n"
        f"• **Ticket Number:** {ticket_num}\n"
        f"• **Requested Dataset:** {data_source}\n"
        f"• **User Email:** {user_email}\n"
        f"• **Status:** Pending IT Security Review & Manager Approval.\n\n"
        f"An email notification has been dispatched to **{user_email}**. Please monitor your inbox for further updates regarding your access."
    )


@tool
def search_knowledge_base_rag(query: str) -> str:
    """
    RAG (Retrieval-Augmented Generation) search over the enterprise Knowledge Base.
    Retrieves relevant documentation snippets, manual excerpts, error descriptions, and remedy steps.
    Use this tool when answering general user questions, troubleshooting procedures, or looking up solutions.
    """
    if _GRAPH_SERVICE is None:
        return "Error: Knowledge Base RAG Service is not initialized."

    docs = _GRAPH_SERVICE.rag_search(query, top_k=5)
    evidence.record_rag_documents(len(docs))
    if not docs:
        return f"No RAG documents retrieved matching '{query}'."

    formatted = []
    for d in docs:
        formatted.append(f"• [{d['source']} -> {d['relationship']} -> {d['target']}]: {d['details']}")
    return "RAG Retrieved Context Documents:\n" + "\n".join(formatted)


@tool
def query_graph_rag(query: str) -> str:
    """
    Hybrid RAG and Knowledge Graph Traversal search engine.
    Use this tool for complex queries requiring document context snippets, relationship graph traversal, and LangChain knowledge triples.
    """
    if _GRAPH_SERVICE is None:
        return "Error: Knowledge Graph Service is not initialized."

    res = _GRAPH_SERVICE.hybrid_graph_rag_search(query)
    docs = res.get("rag_context_documents", [])
    traversals = res.get("graph_traversals", [])
    langchain_facts = _GRAPH_SERVICE.query_langchain_graph(query)

    evidence.record_rag_documents(len(docs))
    evidence.record_graph_lookup(
        [str(t.get("matched_entity", "")) for t in traversals if t.get("matched_entity")]
    )

    output_parts = []
    if docs:
        doc_str = "\n".join([f"  • {d['content']}" for d in docs])
        output_parts.append(f"📄 Knowledge Documentation Context:\n{doc_str}")

    if traversals:
        clean_paths = []
        for t in traversals:
            paths = t.get("formatted_paths", [])
            for p in paths:
                clean_p = p.replace("[", "").replace("]", "").replace(".csv", "")
                if "-->" in clean_p or "via:" in clean_p:
                    clean_paths.append(f"  • {clean_p}")
        if clean_paths:
            output_parts.append("🕸️ Knowledge Graph Lineage Connections:\n" + "\n".join(clean_paths[:5]))

    if langchain_facts:
        clean_triples = []
        for fact in langchain_facts:
            clean_f = fact.replace("[", "").replace("]", "").replace(".csv", "")
            clean_triples.append(f"  • {clean_f}")
        if clean_triples:
            output_parts.append("🧬 Graph Entity Relationships:\n" + "\n".join(clean_triples[:5]))

    if not output_parts:
        return f"No Graph-RAG information found for '{query}'."

    return "\n\n".join(output_parts)



@tool
def query_business_operations(query: str) -> str:
    """Query aggregated leads, appointments, quotes, sales, installations, repairs, and services.

    Always call check_data_access for Business_Operations before this tool.
    """
    if _DATA_SERVICE is None:
        return "Error: Data Service is not initialized."
    result = _DATA_SERVICE.get_business_data(query)
    if not result.get("success"):
        return f"Business data query failed: {result.get('error')}"
    lines = []
    for record in result["records"]:
        dataset = record.pop("dataset")
        details = ", ".join(f"{key}: {value}" for key, value in record.items())
        lines.append(f"[{dataset}] {details}")
    return "Business Operations Results:\n" + "\n".join(lines)


@tool
def query_metric_definitions(query: str) -> str:
    """Explain definitions for leads, net appointments, quotes, net sales, conversion, and service metrics."""
    if _DATA_SERVICE is None:
        return "Error: Data Service is not initialized."
    result = _DATA_SERVICE.get_metric_definitions(query)
    if not result.get("success"):
        return "No metric definition matches that question."
    return "Metric Definitions:\n" + "\n".join(
        f"- {record['metric_name']} ({record['unit']}): {record['definition']}"
        for record in result["definitions"]
    )


@tool
def forecast_boiler_installations() -> str:
    """Create a directional forecast for future boiler installations from the sales pipeline."""
    if _DATA_SERVICE is None:
        return "Error: Data Service is not initialized."
    result = _DATA_SERVICE.forecast_installations()
    if not result.get("success"):
        return f"Installation forecast failed: {result.get('error')}"
    return (
        "Installation Forecast:\n"
        f"- Active leads/quotes: {result.get('leads', 0)}\n"
        f"- Quotes issued: {result.get('quotes_issued', 0)}\n"
        f"- Avg Primary Quotation: {result.get('avg_primary_quotation', 0)}\n"
        f"- Avg Final Quotation: {result.get('avg_final_quotation', 0)}\n"
        f"- Note: {result.get('note', '')}"
    )


@tool
def query_dataset_sample(dataset_name: str) -> str:
    """
    Retrieve a tabular data sample (glimpse) of a specific operational or commercial dataset.
    Use this when the user asks to see a glimpse, sample, or preview of a dataset like 'Customer Master', 'Engineer Skills', etc.
    """
    if _DATA_SERVICE is None:
        return "Error: Data Service is not initialized."
    
    result = _DATA_SERVICE.get_dataset_sample(dataset_name)
    if not result.get("success"):
        return f"Could not retrieve sample for '{dataset_name}': {result.get('error')}"
        
    records = result["sample"]
    if not records:
        return f"Dataset '{result['dataset']}' is empty."
        
    # Format as a markdown table
    headers = list(records[0].keys())
    header_row = "| " + " | ".join(headers) + " |"
    separator_row = "|" + "|".join(["---"] * len(headers)) + "|"
    
    table_lines = [f"Here is a glimpse of the **{result['dataset']}** dataset:", header_row, separator_row]
    for row in records:
        table_lines.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
        
    return "\n".join(table_lines)



# Cap tool output so an unbounded groupby cannot flood the model's context.
MAX_OUTPUT_LINES = 60
MAX_OUTPUT_CHARS = 6000


@tool
def execute_pandas_query(dataset_name: str, query: str) -> str:
    """
    Execute a pandas python script on a specific dataset to answer complex data questions (e.g. counts, sums, groupings).
    The dataset is available as a pandas DataFrame named `df`.
    The script MUST print the final result using `print()`.
    Example code:
    print(df.groupby('status').size())
    """
    if _DATA_SERVICE is None:
        return "Error: Data Service is not initialized."

    import pandas as pd

    evidence.record_pandas_query()
    df, truncated = _DATA_SERVICE.load_frame(dataset_name)
    if df.empty:
        evidence.record_failure()
        available = sorted(p.stem for p in _DATA_SERVICE.data_dir.glob("*.csv"))
        return (
            f"Error: Dataset '{dataset_name}' was not found or is empty. "
            f"Call this tool again with one of these exact dataset names: {', '.join(available)}."
        )

    evidence.record_datasets([Path(str(dataset_name)).stem], records_scanned=len(df))

    import io
    import sys

    old_stdout = sys.stdout
    redirected_output = sys.stdout = io.StringIO()

    try:
        local_namespace = {"df": df, "pd": pd}
        exec(query, {}, local_namespace)
        output = redirected_output.getvalue()
        if not output.strip():
            return (
                "The code ran but printed nothing. Wrap your final expression in print(), "
                "for example: print(df.groupby('region').size())"
            )
    except Exception as error:
        # Hand the agent everything it needs to fix the code and retry, rather
        # than a bare exception it can only give up on.
        evidence.record_failure()
        columns = ", ".join(map(str, df.columns))
        dtypes = ", ".join(f"{col}:{dtype}" for col, dtype in df.dtypes.astype(str).items())
        return (
            f"Error executing pandas code: {type(error).__name__}: {error}\n"
            f"Real columns in '{dataset_name}': {columns}\n"
            f"Column dtypes: {dtypes}\n"
            "Rewrite the code using these exact column names and call execute_pandas_query again."
        )
    finally:
        sys.stdout = old_stdout

    lines = output.splitlines()
    if len(lines) > MAX_OUTPUT_LINES:
        hidden = len(lines) - MAX_OUTPUT_LINES
        lines = lines[:MAX_OUTPUT_LINES] + [f"... [{hidden} further lines omitted - aggregate before printing]"]
    output = "\n".join(lines)[:MAX_OUTPUT_CHARS]

    if truncated:
        output += (
            f"\n\n[Note: '{dataset_name}' was read up to a row cap for demo speed. "
            "Totals and counts cover the leading rows only - say so when quoting them.]"
        )
    return output


MAX_SQL_RESULT_ROWS = 100


@tool
def query_datasets_sql(sql: str) -> str:
    """
    Run read-only SQL across the COMPLETE datasets - every row, no sampling.

    This is the preferred tool for counts, sums, averages, groupings, rankings,
    trends and especially JOINs across datasets, because it scans the full files
    without loading them into memory.

    Each CSV is a view named after its file, e.g. `customer_master`,
    `boiler_master`, `visit_outcome`. Standard DuckDB/Postgres SQL.

    Example:
    SELECT b.boiler_company, count(*) AS repairs
    FROM repair_history r JOIN boiler_master b USING (boiler_id)
    GROUP BY 1 ORDER BY repairs DESC LIMIT 10
    """
    if _SQL_SERVICE is None or not _SQL_SERVICE.available:
        return (
            "Error: the SQL engine is unavailable. "
            "Use execute_pandas_query on a single dataset instead."
        )

    evidence.record_sql_query()
    referenced = _SQL_SERVICE.views_referenced(sql)
    evidence.record_datasets(
        referenced,
        records_scanned=sum(_SQL_SERVICE.row_count(view) for view in referenced),
    )

    res = _SQL_SERVICE.query(sql, max_rows=MAX_SQL_RESULT_ROWS)
    if not res.get("success"):
        evidence.record_failure()
        views = ", ".join(_SQL_SERVICE.datasets)
        return (
            f"Error running SQL: {res.get('error')}\n"
            f"Available tables: {views}\n"
            "Check table and column names, then call query_datasets_sql again."
        )

    columns = res["columns"]
    rows = res["rows"]
    if not rows:
        return "Query ran successfully over the full dataset and returned no rows."

    lines = ["| " + " | ".join(map(str, columns)) + " |",
             "|" + "|".join(["---"] * len(columns)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join("" if v is None else str(v) for v in row) + " |")

    footer = f"\n({res['returned']} rows shown"
    if res["truncated"]:
        footer += f"; result set is larger than {MAX_SQL_RESULT_ROWS} rows - add an ORDER BY/LIMIT or aggregate further"
    footer += ". The query scanned every row of the underlying data.)"
    return "\n".join(lines) + footer


@tool
def query_business_metric(
    metric_name: str,
    dimensions: list = None,
    time_grain: str = None,
    filters: dict = None
) -> str:
    """
    Compute a business KPI or metric dynamically (e.g., total_visits, total_repairs, total_quotes, total_discount).
    This handles SQL generation, dimensional grouping, and time-truncation automatically.
    Use this for all numeric aggregate questions about KPIs instead of query_datasets_sql.
    """
    if _SQL_SERVICE is None or not getattr(_SQL_SERVICE, "available", False):
        return "Error: SQL service unavailable."
    
    try:
        sql = metric_engine.generate_metric_sql(
            metric_name=metric_name,
            dimensions=dimensions,
            time_grain=time_grain,
            filters=filters
        )
    except Exception as e:
        evidence.record_failure()
        return f"Error generating metric SQL: {e}"

    evidence.record_sql_query()
    referenced = _SQL_SERVICE.views_referenced(sql)
    evidence.record_datasets(referenced, records_scanned=sum(_SQL_SERVICE.row_count(v) for v in referenced))

    res = _SQL_SERVICE.query(sql, max_rows=100)
    if not res.get("success"):
        evidence.record_failure()
        return f"Error running metric SQL: {res.get('error')}"

    columns = res["columns"]
    rows = res["rows"]
    if not rows:
        return "Query ran successfully but returned no rows."

    lines = ["| " + " | ".join(map(str, columns)) + " |",
             "|" + "|".join(["---"] * len(columns)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join("" if v is None else str(v) for v in row) + " |")

    return "\n".join(lines)


@tool
def propose_action(
    title: str,
    detail: str,
    rationale: str,
    expected_impact: str,
    action_type: str = "operational",
) -> str:
    """
    Propose ONE concrete action for a human to approve. Use this when your
    analysis leads to something the business should actually DO - rebalance
    engineer capacity, pre-position parts, review pricing, request access.

    Propose the single best action, not a list. If you have already proposed one
    in this answer, do not propose another unless it is genuinely independent.

    Nothing is executed by proposing. The action is shown to the user for
    approval after the figures have been independently verified.

    title: short imperative summary, e.g. "Move 200 engineer hours/week to Midlands"
    detail: what specifically would happen if approved
    rationale: the evidence from your analysis that justifies it
    expected_impact: REQUIRED. What measurably improves if approved, quantified
        wherever the data allows - e.g. "Closes the 735-hour Midlands deficit and
        cuts SLA-breach risk on ~1,400 jobs; ~£250k of protected revenue."
        Say what the assumption is if you have to estimate.
    action_type: one of 'operational', 'access_request', 'capacity', 'procurement', 'pricing'
    """
    if _STORE is None:
        return "Error: the action store is not available, so no action can be queued."

    if not str(expected_impact).strip():
        return (
            "Error: expected_impact is required. Call propose_action again and state what "
            "measurably improves if this is approved, quantified where the data allows."
        )

    action = _STORE.create_action({
        "requested_by": _CURRENT_USER,
        "action_type": action_type,
        "title": title.strip()[:200],
        "detail": detail.strip()[:1500],
        "rationale": rationale.strip()[:1500],
        "expected_impact": str(expected_impact).strip()[:800],
    })
    evidence.record_action_proposed(action["id"])
    return (
        f"Action queued for human approval (id {action['id']}): \"{action['title']}\".\n"
        "It has NOT been executed. It will be shown to the user for approval once your "
        "figures have been verified. Do not propose further actions unless genuinely independent."
    )


@tool
def simulate_capacity_reallocation(from_region: str, to_region: str, hours_per_week: float) -> str:
    """
    Model moving engineer capacity between two regions and report the effect on
    each region's surplus or deficit against forecast demand.

    Use for 'what if' questions about capacity, staffing or regional balance.
    Figures come from regional_capacity_forecast and regional_demand_forecast.
    """
    if _SQL_SERVICE is None or not _SQL_SERVICE.available:
        return "Error: the SQL engine is unavailable, so the simulation cannot run."

    sql = """
        WITH demand AS (
            SELECT region, sum(jobs_hours) AS demand_hours
            FROM regional_demand_forecast
            WHERE date >= (SELECT max(date) - INTERVAL 90 DAY FROM regional_demand_forecast)
            GROUP BY 1
        ), capacity AS (
            SELECT region, sum(available_hours) AS available_hours
            FROM regional_capacity_forecast
            WHERE date >= (SELECT max(date) - INTERVAL 90 DAY FROM regional_capacity_forecast)
            GROUP BY 1
        )
        SELECT d.region, round(c.available_hours) AS available_hours,
               round(d.demand_hours) AS demand_hours,
               round(c.available_hours - d.demand_hours) AS balance
        FROM demand d JOIN capacity c USING (region) ORDER BY balance
    """
    res = _SQL_SERVICE.query(sql, max_rows=50)
    if not res.get("success"):
        return f"Error running the capacity simulation: {res.get('error')}"

    evidence.record_datasets(["regional_demand_forecast", "regional_capacity_forecast"])
    evidence.record_simulation()

    rows = {r[0]: {"available": r[1], "demand": r[2], "balance": r[3]} for r in res["rows"]}
    known = ", ".join(sorted(rows))
    if from_region not in rows or to_region not in rows:
        return (
            f"Error: unknown region. from_region='{from_region}', to_region='{to_region}'. "
            f"Valid regions: {known}. Call the tool again with exact names."
        )

    # The forecast window is ~13 weeks, so a weekly move scales accordingly.
    weeks = 13.0
    moved = float(hours_per_week) * weeks

    if moved > rows[from_region]["balance"] and rows[from_region]["balance"] > 0:
        note = (
            f"\n\nWarning: {from_region} only has a {rows[from_region]['balance']:,.0f} hour surplus "
            f"over {weeks:.0f} weeks. Moving {moved:,.0f} hours would push it into deficit."
        )
    else:
        note = ""

    lines = [
        f"Capacity reallocation: {hours_per_week:,.0f} hrs/week ({moved:,.0f} hrs over ~{weeks:.0f} weeks) "
        f"from {from_region} to {to_region}.",
        "",
        "| Region | Available | Demand | Balance before | Balance after |",
        "|---|---|---|---|---|",
    ]
    for region, vals in sorted(rows.items(), key=lambda kv: kv[1]["balance"]):
        after = vals["balance"]
        if region == from_region:
            after -= moved
        elif region == to_region:
            after += moved
        flag = " ⚠" if after < 0 else ""
        lines.append(
            f"| {region} | {vals['available']:,.0f} | {vals['demand']:,.0f} | "
            f"{vals['balance']:,.0f} | {after:,.0f}{flag} |"
        )
    lines.append("")
    lines.append("(Balance = available hours minus forecast demand hours over the next ~13 weeks.)")
    return "\n".join(lines) + note


@tool
def simulate_weather_scenario(cold_days: int) -> str:
    """
    Model the fault load from a cold-weather event, using the historical
    relationship between temperature and boiler fault mix.

    cold_days: number of days below 3 degrees C to simulate.
    Use for 'what if we get another cold snap' style planning questions.
    """
    if _SQL_SERVICE is None or not _SQL_SERVICE.available:
        return "Error: the SQL engine is unavailable, so the simulation cannot run."

    sql = """
        WITH daily AS (
            SELECT date, min(temperature) AS t FROM weather GROUP BY date
        ), classified AS (
            SELECT r.fault_code, daily.t < 3.0 AS is_cold, r.repair_date
            FROM repair_history r JOIN daily ON daily.date = r.repair_date
        )
        SELECT f.explanation_related_fault_codes AS fault_type,
               round(count(*) FILTER (WHERE is_cold) * 1.0
                     / NULLIF(count(DISTINCT CASE WHEN is_cold THEN repair_date END), 0), 1) AS per_cold_day,
               round(count(*) FILTER (WHERE NOT is_cold) * 1.0
                     / NULLIF(count(DISTINCT CASE WHEN NOT is_cold THEN repair_date END), 0), 1) AS per_mild_day,
               round(avg(f.repair_cost), 2) AS avg_cost
        FROM classified c
        LEFT JOIN (SELECT fault_code, any_value(explanation_related_fault_codes) AS explanation_related_fault_codes,
                          avg(repair_cost) AS repair_cost
                   FROM fault_codes GROUP BY 1) f ON f.fault_code = c.fault_code
        GROUP BY 1 ORDER BY per_cold_day DESC NULLS LAST LIMIT 8
    """
    res = _SQL_SERVICE.query(sql, max_rows=20)
    if not res.get("success"):
        return f"Error running the weather simulation: {res.get('error')}"

    evidence.record_datasets(["repair_history", "weather", "fault_codes"])
    evidence.record_simulation()

    days = max(int(cold_days), 1)
    lines = [
        f"Projected fault load for {days} additional cold day(s) below 3°C, "
        "based on observed per-day rates in the historical data.",
        "",
        "| Fault type | Per cold day | Per mild day | Extra over event | Est. extra cost |",
        "|---|---|---|---|---|",
    ]
    total_extra = 0.0
    total_cost = 0.0
    for fault_type, per_cold, per_mild, avg_cost in res["rows"]:
        if per_cold is None or per_mild is None:
            continue
        extra = (float(per_cold) - float(per_mild)) * days
        if extra <= 0:
            continue
        cost = extra * float(avg_cost or 0)
        total_extra += extra
        total_cost += cost
        lines.append(
            f"| {fault_type} | {per_cold:,.0f} | {per_mild:,.0f} | +{extra:,.0f} | £{cost:,.0f} |"
        )
    lines.append("")
    lines.append(f"**Total additional repairs: ~{total_extra:,.0f}; estimated cost £{total_cost:,.0f}.**")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Planning agents: demand forecast, commercial and pricing.
#
# These tools differ from the query tools above in that the analysis is computed
# in a Python engine rather than composed by the model. The model chooses WHEN to
# run one and explains WHY the result matters; it never gets to choose the
# numbers. That is what makes a forecast correction or a price safe to put in
# front of a human for approval.
# ---------------------------------------------------------------------------

# Datasets each engine reads, for the lineage graph and the evidence ledger.
_ENGINE_DATASETS = {
    "demand": [
        "regional_demand_forecast", "regional_capacity_forecast", "service_history",
        "repair_history", "installation_history", "customer_holdings",
    ],
    "drivers": [
        "service_history", "repair_history", "visit_outcome", "appointment_schedule",
        "weather", "boiler_master", "customer_holdings",
    ],
    "commercial": [
        "installation_history", "quotes_and_sales", "customer_holdings",
        "regional_capacity_forecast",
    ],
    "pricing": [
        "quotes_and_sales", "installation_history", "repair_history", "fault_codes",
        "parts_replaced", "customer_holdings",
    ],
}


def _record_engine_evidence(kind: str) -> None:
    """Attribute an engine run to the datasets it scanned."""
    datasets = _ENGINE_DATASETS.get(kind, [])
    scanned = 0
    if _SQL_SERVICE is not None and getattr(_SQL_SERVICE, "available", False):
        scanned = sum(_SQL_SERVICE.row_count(name) for name in datasets)
    evidence.record_sql_query()
    evidence.record_datasets(datasets, records_scanned=scanned)


def _engine_error(error: Exception, tool: str) -> str:
    evidence.record_failure()
    return f"Error: {tool} could not be computed: {error}"


@tool
def evaluate_demand_forecast(region: str = "", job_type: str = "") -> str:
    """
    Grade the PUBLISHED demand forecast against what demand is actually running
    at, region by region and job type by job type.

    Use this for any question about forecast accuracy, forecast bias, whether the
    forecast can be trusted, or whether it needs correcting. It returns the bias
    per series, the corrected jobs-per-day figure, and what the correction does
    to engineer-hours, engineer-days and the regional capacity balance.

    region: optional single region, e.g. 'Midlands'. Empty means all regions.
    job_type: optional 'Service', 'Repair' or 'Installation'. Empty means all.

    After presenting this, if a series is materially wrong, call
    propose_forecast_correction to put the corrected numbers to a human.
    """
    try:
        result = demand_engine.evaluate(_SQL_SERVICE, region=region, job_type=job_type)
        _record_engine_evidence("demand")
        return demand_engine.render_evaluation(result)
    except Exception as error:  # noqa: BLE001 - a broken engine must not abort the run
        return _engine_error(error, "the forecast evaluation")


@tool
def recommend_improvements() -> str:
    """
    Return a ranked, plain-English plan for CLOSING the capacity gap - what to do
    first, what each step is worth, and what is still left after it.

    This is the answer to "so what do we do about it". Options are ordered the way
    a manager should reach for them: stop creating the work, move people who are
    already qualified, stop wasting visits, buy hours with overtime, and only then
    recruit. Each carries the hours it closes, what it takes to do, how long it
    takes to bite, and the shortfall still open afterwards.

    Call this on any question about what to do, how to fix it, whether we need to
    hire, or how to close a shortfall. Never leave a shortfall on the table
    without it - a finding with no plan is not an answer.
    """
    try:
        result = demand_engine.recommendations(_SQL_SERVICE)
        _record_engine_evidence("demand")
        return demand_engine.render_recommendations(result)
    except Exception as error:  # noqa: BLE001 - a broken engine must not abort the run
        return _engine_error(error, "the improvement plan")


@tool
def detect_forecast_gaps() -> str:
    """
    Find demand the business staffs but does not forecast at all.

    A forecast can be wrong by being ABSENT, which no accuracy measure catches.
    This checks for job types that have engineer capacity provisioned but no
    demand line, regions missing from a job type, and calendar days with no
    forecast row. Use it whenever someone asks whether the forecast is complete,
    what is missing from it, or why capacity and demand do not reconcile.
    """
    try:
        result = demand_engine.gaps(_SQL_SERVICE)
        _record_engine_evidence("demand")
        return demand_engine.render_gaps(result)
    except Exception as error:  # noqa: BLE001 - a broken engine must not abort the run
        return _engine_error(error, "the forecast gap check")


@tool
def generate_demand_forecast(job_type: str, weeks: int = 13) -> str:
    """
    Build a demand forecast from history for a job type that has none, and
    return the actual numbers week by week and region by region.

    Use this when detect_forecast_gaps shows a missing job type, or when the user
    asks for a forecast that does not exist yet. The method is trailing run-rate
    x month-of-year seasonality x trend, and it is stated with the output so the
    numbers can be reproduced.

    job_type: 'Installation', 'Service' or 'Repair'.
    weeks: horizon in weeks, default 13.
    """
    try:
        result = demand_engine.build_forecast(_SQL_SERVICE, job_type, weeks)
        _record_engine_evidence("demand")
        return demand_engine.render_forecast(result)
    except Exception as error:  # noqa: BLE001 - a broken engine must not abort the run
        return _engine_error(error, "the forecast build")


@tool
def explain_demand_drivers(job_type: str = "") -> str:
    """
    Rank the factors that actually move demand, each with its measured effect
    size - including the factors that were tested and found NOT to matter.

    Use this whenever someone asks what is driving demand, what a forecast should
    take account of, or why demand changed. Report the immaterial factors too:
    knowing that weather is worth 1% here is what stops a team building a weather
    model that earns nothing.
    """
    try:
        result = demand_engine.drivers(_SQL_SERVICE, job_type=job_type)
        _record_engine_evidence("drivers")
        return demand_engine.render_drivers(result)
    except Exception as error:  # noqa: BLE001 - a broken engine must not abort the run
        return _engine_error(error, "the demand driver analysis")


def _planning_consequence(job_type: str) -> str:
    """One sentence on what this skill's position means for the plan overall.

    Appended to an approval so the decision is framed against the plan a leader
    is actually managing, not just against the one series being corrected.
    """
    try:
        impact = demand_engine.planning_impact(_SQL_SERVICE)
    except Exception:  # noqa: BLE001 - the correction stands without this framing
        return ""

    skill = next((s for s in impact["skills"] if s["job_type"] == job_type), None)
    if skill is None:
        return ""

    if skill["balance_after"] >= 0:
        return (
            f" Nationally, {job_type.lower()} still has "
            f"{num(skill['balance_after'])} spare hours after this change, so the plan can "
            "absorb it without anyone new."
        )

    # Never leave a shortfall on the table without the cheapest way to close it.
    best = ""
    try:
        plan = demand_engine.recommendations(_SQL_SERVICE)
        top = next((o for o in plan["options"] if o.get("no_new_people")), None)
        if top:
            best = (
                f" The cheapest way to cover it is not recruitment: \"{top['name']}\" alone is "
                f"worth about {num(top['hours_closed'])} hours, and "
                f"{num(plan['closed_without_hiring_pct'], 0)}% of the national shortfall can be "
                "closed with no new people at all."
            )
    except Exception:  # noqa: BLE001 - the correction stands without this framing
        best = ""

    return (
        f" Nationally this leaves {job_type.lower()} short by "
        f"{num(abs(skill['balance_after']))} hours over the next "
        f"{impact['horizon']['weeks']} weeks — roughly {num(skill['fte_equivalent'], 1)} "
        f"full-time engineers, or {num(skill['jobs_at_risk'])} jobs we could not get to. "
        f"There are spare hours in "
        f"{join_plain([s.lower() for s in impact['surplus_skills']]) or 'no other area'}."
        + best
    )


def queue_forecast_correction(
    region: str, job_type: str, reason: str, requested_by: str = ""
) -> dict[str, Any]:
    """Compute and queue a forecast correction. Shared by the tool and the API.

    Returns {"ok": bool, "message": str, "action": dict | None, "row": dict | None}.
    The numbers are always re-derived here so neither caller can supply them.
    """
    if _STORE is None:
        return {"ok": False, "message": "The action store is not available, so no correction "
                                        "can be queued.", "action": None, "row": None}
    if not str(reason).strip():
        return {"ok": False, "message": "A reason is required for a forecast correction.",
                "action": None, "row": None}

    result = demand_engine.evaluate(_SQL_SERVICE, region=region, job_type=job_type)
    rows = result.get("rows") or []
    if not rows:
        return {
            "ok": False,
            "message": f"No forecast series found for region='{region}', job_type='{job_type}'. "
                       "Use the exact region and job type names the evaluation returns.",
            "action": None,
            "row": None,
        }

    row = rows[0]
    _record_engine_evidence("demand")

    if not row["material"]:
        return {
            "ok": False,
            "message": (
                f"{row['region']} {row['job_type']} is only {signed_pct(row['bias_pct'])} out, "
                f"inside the ±{demand_engine.MATERIAL_BIAS_PCT:.0f}% materiality band. No "
                "correction was queued - the change is not worth making."
            ),
            "action": None,
            "row": row,
        }

    # Written for a reader who does not work with forecasts. The technical
    # build-up is kept in the payload; what a person has to read to decide is
    # what is happening, what we suggest doing, and what it costs to ignore.
    gap_per_day = abs(row["actual_jobs_per_day"] - row["forecast_jobs_per_day"])
    short = row["bias_pct"] < 0
    direction = "more" if short else "fewer"
    verb = "Raise" if short else "Lower"

    title = (
        f"{verb} the {row['region']} {row['job_type'].lower()} plan to "
        f"{num(row['suggested_jobs_per_day'], 0)} jobs a day "
        f"(currently {num(row['forecast_jobs_per_day'], 0)})"
    )

    detail = (
        f"We are planning for {num(row['forecast_jobs_per_day'], 0)} "
        f"{row['job_type'].lower()} jobs a day in {row['region']}. We are actually getting "
        f"{num(row['actual_jobs_per_day'], 0)} — about {num(gap_per_day, 0)} {direction} every "
        f"day, and it has been that way for the last eight weeks. So the rota is being built "
        f"for {'less' if short else 'more'} work than turns up.\n\n"
        f"What we recommend:\n"
        f"1. Change the {row['region']} {row['job_type'].lower()} plan to "
        f"{num(row['suggested_jobs_per_day'], 0)} jobs a day — multiply the current numbers by "
        f"{row['correction_factor']}.\n"
        f"2. Check the other regions at the same time. Every one of them is out in the same "
        f"direction, so this is how the forecast is being produced, not a "
        f"{row['region']} problem.\n"
        f"3. Before applying it, confirm the last eight weeks were normal — no catch-up on a "
        f"backlog, no campaign — and that the plan was not deliberately set low because we "
        f"knew we could not staff it."
    )

    expected_impact = (
        f"Getting this right adds {num(abs(row['hours_delta']))} hours of engineer time to the "
        f"plan for this one series — about {num(abs(row['engineer_days_delta']))} days of work, "
        f"{gbp(abs(row['cost_delta_gbp']))} at our assumed labour cost."
        + (
            f" It also turns {row['region']} from having spare {row['job_type'].lower()} capacity "
            "into being short of it, which is the point: the spare capacity was never real."
            if row["balance_after"] < 0 <= row["balance_before"]
            else f" {row['region']} was already short of {row['job_type'].lower()} cover, and this "
            "makes it worse."
            if row["balance_after"] < 0
            else f" {row['region']} on its own can still absorb that."
        )
        + _planning_consequence(row["job_type"])
        + " If we do nothing, the work does not go away — it turns up as missed appointments, "
        "longer waits and unplanned overtime, and nobody traces it back to the forecast."
    )

    action = _STORE.create_action({
        "requested_by": requested_by or _CURRENT_USER,
        "action_type": "forecast_correction",
        "title": title[:200],
        "detail": detail[:1500],
        "rationale": str(reason).strip()[:1500],
        "expected_impact": expected_impact[:800],
        "payload": {
            "kind": "forecast_correction",
            "region": row["region"],
            "job_type": row["job_type"],
            "current_jobs_per_day": row["forecast_jobs_per_day"],
            "corrected_jobs_per_day": row["suggested_jobs_per_day"],
            "correction_factor": row["correction_factor"],
            "bias_pct": row["bias_pct"],
            "hours_delta": row["hours_delta"],
            "engineer_days_delta": row["engineer_days_delta"],
            "cost_delta_gbp": row["cost_delta_gbp"],
            "balance_before": row["balance_before"],
            "balance_after": row["balance_after"],
            "horizon_weeks": demand_engine.HORIZON_WEEKS,
        },
    })
    evidence.record_action_proposed(action["id"])
    return {
        "ok": True,
        "message": f"Forecast correction queued for human approval (id {action['id']}).",
        "action": action,
        "row": row,
    }


@tool
def propose_forecast_correction(region: str, job_type: str, reason: str) -> str:
    """
    Put a demand-forecast correction in front of a human for approval.

    The corrected number, its effect on hours, engineer-days, cost and the
    regional capacity balance are all RE-COMPUTED here from the data - you supply
    only the reason. Nothing is applied to any forecast by calling this; the
    correction is queued and shown to the user with Approve and Reject.

    region: exact region name, e.g. 'Yorkshire'.
    job_type: 'Service', 'Repair' or 'Installation'.
    reason: why this series is biased, in one or two sentences, referencing the
        driver evidence where you have it.
    """
    try:
        outcome = queue_forecast_correction(region, job_type, reason)
    except Exception as error:  # noqa: BLE001 - a broken engine must not abort the run
        return _engine_error(error, "the forecast correction")

    if not outcome["ok"]:
        return outcome["message"]
    return (
        f"{outcome['message']} \"{outcome['action']['title']}\".\n"
        "Nothing has been applied to the forecast. The user will see the before/after "
        "numbers and can approve or reject."
    )


@tool
def weekly_demand_outlook(weeks: int = 13, job_types: str = "Repair,Service") -> str:
    """
    Return the WEEK-BY-WEEK number of jobs the published forecast expects, next
    to what it should say once the known bias is corrected.

    This is the tool for any question asking for weekly, monthly or "next three
    months" job numbers. Weeks are seven-day buckets from the first forecast day,
    so no week is short and no total compares six days with seven.

    weeks: how many weeks ahead. 13 is three months.
    job_types: comma-separated, e.g. 'Repair,Service'. Use 'Repair,Service' unless
        the question names others. Installation has no published forecast - use
        generate_demand_forecast for that one.
    """
    try:
        wanted = [part.strip() for part in str(job_types or "").split(",") if part.strip()]
        result = demand_engine.weekly_outlook(_SQL_SERVICE, weeks=weeks, job_types=wanted or None)
        _record_engine_evidence("demand")
        return demand_engine.render_weekly_outlook(result)
    except Exception as error:  # noqa: BLE001 - a broken engine must not abort the run
        return _engine_error(error, "the weekly outlook")


@tool
def assess_planning_impact() -> str:
    """
    Show what the forecast being wrong means for the PLAN and the forward goals -
    not just for accuracy.

    Adds up the three sources of work the published plan does not carry: the bias
    against actual run-rate, job types that are staffed but never forecast, and
    the return visits implied by jobs that do not complete first time. Reports
    the result per skill as hours, FTE, jobs at risk, and whether surplus in
    another skill can cover it.

    Call this whenever someone asks what a forecast finding MEANS, what it does
    to next quarter, whether the plan is deliverable, what to do about it, or
    what happens if nothing changes. Always pair a forecast correction with this.
    """
    try:
        result = demand_engine.planning_impact(_SQL_SERVICE)
        _record_engine_evidence("demand")
        return demand_engine.render_planning_impact(result)
    except Exception as error:  # noqa: BLE001 - a broken engine must not abort the run
        return _engine_error(error, "the planning impact assessment")


@tool
def analyse_cost_to_serve() -> str:
    """
    Show what a COMPLETED job actually costs, and where the money goes.

    A job costs more than one visit: visits that end without finishing the work,
    visits that are cancelled or cannot get access, and the paid hours that never
    become available for jobs all load onto every completed job. This returns
    first-time-fix rate, visits per completed job, the true cost per job against
    the naive single-visit cost, the annual cost of each line, and what each
    point of operational improvement is worth per year.

    Call this for any question about job costs, cost to serve, why margins are
    thin, whether a price covers its cost, or where operational money is going.
    Use it BEFORE recommending a price - a price set on a single visit when the
    job takes two is a price that loses money on every job.
    """
    try:
        result = pricing_engine.cost_to_serve(_SQL_SERVICE)
        _record_engine_evidence("pricing")
        return pricing_engine.render_cost_to_serve(result)
    except Exception as error:  # noqa: BLE001 - a broken engine must not abort the run
        return _engine_error(error, "the cost to serve analysis")


@tool
def analyse_commercial_seasonality() -> str:
    """
    Show which months are the productive periods of the business year, scored on
    what converts AND on what the estate can actually deliver.

    Use for questions about the trading season, when to run campaigns, when to
    push acquisition, when demand is strongest, or when to schedule maintenance
    work and training. Combines lead volume, conversion, order value and revenue
    per trading day with the installation capacity provisioned for that month.
    """
    try:
        result = commercial_engine.season(_SQL_SERVICE)
        _record_engine_evidence("commercial")
        return commercial_engine.render_season(result)
    except Exception as error:  # noqa: BLE001 - a broken engine must not abort the run
        return _engine_error(error, "the seasonality analysis")


@tool
def recommend_negotiation_position(segment: str = "") -> str:
    """
    Measure what discounting has actually bought, and set the negotiation
    guardrail that follows from it.

    Use for questions about discounting, negotiation, quote-to-close, margin
    leakage, or how hard the sales team should hold price. Bands every quoted
    lead by the discount from the opening to the final quotation, then compares
    conversion and revenue per lead across the bands.

    segment: optional region to restrict the analysis to. Empty means national.
    """
    try:
        result = commercial_engine.negotiation(_SQL_SERVICE, segment=segment)
        _record_engine_evidence("commercial")
        return commercial_engine.render_negotiation(result)
    except Exception as error:  # noqa: BLE001 - a broken engine must not abort the run
        return _engine_error(error, "the negotiation analysis")


@tool
def recommend_service_pricing(service_line: str = "") -> str:
    """
    Recommend a price for the services the business sells - Service, Repair and
    Installation - with the cost build-up, the basis, the confidence and a
    sensitivity table around the recommendation.

    Use for any pricing question: what should we charge, are we under-priced, what
    is a repair worth, should installation prices move. Each line is priced from
    the evidence that exists for it (observed market price for Installation,
    cost-plus for Repair, labour-only floor for Service) and says which it used.

    service_line: optional 'Service', 'Repair' or 'Installation'. Empty prices all three.
    """
    try:
        result = pricing_engine.price_book(_SQL_SERVICE, service_line=service_line)
        _record_engine_evidence("pricing")
        return pricing_engine.render_price_book(result)
    except Exception as error:  # noqa: BLE001 - a broken engine must not abort the run
        return _engine_error(error, "the pricing recommendation")


@tool
def price_repairs_by_fault() -> str:
    """
    Return a repair price schedule per fault type: volume, part cost, labour,
    cost base, the cost the estate records for that fault, and a recommended
    price with its margin.

    Use when someone asks how repairs should be priced by fault, which repairs
    are loss-making, or wants a repair price list.
    """
    try:
        result = pricing_engine.repair_price_list(_SQL_SERVICE)
        _record_engine_evidence("pricing")
        return pricing_engine.render_repair_price_list(result)
    except Exception as error:  # noqa: BLE001 - a broken engine must not abort the run
        return _engine_error(error, "the repair price schedule")


def _serve_line(service_line: str) -> dict[str, Any] | None:
    """Cost-to-serve figures for one line, or None if they cannot be computed."""
    try:
        return next(
            (
                line for line in pricing_engine.cost_to_serve(_SQL_SERVICE)["lines"]
                if line["service_line"] == service_line
            ),
            None,
        )
    except Exception:  # noqa: BLE001 - the price stands without this framing
        return None


def _cost_alternative(service_line: str) -> str:
    """The operational alternative a price change should be weighed against.

    Charging more and costing less improve the same line. Showing the price
    without the alternative invites approving whichever is easier to decide
    rather than whichever is worth more - so the biggest lever travels with it.
    """
    serve = _serve_line(service_line)
    if not serve or not serve.get("levers"):
        return ""

    lever = serve["levers"][0]
    return (
        f" There is another way to get the same result, and it does not touch the customer: "
        f"a {service_line.lower()} job takes {serve['visits_per_completed_job']:.1f} visits "
        f"because only {serve['first_time_fix_pct']:.0f} in every 100 finish first time. "
        f"\"{lever['name']}\" would be worth about {gbp(lever['annual_value_gbp'])} a year by "
        "itself. Both are worth doing — but if only one gets attention this quarter, the "
        "numbers should choose it, not habit."
    )


def queue_price_change(
    service_line: str, reason: str, requested_by: str = ""
) -> dict[str, Any]:
    """Compute and queue a price change. Shared by the tool and the API."""
    if _STORE is None:
        return {"ok": False, "message": "The action store is not available, so no price change "
                                        "can be queued.", "action": None, "line": None}
    if not str(reason).strip():
        return {"ok": False, "message": "A reason is required for a price change.",
                "action": None, "line": None}

    result = pricing_engine.price_book(_SQL_SERVICE, service_line=service_line)
    lines = result.get("lines") or []
    if not lines:
        return {
            "ok": False,
            "message": f"No price could be computed for service line '{service_line}'.",
            "action": None,
            "line": None,
        }

    entry = lines[0]
    _record_engine_evidence("pricing")

    serve = _serve_line(entry["service_line"])
    line_name = entry["service_line"].lower()

    if entry["realised_price"]:
        title = (
            f"Charge {gbp(entry['recommended_price'], 0)} for {line_name} work, "
            f"up from {gbp(entry['realised_price'], 0)} today"
        )
        detail_body = (
            f"We currently close {line_name} work at about "
            f"{gbp(entry['realised_price'], 0)}. Customers who paid nothing off the opening "
            f"quote bought just as often as customers who got a big discount — so the discount "
            f"is not winning the work, it is only lowering the bill.\n\n"
            f"What we recommend:\n"
            f"1. Hold {line_name} pricing at {gbp(entry['recommended_price'], 0)}.\n"
            f"2. Give the sales team something other than price to close with — a longer "
            f"warranty, insurance included, a faster install date.\n"
            f"3. Test it in one or two regions for a quarter before rolling it out, so we find "
            f"out cheaply if customers do walk away."
        )
        impact = (
            f"About {gbp(entry['annual_revenue_effect_gbp'])} more revenue a year at today's "
            f"volume of {num(entry['annual_volume'])} jobs — as long as customers keep buying. "
            "The evidence says they will, because how much we discount has made almost no "
            "difference to how often we win. That is evidence, not proof, so test it first."
        )
    else:
        title = (
            f"Set a published price of {gbp(entry['recommended_price'], 0)} for {line_name} work"
        )
        cost_line = (
            f"A {line_name} job costs us about {gbp(serve['cost_per_completed_job'], 0)} to "
            f"complete once you count the visits that do not finish it"
            if serve else
            f"A {line_name} job costs us about {gbp(entry['cost_base'], 0)}"
        )
        detail_body = (
            f"We do not have a published price for {line_name} work at all. "
            f"{cost_line}. At the margin the business targets, that means charging "
            f"{gbp(entry['recommended_price'], 0)}.\n\n"
            f"What we recommend:\n"
            f"1. Publish {gbp(entry['recommended_price'], 0)} as the standard {line_name} price.\n"
            f"2. Check it against what the billing system actually charges today — the estate "
            f"does not record it, so someone needs to confirm we are not already above or "
            f"below this.\n"
            f"3. Fix the cost first where you can. A cheaper job is worth more than a higher "
            f"price, and it does not cost us a single customer."
        )
        impact = (
            f"At {num(entry['annual_volume'])} jobs a year this is about "
            f"{gbp(entry['annual_revenue_effect_gbp'])} of work being priced properly, on a "
            f"cost of {gbp(entry['cost_base'], 0)} a job and a "
            f"{entry['margin_at_recommended_pct']}% margin. Confidence in this number is "
            f"{entry['confidence']} — read the build-up before publishing it."
        )
    impact += _cost_alternative(entry["service_line"])

    action = _STORE.create_action({
        "requested_by": requested_by or _CURRENT_USER,
        "action_type": "pricing",
        "title": title[:200],
        "detail": detail_body[:1500],
        "rationale": str(reason).strip()[:1500],
        "expected_impact": impact[:800],
        "payload": {
            "kind": "price_change",
            "service_line": entry["service_line"],
            "basis": entry["basis"],
            "confidence": entry["confidence"],
            "cost_base": entry["cost_base"],
            "realised_price": entry["realised_price"],
            "recommended_price": entry["recommended_price"],
            "price_change_pct": entry["price_change_pct"],
            "annual_volume": entry["annual_volume"],
            "annual_revenue_effect_gbp": entry["annual_revenue_effect_gbp"],
            "sensitivity": entry["sensitivity"],
            # The technical build-up moves here so the card a person reads stays
            # plain, without losing the detail an analyst will want to check.
            "build_up": [
                {"name": component["name"], "value": component["value"],
                 "detail": component["detail"]}
                for component in entry["components"]
            ],
            "cost_to_serve": serve,
        },
    })
    evidence.record_action_proposed(action["id"])
    return {
        "ok": True,
        "message": f"Price change queued for human approval (id {action['id']}).",
        "action": action,
        "line": entry,
    }


@tool
def propose_price_change(service_line: str, reason: str) -> str:
    """
    Put a price change in front of a human for approval.

    The recommended price, the movement from today's realised price and the
    annual revenue effect are RE-COMPUTED here - you supply only the reason.
    Nothing is repriced by calling this; it is queued for Approve or Reject.

    service_line: 'Service', 'Repair' or 'Installation'.
    reason: why the price should move, in one or two sentences.
    """
    try:
        outcome = queue_price_change(service_line, reason)
    except Exception as error:  # noqa: BLE001 - a broken engine must not abort the run
        return _engine_error(error, "the price change")

    if not outcome["ok"]:
        return outcome["message"]
    return (
        f"{outcome['message']} \"{outcome['action']['title']}\".\n"
        "Nothing has been repriced. The user will see the build-up and can approve or reject."
    )


def get_all_tools():
    """Return list of tool functions for LangChain agent."""
    return [
        query_datasets_sql,
        propose_action,
        evaluate_demand_forecast,
        weekly_demand_outlook,
        assess_planning_impact,
        recommend_improvements,
        detect_forecast_gaps,
        generate_demand_forecast,
        explain_demand_drivers,
        propose_forecast_correction,
        analyse_commercial_seasonality,
        recommend_negotiation_position,
        analyse_cost_to_serve,
        recommend_service_pricing,
        price_repairs_by_fault,
        propose_price_change,
        simulate_capacity_reallocation,
        simulate_weather_scenario,
        search_knowledge_base_rag,
        query_knowledge_graph,
        query_graph_rag,
        query_live_metrics,
        query_business_operations,
        query_metric_definitions,
        query_dataset_sample,
        forecast_boiler_installations,
        check_data_access,
        raise_access_request,
        execute_pandas_query,
        query_business_metric,
    ] + get_business_tools()
