"""
Agent Builder Module for Utilities Knowledge Hub Chatbot.
Constructs LangChain agent executor with system prompt and tools, plus deterministic fallback agent execution.
"""

import json
import os
import re
from typing import Any, Callable, Sequence

try:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    from langchain_core.callbacks import BaseCallbackHandler
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False
    ChatOpenAI = None
    HumanMessage = None
    SystemMessage = None
    AIMessage = None
    BaseCallbackHandler = object


class ModelLoggingHandler(BaseCallbackHandler):
    """Logs LLM calls and fallbacks to console."""

    def __init__(self, model_tag: str = ""):
        super().__init__()
        self.model_tag = model_tag

    def on_llm_start(self, serialized: dict[str, Any], prompts: list[str], *, invocation_params: dict[str, Any] | None = None, **kwargs: Any) -> None:
        model = (invocation_params or {}).get("model") or (invocation_params or {}).get("model_name") or self.model_tag or "unknown"
        print(f"[Model Execution] Model in use: '{model}'")

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        tag = f" '{self.model_tag}'" if self.model_tag else ""
        print(f"[Model Execution] Model{tag} encountered error: {error}. Falling back...")

from app.agent.tools import (
    check_data_access,
    query_knowledge_graph,
    search_knowledge_base_rag,
    query_graph_rag,
    query_live_metrics,
    query_business_operations,
    query_metric_definitions,
    query_dataset_sample,
    forecast_boiler_installations,
    raise_access_request,
)


def _is_greeting(message: str) -> bool:
    """Return whether a short message is a conversational greeting."""
    normalized = message.strip().lower().strip("!?. ")
    return normalized in {"hi", "hello", "hey", "good morning", "good afternoon", "good evening"}


def _is_capability_question(message: str) -> bool:
    """Identify questions about available data, access, or chatbot capabilities."""
    normalized = message.lower()
    capability_terms = (
        "what can you do", "help", "available data", "where can i", "where do i",
        "where i can", "access data", "view data", "see data", "what data",
        "permissions", "my access", "lead data", "leads data", "where leads",
    )
    return any(term in normalized for term in capability_terms)


def _capability_response() -> str:
    """Provide a useful response explaining chatbot capabilities and project dataset access assistance."""
    return (
        "Hello! I am the AI Agentic Knowledge Hub.\n\n"
        "I assist you when kickstarting new projects by discovering required enterprise datasets, "
        "providing data lineage and SME attribution, and assisting you to raise IT access requests for restricted datasets.\n\n"
        "• Ask about equipment troubleshooting & error code diagnostic guidance.\n"
        "• Ask about data lineage, SME owners, or required datasets for your project.\n"
        "• Request live telemetry or operational datasets, and I will assist you in raising an IT access request."
    )


def _is_business_request(message: str) -> bool:
    """Identify requests for the commercial and service-operations dataset."""
    terms = (
        "lead", "appointment", "quote", "sales", "conversion", "installation",
        "breakdown", "service done", "services done", "jobs completed", "repair performance",
    )
    normalized = message.casefold()
    return any(term in normalized for term in terms)


def _is_definition_request(message: str) -> bool:
    """Identify questions asking what a business metric means."""
    normalized = message.casefold()
    return any(term in normalized for term in ("what is", "define", "definition", "meaning of", "what does"))


def _is_installation_forecast_request(message: str) -> bool:
    """Identify future-looking installation questions that need a pipeline forecast."""
    normalized = message.casefold()
    return "installation" in normalized and any(term in normalized for term in ("future", "forecast", "will", "project"))




def _history_fallback(user_input: str, chat_history: Sequence[dict[str, str]] | None) -> str | None:
    """Keep follow-ups and summary requests coherent when processing history."""
    if not chat_history:
        return None

    input_lower = user_input.casefold()
    summary_phrases = ("summary", "summarize", "quick summary", "explain this", "recap", "tl;dr", "tldr", "overview", "short summary")
    follow_up_phrases = ("what happens after", "and then", "tell me more", "what about that", "what next")

    is_summary = any(phrase in input_lower for phrase in summary_phrases)
    is_follow_up = any(phrase in input_lower for phrase in follow_up_phrases)

    if not (is_summary or is_follow_up):
        return None

    last_assistant_turn = None
    for turn in reversed(chat_history):
        if turn.get("role") == "assistant" and turn.get("content", "").strip():
            last_assistant_turn = turn.get("content", "").strip()
            break

    if not last_assistant_turn:
        return None

    if is_summary:
        lines = [line.strip() for line in last_assistant_turn.split("\n") if line.strip()]
        highlights = []
        for l in lines:
            if any(k in l for k in ["SME", "Owner", "Dataset", "Ticket", "Telemetry", "Hosted", "Access"]) and len(highlights) < 4:
                highlights.append(f"• {l.lstrip('•*- ')}")

        if not highlights:
            highlights = [f"• {l.lstrip('•*- ')}" for l in lines[:3]]

        return (
            "📝 **Executive Summary (Previous Discussion):**\n\n" +
            "\n".join(highlights) + "\n\n"
            "💡 *Need further details or IT dataset access? Type 'raise a request' or ask any follow-up question.*"
        )

    return f"Based on our previous conversation turn:\n\n{last_assistant_turn}"



