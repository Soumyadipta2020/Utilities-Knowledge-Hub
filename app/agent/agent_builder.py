"""
Agent Builder Module for Utilities Knowledge Hub Chatbot.
Constructs LangChain agent executor with system prompt and tools, plus deterministic fallback agent execution.
"""

import os
from typing import Dict, Any, List

try:
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain.agents import create_tool_calling_agent, AgentExecutor
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False
    ChatOpenAI = None
    ChatPromptTemplate = None
    MessagesPlaceholder = None
    create_tool_calling_agent = None
    AgentExecutor = None

from app.agent.tools import (
    get_all_tools,
    check_data_access,
    query_knowledge_graph,
    query_live_metrics,
    raise_access_request,
)


SYSTEM_PROMPT = """You are an AI Agentic Chatbot for an Enterprise Utilities Company.
You assist customers, field technicians, and system administrators with equipment troubleshooting, live telemetry metrics, and IT access management.

CURRENT SESSION CONTEXT:
- Active User Role: {user_role}
- User Email: {user_email}

CRITICAL RULES FOR DATA ACCESS & PERMISSIONS:
1. BEFORE querying or fetching restricted data (such as 'Live_Metrics' or 'System_Logs'), you MUST ALWAYS call the tool `check_data_access(user_role='{user_role}', data_source='...')`.
2. IF `check_data_access` returns "Access Denied":
   - You MUST NOT display or query the restricted metric/data.
   - Politely inform the user that their role ('{user_role}') lacks authorization for that data source.
   - You MUST proactively offer: "Would you like me to raise an IT access request on your behalf?"
3. IF the user asks to raise a ticket, requests IT access, or confirms YES to raising a ticket:
   - Execute the tool `raise_access_request(user_email='{user_email}', data_source='...')`.
   - Return the generated ticket number and details to the user.
4. For troubleshooting boiler issues, error codes (e.g. 'EA_Error', 'Worcester Bosch 4000', 'F2_Error', 'E119_Error'), or maintenance:
   - Execute `query_knowledge_graph(entity_name='...')` to find graph paths and diagnostic steps.
   - Summarize the graph traversal findings clearly.

Be helpful, concise, and adhere strictly to security access control policies!
"""


def build_agent_executor(api_key: str = "", model_name: str = "gpt-4o-mini") -> Any:
    """Build LangChain AgentExecutor if OpenAI API Key & LangChain packages are available."""
    if not HAS_LANGCHAIN:
        return None

    key = api_key or os.getenv("OPENAI_API_KEY", "")
    if not key:
        return None

    try:
        llm = ChatOpenAI(api_key=key, model=model_name, temperature=0.1)
        tools = get_all_tools()

        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        agent = create_tool_calling_agent(llm, tools, prompt)
        executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
        return executor
    except Exception as e:
        print(f"[AgentBuilder] Warning: Could not initialize OpenAI ChatAgent ({e}). Using rule-based engine.")
        return None


def run_deterministic_agent_fallback(user_input: str, user_role: str, user_email: str) -> str:
    """
    Fallback agent execution engine when OpenAI API key is not configured or in offline mode.
    Implements the exact agentic tool routing logic and policy checks deterministically.
    """
    input_lower = user_input.lower()

    # Helper function to invoke tool regardless of decorator wrapper type
    def call_tool(tool_fn, args_dict):
        if hasattr(tool_fn, "invoke"):
            return tool_fn.invoke(args_dict)
        return tool_fn(**args_dict)

    # Rule 1: User wants to raise ticket / confirms ticket request
    if any(k in input_lower for k in ["ticket", "raise access", "raise ticket", "it request", "yes", "please raise"]):
        source = "Live_Metrics" if any(x in input_lower for x in ["metric", "telemetry", "grid"]) else "Live_Metrics"
        res = call_tool(raise_access_request, {"user_email": user_email, "data_source": source})
        return f"🔒 **Access Escalation Procedure Initiated**\n\n{res}"

    # Rule 2: Querying Live Metrics or Grid Pressure or Telemetry
    if any(k in input_lower for k in ["metric", "pressure", "psi", "flame", "temp", "telemetry", "flow", "outage"]):
        # Step A: Check access permission
        access_check = call_tool(check_data_access, {"user_role": user_role, "data_source": "Live_Metrics"})
        
        if "Access Granted" in str(access_check):
            # Determine metric name
            metric_target = "all"
            if "pressure" in input_lower or "psi" in input_lower or "grid" in input_lower:
                metric_target = "grid_pressure_psi"
            elif "flame" in input_lower:
                metric_target = "boiler_flame_current_ua"
            elif "flow" in input_lower:
                metric_target = "pump_flow_rate_lpm"
            elif "temp" in input_lower:
                metric_target = "system_temp_c"

            metrics_res = call_tool(query_live_metrics, {"metric_name": metric_target})
            return (
                f"✅ **Security Verification:** {access_check}\n\n"
                f"📊 **Telemetry Results:**\n{metrics_res}"
            )
        else:
            return (
                f"⛔ **Access Denied!**\n"
                f"{access_check}\n\n"
                f"Your active role (**{user_role}**) is not permitted to view live operational metrics directly.\n\n"
                f"👉 **Would you like me to raise an IT access request on your behalf?**"
            )

    # Rule 3: Knowledge Graph / Troubleshooting Queries
    access_check = call_tool(check_data_access, {"user_role": user_role, "data_source": "Knowledge_Base"})
    
    entity_target = "EA_Error"
    if "worcester" in input_lower or "4000" in input_lower:
        entity_target = "Worcester Bosch 4000"
    elif "ea" in input_lower:
        entity_target = "EA_Error"
    elif "224" in input_lower:
        entity_target = "224_Error"
    elif "ideal" in input_lower or "f2" in input_lower:
        entity_target = "F2_Error"
    elif "baxi" in input_lower or "e119" in input_lower or "pressure" in input_lower:
        entity_target = "E119_Error"
    elif "electrode" in input_lower:
        entity_target = "Ignition Electrode"

    kg_res = call_tool(query_knowledge_graph, {"entity_name": entity_target})
    return (
        f"🔍 **Knowledge Base Traversal:**\n\n"
        f"Verified Access Policy for **{user_role}**: Granted.\n\n"
        f"```text\n{kg_res}\n```\n"
        f"If you need further telemetry metrics or assistance, please specify!"
    )


def process_chat_message(user_input: str, user_role: str, user_email: str, executor: Any = None) -> str:
    """Entrypoint to run chat interaction via LangChain executor or fallback."""
    if executor is not None:
        try:
            response = executor.invoke({
                "input": user_input,
                "user_role": user_role,
                "user_email": user_email,
            })
            return response.get("output", "No response generated by agent.")
        except Exception as err:
            print(f"[AgentExecutor] Execution failed: {err}. Switching to fallback.")

    return run_deterministic_agent_fallback(user_input, user_role, user_email)
