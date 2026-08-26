import asyncio
import os
from typing import Any, Dict, List

from app.services.auth.authorization import auth_manager, UserContext
from app.services.cache.semantic_cache import semantic_cache
from app.services.events.event_bus import event_bus
from app.services.semantic.registry import semantic_registry
from app.services.connectors.base_connector import BaseDataConnector
from app.services.events.tracer import get_current_request_id, RequestContext

class MCPGateway:
    """
    Enterprise MCP Gateway.
    The ONLY path through which agents access data capabilities.
    Provides authentication context, authorization, caching, query pushdown, and telemetry.
    """
    def __init__(self, data_connector: BaseDataConnector):
        self.data_connector = data_connector
        self.max_rows = int(os.getenv("MAX_MCP_ROWS", "100"))

    async def execute_tool(self, user_context: UserContext, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        request_id = get_current_request_id()
        
        event_bus.publish("MCP_TOOL_STARTED", request_id, user_context.user_id, {"tool": tool_name, "args": args})
        
        # 1. Authorization (RBAC + ABAC)
        auth_result = auth_manager.authorize_tool(user_context, tool_name, args)
        if not auth_result.allowed:
            event_bus.publish("AUTHORIZATION_DENIED", request_id, user_context.user_id, {"tool": tool_name, "reason": auth_result.reason})
            return {"error": f"Authorization denied: {auth_result.reason}"}

        # Merge ABAC filters with requested args
        final_args = {**args, **auth_result.filters}

        # 2. Check Cache
        cached_result = semantic_cache.get_query_result(tool_name, final_args)
        if cached_result:
            event_bus.publish("CACHE_HIT", request_id, user_context.user_id, {"tool": tool_name})
            return cached_result
            
        event_bus.publish("CACHE_MISS", request_id, user_context.user_id, {"tool": tool_name})

        # 3. Resolve Semantic Entity to Physical Dataset
        entity_name = self._map_tool_to_entity(tool_name)
        if not entity_name:
            return {"error": f"Unknown tool or no mapped entity: {tool_name}"}
            
        entity = semantic_registry.get_entity(entity_name)
        if not entity:
            return {"error": f"Semantic entity {entity_name} not found in registry."}

        # 4. Execute Query via Connector with Pushdown (limits and filters)
        limit = min(args.get("limit", entity.default_limit), self.max_rows)
        
        # Translate semantic arguments to physical column names for filtering
        physical_filters = {}
        for arg_k, arg_v in final_args.items():
            if arg_k == "limit": continue
            if arg_k in entity.fields:
                physical_filters[entity.fields[arg_k].physical_name] = arg_v

        event_bus.publish("DATA_QUERY_EXECUTED", request_id, user_context.user_id, {"dataset": entity.physical_dataset, "filters": physical_filters})
        
        try:
            results = self.data_connector.read_table(
                table_name=entity.physical_dataset,
                limit=limit,
                filters=physical_filters
            )
            
            # Map physical column names back to semantic names for the LLM
            semantic_results = self._map_to_semantic(results, entity)
            
            response = {
                "success": True,
                "data": semantic_results,
                "count": len(semantic_results),
                "truncated": len(semantic_results) == limit
            }
            
            # 5. Update Cache
            semantic_cache.set_query_result(tool_name, final_args, response)
            
            event_bus.publish("MCP_TOOL_COMPLETED", request_id, user_context.user_id, {"tool": tool_name, "rows": len(semantic_results)})
            return response
            
        except Exception as e:
            event_bus.publish("MCP_TOOL_FAILED", request_id, user_context.user_id, {"tool": tool_name, "error": str(e)})
            return {"error": f"Data execution failed: {str(e)}"}

    def _map_tool_to_entity(self, tool_name: str) -> str:
        mapping = {
            "get_engineer_productivity": "EngineerProductivity",
            "get_regional_demand": "RegionalDemand",
            "get_engineer_capacity": "EngineerCapacity"
        }
        return mapping.get(tool_name)

    def _map_to_semantic(self, rows: List[Dict[str, Any]], entity) -> List[Dict[str, Any]]:
        mapped_rows = []
        # Create reverse lookup map
        reverse_map = {field.physical_name: field.name for field in entity.fields.values()}
        
        for row in rows:
            mapped_row = {}
            for k, v in row.items():
                semantic_key = reverse_map.get(k)
                if semantic_key:
                    # Skip sensitive fields if they were flagged
                    if not entity.fields[semantic_key].is_sensitive:
                        mapped_row[semantic_key] = v
            mapped_rows.append(mapped_row)
        return mapped_rows