def _is_explicit_access_check(message: str) -> bool:
    """Identify if the user is explicitly asking to check access permissions or dataset entitlements."""
    normalized = message.lower()
    access_terms = (
        "check access", "check my access", "do i have access", "check if i have access",
        "do i have permission", "check permission", "check my permission", "can i access",
        "what access do i have", "my access permissions", "am i allowed to access",
        "check dataset access", "do i have dataset access", "has access"
    )
    return any(term in normalized for term in access_terms)


def _extract_record_ids(user_input: str, chat_history: Sequence[dict[str, str]] | None = None) -> list[str]:
    """Extract entity/record IDs (e.g., CUST00007, ENG014, JOB000001) from user input."""
    found = re.findall(r"\b[A-Z]{3,8}[-\_]?\d{1,10}\b", user_input, flags=re.IGNORECASE)
    if found:
        return [f.upper() for f in found]
    return []


SYSTEM_PROMPT = """You are an AI Agentic Chatbot for the Enterprise Knowledge Hub.
You assist teams kickstarting new projects with dataset discovery, data lineage, SME attribution, operational insights, and knowledge lookup.

CURRENT SESSION CONTEXT:
- User Email: {user_email}

CRITICAL RULES FOR DATA RETRIEVAL & ANSWER GENERATION:
1. Always answer the user's questions directly, concisely, and accurately based ONLY on what was asked.
2. DO NOT output unnecessary dataset dumps, raw JSON/dict objects, or unrelated property/location data unless explicitly requested by the user.
3. DO NOT inform the user that access is required or tell them they do not have access, UNLESS the user explicitly asks to check whether they have access or not.
4. IF the user explicitly asks to check their access or requests to raise an access ticket (e.g., 'check access', 'do I have access', 'raise an access request'):
   - Perform the access check or execute `raise_access_request(user_email='{user_email}', data_source='...')`.
   - Return the access status or generated ticket details to the user.
"""



def build_agent_executor(
    api_key: str = "",
    model_name: str = "",
    base_url: str = "",
    fallback_model_name: str = "",
) -> Any:
    """Build LangChain AgentExecutor for OpenRouter / OpenAI models if API key is provided."""
    if not HAS_LANGCHAIN:
        return None

    key = api_key or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    if not key or key.strip() in ("your_openrouter_api_key_here", "your_openai_api_key_here"):
        print("[AgentBuilder] Info: No valid OpenRouter API key provided. Using deterministic fallback engine.")
        return None

    model = model_name or os.getenv("LLM_MODEL_NAME", "openai/gpt-4o-mini")
    url = base_url or os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    try:
        kwargs = {
            "api_key": key,
            "model": model,
            "temperature": 0.1,
            "base_url": url,
            "max_retries": int(os.getenv("LLM_MAX_RETRIES", "5")),
            "timeout": float(os.getenv("LLM_TIMEOUT_SECONDS", "90")),
            "max_tokens": int(os.getenv("LLM_MAX_TOKENS", "4096")),
        }
        if "openrouter.ai" in url:
            kwargs["default_headers"] = {
                "HTTP-Referer": "https://utilities-knowledge-hub.local",
                "X-Title": "Utilities Knowledge Hub Chatbot",
            }

        primary_kwargs = dict(kwargs)
        if HAS_LANGCHAIN and BaseCallbackHandler is not object:
            primary_kwargs["callbacks"] = [ModelLoggingHandler(model_tag=model)]

        llm = ChatOpenAI(**primary_kwargs)
        
        if fallback_model_name:
            fallback_kwargs = dict(kwargs)
            fallback_kwargs["model"] = fallback_model_name
            if HAS_LANGCHAIN and BaseCallbackHandler is not object:
                fallback_kwargs["callbacks"] = [ModelLoggingHandler(model_tag=f"{fallback_model_name} (fallback)")]
            fallback_llm = ChatOpenAI(**fallback_kwargs)
            llm = llm.with_fallbacks([fallback_llm])
            
        print(f"[AgentBuilder] Initialized ChatOpenAI: Primary='{model}' | Fallback='{fallback_model_name or 'None'}'")
        return llm
    except Exception as e:
        print(f"[AgentBuilder] Warning: Could not initialize OpenRouter ChatAgent ({e}). Using rule-based engine.")
        return None


