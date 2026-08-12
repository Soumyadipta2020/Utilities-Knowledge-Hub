"""
Durable store for Watchtower findings, approval-gated actions and decision memory.

These three capabilities all need to survive a process restart. The security
telemetry elsewhere in the app deliberately lives in memory, but "you asked about
the Midlands capacity gap three weeks ago" is worthless if it resets whenever the
server bounces - so this uses SQLite, which is in the standard library and needs
no extra dependency or service.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS findings (
    id TEXT PRIMARY KEY,
    detected_at TEXT NOT NULL,
    kpi TEXT NOT NULL,
    period TEXT NOT NULL,
    severity TEXT NOT NULL,
    headline TEXT NOT NULL,
    observed REAL,
    expected REAL,
    deviation_pct REAL,
    impact_gbp REAL,
    explanation TEXT,
    evidence TEXT,
    status TEXT NOT NULL DEFAULT 'open'
);

CREATE TABLE IF NOT EXISTS actions (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    decided_at TEXT,
    requested_by TEXT NOT NULL,
    decided_by TEXT,
    action_type TEXT NOT NULL,
    title TEXT NOT NULL,
    detail TEXT NOT NULL,
    payload TEXT,
    rationale TEXT,
    expected_impact TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    result TEXT,
    finding_id TEXT
);

CREATE TABLE IF NOT EXISTS decisions (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    user_email TEXT NOT NULL,
    topic TEXT NOT NULL,
    question TEXT NOT NULL,
    finding TEXT NOT NULL,
    recommendation TEXT,
    metrics TEXT
);

CREATE TABLE IF NOT EXISTS claim_reviews (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    reviewed_at TEXT,
    user_email TEXT NOT NULL,
    question TEXT NOT NULL,
    claim TEXT NOT NULL,
    verdict TEXT NOT NULL,
    detail TEXT,
    score INTEGER,
    score_stated INTEGER NOT NULL DEFAULT 0,
    confidence TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    reviewed_by TEXT,
    note TEXT
);

CREATE INDEX IF NOT EXISTS idx_findings_period ON findings(kpi, period);
CREATE INDEX IF NOT EXISTS idx_actions_status ON actions(status);
CREATE INDEX IF NOT EXISTS idx_decisions_user ON decisions(user_email, created_at);
CREATE INDEX IF NOT EXISTS idx_claim_reviews_status ON claim_reviews(status, created_at);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class HubStore:
    """Thread-safe SQLite wrapper. One connection guarded by a lock."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._con = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        with self._lock:
            self._con.executescript(SCHEMA)
            self._migrate()
            self._con.commit()

    def _migrate(self) -> None:
        """Add columns introduced after a database was first created."""
        existing = {row["name"] for row in self._con.execute("PRAGMA table_info(actions)")}
        if "expected_impact" not in existing:
            self._con.execute("ALTER TABLE actions ADD COLUMN expected_impact TEXT")

        claim_cols = {row["name"] for row in self._con.execute("PRAGMA table_info(claim_reviews)")}
        if "score" not in claim_cols:
            self._con.execute("ALTER TABLE claim_reviews ADD COLUMN score INTEGER")
        if "score_stated" not in claim_cols:
            self._con.execute(
                "ALTER TABLE claim_reviews ADD COLUMN score_stated INTEGER NOT NULL DEFAULT 0"
            )

    # ---------------------------------------------------------------- findings

    def upsert_finding(self, finding: dict[str, Any]) -> str:
        """Insert a finding, or refresh the existing one for the same KPI+period.

        Re-running a scan must not pile up duplicates of the same anomaly.
        """
        key = (finding["kpi"], finding["period"])
        with self._lock:
            row = self._con.execute(
                "SELECT id, status FROM findings WHERE kpi = ? AND period = ?", key
            ).fetchone()
            finding_id = row["id"] if row else uuid.uuid4().hex[:12]
            self._con.execute(
                """
                INSERT INTO findings (id, detected_at, kpi, period, severity, headline,
                                      observed, expected, deviation_pct, impact_gbp,
                                      explanation, evidence, status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    severity=excluded.severity, headline=excluded.headline,
                    observed=excluded.observed, expected=excluded.expected,
                    deviation_pct=excluded.deviation_pct, impact_gbp=excluded.impact_gbp,
                    explanation=COALESCE(excluded.explanation, findings.explanation),
                    evidence=excluded.evidence
                """,
                (
                    finding_id, _now(), finding["kpi"], finding["period"],
                    finding.get("severity", "medium"), finding["headline"],
                    finding.get("observed"), finding.get("expected"),
                    finding.get("deviation_pct"), finding.get("impact_gbp"),
                    finding.get("explanation"),
                    json.dumps(finding.get("evidence", {}), default=str),
                    row["status"] if row else "open",
                ),
            )
            self._con.commit()
        return finding_id

    def set_finding_explanation(self, finding_id: str, explanation: str) -> None:
        with self._lock:
            self._con.execute(
                "UPDATE findings SET explanation = ? WHERE id = ?", (explanation, finding_id)
            )
            self._con.commit()

    def list_findings(self, limit: int = 25) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._con.execute(
                "SELECT * FROM findings ORDER BY abs(COALESCE(deviation_pct,0)) DESC, detected_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._finding_row(r) for r in rows]

    def get_finding(self, finding_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._con.execute("SELECT * FROM findings WHERE id = ?", (finding_id,)).fetchone()
        return self._finding_row(row) if row else None

    @staticmethod
    def _finding_row(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        try:
            item["evidence"] = json.loads(item.get("evidence") or "{}")
        except json.JSONDecodeError:
            item["evidence"] = {}
        return item

    # ----------------------------------------------------------------- actions

    def create_action(self, action: dict[str, Any]) -> dict[str, Any]:
        action_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._con.execute(
                """INSERT INTO actions (id, created_at, requested_by, action_type, title,
                                        detail, payload, rationale, expected_impact,
                                        status, finding_id)
                   VALUES (?,?,?,?,?,?,?,?,?,'pending',?)""",
                (
                    action_id, _now(), action.get("requested_by", "agent"),
                    action.get("action_type", "generic"), action["title"],
                    action.get("detail", ""), json.dumps(action.get("payload", {}), default=str),
                    action.get("rationale", ""), action.get("expected_impact", ""),
                    action.get("finding_id"),
                ),
            )
            self._con.commit()
        return self.get_action(action_id)  # type: ignore[return-value]

    def get_action(self, action_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._con.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
        return self._action_row(row) if row else None

    def list_actions(self, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        query = "SELECT * FROM actions"
        params: tuple = ()
        if status:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY created_at DESC LIMIT ?"
        params = params + (limit,)
        with self._lock:
            rows = self._con.execute(query, params).fetchall()
        return [self._action_row(r) for r in rows]

    def decide_action(self, action_id: str, approved: bool, decided_by: str, result: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._con.execute(
                "SELECT status FROM actions WHERE id = ?", (action_id,)
            ).fetchone()
            if row is None or row["status"] != "pending":
                return None  # already decided; never execute twice
            self._con.execute(
                "UPDATE actions SET status = ?, decided_at = ?, decided_by = ?, result = ? WHERE id = ?",
                ("approved" if approved else "rejected", _now(), decided_by, result, action_id),
            )
            self._con.commit()
        return self.get_action(action_id)

    @staticmethod
    def _action_row(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        try:
            item["payload"] = json.loads(item.get("payload") or "{}")
        except json.JSONDecodeError:
            item["payload"] = {}
        return item

    # ---------------------------------------------------------- claim reviews

    def record_claim_reviews(
        self,
        *,
        user_email: str,
        question: str,
        confidence: str,
        results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Log each re-derived claim as awaiting a human accept/discard.

        The verifier's opinion is not the last word - a leader still has to say
        whether they are willing to stand behind the figure. Persisting the claim
        is what makes that decision auditable later.
        """
        stored: list[dict[str, Any]] = []
        with self._lock:
            for result in results:
                review_id = uuid.uuid4().hex[:12]
                self._con.execute(
                    """INSERT INTO claim_reviews (id, created_at, user_email, question,
                                                  claim, verdict, detail, score, score_stated,
                                                  confidence, status)
                       VALUES (?,?,?,?,?,?,?,?,?,?,'pending')""",
                    (
                        review_id, _now(), (user_email or "").strip().casefold(),
                        str(question)[:600], str(result.get("claim", ""))[:1200],
                        str(result.get("verdict", "UNVERIFIABLE")).upper(),
                        str(result.get("detail", ""))[:600],
                        int(result.get("score") or 0),
                        1 if result.get("score_stated") else 0,
                        confidence,
                    ),
                )
                stored.append({**result, "id": review_id, "status": "pending"})
            self._con.commit()
        return stored

    def get_claim_review(self, review_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._con.execute(
                "SELECT * FROM claim_reviews WHERE id = ?", (review_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_claim_reviews(self, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        query = "SELECT * FROM claim_reviews"
        params: tuple = ()
        if status:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY created_at DESC LIMIT ?"
        params = params + (limit,)
        with self._lock:
            rows = self._con.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def decide_claim_review(
        self, review_id: str, accepted: bool, reviewed_by: str, note: str = ""
    ) -> dict[str, Any] | None:
        """Accept or discard one claim. Returns None if it was already decided."""
        with self._lock:
            row = self._con.execute(
                "SELECT status FROM claim_reviews WHERE id = ?", (review_id,)
            ).fetchone()
            if row is None or row["status"] != "pending":
                return None
            self._con.execute(
                """UPDATE claim_reviews
                   SET status = ?, reviewed_at = ?, reviewed_by = ?, note = ?
                   WHERE id = ?""",
                (
                    "accepted" if accepted else "discarded", _now(),
                    reviewed_by, note[:400], review_id,
                ),
            )
            self._con.commit()
        return self.get_claim_review(review_id)

    # --------------------------------------------------------------- decisions

    def record_decision(self, entry: dict[str, Any]) -> str:
        decision_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._con.execute(
                """INSERT INTO decisions (id, created_at, user_email, topic, question,
                                          finding, recommendation, metrics)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    decision_id, _now(), entry.get("user_email", ""), entry.get("topic", ""),
                    entry.get("question", "")[:600], entry.get("finding", "")[:1200],
                    entry.get("recommendation", "")[:800],
                    json.dumps(entry.get("metrics", {}), default=str),
                ),
            )
            self._con.commit()
        return decision_id

    def recent_decisions(self, user_email: str | None = None, limit: int = 8) -> list[dict[str, Any]]:
        query = "SELECT * FROM decisions"
        params: tuple = ()
        if user_email:
            query += " WHERE user_email = ?"
            params = (user_email.strip().casefold(),)
        query += " ORDER BY created_at DESC LIMIT ?"
        params = params + (limit,)
        with self._lock:
            rows = self._con.execute(query, params).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            try:
                item["metrics"] = json.loads(item.get("metrics") or "{}")
            except json.JSONDecodeError:
                item["metrics"] = {}
            out.append(item)
        return out

    def find_related_decisions(self, topic_terms: list[str], limit: int = 3) -> list[dict[str, Any]]:
        """Prior decisions whose topic or question mentions any of these terms."""
        if not topic_terms:
            return []
        clause = " OR ".join(["(lower(topic) LIKE ? OR lower(question) LIKE ?)"] * len(topic_terms))
        params: list[Any] = []
        for term in topic_terms:
            like = f"%{term.strip().casefold()}%"
            params.extend([like, like])
        params.append(limit)
        with self._lock:
            rows = self._con.execute(
                f"SELECT * FROM decisions WHERE {clause} ORDER BY created_at DESC LIMIT ?", params
            ).fetchall()
        return [dict(r) for r in rows]
