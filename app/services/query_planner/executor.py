import asyncio
from typing import Any, Dict, List
import time

from app.services.auth.authorization import UserContext
from app.services.events.tracer import get_current_request_id
from app.services.events.event_bus import event_bus
from app.services.mcp_gateway.gateway import MCPGateway
from .planner import QueryPlan

class PlanExecutor:
    """
    Executes a QueryPlan against the MCP Gateway.
    Supports asynchronous parallel execution of independent tool calls.
    """
    def __init__(self, gateway: MCPGateway):
        self.gateway = gateway
        
    async def _execute_tool_async(self, user_context: UserContext, tool_def: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapper to execute a single tool with timeout and error handling."""
        tool_name = tool_def["name"]
        args = tool_def.get("args", {})
        
        try:
            # Set a 5-second timeout for any individual tool
            return await asyncio.wait_for(
                self.gateway.execute_tool(user_context, tool_name, args),
                timeout=5.0
            )
        except asyncio.TimeoutError:
            return {"error": f"Tool {tool_name} timed out after 5.0s"}
        except Exception as e:
            return {"error": f"Tool {tool_name} failed: {str(e)}"}

    async def execute_plan(self, user_context: UserContext, plan: QueryPlan) -> Dict[str, Any]:
        """Execute the full plan."""
        request_id = get_current_request_id()
        event_bus.publish("QUERY_PLAN_CREATED", request_id, user_context.user_id, {
            "intent": plan.intent,
            "tools": [t["name"] for t in plan.tools],
            "parallel": plan.parallel
        })
        
        results = {}
        start_time = time.time()
        
        if plan.parallel and len(plan.tools) > 1:
            # Execute all tools concurrently
            tasks = [self._execute_tool_async(user_context, tool_def) for tool_def in plan.tools]
            completed_results = await asyncio.gather(*tasks)
            
            for tool_def, result in zip(plan.tools, completed_results):
                results[tool_def["name"]] = result
        else:
            # Execute sequentially
            for tool_def in plan.tools:
                result = await self._execute_tool_async(user_context, tool_def)
                results[tool_def["name"]] = result
                
        execution_time = (time.time() - start_time) * 1000
        
        return {
            "intent": plan.intent,
            "execution_time_ms": execution_time,
            "parallel_execution": plan.parallel,
            "results": results
        }
