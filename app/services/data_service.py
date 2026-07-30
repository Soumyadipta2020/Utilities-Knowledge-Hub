"""
Data Service using Pandas.
Handles interaction with Live_Metrics.xlsx and Metadata_Access.xlsx Excel silos.
"""

from typing import Dict, Any, List, Optional
import pandas as pd
from pathlib import Path


class DataService:
    """Service to interact with structured Excel datasets via Pandas."""

    def __init__(self, metrics_path: Path, access_path: Path):
        self.metrics_path = metrics_path
        self.access_path = access_path

    def check_access_permission(self, user_role: str, data_source: str) -> Dict[str, Any]:
        """
        Check Metadata_Access.xlsx to determine if user_role has permission for data_source.
        Rules:
        - Customer: Knowledge_Base only.
        - Employee: Knowledge_Base + Live_Metrics.
        - Admin: All data sources.
        """
        if not self.access_path.exists():
            raise FileNotFoundError(f"Metadata Access Excel file missing at: {self.access_path}")

        df = pd.read_excel(self.access_path)
        role_clean = str(user_role).strip().capitalize()
        source_clean = str(data_source).strip()

        # Direct match or case-insensitive match in dataframe
        matches = df[
            (df["required_role"].str.lower() == role_clean.lower()) &
            (df["data_source"].str.lower().str.contains(source_clean.lower()))
        ]

        if not matches.empty:
            match_row = matches.iloc[0]
            return {
                "access_granted": True,
                "status": "Access Granted",
                "user_role": role_clean,
                "data_source": match_row["data_source"],
                "access_level": match_row["access_level"],
                "description": match_row["description"],
            }

        # Handle Admin fallback rule (Admin has all access)
        if role_clean.lower() == "admin":
            return {
                "access_granted": True,
                "status": "Access Granted",
                "user_role": "Admin",
                "data_source": source_clean,
                "access_level": "Full-Access",
                "description": "Administrator master privilege",
            }

        # Otherwise access is denied
        return {
            "access_granted": False,
            "status": "Access Denied",
            "user_role": role_clean,
            "data_source": source_clean,
            "reason": f"Role '{role_clean}' is not authorized to access data source '{source_clean}'.",
        }

    def get_live_metrics(self, metric_name: str = "all") -> Dict[str, Any]:
        """
        Query Live_Metrics.xlsx using pandas.
        """
        if not self.metrics_path.exists():
            raise FileNotFoundError(f"Live Metrics Excel file missing at: {self.metrics_path}")

        df = pd.read_excel(self.metrics_path)

        if metric_name.lower() in ["all", "", "list"]:
            records = df.to_dict(orient="records")
            return {
                "success": True,
                "metric_requested": "all",
                "count": len(records),
                "metrics": records,
            }

        query_clean = metric_name.lower().strip()
        matches = df[df["metric_name"].str.lower().str.contains(query_clean)]

        if matches.empty:
            return {
                "success": False,
                "metric_requested": metric_name,
                "error": f"No metric found matching '{metric_name}'.",
                "available_metrics": df["metric_name"].tolist(),
            }

        records = matches.to_dict(orient="records")
        return {
            "success": True,
            "metric_requested": metric_name,
            "count": len(records),
            "metrics": records,
        }
