"""
Baseline chatbot: a plain language model with no tools and no data access.

This exists purely as the control arm of the side-by-side comparison. It is the
same model, at the same temperature, answering the same question - the ONLY
difference is that it has no knowledge graph, no dataset access and no ability
to run a query. That isolates the contribution of the agent and the graph rather
than confounding it with a model change.
"""

from __future__ import annotations

import time
from typing import Any, Sequence

try:
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    HAS_MESSAGES = True
except ImportError:  # pragma: no cover
    HAS_MESSAGES = False
    AIMessage = HumanMessage = SystemMessage = None  # type: ignore[assignment]


# Deliberately generic. A normal assistant is not told that a utilities data
# estate exists, because that is exactly the capability being compared.
BASELINE_SYSTEM_PROMPT = """You are a helpful AI assistant, like a standard general-purpose chatbot.

Answer the user's question as well as you can from your own general knowledge.
You have no access to any company systems, databases, files or live data, and no
ability to look anything up. Answer directly and helpfully in concise markdown.
"""


def run_baseline_chat(
    llm: Any,
    user_input: str,
    history: Sequence[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Answer with the bare model. Returns {answer, elapsed_ms, available}."""
    started = time.perf_counter()

    if llm is None or not HAS_MESSAGES:
        return {
            "answer": (
                "_No language model is configured, so the baseline chatbot cannot "
                "respond. Set OPENROUTER_API_KEY to run the comparison._"
            ),
            "elapsed_ms": 0,
            "available": False,
        }

    messages: list[Any] = [SystemMessage(content=BASELINE_SYSTEM_PROMPT)]
    for turn in list(history or [])[-6:]:
        content = str(turn.get("content", "")).strip()
        if not content:
            continue
        if turn.get("role") == "assistant":
            messages.append(AIMessage(content=content[:800]))
        else:
            messages.append(HumanMessage(content=content[:800]))
    messages.append(HumanMessage(content=user_input))

    try:
        response = llm.invoke(messages)
        answer = getattr(response, "content", "")
        if isinstance(answer, list):
            answer = "".join(
                str(part.get("text", "")) if isinstance(part, dict) else str(part)
                for part in answer
            )
        answer = str(answer).strip() or "_The baseline model returned an empty response._"
    except Exception as error:  # noqa: BLE001 - the comparison must still render
        answer = f"_The baseline chatbot failed to respond: {error}_"

    return {
        "answer": answer,
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "available": True,
    }
