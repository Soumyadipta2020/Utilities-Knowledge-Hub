"""
Agentic runtime for the Utilities Knowledge Hub.

This module owns the *agent loop*. The LLM decides which tools to call, reads the
results, corrects itself when a tool fails, and composes the final answer. Every
step of that loop is emitted as a trace event so the UI can show the reasoning as
it happens instead of a single opaque reply.

The deterministic keyword router in `agent_builder` is now strictly a fallback:
it runs only when no model is configured, or when the agent loop raises.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from threading import Lock
from typing import Any, Iterator, Sequence

import pandas as pd

from app.agent import evidence

try:
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    from langgraph.prebuilt import ToolNode, create_react_agent

    HAS_AGENT_STACK = True
except ImportError:  # pragma: no cover - exercised only on incomplete installs
    HAS_AGENT_STACK = False
    AIMessage = HumanMessage = SystemMessage = None  # type: ignore[assignment]
    create_react_agent = ToolNode = None  # type: ignore[assignment]


def _tool_error_message(error: Exception) -> str:
    """Turn a raised tool exception into something the agent can recover from.

    Without this a single bad tool - for example one written against a retired
    dataset schema - propagates out and aborts the entire run.
    """
    return (
        f"Error: the tool raised {type(error).__name__}: {error}. "
        "This tool is unavailable for that input. Either call it with different "
        "arguments, or use execute_pandas_query on the relevant dataset instead."
    )


# Upper bound on agent loop iterations. Each iteration is one model turn plus any
# tool calls it requested. Deep root-cause runs regularly use 10-12 tool calls,
# which sat right on the old ceiling and aborted with a recursion-limit error.
MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "18"))

# Number of history turns replayed into the agent.
HISTORY_TURNS = int(os.getenv("AGENT_HISTORY_TURNS", "8"))

# Wall-clock budget for one agent run. On expiry the loop stops and answers with
# what it has, so a wandering agent cannot stall a live demo.
DEADLINE_SECONDS = float(os.getenv("AGENT_DEADLINE_SECONDS", "120"))

# Supervisor routing to named specialists. Off puts every question through the
# single generalist agent.
ENABLE_SPECIALISTS = os.getenv("AGENT_SPECIALISTS", "1") not in ("0", "false", "False")


SYSTEM_PROMPT = """You are the Utilities Knowledge Hub agent for a UK gas, heating and energy-services company.

CURRENT SESSION
- User email: {user_email}

HOW YOU WORK
You answer by investigating with tools, not by guessing. Work through a question in steps:

1. Decide which datasets and tools actually answer the question. A multi-part
   question needs multiple tool calls - make all of them before answering.
2. For ANY numeric or aggregate question (counts, sums, averages, groupings,
   trends, rankings, comparisons) and for anything spanning two or more
   datasets, call `query_datasets_sql`. It scans EVERY row of the full datasets
   and handles joins efficiently. Never state a number you did not compute.
   Use `execute_pandas_query` only for single-dataset row-level inspection that
   is awkward in SQL. Both see the complete data - neither samples.
3. If a tool returns an error, read the error, fix your input and call the tool
   again. Tool errors list the real table and column names - use them. You have
   up to 3 attempts per tool before you should explain the limitation instead.
4. Cross-reference before concluding. If a finding could be explained by another
   dataset - weather, engineer skill, parts availability, capacity forecast -
   check that dataset too rather than asserting a single cause.
5. Finish with a `Sources:` line naming the datasets and tools you actually used.

6. Translate impact into money whenever the data allows it. A leader acts on
   "£1.9m of deferred revenue", not "16,400 visits". Say what the rate assumption
   is when you convert.
7. When your analysis implies something the business should DO, call
   `propose_action` ONCE with the single best recommendation - not a list of
   options. It requires an expected_impact stating what measurably improves,
   quantified where the data allows. Never claim you have done something;
   proposing is not doing.

ANSWER STYLE
- Concise markdown. Lead with the answer, then the supporting detail.
- Never dump raw dicts, JSON or full dataframes.
- Do NOT tell the user access is denied or required unless they explicitly asked
  about access or entitlements.
- If the user asks to raise a request or ticket, call `raise_access_request` with
  user_email='{user_email}'.

