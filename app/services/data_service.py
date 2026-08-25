"""Pandas access layer for the local CSV datasets."""

from collections import OrderedDict
from pathlib import Path
from threading import Lock
from typing import Any
import os
import re

import pandas as pd

# Full data by default: no row limit. Set AGENT_MAX_ROWS to a positive number
# only if a machine cannot hold the frames.
MAX_QUERY_ROWS = int(os.getenv("AGENT_MAX_ROWS", "0"))

# Loaded frames are cached with a safe memory budget suited for lightweight and
# containerized free-tier environments (e.g. Render Free 512MB RAM).
FRAME_CACHE_BUDGET_BYTES = int(
    float(os.getenv("AGENT_FRAME_CACHE_MB", os.getenv("AGENT_FRAME_CACHE_GB", "0.128") if "AGENT_FRAME_CACHE_GB" in os.environ else "128"))
    * (1024**2 if "AGENT_FRAME_CACHE_MB" in os.environ or "AGENT_FRAME_CACHE_GB" not in os.environ else 1024**3)
)


class DataService:
    """Read CSV datasets for the chatbot."""

    def __init__(self, data_dir: Path, sql_service: Any = None) -> None:
        self.data_dir = data_dir
        if sql_service is None:
            from app.services.sql_service import get_sql_service

            sql_service = get_sql_service(data_dir)
        self.sql_service = sql_service
        self._frame_cache: OrderedDict[str, tuple[pd.DataFrame, bool]] = OrderedDict()
        self._frame_sizes: dict[str, int] = {}
        self._cache_lock = Lock()

    def _read_csv_safe(self, filename: str) -> pd.DataFrame:
        path = self.data_dir / filename
        if not path.exists():
            return pd.DataFrame()
        return pd.read_csv(path)

    def _read_head(self, filename: str, rows: int) -> pd.DataFrame:
        """Read only the leading rows of a dataset without loading the whole file."""
        path = self.data_dir / filename
        if not path.exists():
            return pd.DataFrame()
        try:
            return pd.read_csv(path, nrows=rows)
        except Exception:  # noqa: BLE001 - a malformed CSV should just be skipped
            return pd.DataFrame()

    def load_frame(self, filename: str) -> tuple[pd.DataFrame, bool]:
        """
        Return (dataframe, truncated) for a dataset, caching recent frames.

        `truncated` is True when the row cap kicked in, so callers can tell the
        agent that aggregate figures cover only the leading rows.
        """
        name = Path(str(filename)).name
        if not name.endswith(".csv"):
            name += ".csv"

        with self._cache_lock:
            cached = self._frame_cache.get(name)
            if cached is not None:
                self._frame_cache.move_to_end(name)
                return cached

        path = self.data_dir / name
        if not path.exists():
            return pd.DataFrame(), False

        if MAX_QUERY_ROWS > 0:
            # Read one extra row so a full-length result is detectable as truncated.
            frame = pd.read_csv(path, nrows=MAX_QUERY_ROWS + 1)
            truncated = len(frame) > MAX_QUERY_ROWS
            if truncated:
                frame = frame.head(MAX_QUERY_ROWS)
        else:
            frame = pd.read_csv(path)
            truncated = False

        try:
            frame_bytes = int(frame.memory_usage(deep=True).sum())
        except Exception:  # noqa: BLE001 - sizing must never fail a read
            frame_bytes = 0

        with self._cache_lock:
            self._frame_cache[name] = (frame, truncated)
            self._frame_sizes[name] = frame_bytes
            self._frame_cache.move_to_end(name)
            # Evict least-recently-used frames until the cache fits its budget.
            # A single frame larger than the budget is kept (we just loaded it)
            # but nothing else is retained alongside it.
            while (
                len(self._frame_cache) > 1
                and sum(self._frame_sizes.values()) > FRAME_CACHE_BUDGET_BYTES
            ):
                evicted, _ = self._frame_cache.popitem(last=False)
                self._frame_sizes.pop(evicted, None)

        return frame, truncated

    def check_access_permission(self, user_role: str, data_source: str) -> dict[str, Any]:
        """Return the metadata-backed permission decision for one data source."""
        # For now, allow everything or mock it since we removed Metadata_Access.xlsx
        role = user_role.strip().capitalize()
        return {
            "access_granted": True,
            "status": "Access Granted",
            "user_role": role,
            "data_source": data_source,
            "access_level": "Full",
            "description": "Auto-granted access for new CSV schema.",
        }

    def get_live_metrics(self, metric_name: str = "all") -> dict[str, Any]:
        """Query some metrics dataset. Let's use engineer_productivity.csv as an example."""
        df = self._read_csv_safe("engineer_productivity.csv")
        if df.empty:
            return {"success": False, "error": "engineer_productivity.csv is missing."}
            
        records = df.head(10).to_dict(orient="records")
        return {"success": True, "count": len(records), "metrics": records}

    def get_business_data(self, query: str) -> dict[str, Any]:
        """Return matching aggregated business data across all CSV datasets."""
        csv_files = list(self.data_dir.glob("*.csv"))
        matches: list[dict[str, Any]] = []
        query_terms = set(query.casefold().replace("_", " ").split())
        
        for csv_file in csv_files:
            df = self._read_head(csv_file.name, 100)
            if df.empty: continue
            for record in df.to_dict(orient="records"):
                searchable = " ".join(str(value) for value in record.values()).casefold().replace("_", " ")
                if query_terms.intersection(searchable.split()) or any(term in searchable for term in query_terms if len(term) > 2):
                    matches.append({"dataset": csv_file.stem, **record})
                    if len(matches) >= 50:
                        break
            if len(matches) >= 50:
                break
                    
        if not matches:
            # Fall back to returning top sample records from first available dataset
            first_df = self._read_head("customer_master.csv", 5)
            matches = [{"dataset": "customer_master", **record} for record in first_df.head(5).to_dict(orient="records")] if not first_df.empty else []
            
        return {"success": True, "count": len(matches), "records": matches}

    def _search_records_sql(self, id_tokens: set[str], limit: int = 20) -> list[dict[str, Any]] | None:
        """Find records matching any ID token across all datasets, full scan.

        Returns None if the SQL engine errors, so the caller can fall back.
        """
        service = self.sql_service
        literals = ", ".join("'" + token.replace("'", "''") + "'" for token in id_tokens)
        matches: list[dict[str, Any]] = []

        for view in service.datasets:
            if view in {"dataset_ownership", "business_rules"}:
                continue
            # Identifiers are text, so numeric and date columns cannot match.
            # Skipping them avoids casting every column of every row.
            text_cols = [
                name
                for name, dtype in service.columns_with_types(view)
                if "CHAR" in dtype.upper() or "TEXT" in dtype.upper()
            ]
            if not text_cols:
                continue

            predicate = " OR ".join(
                f'upper(trim("{col}")) IN ({literals})' for col in text_cols
            )
            try:
                res = service.query(
                    f'SELECT * FROM "{view}" WHERE {predicate} LIMIT {limit - len(matches)}',
                    max_rows=limit,
                )
            except Exception:  # noqa: BLE001 - fall back to the pandas scan
                return None

            if not res.get("success"):
                continue
            for row in res["rows"]:
                record = {
                    key: value
                    for key, value in zip(res["columns"], row)
                    if value is not None and str(value) != "nan"
                }
                matches.append({"_dataset": view, **record})
            if len(matches) >= limit:
                break

        return matches

    def search_records(self, query: str) -> dict[str, Any]:
        """Search all CSV datasets in data_dir for exact or token matches (e.g. CUST00003, CUST00001, ENG-44)."""
        csv_files = list(self.data_dir.glob("*.csv"))
        matches: list[dict[str, Any]] = []

        id_tokens = set([m.upper() for m in re.findall(r"\b[A-Z]{3,8}[-\_]?\d{1,10}\b", query, flags=re.IGNORECASE)])

        if not id_tokens:
            return {"success": False, "count": 0, "results": []}

        # Prefer the SQL engine: it scans every row of every dataset without
        # loading them, so record lookups are complete rather than sampled.
        if self.sql_service is not None and self.sql_service.available:
            sql_matches = self._search_records_sql(id_tokens)
            if sql_matches is not None:
                return {"success": bool(sql_matches), "count": len(sql_matches), "results": sql_matches}

        for csv_file in csv_files:
            if csv_file.name in ["dataset_ownership.csv", "business_rules.csv"]:
                continue
            df, _ = self.load_frame(csv_file.name)
            if df.empty:
                continue

            # Vectorized ID match. Row-by-row to_dict over a 400 MB frame took
            # minutes and gigabytes; this scans the object columns in one pass.
            candidates = df.select_dtypes(include=["object", "string"])
            if candidates.empty:
                continue

            mask = pd.Series(False, index=df.index)
            for column in candidates.columns:
                upper = candidates[column].astype("string").str.strip().str.upper()
                mask |= upper.isin(id_tokens)
                if mask.sum() >= 20:
                    break

            hits = df[mask].head(20 - len(matches))
            for record in hits.to_dict(orient="records"):
                cleaned_rec = {k: v for k, v in record.items() if pd.notnull(v) and str(v) != "nan"}
                matches.append({"_dataset": csv_file.stem, **cleaned_rec})

            if len(matches) >= 20:
                break

        return {"success": bool(matches), "count": len(matches), "results": matches}



    def get_metric_definitions(self, query: str) -> dict[str, Any]:
        """Return definitions from business_rules.csv."""
        df = self._read_csv_safe("business_rules.csv")
        if df.empty:
            return {"success": False, "definitions": []}
            
        query_tokens = set(re.findall(r"[a-z0-9]+", query.casefold().replace("_", " ")))
        records = []
        for record in df.to_dict(orient="records"):
            name_tokens = set(str(record.get("rule_name", "")).replace("_", " ").casefold().split())
            if name_tokens.intersection(query_tokens):
                records.append(record)
                
        return {"success": bool(records), "definitions": records}

    def forecast_installations(self) -> dict[str, Any]:
        """Forecast from quotes_and_sales."""
        df = self._read_csv_safe("quotes_and_sales.csv")
        if df.empty:
            return {"success": False, "error": "No quotes and sales records are available."}
            
        quotes = len(df)
        avg_primary = df["primary_qutation"].mean()
        avg_final = df["final_quotation"].mean()
        
        return {
            "success": True,
            "leads": quotes,
            "quotes_issued": quotes,
            "avg_primary_quotation": round(float(avg_primary), 2) if pd.notnull(avg_primary) else 0,
            "avg_final_quotation": round(float(avg_final), 2) if pd.notnull(avg_final) else 0,
            "note": "Directional estimate based on generated synthetic sales data.",
        }

    def get_dataset_sample(self, dataset_name: str) -> dict[str, Any]:
        """Return a small sample of the requested dataset CSV."""
        if not dataset_name.endswith(".csv"):
            dataset_name += ".csv"
            
        df = self._read_csv_safe(dataset_name)
        if df.empty:
            return {"success": False, "error": f"Dataset '{dataset_name}' not found."}
            
        records = df.head(5).to_dict(orient="records")
        return {"success": True, "dataset": dataset_name, "sample": records}

    def get_dataset_ownership(self, dataset_name: str | None = None) -> dict[str, Any]:
        """Return dataset ownership details from dataset_ownership.json or dataset_ownership.csv."""
        import json
        json_path = self.data_dir / "dataset_ownership.json"
        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    datasets = data.get("datasets", [])
                    if dataset_name:
                        clean_target = dataset_name.replace("Dataset:", "").replace(".csv", "").strip().lower()
                        match = next((d for d in datasets if d["dataset_id"].lower() == clean_target or d["dataset_name"].lower() == clean_target), None)
                        if match:
                            return {"success": True, "ownership": match}
                        return {"success": False, "error": f"No ownership record found for '{dataset_name}'."}
                    return {"success": True, "datasets": datasets, "total": len(datasets)}
            except Exception as e:
                print(f"[Dataset Ownership Error]: {e}")

        # Fallback if json not loaded
        csv_path = self.data_dir / "dataset_ownership.csv"
        if csv_path.exists():
            df = self._read_csv_safe("dataset_ownership.csv")
            if not df.empty:
                records = df.to_dict(orient="records")
                if dataset_name:
                    clean_target = dataset_name.replace("Dataset:", "").replace(".csv", "").strip().lower()
                    match = next((d for d in records if str(d.get("dataset_id")).lower() == clean_target), None)
                    if match:
                        return {"success": True, "ownership": match}
                    return {"success": False, "error": f"No ownership record found for '{dataset_name}'."}
                return {"success": True, "datasets": records, "total": len(records)}

        return {"success": False, "error": "dataset_ownership file not found."}


