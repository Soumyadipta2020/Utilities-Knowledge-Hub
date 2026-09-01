import os
import re
import json
from typing import Dict, Any, Tuple
from app.config import (
    OPENROUTER_API_KEY, 
    OPENROUTER_BASE_URL,
    ROUTER_MODE,
    CLASSIFIER_MODEL_NAME, 
    SLM_MODEL_NAME, 
    LLM_MODEL_NAME,
    SLM_FALLBACK_MODEL_NAME,
    LLM_FALLBACK_MODEL_NAME
)
try:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage, HumanMessage
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False


class DeterministicClassifier:
    """
    Zero-token, instantaneous deterministic query complexity classification engine.
    Analyzes intent patterns, vocabulary, multi-dataset joins, and question structure.
    """

    GREETINGS = {
        "hi", "hello", "hey", "good morning", "good afternoon", "good evening", "how are you"
    }

    CAPABILITY_TERMS = (
        "what can you do", "help", "who are you", "what are your capabilities", "available tools"
    )

    ACCESS_TERMS = (
        "check access", "check my access", "do i have access", "check permission",
        "raise ticket", "raise access", "raise request", "it request", "submit ticket",
        "request access", "escalate"
    )

    SME_GOVERNANCE_TERMS = (
        "who is the sme", "who owns", "sme for", "data owner", "data steward",
        "where is it hosted", "storage provider", "governance tier", "who is the owner"
    )

    SIMPLE_LOOKUP_TERMS = (
        "sample", "preview", "glimpse", "show rows", "show sample",
        "define", "definition of", "what is the definition", "meaning of"
    )

    ENTITY_REGEX = re.compile(r"\b[A-Z]{3,8}[-_]?\d{1,10}\b", re.IGNORECASE)

    COMPLEX_ANALYTICAL_KEYWORDS = (
        # Causality & root cause
        "why", "root cause", "how come", "what caused", "investigate", "reconciliation",
        "explain the dip", "explain the drop", "explain why", "reason for the",
        # Comparison & correlation
        "compare", "comparison", "versus", " vs ", "difference between", "correlate", "correlation",
        # Trend, forecasting & projections
        "forecast", "forecasting", "predict", "projection", "trend", "seasonality",
        "seasonal", "trajectory", "outlook", "run-rate",
        # Strategic & Financial Impact
        "impact of", "sensitivity", "cost to serve", "trade-off", "trade off",
        "recommendation", "recommend", "what should we change", "lost revenue",
        "deferred revenue", "jobs at risk", "headroom",
        # Multi-dimensional aggregations & joins
        "breakdown by", "broken down by", "grouped by", "per region and", "cross-reference",
        "across all regions", "net appointments", "net of"
    )

    KNOWN_DATASETS = (
        "customer_master", "inventory_and_van_stock", "boiler_telemetry_logs",
        "fault_codes", "telemetry_logs", "engineer_master", "repair_history",
        "epc_property_data", "appointment_schedule", "engineer_availability_and_shifts",
        "quotes_and_sales", "contact_center_interaction", "customer_holdings",
        "engineer_skill", "parts_replaced", "product_and_warranty_info", "weather",
        "service_history", "installation_history", "visit_outcome", "knowledge_base",
        "business_rules", "boiler_master", "regional_demand_forecast", "regional_capacity_forecast"
    )

    def classify(self, query: str) -> Tuple[str, str]:
        """
        Classifies query into 'simple' or 'complex' deterministically (0 tokens, 0ms latency).
        Returns: (complexity, reason)
        """
        raw = query.strip()
        lowered = raw.lower()
        words = lowered.split()
        word_count = len(words)

        # 1. Obvious simple conversational / capability
        clean_punct = lowered.strip("!?. ")
        if clean_punct in self.GREETINGS or any(term in lowered for term in self.CAPABILITY_TERMS):
            return "simple", "Conversational greeting or capability inquiry"

        # 2. Access entitlement checks & ticket requests
        if any(term in lowered for term in self.ACCESS_TERMS):
            return "simple", "Access entitlement check or ticket request"

        # 3. Governance and SME ownership lookups
        if any(term in lowered for term in self.SME_GOVERNANCE_TERMS):
            return "simple", "Direct data ownership or SME lookup"

        # 4. Simple definition or sampling previews
        if any(term in lowered for term in self.SIMPLE_LOOKUP_TERMS):
            return "simple", "Simple definition or dataset preview request"

        # 5. Multi-dataset cross-referencing (joins require complex multi-step reasoning)
        mentioned_datasets = [ds for ds in self.KNOWN_DATASETS if ds in lowered]
        if len(mentioned_datasets) >= 2:
            return "complex", f"Cross-dataset join required across {len(mentioned_datasets)} datasets: {', '.join(mentioned_datasets)}"

        # 6. Check complex analytical keywords
        for kw in self.COMPLEX_ANALYTICAL_KEYWORDS:
            if kw in lowered:
                return "complex", f"Analytical intent detected ('{kw}')"

        # 7. Compound multi-part questions
        if raw.count("?") >= 2:
            return "complex", f"Compound multi-part question ({raw.count('?')} questions detected)"

        # 8. Single entity ID lookups (e.g. CUST00007, ENG014)
        if self.ENTITY_REGEX.search(raw) and word_count <= 14:
            return "simple", "Direct entity record lookup"

        # 9. Length / detail density heuristic
        if word_count > 18:
            return "complex", f"High query length and detail density ({word_count} words)"

        return "simple", "Direct single-topic inquiry"


