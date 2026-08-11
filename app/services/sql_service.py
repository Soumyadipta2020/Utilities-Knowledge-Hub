"""
Full-fidelity SQL access over the CSV data estate.

The datasets here run to millions of rows and hundreds of megabytes each, which
makes `pandas.read_csv` a poor fit: loading `boiler_master.csv` alone costs ~15s
and ~3 GB of RAM, and joining two such datasets exceeds the memory available.

DuckDB reads the CSVs out-of-core with column and predicate pushdown, so queries
run against **every row** without materialising the file. The same join costs a
few seconds and a few hundred megabytes.

Only the number of rows *returned* is bounded, because that output is fed into a
language-model context window. The scan itself is always complete.
"""

from __future__ import annotations

import re
from pathlib import Path
from threading import Lock
from typing import Any

# Row counts keyed by path -> (mtime, size, rows). Counting newlines in a
# streamed pass is far cheaper than SELECT count(*) re-parsing the CSV.
_ROW_COUNTS: dict[str, tuple[float, int, int]] = {}
_ROW_COUNTS_LOCK = Lock()


def count_csv_rows(path: Path) -> int:
    """Data-row count for a CSV (excluding the header), cached on mtime+size."""
    try:
        stat = path.stat()
    except OSError:
        return 0

    key = str(path)
    with _ROW_COUNTS_LOCK:
        cached = _ROW_COUNTS.get(key)
        if cached and cached[0] == stat.st_mtime and cached[1] == stat.st_size:
            return cached[2]

    newlines = 0
    last_byte = b"\n"
    try:
        with open(path, "rb") as handle:
            while chunk := handle.read(8 * 1024 * 1024):
                newlines += chunk.count(b"\n")
                last_byte = chunk[-1:]
    except OSError:
        return 0

    rows = newlines - 1
    if last_byte not in (b"\n", b""):
        rows += 1
    rows = max(rows, 0)

    with _ROW_COUNTS_LOCK:
        _ROW_COUNTS[key] = (stat.st_mtime, stat.st_size, rows)
    return rows

try:
    import duckdb

    HAS_DUCKDB = True
except ImportError:  # pragma: no cover - falls back to the pandas tool
    duckdb = None  # type: ignore[assignment]
    HAS_DUCKDB = False


_INSTANCES: dict[str, "SqlService"] = {}
_INSTANCES_LOCK = Lock()


def get_sql_service(data_dir: Path) -> "SqlService":
    """Return the shared SqlService for a data directory.

    Services construct this by default so every caller - the agent, the data
    layer and the pipeline - queries full data through one connection instead of
    silently falling back to sampled pandas reads.
    """
    key = str(Path(data_dir).resolve())
    with _INSTANCES_LOCK:
        service = _INSTANCES.get(key)
        if service is None:
            service = SqlService(Path(data_dir))
            _INSTANCES[key] = service
        return service


class SqlService:
    """A DuckDB connection with one view per CSV dataset."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self._con: Any = None
        self._lock = Lock()
        self._views: list[str] = []
        if HAS_DUCKDB:
            self._connect()

    @property
    def available(self) -> bool:
        return self._con is not None

    def _connect(self) -> None:
        try:
            con = duckdb.connect(database=":memory:")
            # The progress bar writes escape codes to stdout and corrupts logs.
            con.execute("SET enable_progress_bar = false")
            self._con = con
            self.refresh_views()
        except Exception as error:  # noqa: BLE001 - never block boot on SQL setup
            print(f"[SqlService] DuckDB unavailable: {error}")
            self._con = None

    def refresh_views(self) -> None:
        """Expose each CSV as a lazily-scanned view named after the file stem."""
        if self._con is None:
            return
        names: list[str] = []
        for path in sorted(self.data_dir.glob("*.csv")):
            view = path.stem
            if not view.replace("_", "").isalnum():
                continue
            posix = str(path.resolve()).replace("\\", "/").replace("'", "''")
            try:
                # A view is metadata only - no rows are read until it is queried.
                self._con.execute(
                    f'CREATE OR REPLACE VIEW "{view}" AS '
                    f"SELECT * FROM read_csv_auto('{posix}', union_by_name=true)"
                )
                names.append(view)
            except Exception as error:  # noqa: BLE001 - skip an unreadable CSV
                print(f"[SqlService] Skipped view {view}: {error}")
        self._views = names
        print(f"[SqlService] Registered {len(names)} dataset views (full data, no row limit).")

    @property
    def datasets(self) -> list[str]:
        return list(self._views)

    def row_count(self, view: str) -> int:
        """True row count for a dataset view."""
        return count_csv_rows(self.data_dir / f"{view}.csv")

    def views_referenced(self, sql: str) -> list[str]:
        """Dataset views named in a SQL statement.

        Used for evidence reporting: because these views are CSV scans, every
        row of a referenced dataset is read.
        """
        tokens = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", sql))
        return [view for view in self._views if view in tokens]

    def columns_with_types(self, view: str) -> list[tuple[str, str]]:
        """Return [(column, type)] for a view, or [] if it cannot be described."""
        if self._con is None:
            return []
        try:
            with self._lock:
                rows = self._con.execute(f'DESCRIBE "{view}"').fetchall()
            return [(str(row[0]), str(row[1])) for row in rows]
        except Exception:  # noqa: BLE001
            return []

    def schema_text(self) -> str:
        """Column listing for every view, for the agent's system prompt."""
        if self._con is None:
            return ""
        lines = []
        for view in self._views:
            try:
                cols = self._con.execute(f'DESCRIBE "{view}"').fetchall()
                rendered = ", ".join(f"{row[0]} {row[1]}" for row in cols)
                lines.append(f"- {view}({rendered})")
            except Exception:  # noqa: BLE001
                continue
        return "\n".join(lines)

    def query(self, sql: str, max_rows: int = 100) -> dict[str, Any]:
        """
        Run a read-only SQL statement across the full datasets.

        Returns {"success", "columns", "rows", "row_count", "truncated"}.
        `row_count` is the true size of the result set; `rows` is capped at
        `max_rows` purely to bound what gets pushed into the model context.
        """
        if self._con is None:
            return {"success": False, "error": "DuckDB is not available in this environment."}

        statement = sql.strip().rstrip(";").strip()
        if not statement:
            return {"success": False, "error": "Empty SQL statement."}

        lowered = statement.lower()
        forbidden = ("insert ", "update ", "delete ", "drop ", "alter ", "attach ", "copy ", "create ")
        if any(lowered.startswith(word) or f"; {word}" in lowered for word in forbidden):
            return {
                "success": False,
                "error": "Only read-only SELECT/WITH queries are permitted.",
            }

        with self._lock:
            try:
                # LIMIT is applied to a wrapper so the inner query still scans and
                # aggregates over every row.
                relation = self._con.sql(statement)
                columns = list(relation.columns)
                rows = relation.limit(max_rows + 1).fetchall()
            except Exception as error:  # noqa: BLE001 - surfaced back to the agent
                return {"success": False, "error": f"{type(error).__name__}: {error}"}

        truncated = len(rows) > max_rows
        if truncated:
            rows = rows[:max_rows]

        return {
            "success": True,
            "columns": columns,
            "rows": rows,
            "returned": len(rows),
            "truncated": truncated,
        }
