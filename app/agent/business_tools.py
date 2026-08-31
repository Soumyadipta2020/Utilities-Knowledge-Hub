import asyncio
from typing import Any, Dict, Optional
import json

from app.services.auth.authorization import UserContext
from app.services.mcp_gateway.gateway import MCPGateway
from app.services.events.tracer import get_current_user_id

try:
    from langchain_core.tools import tool
except ImportError:
    # Fallback if langchain isn't available
    def tool(func):
        setattr(func, "is_tool", True)
        setattr(func, "name", func.__name__)
        setattr(func, "description", func.__doc__ or "")
        setattr(func, "invoke", lambda args: func(**args) if isinstance(args, dict) else func(args))
        return func

_GATEWAY: Optional[MCPGateway] = None

def register_gateway(gateway: MCPGateway):
    global _GATEWAY
    _GATEWAY = gateway

def _run_gateway(tool_name: str, args: Dict[str, Any]) -> str:
    if not _GATEWAY:
        return "Error: MCP Gateway is not initialized."
        
    user_id = get_current_user_id()
    # In a real app, role and department would be pulled from a session or token.
    # We use a default demo context here.
    user_context = UserContext(user_id=user_id, role="operations_manager", region="London")
    
    try:
        # Run async code in a synchronous tool wrapper
        try:
            loop = asyncio.get_running_loop()
            # If we are in an event loop, we shouldn't use run(). 
            # For simplicity in this synchronous LangChain setup, run via a new loop if needed or create task.
            # However, standard tools are synchronous.
            return "Error: Cannot run synchronous tool inside an active event loop without async wrappers."
        except RuntimeError:
            result = asyncio.run(_GATEWAY.execute_tool(user_context, tool_name, args))
            return json.dumps(result, indent=2)
    except Exception as e:
        return f"Tool execution failed: {str(e)}"

@tool
def get_engineer_productivity(region: Optional[str] = None, period: Optional[str] = None) -> str:
    """
    Retrieve engineer productivity metrics (completed jobs / available hours).
    Optionally filter by region or period.
    """
    args = {}
    if region: args["region"] = region
    if period: args["period"] = period
    return _run_gateway("get_engineer_productivity", args)

@tool
def get_regional_demand(region: Optional[str] = None, period: Optional[str] = None) -> str:
    """
    Retrieve forecasted regional demand for services.
    Optionally filter by region or period.
    """
    args = {}
    if region: args["region"] = region
    if period: args["period"] = period
    return _run_gateway("get_regional_demand", args)

@tool
def get_engineer_capacity(region: Optional[str] = None, skill: Optional[str] = None) -> str:
    """
    Retrieve engineer capacity and skills mapping.
    Optionally filter by region or skill.
    """
    args = {}
    if region: args["region"] = region
    if skill: args["skill"] = skill
    return _run_gateway("get_engineer_capacity", args)

def get_business_tools():
    """Return the list of semantic business tools for the agent."""
    return [get_engineer_productivity, get_regional_demand, get_engineer_capacity]
