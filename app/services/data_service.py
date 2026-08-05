"""Pandas access layer for the local CSV datasets."""

from pathlib import Path
from typing import Any
import re

import pandas as pd


class DataService:
    """Read CSV datasets for the chatbot."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir

    def _read_csv_safe(self, filename: str) -> pd.DataFrame:
        path = self.data_dir / filename
        if not path.exists():
            return pd.DataFrame()
        return pd.read_csv(path)

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
        """Return matching aggregated business data from quotes_and_sales or service_history."""
        df_quotes = self._read_csv_safe("quotes_and_sales.csv")
        df_service = self._read_csv_safe("service_history.csv")
        
        matches: list[dict[str, Any]] = []
        query_terms = set(query.casefold().replace("_", " ").split())
        
        for name, df in [("quotes", df_quotes), ("services", df_service)]:
            if df.empty: continue
            for record in df.to_dict(orient="records"):
                searchable = " ".join(str(value) for value in record.values()).casefold()
                if query_terms.intersection(searchable.split()) or any(term in searchable for term in query_terms if len(term) > 3):
                    matches.append({"dataset": name, **record})
                    
        if not matches:
            return {"success": False, "error": "No business records match that query."}
        return {"success": True, "count": len(matches), "records": matches}

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

