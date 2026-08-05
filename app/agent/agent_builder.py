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
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False
    ChatOpenAI = None
    HumanMessage = None
    SystemMessage = None
    AIMessage = None

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
    """Keep a follow-up coherent if the external model is temporarily unavailable."""
    follow_up_phrases = ("what happens after", "and then", "tell me more", "what about that", "what next")
    if not chat_history or not any(phrase in user_input.casefold() for phrase in follow_up_phrases):
        return None
    for turn in reversed(chat_history):
        if turn.get("role") == "assistant" and turn.get("content", "").strip():
            return f"Based on our previous answer:\n\n{turn['content']}"
    return None


SYSTEM_PROMPT = """You are an AI Agentic Chatbot for the Enterprise Knowledge Hub.
You assist teams kickstarting new projects with dataset discovery, data lineage, SME attribution, and automated IT access requests.

CURRENT SESSION CONTEXT:
- User Email: {user_email}

CRITICAL RULES FOR DATA RETRIEVAL & AI ANSWER GENERATION:
1. When responding to user questions about equipment troubleshooting, error codes, appliance models, or maintenance procedures:
   - Use RAG tools (`search_knowledge_base_rag` or `query_graph_rag`) to retrieve documentation snippets and remedy facts.
   - Synthesize the retrieved RAG context into a clear, accurate AI answer.
2. CRITICAL RULES FOR DATASETS & ACCESS REQUESTS:
   - Users do not have default access to raw operational datasets (`Live_Metrics`, `Business_Operations`, `System_Logs`).
   - When a user asks to access or view operational dataset records, inform them that access to the dataset is required for their project and ask if they would like you to raise an IT access request.
3. IF the user requests or confirms raising an access ticket:
   - Execute `raise_access_request(user_email='{user_email}', data_source='...')`.
   - Return the generated ticket number and approval details to the user.
"""


def build_agent_executor(
    api_key: str = "",
    model_name: str = "",
    base_url: str = "",
) -> Any:
    """Build LangChain AgentExecutor for OpenRouter / OpenAI models if API key is provided."""
    if not HAS_LANGCHAIN:
        return None

    key = api_key or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    if not key or key.strip() in ("your_openrouter_api_key_here", "your_openai_api_key_here"):
        print("[AgentBuilder] Info: No valid OpenRouter API key provided. Using deterministic fallback engine.")
        return None

    model = model_name or os.getenv("OPENROUTER_MODEL_NAME") or os.getenv("LLM_MODEL", "openai/gpt-4o-mini")
    url = base_url or os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    try:
        kwargs = {
            "api_key": key,
            "model": model,
            "temperature": 0.1,
            "base_url": url,
        }
        if "openrouter.ai" in url:
            kwargs["default_headers"] = {
                "HTTP-Referer": "https://utilities-knowledge-hub.local",
                "X-Title": "Utilities Knowledge Hub Chatbot",
            }

        llm = ChatOpenAI(**kwargs)
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


def _extract_recent_context(chat_history: Sequence[dict[str, str]] | None) -> dict[str, str]:
    """Inspect previous turns in chat_history to extract active dataset/topic context."""
    if not chat_history:
        return {}

    combined_text = ""
    for turn in reversed(list(chat_history)):
        combined_text += " " + turn.get("content", "").lower()

    if any(k in combined_text for k in ["sales", "conversion", "lead", "appointment", "quote", "business_operations", "sales_funnel", "installation"]):
        return {
            "dataset": "Business_Operations",
            "dataset_file": "Business_Operations.xlsx",
            "topic": "sales conversion and commercial operational metrics"
        }
    if any(k in combined_text for k in ["pressure", "psi", "flame", "temp", "telemetry", "live_metrics", "sensor"]):
        return {
            "dataset": "Live_Metrics",
            "dataset_file": "Live_Metrics.xlsx",
            "topic": "live telemetry and grid pressure metrics"
        }
    return {}