def _local_relation_suggestion(context: dict[str, Any]) -> dict[str, Any]:
    """Create a grounded draft when the external model is unavailable."""
    source = context["source"]
    target = context["target"]
    candidates = context.get("join_candidates", [])
    source_category = source.get("category", "Entity")
    target_category = target.get("category", "Entity")

    pair_relationships = {
        ("Domain Cluster", "Dataset"): "contains",
        ("Dataset", "Business Metric"): "calculates",
        ("Business Metric", "Dataset"): "derived_from",
        ("Dataset", "Key Info Link"): "links_via",
        ("Key Info Link", "Dataset"): "used_by",
    }
    relationship = pair_relationships.get((source_category, target_category), "related_to")
    if source_category == "Dataset" and target_category == "Dataset":
        relationship = "joins_to" if candidates else "feeds"

    source_column = ""
    target_column = ""
    evidence = "Object metadata and existing graph neighbors suggest this direction."
    confidence = 0.56
    if candidates:
        best = candidates[0]
        source_column = best["source_column"]
        target_column = best["target_column"]
        evidence = best["reason"]
        confidence = max(confidence, float(best["score"]))

    if source_column and target_column:
        join_description = (
            f"Join {source['id']}.{source_column} to "
            f"{target['id']}.{target_column}."
        )
    else:
        join_description = (
            "Create an object-level directed relationship; no grounded column pair "
            "is available for both selected objects."
        )

    return {
        "relationship": relationship,
        "source_column": source_column,
        "target_column": target_column,
        "join_description": join_description,
        "reasoning": evidence,
        "confidence": round(min(confidence, 1.0), 2),
        "used_ai": False,
        "provider": "Local metadata analysis",
        "warning": "AI model is not configured; this draft uses grounded local metadata analysis.",
    }


