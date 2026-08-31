import os
from typing import Any, Dict, List
from pathlib import Path

from .base_connector import BaseDataConnector
from app.services.data_service import DataService
from app.services.sql_service import SqlService, get_sql_service

class CSVConnector(BaseDataConnector):
    """
    CSV Implementation of the Data Connector.
    Used for Render Free demo deployments where paid data infrastructure is unavailable.
    Wraps the existing DataService (Pandas) and SqlService (DuckDB).
    """

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.sql_service = get_sql_service(data_dir)
        self.data_service = DataService(data_dir, self.sql_service)
        self._connected = False

    def connect(self) -> bool:
        # SQL service initialization triggers DuckDB view creation
        self._connected = self.sql_service.available
        return self._connected

    def list_tables(self) -> List[str]:
        return self.sql_service.datasets

    def get_schema(self, table_name: str) -> Dict[str, Any]:
        # Simple schema fetch using DuckDB
        if not self.sql_service.available:
            return {}
        try:
            res = self.sql_service._con.execute(f"DESCRIBE {table_name}").fetchall()
            schema = {row[0]: row[1] for row in res}
            return schema
        except Exception:
            return {}

    def query(self, sql_query: str, limit: int = 100) -> List[Dict[str, Any]]:
        if not self.sql_service.available:
            return []
        try:
            # Ensure query has limit if not provided in SQL
            if "limit" not in sql_query.lower():
                sql_query = f"{sql_query} LIMIT {limit}"
            
            df = self.sql_service._con.execute(sql_query).df()
            return df.to_dict(orient="records")
        except Exception as e:
            print(f"[CSVConnector] Query error: {e}")
            return []

    def read_table(self, table_name: str, limit: int = 100, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        # Pushdown filtering to DuckDB
        if not filters:
            query = f"SELECT * FROM {table_name} LIMIT {limit}"
        else:
            conditions = []
            for k, v in filters.items():
                if isinstance(v, str):
                    conditions.append(f"{k} = '{v}'")
                else:
                    conditions.append(f"{k} = {v}")
            where_clause = " AND ".join(conditions)
            query = f"SELECT * FROM {table_name} WHERE {where_clause} LIMIT {limit}"
        
        return self.query(query, limit)

    def validate_access(self, user_role: str, table_name: str) -> bool:
        res = self.data_service.check_access_permission(user_role, table_name)
        return res.get("access_granted", False)
