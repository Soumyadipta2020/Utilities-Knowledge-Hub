import json
from fastmcp import FastMCP
from mcp_server.cache.duckdb_cache import duckdb_cache

def register_catalog_resources(mcp: FastMCP):
    
    @mcp.resource("schema://{catalog}/{schema}/{table}")
    def get_table_schema(catalog: str, schema: str, table: str) -> str:
        """Fetches instantaneous cached table DDL and partition keys."""
        result = duckdb_cache.lookup_schema(table)
        if not result:
            return f"Table {table} not found in catalog {catalog}.{schema}"
        return json.dumps(result, indent=2)

    @mcp.resource("metrics://energy/{metric_name}")
    def get_energy_metric(metric_name: str) -> str:
        """Returns business definitions, grain, and validated SQL snippets for standard utility KPIs."""
        result = duckdb_cache.lookup_metric(metric_name)
        if not result:
            return f"Metric {metric_name} not found in cache."
        return json.dumps(result, indent=2)
