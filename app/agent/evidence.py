"""
Per-request evidence ledger.

Records what the agent actually touched while answering - which datasets, how
many records were scanned, which knowledge-graph entities were traversed. The
comparison view uses this to show leadership the concrete difference between a
grounded answer and one produced from a model's memory alone.

A ContextVar is used so concurrent requests each get their own ledger.
"""

from __future__ import annotations

from typing import Any

_LEDGER_DICT: dict[str, Any] = {}
_ACTIVE_LEDGER_ID: str = "default"


def start_collection() -> None:
    """Begin a fresh ledger for the current request."""
    _LEDGER_DICT[_ACTIVE_LEDGER_ID] = {
        "datasets": set(),
        "records_scanned": 0,
        "actions_proposed": 0,
        "proposed_action_ids": [],
        "searches": 0,
        "pandas_queries": 0,
        "graph_traversals": 0,
        "sql_queries": 0,
        "graph_entities": [],
        "graph_lookups": 0,
        "failed_calls": 0,
        "simulations": 0,
    }

def _ledger() -> dict[str, Any] | None:
    return _LEDGER_DICT.get(_ACTIVE_LEDGER_ID)


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
        "failed_calls": ledger["failed_calls"],
        "simulations": ledger["simulations"],
        "actions_proposed": ledger["actions_proposed"],
        "proposed_action_ids": list(ledger["proposed_action_ids"]),
    }
