from .base_connector import BaseDataConnector
from .csv_connector import CSVConnector
from .databricks_connector import DatabricksConnector
import os
from pathlib import Path

def get_connector(data_dir: Path) -> BaseDataConnector:
    """Factory to get the configured data connector."""
    backend = os.getenv("DATA_BACKEND", "csv").lower()
    
    if backend == "databricks":
        return DatabricksConnector(
            host=os.getenv("DATABRICKS_HOST", ""),
            token=os.getenv("DATABRICKS_TOKEN", ""),
            cluster_id=os.getenv("DATABRICKS_CLUSTER_ID", "")
        )
    else:
        # Default for the Render Free demo
        connector = CSVConnector(data_dir)
        connector.connect()
        return connector

__all__ = ["BaseDataConnector", "CSVConnector", "DatabricksConnector", "get_connector"]