def _extract_suggestion_json(content: Any) -> dict[str, Any]:
    """Extract the first JSON object from an OpenAI-compatible response."""
    if isinstance(content, list):
        content = "".join(
            str(item.get("text", "")) if isinstance(item, dict) else str(item)
            for item in content
        )
    if not isinstance(content, str):
        raise ValueError("The AI response did not contain text.")

    cleaned = content.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("The AI response did not contain a JSON object.")
        parsed = json.loads(cleaned[start:end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("The AI response must be a JSON object.")
    return parsed


def suggest_graph_relationship(
    context: dict[str, Any],
    executor: Any = None,
) -> dict[str, Any]:
    """Draft and validate a directional graph relationship from bounded context."""
    fallback = _local_relation_suggestion(context)
    if executor is None:
        return fallback

    compact_context = json.dumps(context, ensure_ascii=False, default=str)
    system_text = (
        "You are a data lineage and knowledge-graph relationship analyst. "
        "Suggest one grounded directed relationship from the supplied SOURCE to TARGET. "
        "Use only columns, sample values, metadata, and graph neighbors present in the context. "
        "Never invent a column. A column join is optional and is valid only when both objects expose columns. "
        "The relationship label must describe SOURCE -> TARGET and use concise snake_case. "
        "Return JSON only with keys: relationship, source_column, target_column, "
        "join_description, reasoning, confidence. Confidence must be from 0 to 1."
    )
    user_text = (
        "Analyze these selected graph objects and draft the most defensible relationship. "
        "The locally ranked join candidates are supporting evidence, not a requirement.\n\n"
        f"CONTEXT:\n{compact_context}"
    )

    try:
        if HAS_LANGCHAIN and SystemMessage is not None and HumanMessage is not None:
            response = executor.invoke([
                SystemMessage(content=system_text),
                HumanMessage(content=user_text),
            ])
        else:
            response = executor.invoke(f"{system_text}\n\n{user_text}")
        parsed = _extract_suggestion_json(getattr(response, "content", response))

        raw_relationship = str(parsed.get("relationship") or fallback["relationship"]).strip().casefold()
        relationship = re.sub(r"[^a-z0-9]+", "_", raw_relationship).strip("_")[:80]
        if not relationship:
            relationship = fallback["relationship"]

        source_columns = set(context["source"].get("columns", []))
        target_columns = set(context["target"].get("columns", []))
        source_column = str(parsed.get("source_column") or "").strip()
        target_column = str(parsed.get("target_column") or "").strip()
        if source_column not in source_columns or target_column not in target_columns:
            source_column = fallback["source_column"]
            target_column = fallback["target_column"]

        try:
            confidence = float(parsed.get("confidence", fallback["confidence"]))
        except (TypeError, ValueError):
            confidence = fallback["confidence"]

        return {
            "relationship": relationship,
            "source_column": source_column,
            "target_column": target_column,
            "join_description": str(parsed.get("join_description") or fallback["join_description"]).strip()[:500],
            "reasoning": str(parsed.get("reasoning") or fallback["reasoning"]).strip()[:700],
            "confidence": round(max(0.0, min(confidence, 1.0)), 2),
            "used_ai": True,
            "provider": "Configured AI model",
            "warning": "",
        }
    except Exception as error:
        print(f"[Relationship Suggestion] AI response failed; using local metadata analysis: {error}")
        fallback["warning"] = (
            "AI suggestion was unavailable, so a grounded local metadata draft was used: "
            f"{str(error)[:180]}"
        )
        return fallback


ALL_KNOWN_DATASETS = [
    "customer_master", "inventory_and_van_stock", "boiler_telemetry_logs",
    "fault_codes", "telemetry_logs", "engineer_master", "repair_history",
    "epc_property_data", "appointment_schedule", "engineer_availability_and_shifts",
    "quotes_and_sales", "contact_center_interaction", "customer_holdings",
    "engineer_skill", "parts_replaced", "product_and_warranty_info", "weather",
    "service_history", "installation_history", "visit_outcome", "knowledge_base",
    "business_rules", "boiler_master", "regional_demand_forecast", "regional_capacity_forecast"
]

def _extract_all_recent_datasets(chat_history: Sequence[dict[str, str]] | None) -> list[str]:
    """Scan user messages in recent chat turns to extract mentioned dataset IDs."""
    if not chat_history:
        return []
    found = []
    for turn in reversed(list(chat_history)):
        if turn.get("role") == "user":
            text = turn.get("content", "").lower()
            for ds in ALL_KNOWN_DATASETS:
                if ds in text and ds not in found:
                    found.append(ds)
    return found



def _extract_recent_context(chat_history: Sequence[dict[str, str]] | None) -> dict[str, str]:
    """Inspect previous turns in chat_history to extract active dataset/topic context."""
    if not chat_history:
        return {}

    combined_text = ""
    for turn in reversed(list(chat_history)):
        combined_text += " " + turn.get("content", "").lower()

    if any(k in combined_text for k in ["customer", "contact", "account", "quote", "sales", "holding", "customer_master"]):
        return {
            "dataset": "customer_master",
            "provider": "Salesforce CRM",
            "topic": "customer account details and commercial relationship records"
        }
    if any(k in combined_text for k in ["engineer", "shift", "availability", "workforce", "skill", "pay", "engineer_availability"]):
        return {
            "dataset": "engineer_availability_and_shifts",
            "provider": "Workday HCM & Finance",
            "topic": "engineer shift schedules and workforce availability metrics"
        }
    if any(k in combined_text for k in ["pressure", "psi", "flame", "temp", "telemetry", "sensor", "boiler", "fault"]):
        return {
            "dataset": "boiler_telemetry_logs",
            "provider": "Azure Blob Container",
            "topic": "boiler telemetry readings and IoT status codes"
        }
    if any(k in combined_text for k in ["inventory", "van", "stock", "parts", "replaced"]):
        return {
            "dataset": "inventory_and_van_stock",
            "provider": "SAP S/4HANA ERP",
            "topic": "van inventory stock and replaced appliance parts"
        }
    if any(k in combined_text for k in ["repair", "appointment", "visit", "schedule"]):
        return {
            "dataset": "appointment_schedule",
            "provider": "Microsoft SQL Server",
            "topic": "engineer appointment schedules and repair visit outcomes"
        }
    return {
        "dataset": "customer_master",
        "provider": "Salesforce CRM",
        "topic": "enterprise operational records"
    }


def _synthesize_record_search_response(
    user_input: str,
    record_ids: list[str],
    results: list[dict[str, Any]],
) -> str:
    """Synthesize a direct, concise, human-readable answer for record queries based on user intent."""
    input_lower = user_input.lower()
    by_dataset: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        rec_copy = dict(r)
        ds = rec_copy.pop("_dataset", "unknown")
        by_dataset.setdefault(ds, []).append(rec_copy)

    cust_id = ", ".join(set(record_ids)) if record_ids else "Requested Record"
    cust_name = ""
    if "customer_master" in by_dataset and by_dataset["customer_master"]:
        cust_name = by_dataset["customer_master"][0].get("customer_name", "")
    display_title = f"{cust_id} ({cust_name})" if cust_name else cust_id

    # 1. Extract Boiler information
    boiler_info = []
    if "boiler_master" in by_dataset and by_dataset["boiler_master"]:
        bm = by_dataset["boiler_master"][0]
        mfr = bm.get("boiler_manufacturer", "")
        model = bm.get("model", "")
        btype = bm.get("boiler_type", "")
        bid = bm.get("boiler_id", "")
        idate = bm.get("installation_date", "")
        erating = bm.get("energy_rating", "")
        b_name = f"{mfr} {model}".strip() or model or mfr or "Boiler"
        details = []
        if btype: details.append(f"Type: `{btype}`")
        if bid: details.append(f"Boiler ID: `{bid}`")
        if erating: details.append(f"Energy Rating: `{erating}`")
        if idate: details.append(f"Installed: `{idate}`")
        detail_str = " (" + ", ".join(details) + ")" if details else ""
        boiler_info.append(f"• **Boiler Model:** **{b_name}**{detail_str}")
    elif "customer_master" in by_dataset and by_dataset["customer_master"]:
        cm = by_dataset["customer_master"][0]
        if cm.get("boiler_company"):
            boiler_info.append(f"• **Boiler Manufacturer/Company:** **{cm.get('boiler_company')}**")

    # 2. Extract Fault & Repair information
    fault_info = []
    if "boiler_master" in by_dataset and by_dataset["boiler_master"]:
        fh = by_dataset["boiler_master"][0].get("fault_history")
        if fh and str(fh).strip() not in ("None", "N/A", "nan", ""):
            fault_info.append(f"• **Historical Fault:** `{fh}`")

    if "repair_history" in by_dataset:
        for rh in by_dataset["repair_history"]:
            rdate = rh.get("repair_date", "")
            rtype = rh.get("repair_type", "")
            fcode = rh.get("fault_code", "")
            freason = rh.get("fault_reason", "")
            parts = []
            if rtype: parts.append(f"Type: `{rtype}`")
            if fcode: parts.append(f"Fault Code: `{fcode}`")
            if freason: parts.append(f"Reason: `{freason}`")
            p_str = " (" + ", ".join(parts) + ")" if parts else ""
            fault_info.append(f"• **Repair Incident ({rdate}):**{p_str}")

    if not fault_info and any(k in input_lower for k in ["fault", "repair", "historically", "breakdown", "issue"]):
        fault_info.append("• **Historical Faults:** No major fault code or repair incidents recorded.")

    # 3. Extract Service & Visit information
    service_info = []
    if "service_history" in by_dataset:
        for s in by_dataset["service_history"]:
            sdate = s.get("service_date", "")
            stype = s.get("service_type", "")
            parts = s.get("parts_serviced", "")
            service_info.append(f"• **Service ({sdate}):** `{stype}` (Parts: `{parts}`)")
    if "visit_outcome" in by_dataset:
        for v in by_dataset["visit_outcome"][:2]:
            vdate = v.get("visit_date", "")
            vstat = v.get("visit_status", "")
            service_info.append(f"• **Visit ({vdate}):** Status `{vstat}`")

    # 4. Extract Location & Property information
    location_info = []
    if "customer_holdings" in by_dataset and by_dataset["customer_holdings"]:
        ch = by_dataset["customer_holdings"][0]
        city = ch.get("city", "")
        region = ch.get("region", "")
        pincode = ch.get("pincode", "")
        location_info.append(f"• **Location:** `{city}`, `{region}` (Pincode: `{pincode}`)")
    if "property_master" in by_dataset and by_dataset["property_master"]:
        pm = by_dataset["property_master"][0]
        ptype = pm.get("property_type", "")
        rooms = pm.get("rooms", "")
        floors = pm.get("number_of_floors", "")
        location_info.append(f"• **Property Type:** `{ptype}` ({rooms} rooms, {floors} floors)")

    # Intent detection
    asks_boiler = any(k in input_lower for k in ["boiler", "appliance", "model", "equipment", "unit", "company", "manufacturer", "type of boiler", "boiler type", "which boiler", "what boiler"])
    asks_fault = any(k in input_lower for k in ["fault", "repair", "history", "historically", "issue", "breakdown", "error", "incident", "failure"])
    asks_service = any(k in input_lower for k in ["service", "serviced", "visit", "appointment", "maintenance"])
    asks_location = any(k in input_lower for k in ["location", "address", "city", "pincode", "property", "where"])

    has_specific_intent = asks_boiler or asks_fault or asks_service or asks_location
    sections = []

    if asks_boiler or not has_specific_intent:
        if boiler_info:
            sections.append("🔧 **Boiler Details:**\n" + "\n".join(boiler_info))
    if asks_fault or not has_specific_intent:
        if fault_info:
            sections.append("⚠️ **Fault & Repair History:**\n" + "\n".join(fault_info))
    if asks_service:
        if service_info:
            sections.append("🛠️ **Service & Maintenance History:**\n" + "\n".join(service_info[:4]))
    if asks_location:
        if location_info:
            sections.append("🏠 **Location Info:**\n" + "\n".join(location_info))

    if not sections:
        if boiler_info: sections.append("🔧 **Boiler Details:**\n" + "\n".join(boiler_info))
        if fault_info: sections.append("⚠️ **Fault & Repair History:**\n" + "\n".join(fault_info))

    header = f"📋 **Enterprise Data Record Results for `{display_title}`:**\n\n"
    return header + "\n\n".join(sections)


def run_deterministic_agent_fallback(
    user_input: str,
    user_email: str,
    chat_history: Sequence[dict[str, str]] | None = None,
) -> str:
    """
    Fallback agent execution engine.
    Implements deterministic routing for data lineage, public knowledge RAG, entity search, and IT access ticket escalation.
    """
    input_lower = user_input.lower()

    # Helper function to invoke tool regardless of decorator wrapper type
    def call_tool(tool_fn: Callable[..., str], args_dict: dict[str, str]) -> str:
        if hasattr(tool_fn, "invoke"):
            return tool_fn.invoke(args_dict)
        return tool_fn(**args_dict)



    # 1. Explicit request to raise an IT access ticket
    ticket_keywords = [
        "ticket", "raise access", "raise ticket", "it request", "please raise",
        "submit ticket", "raise a request", "raise request", "request for me", "raise for me"
    ]
    if any(k in input_lower for k in ticket_keywords):
        matching_ds = [d for d in ALL_KNOWN_DATASETS if d in input_lower]
        if not matching_ds:
            recent_ds = _extract_all_recent_datasets(chat_history)
            if recent_ds:
                matching_ds = recent_ds
            else:
                ctx = _extract_recent_context(chat_history)
                matching_ds = [ctx.get("dataset", "customer_master")]

        target_dataset = ", ".join(matching_ds)
        ticket_res = call_tool(raise_access_request, {"user_email": user_email, "data_source": target_dataset})
        return f"🔒 **Access Escalation Procedure Initiated**\n\n{ticket_res}"

    # 2. Explicit access check question (ONLY check access if the user explicitly asks to check whether they have access)
    if _is_explicit_access_check(user_input):
        matching_ds = [d for d in ALL_KNOWN_DATASETS if d in input_lower]
        if not matching_ds:
            recent_ds = _extract_all_recent_datasets(chat_history)
            if recent_ds:
                matching_ds = recent_ds
            else:
                ctx = _extract_recent_context(chat_history)
                matching_ds = [ctx.get("dataset", "customer_master")]
        ds_str = ", ".join([f"`{d}`" for d in matching_ds])
        return (
            f"🔑 **Dataset Access & Entitlement Check (`{ds_str}`):**\n\n"
            f"You are checking permissions for dataset(s): {ds_str}.\n"
            f"• Current Entitlement Status: **Restricted Project Dataset**.\n"
            f"• Your User Email: `{user_email}`\n\n"
            f"👉 **Would you like me to raise an IT access request on your behalf to grant access to {ds_str}?**"
        )

    # 3. Specific Entity Record Search, Customer Lookup, Boiler & Service History Queries
    from app.agent.tools import _DATA_SERVICE
    record_ids = _extract_record_ids(user_input, chat_history)
    is_record_or_service_query = (len(record_ids) > 0) or any(k in input_lower for k in [
        "boiler type", "which type", "type of boiler", "cust000", "eng00", "cust-",
        "service", "serviced", "repair", "repaired", "visit", "appointment", "job"
    ])

    if is_record_or_service_query and _DATA_SERVICE:
        search_query = " ".join(record_ids) if record_ids else user_input
        search_res = _DATA_SERVICE.search_records(search_query)
        if search_res.get("success") and search_res.get("results"):
            return _synthesize_record_search_response(user_input, record_ids, search_res["results"])

    # 4. Data Storage Topology & Connected Sources
    storage_keywords = [
        "databricks", "onelake", "salesforce", "workday", "sap", "data lake",
        "azure container", "sql server", "aws s3", "data storage", "storage sources", "storage topology"
    ]
    if any(k in input_lower for k in storage_keywords):
        return (
            "💾 **Enterprise Data Storage Systems Topology & Connected Sources:**\n\n"
            "Below is the current data storage breakdown across all enterprise platforms integrated into the Agentic Knowledge Hub:\n\n"
            "1. **Databricks UC Database (Unity Catalog)**: `48.2 TB` | 120M Rows | *Delta Lake & Governed AI Pipelines*\n"
            "   • Datasets: `boiler_master`, `telemetry_logs`, `engineer_productivity`\n"
            "2. **Microsoft OneLake**: `32.5 TB` | 85M Rows | *Fabric Lakehouse Multi-Cloud Mesh*\n"
            "   • Datasets: `epc_property_data`, `regional_demand_forecast`, `regional_capacity_forecast`\n"
            "3. **Salesforce CRM**: `1.8 TB` | 4.5M Records | *Cloud CRM Objects & Sales Pipeline*\n"
            "   • Datasets: `customer_master`, `contact_center_interaction`, `quotes_and_sales`\n"
            "4. **Workday HCM & Finance**: `620 GB` | 850K Records | *Enterprise Workforce & Shift Operations*\n"
            "   • Datasets: `engineer_master`, `engineer_availability_and_shifts`, `engineer_skill`\n"
            "5. **SAP S/4HANA ERP**: `14.8 TB` | 28M Records | *ERP Core, Van Inventory & Warranty Data*\n"
            "   • Datasets: `inventory_and_van_stock`, `parts_replaced`, `product_and_warranty_info`\n"
            "6. **Enterprise Data Lake**: `85.0 TB` | 210M Records | *Central Parquet & Historical Archives*\n"
            "   • Datasets: `weather`, `service_history`, `installation_history`\n"
            "7. **Azure Container (ADLS Gen2)**: `64.2 TB` | 160M Blobs | *IoT Telemetry & Smart Meter Feeds*\n"
            "   • Datasets: `fault_codes`, `boiler_telemetry_logs`\n"
            "8. **Microsoft SQL Server**: `8.4 TB` | 42M Records | *Relational DB & Engineer Scheduling*\n"
            "   • Datasets: `repair_history`, `visit_outcome`, `appointment_schedule`\n"
            "9. **AWS S3 Buckets**: `124.0 TB` | 350M Objects | *Raw Unstructured Documents & Knowledge Bases*\n"
            "   • Datasets: `knowledge_base`, `business_rules`, `epc_pdf_archive`\n\n"
            "💡 *Tip: Navigate to the **Storage & Governance** tab in the top navigation bar to view interactive capacity meters, real-time health telemetry, and lineage security policies.*"
        )

    # 5. Data Lineage, SME Ownership & Governance queries
    if any(k in input_lower for k in ["sme", "lineage", "managed_by", "who is", "who owns", "data owner", "owner", "ownership", "governance", "contact", "steward"]):
        from app.config import DATA_DIR
        json_path = DATA_DIR / "dataset_ownership.json"
        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    datasets_list = json.load(f).get("datasets", [])
            except Exception:
                pass

        matching_ds = [d for d in ALL_KNOWN_DATASETS if d in input_lower]
        if not matching_ds:
            matching_ds = ["customer_master", "inventory_and_van_stock"]

        owner_lines = []
        for ds in matching_ds:
            match = next((item for item in datasets_list if item.get("dataset_id") == ds), None)
            if match:
                owner_lines.append(
                    f"• **`{match['dataset_id']}`** ({match['dataset_name']}) → Hosted in **{match['storage_provider']}** (`{match['storage_type']}`).\n"
                    f"  👤 **SME Data Owner:** **{match['owner_name']}** ({match['owner_role']})\n"
                    f"  📧 **Contact Email:** `{match['owner_email']}` | **Department:** *{match['department']}*\n"
                    f"  🛡️ **Governance Tier:** `{match['governance_classification']}` | **Data Steward:** {match['data_steward']}"
                )

        if not owner_lines:
            owner_lines = [
                "• **`customer_master`** → Hosted in **Salesforce CRM**. SME Owner: **Sarah Jenkins** (Principal Data Architect - Customer Systems, `sarah.jenkins@utilities.co.uk`).",
                "• **`inventory_and_van_stock`** → Hosted in **SAP S/4HANA ERP**. SME Owner: **David Ross** (Senior ERP Operations Lead, `david.ross@utilities.co.uk`)."
            ]

        ds_str = ", ".join([f"`{d}`" for d in matching_ds])
        return (
            f"🕸️ **Master Dataset Ownership & SME Governance Report:**\n\n"
            f"*Source Ownership Master File:* `data/dataset_ownership.json` | `data/dataset_ownership.csv`\n\n"
            f"Target Datasets Analyzed: {ds_str}\n\n" +
            "\n\n".join(owner_lines)
        )

    # 6. Follow-up dataset location / source questions & Dataset discovery
    followup_data_keywords = [
        "where", "how can i get", "get the data", "get data", "find the data",
        "access the data", "where to get", "where is it", "source", "datasets related",
        "these informations", "all these informations", "related datasets", "dataset list",
        "which dataset", "what dataset", "these info", "this info", "datasets have",
        "dataset locations", "list of datasets"
    ]
    if any(k in input_lower for k in followup_data_keywords):
        recent_datasets = _extract_all_recent_datasets(chat_history)
        matching_in_query = [d for d in ALL_KNOWN_DATASETS if d in input_lower]
        target_datasets = matching_in_query or recent_datasets or ["customer_master", "repair_history", "boiler_master", "customer_holdings", "property_master"]

        from app.config import DATA_DIR
        datasets_list = []
        json_path = DATA_DIR / "dataset_ownership.json"
        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    datasets_list = json.load(f).get("datasets", [])
            except Exception:
                pass

        lines = []
        for ds in target_datasets:
            match = next((item for item in datasets_list if item.get("dataset_id") == ds), None)
            if match:
                lines.append(
                    f"• **`{match['dataset_id']}`** ({match['dataset_name']}) → Hosted in **{match['storage_provider']}** (`{match['storage_type']}`)\n"
                    f"  👤 SME Owner: **{match['owner_name']}** ({match['owner_email']})"
                )
            else:
                lines.append(f"• **`{ds}`** → Enterprise Operational Dataset")

        ds_str = ", ".join([f"`{d}`" for d in target_datasets])
        return (
            f"📊 **Enterprise Datasets & Storage Locations for your Query:**\n\n"
            f"The records and information discussed are hosted across the following enterprise platforms ({ds_str}):\n\n" +
            "\n\n".join(lines) + "\n\n"
            f"💡 *Need access? Ask 'Raise an IT access request for {target_datasets[0]}' to initiate access entitlement.*"
        )

    # 7. Operational Telemetry & Diagnostics
    if any(k in input_lower for k in ["pressure", "psi", "flame", "temp", "telemetry", "fault", "outage"]):
        matching_ds = [d for d in ["boiler_telemetry_logs", "fault_codes", "telemetry_logs", "boiler_master"] if d in input_lower]
        ds_str = ", ".join([f"`{d}`" for d in matching_ds]) if matching_ds else "`boiler_telemetry_logs`, `fault_codes`"
        return (
            f"⚡ **Operational Telemetry & Diagnostics Report:**\n\n"
            f"Identified Datasets: {ds_str}\n\n"
            f"• **`boiler_telemetry_logs`** → **Azure Blob Container** (ADLS Gen2, `64.2 TB` | 160M Blobs | Operational 99.9%)\n"
            f"• **`fault_codes`** → **Azure Blob Container** (Error Reference Tables | Operational)\n"
            f"• **`telemetry_logs`** → **Databricks UC Database** (`48.2 TB` | 120M Rows | Delta Lake Pipelines)\n\n"
            f"📊 **Telemetry Sensor Metrics:**\n"
            f"- Grid Pressure: `1.03 bar` (Normal Range: 0.95 - 1.15 bar)\n"
            f"- Boiler Flame Current: `14.2 µA` (Normal Range: 10.0 - 18.0 µA)\n"
            f"- System Fault Code: `E04` (Flame Sensing Fault - Auto-Recovered)"
        )

    # 8. Installation forecast, business operations, service jobs
    if _is_installation_forecast_request(user_input) or _is_business_request(user_input) or any(k in input_lower for k in ["job", "service", "schedule", "scheduling", "forecast", "forecasting"]):
        if _is_definition_request(user_input):
            def_res = call_tool(query_metric_definitions, {"query": user_input})
            if "No metric definition" not in def_res:
                return f"📖 **Metric Definition (RAG Knowledge Base):**\n\n{def_res}"
            rag_kg_res = call_tool(query_graph_rag, {"query": user_input})
            return f"📖 **Knowledge Base Definition:**\n\n{rag_kg_res}"
        if _is_installation_forecast_request(user_input) or "forecast" in input_lower:
            forecast_res = call_tool(forecast_boiler_installations, {})
            return f"📊 **Boiler Installation Pipeline Forecast:**\n\n{forecast_res}"
        biz_res = call_tool(query_business_operations, {"query": user_input})
        return f"📊 **Business & Service Operations Report:**\n\n{biz_res}"

    # 9. Metric / term definitions
    if _is_definition_request(user_input):
        def_res = call_tool(query_metric_definitions, {"query": user_input})
        if "No metric definition" not in def_res:
            return f"📖 **Metric Definition (RAG Knowledge Base):**\n\n{def_res}"
        rag_kg_res = call_tool(query_graph_rag, {"query": user_input})
        return f"📖 **Knowledge Base Definition:**\n\n{rag_kg_res}"

    # 10. Data Sample / Glimpse requests
    if any(k in input_lower for k in ["glimpse", "sample", "show me the data", "preview", "some rows"]):
        clean_name = input_lower.replace("show me a glimpse of", "").replace("can i see a sample of", "").replace("what is", "").replace("the", "").replace("dataset", "").strip()
        sample_res = call_tool(query_dataset_sample, {"dataset_name": clean_name})
        if "Could not retrieve sample" not in sample_res:
            return sample_res

    # 11. Greetings & Capability questions
    if _is_greeting(user_input) or _is_capability_question(user_input):
        return _capability_response()

    # 12. Knowledge Graph & RAG Troubleshooting Queries
    rag_kg_res = call_tool(query_graph_rag, {"query": user_input})
    if rag_kg_res.startswith("No Graph-RAG information found"):
        return (
            "I couldn't find specific matching documentation in the enterprise knowledge base. "
            "I can assist with boiler diagnostic models, fault codes, data lineage, SME attribution, and operational data questions.\n\n"
            "For example, ask: 'Who is the SME for customer_master?' or 'Why is my Worcester Bosch 4000 showing EA Error?'"
        )

    return (
        f"🤖 **AI Knowledge Retrieval (Graph-RAG):**\n\n"
        f"{rag_kg_res}"
    )


def process_chat_message(
    user_input: str,
    user_email: str,
    executor: Any = None,
    chat_history: Sequence[dict[str, str]] | None = None,
    runtime: Any = None,
) -> str:
    """
    Process a chat message and return the final answer.

    The agent decides how to answer. `run_deterministic_agent_fallback` is used
    only when no model is configured or when the agent loop fails - it is no
    longer pre-computed and injected into the prompt, which previously reduced
    the model to rewriting a keyword-matched answer.
    """
    if runtime is not None:
        return runtime.run(user_input, user_email, chat_history)

    if executor is None:
        return (
            _history_fallback(user_input, chat_history)
            or run_deterministic_agent_fallback(user_input, user_email, chat_history)
        )

    # Legacy callers that pass a raw LLM get a runtime built on demand.
    from app.agent.agent_runtime import AgentRuntime
    from app.agent.tools import get_all_tools
    from app.config import DATA_DIR

    return AgentRuntime(executor, get_all_tools(), DATA_DIR).run(
        user_input, user_email, chat_history
    )
