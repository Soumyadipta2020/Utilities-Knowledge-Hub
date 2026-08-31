import os
from typing import Dict, Any

class ModelRouter:
    """
    Classifies requests and routes them to the appropriate LLM.
    For this demo, it routes everything to the default configured model,
    but demonstrates the enterprise routing architecture.
    """
    
    def __init__(self):
        self.default_model = os.getenv("OPENROUTER_MODEL_NAME", "anthropic/claude-3-haiku")
        
    def route_request(self, query: str) -> Dict[str, Any]:
        """
        Determine the complexity of the request and route appropriately.
        """
        query_lower = query.lower()
        complexity = "simple"
        selected_model = self.default_model
        routing_reason = "Default fast model for basic queries."
        
        # Analyze complexity based on keywords and length
        complex_keywords = ["why", "compare", "decline", "despite", "analyze", "forecast", "trend"]
        
        if len(query_lower.split()) > 15 or any(k in query_lower for k in complex_keywords):
            complexity = "complex_reasoning"
            routing_reason = "Complex analytical request requiring strong reasoning."
            # In a full deployment, this might change `selected_model` to GPT-4 or Claude-3-Opus
            
        elif "summarize" in query_lower or len(query_lower.split()) > 50:
            complexity = "summarization"
            routing_reason = "Long context/summarization required."
            
        return {
            "selected_model": selected_model,
            "complexity": complexity,
            "routing_reason": routing_reason
        }

model_router = ModelRouter()
