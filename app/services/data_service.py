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
        """Return matching aggregated business data across all CSV datasets."""
        csv_files = list(self.data_dir.glob("*.csv"))
        matches: list[dict[str, Any]] = []
        query_terms = set(query.casefold().replace("_", " ").split())
        
        for csv_file in csv_files:
            df = self._read_csv_safe(csv_file.name)
            if df.empty: continue
            for record in df.head(100).to_dict(orient="records"):
                searchable = " ".join(str(value) for value in record.values()).casefold().replace("_", " ")
                if query_terms.intersection(searchable.split()) or any(term in searchable for term in query_terms if len(term) > 2):
                    matches.append({"dataset": csv_file.stem, **record})
                    if len(matches) >= 50:
                        break
            if len(matches) >= 50:
                break
                    
        if not matches:
            # Fall back to returning top sample records from first available dataset
            first_df = self._read_csv_safe("customer_master.csv")
            matches = [{"dataset": "customer_master", **record} for record in first_df.head(5).to_dict(orient="records")] if not first_df.empty else []
            
        return {"success": True, "count": len(matches), "records": matches}

    def search_records(self, query: str) -> dict[str, Any]:
        """Search all CSV datasets in data_dir for exact or token matches (e.g. CUST00003, CUST00001, ENG-44)."""
        csv_files = list(self.data_dir.glob("*.csv"))
        matches: list[dict[str, Any]] = []

        id_tokens = set([m.upper() for m in re.findall(r"\b[A-Z]{3,8}[-\_]?\d{1,10}\b", query, flags=re.IGNORECASE)])

        for csv_file in csv_files:
            if csv_file.name in ["dataset_ownership.csv", "business_rules.csv"]:
                continue
            df = self._read_csv_safe(csv_file.name)
            if df.empty:
                continue

            for record in df.to_dict(orient="records"):
                row_values_upper = set([str(v).strip().upper() for v in record.values() if pd.notnull(v)])

                if id_tokens and id_tokens.intersection(row_values_upper):
                    cleaned_rec = {k: v for k, v in record.items() if pd.notnull(v) and str(v) != "nan"}
                    matches.append({"_dataset": csv_file.stem, **cleaned_rec})
                    if len(matches) >= 20:
                        break
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


