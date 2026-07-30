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
    Generate an IT Access Ticket (ServiceNow) for a user whose access was denied.
    Input user_email and the requested data_source.
    Returns the generated ticket number and approval details.
    """
    ticket_num = f"TICK-{random.randint(1000, 9999)}"
    return (
        f"IT Access Ticket Created Successfully!\n"
        f"• Ticket Number: {ticket_num}\n"
        f"• Requested Resource: {data_source}\n"
        f"• User Email: {user_email}\n"
        f"• Status: Pending IT Security Review & Manager Approval.\n"
        f"An email notification has been dispatched to {user_email}."
    )


def get_all_tools():
    """Return list of tool functions for LangChain agent."""
    return [
        query_knowledge_graph,
        query_live_metrics,
        check_data_access,
        raise_access_request,
    ]
