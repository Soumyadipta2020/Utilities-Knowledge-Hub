"""
Baseline chatbot: a standard RAG assistant over the unstructured document corpus.

This is the control arm of the side-by-side comparison, and it is deliberately a
*fair* control - not a crippled one. It runs the same model at the same
temperature, and it retrieves: top-k document chunks come back from the same
enterprise knowledge corpus (see `app/services/rag_service.py`) and are stuffed
into its prompt, exactly as a conventional enterprise RAG chatbot would do.

What it does not have is the knowledge graph or the agent loop:

  * retrieval is flat - chunks have no relationships, so it cannot traverse
    dataset -> owner -> platform -> governance tier, or appointments -> region ->
    weather -> engineer shifts;
  * it retrieves prose *about* the data estate, never rows *from* it, so it
    cannot compute, aggregate or join a single figure;
  * one retrieval, one answer - no tool calls, no follow-up queries.

So any difference the audience sees is attributable to the knowledge graph plus
the tool-using agent on top of RAG, not to a better model and not to the baseline
having been denied retrieval.
"""

from __future__ import annotations

import time
from typing import Any, Sequence

from app.agent.charts import CHART_INSTRUCTIONS, sanitize_answer

try:
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    HAS_MESSAGES = True
except ImportError:  # pragma: no cover
    HAS_MESSAGES = False
    AIMessage = HumanMessage = SystemMessage = None  # type: ignore[assignment]


TOP_K = 6

# The prompt tells the baseline to ANSWER - with the real figures its retrieval
# returned - and to be precise about the one thing it cannot do. A chatbot that
# simply refuses is a strawman, and a strawman proves nothing about the graph. The
# honest failure mode of document RAG over a data estate is a confident answer off
# a single pre-aggregated source: right arithmetic, wrong definition, no lineage.
BASELINE_SYSTEM_PROMPT = """You are a standard enterprise RAG chatbot.

Your capability is vector search over a document corpus, and nothing else. The
corpus holds three kinds of chunk, all provided below under RETRIEVED CONTEXT:
- knowledge base articles describing what each dataset contains;
- business rule documents defining metrics and SLAs;
- pre-aggregated reporting extracts exported from individual datasets (weekly
  volumes, category distributions, dataset profiles) with real figures in them.

So you CAN answer questions with numbers - use the figures in the extracts.

You do NOT have:
- the datasets themselves. You only ever see whatever the extract already
  aggregated; you cannot read, filter or re-cut the underlying rows;
- any ability to combine two sources. Every extract comes from ONE dataset and
  carries no join key, so a figure that needs two datasets cannot be produced;
- a knowledge graph, so you have no entity relationships, no data lineage, no
  ownership or governance register, and no way to connect a dataset, region,
  team, customer or system to another;
- any tools, and no second retrieval - this is a single-shot answer.

Rules:
1. ANSWER the question as fully as the retrieved extracts allow. If weekly
   figures are present, give the trend, quote the numbers and describe the shape.
   Prefer a markdown table for a series.
2. Use ONLY figures that appear verbatim in the RETRIEVED CONTEXT. Never invent,
   extrapolate or illustrate a number. Never present an arithmetic result you
   cannot derive from the quoted figures.
3. Label what you give honestly. If the extract is gross and the question asked
   for net, say so, give the gross figures, and name what would have to be
   excluded and which dataset holds it.
4. State the limitation once, briefly, at the end - what is missing and why (no
   join between sources / no per-week or per-region breakdown / no lineage or
   ownership graph). Do not repeat it in every line.
5. Concise markdown. Do not offer to run anything - you cannot.

{chart_instructions}

One extra charting rule for you: label the series for what it actually is. If the
figures are gross, the series name says "Gross ...", never "Net ...".
"""

NO_CONTEXT_NOTE = (
    "No chunks scored above the retrieval threshold for this question. The corpus "
    "contains dataset descriptions, business rules and single-dataset reporting "
    "extracts only."
)


def _format_context(chunks: Sequence[dict[str, Any]]) -> str:
    if not chunks:
        return NO_CONTEXT_NOTE
    lines = []
    for position, chunk in enumerate(chunks, start=1):
        lines.append(
            f"[{position}] {chunk['title']} ({chunk['doc_type']}; source "
            f"{chunk['source']}; chunk {chunk['chunk_id']}; similarity {chunk['score']})"
            f"\n{chunk['text']}"
        )
    return "\n\n".join(lines)


def run_baseline_chat(
    llm: Any,
    user_input: str,
    history: Sequence[dict[str, str]] | None = None,
    rag_service: Any = None,
) -> dict[str, Any]:
    """Retrieve, then answer. Returns {answer, elapsed_ms, available, retrieval}."""
    started = time.perf_counter()

    chunks: list[dict[str, Any]] = []
    corpus: dict[str, int] = {}
    if rag_service is not None:
        try:
            chunks = rag_service.search(user_input, top_k=TOP_K)
            corpus = rag_service.corpus_stats()
        except Exception as error:  # noqa: BLE001 - retrieval failure must not break the demo
            print(f"[Baseline RAG Error]: {error}")

    # Datasets whose *pre-aggregated extracts* were retrieved. Reported separately
    # from the agent's dataset queries: reading an export is not querying the rows.
    extract_sources = sorted({
        chunk["source"].split(".csv")[0]
        for chunk in chunks
        if "reporting extract" in str(chunk.get("source", "")).lower()
    })

    retrieval = {
        "method": "TF-IDF vector search over documents and reporting extracts",
        "chunks": chunks,
        "chunk_count": len(chunks),
        "top_score": chunks[0]["score"] if chunks else 0.0,
        "corpus_documents": corpus.get("documents", 0),
        "corpus_chunks": corpus.get("chunks", 0),
        "extract_sources": extract_sources,
        "graph_hops": 0,
        "joins": 0,
    }

    if llm is None or not HAS_MESSAGES:
        return {
            "answer": (
                "_No language model is configured, so the baseline RAG chatbot cannot "
                "respond. Set OPENROUTER_API_KEY to run the comparison._"
            ),
            "elapsed_ms": 0,
            "available": False,
            "retrieval": retrieval,
        }

    messages: list[Any] = [SystemMessage(
        content=BASELINE_SYSTEM_PROMPT.format(chart_instructions=CHART_INSTRUCTIONS)
    )]
    for turn in list(history or [])[-6:]:
        content = str(turn.get("content", "")).strip()
        if not content:
            continue
        if turn.get("role") == "assistant":
            messages.append(AIMessage(content=content[:800]))
        else:
            messages.append(HumanMessage(content=content[:800]))

    messages.append(HumanMessage(content=(
        f"RETRIEVED CONTEXT (top {len(chunks)} chunks by cosine similarity):\n"
        f"{_format_context(chunks)}\n\n"
        f"QUESTION: {user_input}"
    )))

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
        answer = f"_The baseline RAG chatbot failed to respond: {error}_"

    answer, specs = sanitize_answer(answer)
    retrieval["charts"] = len(specs)

    return {
        "answer": answer,
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "available": True,
        "retrieval": retrieval,
    }
