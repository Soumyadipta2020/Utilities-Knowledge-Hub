"""
Custom Tools for Utilities Knowledge Hub Chatbot.
"""

import random
from pathlib import Path
from typing import Dict, Any, Callable

from app.agent import evidence

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


def get_all_tools():
    """Return list of tool functions for LangChain agent."""
    return [
        query_datasets_sql,
        propose_action,
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
    ]
