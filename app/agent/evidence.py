"""
Per-request evidence ledger.

Records what the agent actually touched while answering - which datasets, how
many records were scanned, which knowledge-graph entities were traversed. The
comparison view uses this to show leadership the concrete difference between a
grounded answer and one produced from a model's memory alone.

A ContextVar is used so concurrent requests each get their own ledger.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

_LEDGER: ContextVar[dict[str, Any] | None] = ContextVar("evidence_ledger", default=None)


def start_collection() -> None:
    """Begin a fresh ledger for the current request."""
    _LEDGER.set({
        "datasets": [],
        "records_scanned": 0,
        "sql_queries": 0,
        "pandas_queries": 0,
        "graph_entities": [],
        "graph_lookups": 0,
        "rag_documents": 0,
        "failed_calls": 0,
        "simulations": 0,
        "actions_proposed": 0,
        "proposed_action_ids": [],
    })


def _ledger() -> dict[str, Any] | None:
    return _LEDGER.get()


def record_datasets(datasets: list[str], records_scanned: int = 0) -> None:
    ledger = _ledger()
    if ledger is None:
        return
    for dataset in datasets:
        if dataset and dataset not in ledger["datasets"]:
            ledger["datasets"].append(dataset)
    ledger["records_scanned"] += max(records_scanned, 0)


def record_sql_query() -> None:
    ledger = _ledger()
    if ledger is not None:
        ledger["sql_queries"] += 1


def record_pandas_query() -> None:
    ledger = _ledger()
    if ledger is not None:
        ledger["pandas_queries"] += 1


def record_graph_lookup(entities: list[str]) -> None:
    ledger = _ledger()
    if ledger is None:
        return
    ledger["graph_lookups"] += 1
    for entity in entities:
        if entity and entity not in ledger["graph_entities"]:
            ledger["graph_entities"].append(entity)


def record_rag_documents(count: int) -> None:
    """Note document chunks retrieved by RAG.

    Tracked separately from graph lookups because the comparison view has to show
    that the agent does the same document retrieval the baseline does, and then
    traverses the graph on top of it.
    """
    ledger = _ledger()
    if ledger is not None:
        ledger["rag_documents"] += max(int(count), 0)


def record_failure() -> None:
    ledger = _ledger()
    if ledger is not None:
        ledger["failed_calls"] += 1


def record_simulation() -> None:
    ledger = _ledger()
    if ledger is not None:
        ledger["simulations"] += 1


def record_action_proposed(action_id: str = "") -> None:
    """Note an action proposed during THIS turn.

    The ids matter: the approval card must show only what this answer proposed,
    not every action still pending from earlier questions.
    """
    ledger = _ledger()
    if ledger is not None:
        ledger["actions_proposed"] += 1
        if action_id:
            ledger["proposed_action_ids"].append(action_id)


def snapshot() -> dict[str, Any]:
    """Return the current ledger, or an empty one if collection never started."""
    ledger = _ledger()
    if ledger is None:
        return {
            "datasets": [],
            "records_scanned": 0,
            "sql_queries": 0,
            "pandas_queries": 0,
            "graph_entities": [],
            "graph_lookups": 0,
            "rag_documents": 0,
            "failed_calls": 0,
            "simulations": 0,
            "actions_proposed": 0,
            "proposed_action_ids": [],
        }
    return {
        "datasets": list(ledger["datasets"]),
        "records_scanned": ledger["records_scanned"],
        "sql_queries": ledger["sql_queries"],
        "pandas_queries": ledger["pandas_queries"],
        "graph_entities": list(ledger["graph_entities"])[:40],
        "graph_lookups": ledger["graph_lookups"],
        "rag_documents": ledger["rag_documents"],
        "failed_calls": ledger["failed_calls"],
        "simulations": ledger["simulations"],
        "actions_proposed": ledger["actions_proposed"],
        "proposed_action_ids": list(ledger["proposed_action_ids"]),
    }