DATASETS AVAILABLE (exact names and columns - use verbatim in SQL and pandas):
{dataset_schemas}
"""


# Which argument of each tool names a dataset. Used to light up the lineage graph
# and to label trace rows.
_TOOL_DATASET_ARG = {
    "execute_pandas_query": "dataset_name",
    "query_dataset_sample": "dataset_name",
    "check_data_access": "data_source",
    "raise_access_request": "data_source",
}

_TOOL_LABELS = {
    "search_knowledge_base_rag": "Searching knowledge base",
    "query_knowledge_graph": "Traversing knowledge graph",
    "query_graph_rag": "Hybrid graph + document retrieval",
    "query_live_metrics": "Reading live telemetry",
    "query_business_operations": "Querying business operations",
    "query_metric_definitions": "Looking up metric definition",
    "query_dataset_sample": "Sampling dataset",
    "forecast_boiler_installations": "Running installation forecast",
    "check_data_access": "Checking entitlements",
    "raise_access_request": "Raising IT access request",
    "execute_pandas_query": "Analysing dataset",
}


class DatasetSchemaCache:
    """Read every CSV header once at boot instead of on every chat message."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self._columns: dict[str, list[str]] = {}
        self._prompt_text = ""
        self._lock = Lock()
        self.refresh()

    def refresh(self) -> None:
        columns: dict[str, list[str]] = {}
        for path in sorted(self.data_dir.glob("*.csv")):
            try:
                columns[path.name] = pd.read_csv(path, nrows=0).columns.tolist()
            except Exception as error:  # noqa: BLE001 - a bad CSV must not stop boot
                print(f"[SchemaCache] Skipped {path.name}: {error}")

        lines = [f"- {name}: {', '.join(cols)}" for name, cols in columns.items()]
        with self._lock:
            self._columns = columns
            self._prompt_text = "\n".join(lines)

    @property
    def prompt_text(self) -> str:
        with self._lock:
            return self._prompt_text

    def columns_for(self, dataset: str) -> list[str]:
        name = Path(str(dataset)).name
        if not name.endswith(".csv"):
            name += ".csv"
        with self._lock:
            return list(self._columns.get(name, []))

    @property
    def dataset_names(self) -> list[str]:
        with self._lock:
            return list(self._columns)


def _summarize_tool_args(tool_name: str, args: dict[str, Any]) -> str:
    """Build a short human-readable label for a tool call."""
    if not isinstance(args, dict) or not args:
        return ""

    if tool_name == "execute_pandas_query":
        dataset = str(args.get("dataset_name", "")).strip()
        code = " ".join(str(args.get("query", "")).split())
        if len(code) > 110:
            code = code[:107] + "..."
        return f"{dataset} · {code}" if dataset else code

    parts = []
    for value in args.values():
        text = " ".join(str(value).split())
        if text:
            parts.append(text[:90])
    return " · ".join(parts)[:180]


def _datasets_in_tool_call(tool_name: str, args: dict[str, Any], known: Sequence[str]) -> list[str]:
    """Return dataset names a tool call touched, for lineage highlighting."""
    found: list[str] = []
    arg_name = _TOOL_DATASET_ARG.get(tool_name)
    if arg_name and isinstance(args, dict):
        raw = str(args.get(arg_name, "")).strip()
        for piece in raw.replace(",", " ").split():
            stem = Path(piece).name
            stem = stem[:-4] if stem.endswith(".csv") else stem
            if stem and stem not in found:
                found.append(stem)

    if not found and isinstance(args, dict):
        blob = " ".join(str(v) for v in args.values()).casefold()
        for name in known:
            stem = name[:-4] if name.endswith(".csv") else name
            if stem in blob and stem not in found:
                found.append(stem)
    return found[:6]


def _preview(text: str, limit: int = 260) -> str:
    flat = " ".join(str(text).split())
    return flat[:limit] + ("..." if len(flat) > limit else "")


