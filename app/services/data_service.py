"""Pandas access layer for the local Excel data silos."""

from pathlib import Path
from typing import Any
import re

import pandas as pd


class DataService:
    """Read operational, telemetry, and metadata workbooks for the chatbot."""

    def __init__(self, metrics_path: Path, access_path: Path, operations_path: Path) -> None:
        self.metrics_path = metrics_path
        self.access_path = access_path
        self.operations_path = operations_path

    @staticmethod
    def _require_file(path: Path, label: str) -> None:
        if not path.exists():
            raise FileNotFoundError(f"{label} is missing at {path}. Run app/data/generate_mock_data.py.")

    def check_access_permission(self, user_role: str, data_source: str) -> dict[str, Any]:
        """Return the metadata-backed permission decision for one data source."""
        self._require_file(self.access_path, "Metadata Access workbook")
        data_frame = pd.read_excel(self.access_path)
        role = user_role.strip().capitalize()
        source = data_source.strip()
        matches = data_frame[
            (data_frame["required_role"].str.casefold() == role.casefold())
            & (data_frame["data_source"].str.casefold() == source.casefold())
        ]
        if not matches.empty:
            record = matches.iloc[0]
            return {
                "access_granted": True,
                "status": "Access Granted",
                "user_role": role,
                "data_source": str(record["data_source"]),
                "access_level": str(record["access_level"]),
                "description": str(record["description"]),
            }
        return {
            "access_granted": False,
            "status": "Access Denied",
            "user_role": role,
            "data_source": source,
            "reason": f"Role '{role}' is not authorized to access data source '{source}'.",
        }

    def get_live_metrics(self, metric_name: str = "all") -> dict[str, Any]:
        """Query the Live_Metrics workbook by metric name."""
        self._require_file(self.metrics_path, "Live Metrics workbook")
        data_frame = pd.read_excel(self.metrics_path)
        if metric_name.strip().casefold() in {"all", "", "list"}:
            records = data_frame.to_dict(orient="records")
        else:
            records = data_frame[
                data_frame["metric_name"].str.casefold().str.contains(metric_name.strip().casefold(), regex=False)
            ].to_dict(orient="records")
        if not records:
            return {"success": False, "error": f"No metric matches '{metric_name}'.", "available_metrics": data_frame["metric_name"].tolist()}
        return {"success": True, "count": len(records), "metrics": records}

    def get_business_data(self, query: str) -> dict[str, Any]:
        """Return matching aggregated business data from the operations workbook."""
        self._require_file(self.operations_path, "Business Operations workbook")
        query_terms = set(query.casefold().replace("_", " ").split())
        matches: list[dict[str, Any]] = []
        for sheet_name in ("Sales_Funnel", "Service_Activity"):
            data_frame = pd.read_excel(self.operations_path, sheet_name=sheet_name)
            for record in data_frame.to_dict(orient="records"):
                searchable = " ".join(str(value) for value in record.values()).casefold()
                if query_terms.intersection(searchable.split()) or any(term in searchable for term in query_terms if len(term) > 3):
                    matches.append({"dataset": sheet_name, **record})
        if not matches:
            return {"success": False, "error": "No business records match that query."}
        return {"success": True, "count": len(matches), "records": matches}

    def get_metric_definitions(self, query: str) -> dict[str, Any]:
        """Return definitions for requested operational or commercial metrics."""
        self._require_file(self.operations_path, "Business Operations workbook")
        data_frame = pd.read_excel(self.operations_path, sheet_name="Metric_Definitions")
        query_tokens = set(re.findall(r"[a-z0-9]+", query.casefold().replace("_", " ")))
        query_tokens_singular = {t[:-1] if t.endswith('s') and len(t) > 3 else t for t in query_tokens}
        
        records = []
        for record in data_frame.to_dict(orient="records"):
            name_tokens = set(record["metric_name"].replace("_", " ").casefold().split())
            name_tokens.discard("pct")
            name_tokens_singular = {t[:-1] if t.endswith('s') and len(t) > 3 else t for t in name_tokens}
            
            overlap = name_tokens_singular.intersection(query_tokens_singular)
            if overlap:
                records.append(record)
                
        return {"success": bool(records), "definitions": records}

    def forecast_installations(self) -> dict[str, Any]:
        """Create a transparent directional installation forecast from the active pipeline."""
        self._require_file(self.operations_path, "Business Operations workbook")
        funnel = pd.read_excel(self.operations_path, sheet_name="Sales_Funnel")
        installations = funnel[funnel["service_line"].str.casefold() == "heating installation"]
        if installations.empty:
            return {"success": False, "error": "No heating-installation pipeline records are available."}
        leads = int(installations["leads"].sum())
        appointments = int(installations["net_appointments"].sum())
        quotes = int(installations["quotes_issued"].sum())
        conversion = float(installations["sales_conversion_pct"].mean())
        projected_sales = round(leads * conversion / 100)
        return {
            "success": True,
            "leads": leads,
            "net_appointments": appointments,
            "quotes_issued": quotes,
            "conversion_pct": conversion,
            "projected_installations": projected_sales,
            "note": "Directional estimate based on the current installation lead volume and observed conversion rate; additional historical periods improve forecast reliability.",
        }

    def get_dataset_sample(self, dataset_name: str) -> dict[str, Any]:
        """Return a small sample of the requested dataset from Business_Operations.xlsx."""
        self._require_file(self.operations_path, "Business Operations workbook")
        try:
            xl = pd.ExcelFile(self.operations_path)
            sheet_names = xl.sheet_names
            
            target_sheet = None
            query_clean = dataset_name.lower().replace("_", " ").strip()
            for sn in sheet_names:
                if query_clean in sn.lower().replace("_", " ") or sn.lower().replace("_", " ") in query_clean:
                    target_sheet = sn
                    break
            
            if not target_sheet:
                return {"success": False, "error": f"Dataset '{dataset_name}' not found."}
                
            data_frame = pd.read_excel(self.operations_path, sheet_name=target_sheet)
            records = data_frame.head(5).to_dict(orient="records")
            return {"success": True, "dataset": target_sheet, "sample": records}
        except Exception as e:
            return {"success": False, "error": str(e)}
