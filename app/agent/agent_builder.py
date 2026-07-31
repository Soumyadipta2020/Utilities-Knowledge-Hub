"""
Agent Builder Module for Utilities Knowledge Hub Chatbot.
Constructs LangChain agent executor with system prompt and tools, plus deterministic fallback agent execution.
"""

import os
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
        "Hello! I am ABC's AI Agentic Knowledge Hub.\n\n"
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


def _definition_entity(message: str) -> str:
    """Map a business-definition question to its public knowledge-graph entity."""
    normalized = message.casefold()
    if "appointment" in normalized:
        return "Net Appointment"
    if "quote" in normalized:
        return "Quote"
    if "conversion" in normalized:
        return "Sales Conversion"
    if "sale" in normalized:
        return "Net Sale"
    return "Lead"


def _history_fallback(user_input: str, chat_history: Sequence[dict[str, str]] | None) -> str | None:
    """Keep a follow-up coherent if the external model is temporarily unavailable."""
    follow_up_phrases = ("what happens after", "and then", "tell me more", "what about that", "what next")
    if not chat_history or not any(phrase in user_input.casefold() for phrase in follow_up_phrases):
        return None
    for turn in reversed(chat_history):
        if turn.get("role") == "assistant" and turn.get("content", "").strip():
            return f"Based on our previous answer:\n\n{turn['content']}"
    return None


SYSTEM_PROMPT = """You are an AI Agentic Chatbot for ABC's Enterprise Knowledge Hub.
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


def run_deterministic_agent_fallback(user_input: str, user_email: str) -> str:
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

    # Rule 1: User confirms ticket request / wants to raise ticket for dataset
    ticket_keywords = ["ticket", "raise access", "raise ticket", "it request", "yes", "please raise", "submit ticket"]
    if any(k in input_lower for k in ticket_keywords):
        target_dataset = "Live_Metrics"
        if "business" in input_lower or "funnel" in input_lower or "sales" in input_lower:
            target_dataset = "Business_Operations"
        ticket_res = call_tool(raise_access_request, {"user_email": user_email, "data_source": target_dataset})
        return f"🔒 **Access Escalation Procedure Initiated**\n\n{ticket_res}"

    # Rule 2: Data Lineage, SME Ownership & Governance queries
    if any(k in input_lower for k in ["sme", "lineage", "managed_by", "data owner", "owner", "governance", "dashboard"]):
        rag_kg_res = call_tool(query_graph_rag, {"query": user_input})
        return f"🕸️ **ABC Data Lineage & SME Governance:**\n\n{rag_kg_res}"

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
            definition = call_tool(query_knowledge_graph, {"entity_name": _definition_entity(user_input)})
            return f"📖 **Knowledge Base Definition:**\n\n{definition}"

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
        definition = call_tool(query_knowledge_graph, {"entity_name": _definition_entity(user_input)})
        return f"📖 **Knowledge Base Definition:**\n\n{definition}"

    # Rule 6: Greetings & Capability questions
    if _is_greeting(user_input) or _is_capability_question(user_input):
        return _capability_response()

    # Rule 7: Knowledge Graph & RAG Troubleshooting Queries
    rag_kg_res = call_tool(query_graph_rag, {"query": user_input})
    if rag_kg_res.startswith("No Graph-RAG information found"):
        return (
            "I couldn't find that in ABC's enterprise knowledge base. I can help with boiler "
            "models, fault codes, repair components, data lineage, SMEs, and dataset access requests.\n\n"
            "For example, ask: 'Who is the SME for Sales_Funnel_Dataset?' or 'Why is my Worcester Bosch 4000 showing EA Error?'"
        )

    return (
        f"🤖 **ABC AI Knowledge Retrieval (Graph-RAG):**\n\n"
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
    verified_evidence = run_deterministic_agent_fallback(user_input, user_email)
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