def run_deterministic_agent_fallback(
    user_input: str,
    user_email: str,
    chat_history: Sequence[dict[str, str]] | None = None,
) -> str:
    """
    Fallback agent execution engine.
    Implements deterministic routing for data lineage, public knowledge RAG, and IT access ticket escalation.
    """
    input_lower = user_input.lower()

    # Helper function to invoke tool regardless of decorator wrapper type
    def call_tool(tool_fn: Callable[..., str], args_dict: dict[str, str]) -> str:
        if hasattr(tool_fn, "invoke"):
            return tool_fn.invoke(args_dict)
        return tool_fn(**args_dict)

    # Rule 0.5: Explicit request for storage sources / storage systems
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


    # Rule 0: Follow-up question asking where to get data / dataset access for previous turn topic
    followup_data_keywords = [
        "where", "how can i get", "get the data", "get data", "find the data",
        "access the data", "access it", "where to get", "where is it", "source", "dataset"
    ]
    if any(k in input_lower for k in followup_data_keywords):
        ctx = _extract_recent_context(chat_history)
        if ctx:
            ds = ctx["dataset"]
            file_name = ctx["dataset_file"]
            topic = ctx["topic"]
            return (
                f"📊 **Dataset Identified:**\n"
                f"The {topic} discussed in our previous turn is located in the **{ds}** dataset (`{file_name}`).\n\n"
                f"⛔ **Dataset Access Required:**\n"
                f"You currently do not have active access permissions for **{ds}**.\n\n"
                f"👉 **Would you like me to raise an IT access request on your behalf to grant access to '{ds}'?**"
            )

    # Rule 1: User confirms ticket request / wants to raise ticket for dataset
    ticket_keywords = ["ticket", "raise access", "raise ticket", "it request", "yes", "please raise", "submit ticket"]
    if any(k in input_lower for k in ticket_keywords):
        target_dataset = "Live_Metrics"
        ctx = _extract_recent_context(chat_history)
        if ctx:
            target_dataset = ctx["dataset"]
        elif "business" in input_lower or "funnel" in input_lower or "sales" in input_lower:
            target_dataset = "Business_Operations"
        ticket_res = call_tool(raise_access_request, {"user_email": user_email, "data_source": target_dataset})
        return f"🔒 **Access Escalation Procedure Initiated**\n\n{ticket_res}"

    # Rule 2: Data Lineage, SME Ownership & Governance queries
    if any(k in input_lower for k in ["sme", "lineage", "managed_by", "data owner", "owner", "governance", "dashboard"]):
        rag_kg_res = call_tool(query_graph_rag, {"query": user_input})
        return f"🕸️ **Data Lineage & SME Governance:**\n\n{rag_kg_res}"

    # Rule 3: Live Metrics / Telemetry dataset access request
    if any(k in input_lower for k in ["pressure", "psi", "flame", "temp", "telemetry", "flow", "outage"]):
        return (
            f"📊 **Dataset Identified:**\n"
            f"The operational telemetry data required for your query/project is located in the **Live_Metrics** dataset (`Live_Metrics.xlsx`).\n\n"
            f"⛔ **Dataset Access Required:**\n"
            f"You currently do not have active access permissions for **Live_Metrics**.\n\n"
            f"👉 **Would you like me to raise an IT access request on your behalf to grant access to 'Live_Metrics'?**"
        )

    # Rule 4: Predictive installation forecast, service jobs, scheduling, or operational dataset queries
    if _is_installation_forecast_request(user_input) or _is_business_request(user_input) or any(k in input_lower for k in ["job", "service", "schedule", "scheduling", "forecast", "forecasting"]):
        if _is_definition_request(user_input):
            def_res = call_tool(query_metric_definitions, {"query": user_input})
            if "No metric definition" not in def_res:
                return f"📖 **Metric Definition (RAG Knowledge Base):**\n\n{def_res}"
            rag_kg_res = call_tool(query_graph_rag, {"query": user_input})
            return f"📖 **Knowledge Base Definition:**\n\n{rag_kg_res}"
        return (
            f"📊 **Dataset Identified:**\n"
            f"The service job activity and commercial operational data required for your query/project is located in the **Business_Operations** dataset (`Business_Operations.xlsx`).\n\n"
            f"⛔ **Dataset Access Required:**\n"
            f"You currently do not have active access permissions for **Business_Operations**.\n\n"
            f"👉 **Would you like me to raise an IT access request on your behalf to grant access to 'Business_Operations'?**"
        )

    # Rule 5: Standalone metric / term definitions
    if _is_definition_request(user_input):
        def_res = call_tool(query_metric_definitions, {"query": user_input})
        if "No metric definition" not in def_res:
            return f"📖 **Metric Definition (RAG Knowledge Base):**\n\n{def_res}"
        rag_kg_res = call_tool(query_graph_rag, {"query": user_input})
        return f"📖 **Knowledge Base Definition:**\n\n{rag_kg_res}"
        
    # Rule 5.5: Data Sample / Glimpse requests
    if any(k in input_lower for k in ["glimpse", "sample", "show me the data", "preview", "some rows"]):
        # Extract potential dataset name by removing common words
        clean_name = input_lower.replace("show me a glimpse of", "").replace("can i see a sample of", "").replace("what is", "").replace("the", "").replace("dataset", "").strip()
        sample_res = call_tool(query_dataset_sample, {"dataset_name": clean_name})
        if "Could not retrieve sample" not in sample_res:
            return sample_res

    # Rule 6: Greetings & Capability questions
    if _is_greeting(user_input) or _is_capability_question(user_input):
        return _capability_response()

    # Rule 7: Knowledge Graph & RAG Troubleshooting Queries
    rag_kg_res = call_tool(query_graph_rag, {"query": user_input})
    if rag_kg_res.startswith("No Graph-RAG information found"):
        return (
            "I couldn't find that in the enterprise knowledge base. I can help with boiler "
            "models, fault codes, repair components, data lineage, SMEs, and dataset access requests.\n\n"
            "For example, ask: 'Who is the SME for Sales_Funnel_Dataset?' or 'Why is my Worcester Bosch 4000 showing EA Error?'"
        )

    return (
        f"🤖 **AI Knowledge Retrieval (Graph-RAG):**\n\n"
        f"{rag_kg_res}\n\n"
        f"If you need dataset access for a new project, please let me know!"
    )


