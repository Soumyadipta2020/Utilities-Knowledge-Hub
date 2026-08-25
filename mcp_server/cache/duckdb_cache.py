import duckdb
import json
from config.settings import settings

class DuckDBCache:
    def __init__(self):
        self.conn = duckdb.connect(settings.duckdb_cache_path)
        self._initialize_tables()

    def _initialize_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS cached_tables (
                table_name VARCHAR PRIMARY KEY,
                catalog VARCHAR,
                schema VARCHAR,
                description VARCHAR
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS cached_columns (
                table_name VARCHAR,
                column_name VARCHAR,
                data_type VARCHAR,
                comment VARCHAR,
                is_partition_key BOOLEAN,
                PRIMARY KEY (table_name, column_name)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS cached_metrics (
                metric_name VARCHAR PRIMARY KEY,
                description VARCHAR,
                sql_formula VARCHAR,
                grain VARCHAR
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS cached_partitions (
                table_name VARCHAR,
                partition_id VARCHAR,
                PRIMARY KEY (table_name, partition_id)
            )
        """)

    def lookup_schema(self, table_name: str) -> dict:
        table_result = self.conn.execute(
            "SELECT catalog, schema, description FROM cached_tables WHERE table_name = ?",
            (table_name,)
        ).fetchone()

        if not table_result:
            return {}

        columns_result = self.conn.execute(
            "SELECT column_name, data_type, comment, is_partition_key FROM cached_columns WHERE table_name = ?",
            (table_name,)
        ).fetchall()

        columns = [
            {
                "column_name": col[0],
                "data_type": col[1],
                "comment": col[2],
                "is_partition_key": col[3]
            }
            for col in columns_result
        ]
        
        partition_keys = [col["column_name"] for col in columns if col["is_partition_key"]]

        return {
            "table_name": table_name,
            "catalog": table_result[0],
            "schema": table_result[1],
            "description": table_result[2],
            "columns": columns,
            "partition_keys": partition_keys
        }

    def lookup_metric(self, metric_name: str) -> dict:
        result = self.conn.execute(
            "SELECT description, sql_formula, grain FROM cached_metrics WHERE metric_name = ?",
            (metric_name,)
        ).fetchone()

        if not result:
            return {}

        return {
            "metric_name": metric_name,
            "description": result[0],
            "sql_formula": result[1],
            "grain": result[2]
        }

    def upsert_catalog_metadata(self, metadata: dict) -> None:
        if "tables" in metadata:
            for table in metadata["tables"]:
                self.conn.execute(
                    "INSERT OR REPLACE INTO cached_tables (table_name, catalog, schema, description) VALUES (?, ?, ?, ?)",
                    (table["table_name"], table.get("catalog"), table.get("schema"), table.get("description"))
                )
                for col in table.get("columns", []):
                    self.conn.execute(
                        "INSERT OR REPLACE INTO cached_columns (table_name, column_name, data_type, comment, is_partition_key) VALUES (?, ?, ?, ?, ?)",
                        (table["table_name"], col["column_name"], col.get("data_type"), col.get("comment"), col.get("is_partition_key", False))
                    )
        
        if "metrics" in metadata:
            for metric in metadata["metrics"]:
                self.conn.execute(
                    "INSERT OR REPLACE INTO cached_metrics (metric_name, description, sql_formula, grain) VALUES (?, ?, ?, ?)",
                    (metric["metric_name"], metric.get("description"), metric.get("sql_formula"), metric.get("grain"))
                )

duckdb_cache = DuckDBCache()
