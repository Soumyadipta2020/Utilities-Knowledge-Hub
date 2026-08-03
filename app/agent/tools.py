"""
Custom Tools for Utilities Knowledge Hub Chatbot.
"""

import random
from typing import Dict, Any, Callable

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


def register_services(graph_service, data_service) -> None:
    """Inject service dependencies into the tools module."""
    global _GRAPH_SERVICE, _DATA_SERVICE
    _GRAPH_SERVICE = graph_service
    _DATA_SERVICE = data_service


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
        return (
            f"No direct knowledge graph match for '{entity_name}'. "
            f"Available entities: {', '.join(res.get('available_entities', []))}"
        )

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
    formatted = []
    for m in metrics:
        formatted.append(
            f"• {m['metric_name']}: {m['value']} {m['unit']} (Status: {m['status']}) - {m['description']}"
        )
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
    Combined Graph-RAG Search powered by LangChain NetworkxEntityGraph.
    Performs RAG context retrieval AND Knowledge Graph path traversal together.
    Use this tool for complex queries requiring document context snippets, relationship graph traversal, and LangChain knowledge triples.
    """
    if _GRAPH_SERVICE is None:
        return "Error: Knowledge Graph Service is not initialized."

    res = _GRAPH_SERVICE.hybrid_graph_rag_search(query)
    docs = res.get("rag_context_documents", [])
    traversals = res.get("graph_traversals", [])
    langchain_facts = _GRAPH_SERVICE.query_langchain_graph(query)

    output_parts = []
    if docs:
        doc_str = "\n".join([f"  • {d['content']}" for d in docs])
        output_parts.append(f"📄 RAG Document Snippets:\n{doc_str}")

    if traversals:
        graph_strs = []
        for t in traversals:
            paths = t.get("formatted_paths", [])
            if paths:
                graph_strs.append(f"Entity '{t['matched_entity']}':\n  " + "\n  ".join(paths))
        if graph_strs:
            output_parts.append("🕸️ Knowledge Graph Traversal Paths:\n" + "\n\n".join(graph_strs))

    if langchain_facts:
        lc_str = "\n".join([f"  • {fact}" for fact in langchain_facts])
        output_parts.append(f"🧬 LangChain NetworkxEntityGraph Knowledge Triples:\n{lc_str}")

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
        f"- Active leads: {result['leads']}\n"
        f"- Net appointments: {result['net_appointments']}\n"
        f"- Quotes issued: {result['quotes_issued']}\n"
        f"- Observed conversion: {result['conversion_pct']:.1f}%\n"
        f"- Directional projected installations: {result['projected_installations']}\n"
        f"- Note: {result['note']}"
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



def get_all_tools():
    """Return list of tool functions for LangChain agent."""
    return [
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
    ]