class AgentRuntime:
    """Owns the compiled agent graph and streams its reasoning trace."""

    def __init__(
        self,
        llm: Any,
        tools: Sequence[Any],
        data_dir: Path,
        sql_service: Any = None,
        store: Any = None,
    ) -> None:
        self.llm = llm
        self.tools = list(tools)
        self.sql_service = sql_service
        self.store = store
        self.schemas = DatasetSchemaCache(data_dir)
        self._agent: Any = None
        self._build_lock = Lock()

        if self.available:
            # Compile the graph once, at boot, rather than per message. A raising
            # tool is converted into an error observation so the agent can retry
            # rather than the whole run dying.
            tool_node = ToolNode(self.tools, handle_tool_errors=_tool_error_message)
            self._agent = create_react_agent(self.llm, tools=tool_node)
            print(f"[AgentRuntime] Agent compiled with {len(self.tools)} tools, max {MAX_STEPS} steps.")
        else:
            print("[AgentRuntime] No model configured - deterministic router will answer.")

    @property
    def available(self) -> bool:
        return bool(self.llm is not None and HAS_AGENT_STACK and create_react_agent is not None)

    def _memory_block(self, user_input: str, user_email: str) -> str:
        """Prior findings on this topic, so the agent picks up where it left off."""
        if self.store is None:
            return ""
        terms = [w for w in re.findall(r"[a-z_]{5,}", user_input.casefold())][:6]
        try:
            related = self.store.find_related_decisions(terms, limit=3)
        except Exception:  # noqa: BLE001 - memory is an enhancement, never a blocker
            return ""
        if not related:
            return ""
        lines = [
            "\n\nPRIOR ANALYSIS ON RECORD (from earlier sessions - reference it where relevant,",
            "and say if the position has changed since):",
        ]
        for item in related:
            stamp = str(item.get("created_at", ""))[:10]
            lines.append(f"- [{stamp}] asked: {str(item.get('question',''))[:160]}")
            lines.append(f"  found: {str(item.get('finding',''))[:240]}")
            if item.get("recommendation"):
                lines.append(f"  recommended: {str(item['recommendation'])[:200]}")
        return "\n".join(lines)

    def _build_messages(
        self,
        user_input: str,
        user_email: str,
        history: Sequence[dict[str, str]] | None,
        specialist: Any = None,
    ) -> list[Any]:
        # The SQL engine reports true column types, so prefer its schema when
        # available and fall back to the CSV header cache otherwise.
        schema_text = ""
        if self.sql_service is not None and self.sql_service.available:
            schema_text = self.sql_service.schema_text()
        if not schema_text:
            schema_text = self.schemas.prompt_text

        system_text = SYSTEM_PROMPT.format(
            user_email=user_email,
            dataset_schemas=schema_text,
        )
        if specialist is not None:
            from app.agent.specialists import specialist_directive

            system_text += specialist_directive(specialist)
        system_text += self._memory_block(user_input, user_email)

        messages: list[Any] = [SystemMessage(content=system_text)]
        for turn in list(history or [])[-HISTORY_TURNS:]:
            content = str(turn.get("content", "")).strip()
            if not content:
                continue
            if turn.get("role") == "assistant":
                messages.append(AIMessage(content=content[:1200]))
            else:
                messages.append(HumanMessage(content=content[:1200]))
        messages.append(HumanMessage(content=user_input))
        return messages

    def stream(
        self,
        user_input: str,
        user_email: str,
        history: Sequence[dict[str, str]] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Run the agent, yielding trace events and finally the answer."""
        started = time.perf_counter()
        evidence.start_collection()

        # Attribute any action the agent proposes to the person who asked.
        try:
            from app.agent.tools import set_current_user

            set_current_user(user_email)
        except Exception:  # noqa: BLE001
            pass

        if not self.available:
            yield from self._deterministic_stream(user_input, user_email, history, started, reason="no_model")
            return

        known_datasets = self.schemas.dataset_names
        pending: dict[str, dict[str, Any]] = {}
        # Consecutive failures per tool. A call is only a "self-correction" when
        # the previous call to that same tool errored - successive successful
        # calls are ordinary multi-step work, not retries.
        failures: dict[str, int] = {}
        tool_calls = 0
        step = 0
        answer = ""

        yield {"type": "status", "state": "planning", "text": "Reading question and planning approach"}

        # The supervisor picks a specialist before any tool runs, so the handoff
        # is visible in the trace rather than hidden inside one opaque loop.
        specialist = None
        if ENABLE_SPECIALISTS:
            try:
                from app.agent.specialists import route

                specialist, how = route(user_input, self.llm)
                yield {
                    "type": "handoff",
                    "specialist": specialist.key,
                    "name": specialist.name,
                    "icon": specialist.icon,
                    "remit": specialist.remit,
                    "routed_by": how,
                }
            except Exception as error:  # noqa: BLE001 - routing must not block
                print(f"[AgentRuntime] Specialist routing skipped: {error}")

        try:
            messages = self._build_messages(user_input, user_email, history, specialist)
            stream = self._agent.stream(
                {"messages": messages},
                stream_mode="updates",
                config={"recursion_limit": MAX_STEPS * 2 + 1},
            )

            timed_out = False
            for chunk in stream:
                if DEADLINE_SECONDS > 0 and (time.perf_counter() - started) > DEADLINE_SECONDS:
                    timed_out = True
                    stream.close()
                    yield {
                        "type": "status",
                        "state": "deadline",
                        "text": f"Time budget of {DEADLINE_SECONDS:.0f}s reached - answering with findings so far",
                    }
                    break
                if not isinstance(chunk, dict):
                    continue
                for update in chunk.values():
                    if not isinstance(update, dict):
                        continue
                    for message in update.get("messages", []) or []:
                        kind = getattr(message, "type", "")

                        if kind == "ai":
                            requested = getattr(message, "tool_calls", None) or []
                            if requested:
                                step += 1
                                yield {"type": "step", "n": step}
                            for call in requested:
                                tool_calls += 1
                                name = call.get("name", "tool")
                                args = call.get("args", {}) or {}
                                call_id = str(call.get("id") or f"call_{tool_calls}")
                                pending[call_id] = {"name": name, "started": time.perf_counter()}
                                yield {
                                    "type": "tool_call",
                                    "id": call_id,
                                    "tool": name,
                                    "label": _TOOL_LABELS.get(name, name.replace("_", " ").title()),
                                    "detail": _summarize_tool_args(name, args),
                                    "datasets": _datasets_in_tool_call(name, args, known_datasets),
                                    "attempt": failures.get(name, 0) + 1,
                                }
                            text = getattr(message, "content", "")
                            if isinstance(text, str) and text.strip():
                                answer = text.strip()

                        elif kind == "tool":
                            call_id = str(getattr(message, "tool_call_id", "") or "")
                            record = pending.pop(call_id, None)
                            content = getattr(message, "content", "") or ""
                            if not isinstance(content, str):
                                content = str(content)
                            failed = content.lstrip().lower().startswith("error")
                            tool_name = (record or {}).get("name") or getattr(message, "name", "tool")
                            failures[tool_name] = (failures.get(tool_name, 0) + 1) if failed else 0
                            elapsed_ms = (
                                int((time.perf_counter() - record["started"]) * 1000) if record else 0
                            )
                            yield {
                                "type": "tool_result",
                                "id": call_id,
                                "tool": tool_name,
                                "ok": not failed,
                                "ms": elapsed_ms,
                                "preview": _preview(content),
                            }

            if not answer:
                answer = (
                    "I ran out of time before summarising. Findings so far are in the "
                    "trace - try narrowing the question to one dataset or metric."
                    if timed_out
                    else "I ran the analysis but did not produce a final summary. "
                    "Try narrowing the question to one dataset or metric."
                )

            yield {"type": "answer", "text": answer}
            yield {
                "type": "done",
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
                "tool_calls": tool_calls,
                "steps": step,
                "engine": "agent",
                "specialist": specialist.name if specialist else None,
                "evidence": evidence.snapshot(),
            }

        except Exception as error:  # noqa: BLE001 - the demo must always answer
            print(f"[AgentRuntime] Agent loop failed, falling back: {error}")
            yield {
                "type": "status",
                "state": "fallback",
                "text": f"Agent loop error, switching to deterministic router: {str(error)[:160]}",
            }
            yield from self._deterministic_stream(
                user_input, user_email, history, started, reason="agent_error"
            )

    def _deterministic_stream(
        self,
        user_input: str,
        user_email: str,
        history: Sequence[dict[str, str]] | None,
        started: float,
        reason: str,
    ) -> Iterator[dict[str, Any]]:
        """Emit the rule-based answer as a trace so the UI stays consistent."""
        from app.agent.agent_builder import run_deterministic_agent_fallback

        if reason == "no_model":
            yield {
                "type": "status",
                "state": "fallback",
                "text": "No model configured - answering from the deterministic knowledge router",
            }

        call_started = time.perf_counter()
        yield {
            "type": "tool_call",
            "id": "deterministic",
            "tool": "deterministic_router",
            "label": "Deterministic knowledge router",
            "detail": _preview(user_input, 90),
            "datasets": [],
            "attempt": 1,
        }
        answer = run_deterministic_agent_fallback(user_input, user_email, history)
        yield {
            "type": "tool_result",
            "id": "deterministic",
            "tool": "deterministic_router",
            "ok": True,
            "ms": int((time.perf_counter() - call_started) * 1000),
            "preview": _preview(answer),
        }
        yield {"type": "answer", "text": answer}
        yield {
            "type": "done",
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "tool_calls": 1,
            "steps": 1,
            "engine": "deterministic",
            "evidence": evidence.snapshot(),
        }

    def run(
        self,
        user_input: str,
        user_email: str,
        history: Sequence[dict[str, str]] | None = None,
    ) -> str:
        """Non-streaming entry point - drains the trace and returns the answer."""
        answer = ""
        for event in self.stream(user_input, user_email, history):
            if event.get("type") == "answer":
                answer = event.get("text", "")
        return answer
