from typing import Any, Dict, List
import json
import re

class QueryPlan:
    def __init__(self, intent: str, entities: List[str], tools: List[Dict[str, Any]], parallel: bool = False):
        self.intent = intent
        self.entities = entities
        self.tools = tools
        self.parallel = parallel

class QueryPlanner:
    """
    Analyzes a user question and creates an execution plan.
    In a real system, this could use a small/fast LLM to generate the JSON plan.
    For this demo, we use a lightweight deterministic rules engine.
    """
    
    def __init__(self):
        # Basic keyword to tool mapping for the demo
        self.intent_patterns = {
            "productivity": {
                "intent": "productivity_analysis",
                "entities": ["EngineerProductivity"],
                "tools": [{"name": "get_engineer_productivity", "args": {}}]
            },
            "capacity": {
                "intent": "capacity_analysis",
                "entities": ["EngineerCapacity"],
                "tools": [{"name": "get_engineer_capacity", "args": {}}]
            },
            "demand": {
                "intent": "demand_analysis",
                "entities": ["RegionalDemand"],
                "tools": [{"name": "get_regional_demand", "args": {}}]
            }
        }

    def create_plan(self, query: str) -> QueryPlan:
        """Create a plan by analyzing the query string."""
        query_lower = query.lower()
        matched_tools = []
        matched_entities = []
        intents = []
        
        # Simple extraction
        for keyword, mapping in self.intent_patterns.items():
            if keyword in query_lower:
                intents.append(mapping["intent"])
                matched_entities.extend(mapping["entities"])
                # Deep copy tool def
                tool_def = json.loads(json.dumps(mapping["tools"][0]))
                
                # Extract simple filters (e.g., region)
                if "london" in query_lower:
                    tool_def["args"]["region"] = "London"
                    
                matched_tools.append(tool_def)
                
        # If multiple tools are matched, we can often run them in parallel
        parallel = len(matched_tools) > 1
        
        # Deduplicate
        matched_entities = list(set(matched_entities))
        final_intent = "_and_".join(intents) if intents else "general_query"
        
        return QueryPlan(
            intent=final_intent,
            entities=matched_entities,
            tools=matched_tools,
            parallel=parallel
        )