def process_chat_message(
    user_input: str,
    user_email: str,
    executor: Any = None,
    chat_history: Sequence[dict[str, str]] | None = None,
) -> str:
    """Process a chat message with automated IT access request assistance."""
    verified_evidence = run_deterministic_agent_fallback(user_input, user_email, chat_history)
    if executor is None:
        return _history_fallback(user_input, chat_history) or verified_evidence

    try:
        messages: list[Any] = [
            SystemMessage(content=(
                "You are a helpful utilities-company assistant. Answer naturally and directly, "
                "using only the verified evidence supplied by the application. Never invent data, "
                "and assist users to raise IT access requests when dataset access is required."
            ))
        ]
        for turn in (chat_history or [])[-6:]:
            content = turn.get("content", "").strip()
            if not content:
                continue
            if turn.get("role") == "assistant":
                messages.append(AIMessage(content=content[:700]))
            else:
                messages.append(HumanMessage(content=content[:700]))

        messages.append(HumanMessage(content=(
            f"User question: {user_input}\nUser email: {user_email}\n\n"
            f"Verified evidence:\n{verified_evidence}"
        )))
        response = executor.invoke(messages)
        content = getattr(response, "content", "")
        return content if isinstance(content, str) and content.strip() else verified_evidence
    except Exception as error:
        print(f"[AgentExecutor] API response failed; returning verified local answer: {error}")
        return _history_fallback(user_input, chat_history) or verified_evidence