class ModelRouter:
    """
    Classifies requests and routes them to the appropriate model (SLM or LLM).
    Uses a zero-token deterministic engine by default, or an LLM classifier if configured.
    """
    
    def __init__(self):
        self.router_mode = ROUTER_MODE
        self.deterministic_engine = DeterministicClassifier()
        self.classifier_model = CLASSIFIER_MODEL_NAME
        self.slm_model = SLM_MODEL_NAME
        self.llm_model = LLM_MODEL_NAME
        self.slm_fallback = SLM_FALLBACK_MODEL_NAME
        self.llm_fallback = LLM_FALLBACK_MODEL_NAME
        
        self.classifier_llm = None
        if self.router_mode == "llm" and HAS_LANGCHAIN and OPENROUTER_API_KEY:
            try:
                self.classifier_llm = ChatOpenAI(
                    api_key=OPENROUTER_API_KEY,
                    model=self.classifier_model,
                    base_url=OPENROUTER_BASE_URL,
                    temperature=0.0
                )
            except Exception:
                pass

    def route_request(self, query: str) -> Dict[str, Any]:
        """
        Determine the complexity of the request and route appropriately.
        """
        query_preview = query[:80] + ("..." if len(query) > 80 else "")
        print(f"\n[ModelRouter] Evaluating query: \"{query_preview}\"")
        
        complexity = "simple"
        reason = ""

        if self.router_mode == "deterministic" or not self.classifier_llm:
            # Zero-token, instantaneous deterministic classification
            complexity, reason = self.deterministic_engine.classify(query)
            print(f"[ModelRouter] Engine: DETERMINISTIC (0 tokens) | Rating: '{complexity.upper()}' | Reason: {reason}")
        else:
            # Optional LLM-based classification
            try:
                print(f"[ModelRouter] Engine: LLM Classifier | Model: '{self.classifier_model}'")
                sys_msg = SystemMessage(
                    content="You are a classification agent. Rate the complexity of the following user query as either 'simple' or 'complex'. Reply with a JSON object: {\"complexity\": \"simple\"} or {\"complexity\": \"complex\"}."
                )
                human_msg = HumanMessage(content=query)
                resp = self.classifier_llm.invoke([sys_msg, human_msg])
                
                content = getattr(resp, "content", "").strip().lower()
                if "complex" in content and "simple" not in content:
                    complexity = "complex"
                elif "complex" in content and "simple" in content:
                    try:
                        match = re.search(r'\{.*\}', content, re.DOTALL)
                        if match:
                            data = json.loads(match.group(0))
                            complexity = data.get("complexity", "simple").lower()
                    except Exception:
                        pass
                else:
                    complexity = "simple"
                reason = f"Classified by model '{self.classifier_model}'"
                print(f"[ModelRouter] LLM Classifier rated query as: '{complexity.upper()}'")
            except Exception as e:
                print(f"[ModelRouter] LLM Classifier failed ({e}). Falling back to deterministic engine.")
                complexity, reason = self.deterministic_engine.classify(query)
                print(f"[ModelRouter] Deterministic Engine rated query as: '{complexity.upper()}' | Reason: {reason}")

        if complexity == "complex":
            selected_model = self.llm_model
            fallback_model = self.llm_fallback
            routing_reason = reason or "Complex analytical request requiring strong reasoning."
        else:
            selected_model = self.slm_model
            fallback_model = self.slm_fallback
            routing_reason = reason or "Simple query, routing to small language model."
            
        print(f"[ModelRouter] Decision: Pipeline={'LLM' if complexity == 'complex' else 'SLM'} | Active Model='{selected_model}' | Fallback='{fallback_model}'\n")
        return {
            "selected_model": selected_model,
            "fallback_model": fallback_model,
            "complexity": complexity,
            "routing_reason": routing_reason
        }


model_router = ModelRouter()

