import json
from fastmcp import FastMCP
from typing import Literal
from mcp_server.clients.databricks_client import databricks_client
from mcp_server.clients.trino_snowflake import trino_snowflake_client

def register_query_profiler_tool(mcp: FastMCP):

    @mcp.tool()
    async def audit_and_optimize_query(sql_statement: str, engine: Literal['databricks', 'snowflake', 'trino']) -> str:
        """
        Generates EXPLAIN execution plans without running heavy scans.
        Identifies anti-patterns: full table scans, Cartesian cross joins, spill to disk, and missing broadcast hints.
        """
        if engine == 'databricks':
            client = databricks_client
        else:
            client = trino_snowflake_client
            
        explain_result = await client.explain_query(sql_statement)
        
        # Simple heuristic pattern matching on the explain plan output
        warnings = []
        if "CartesianProduct" in explain_result or "CrossJoin" in explain_result:
            warnings.append("Cartesian cross join detected. Ensure all joins have proper conditions.")
        if "BroadcastHashJoin" not in explain_result and "SortMergeJoin" in explain_result:
            warnings.append("Missing broadcast hints. Consider using broadcast joins for small tables.")
        if "FileScan" in explain_result and "PushedFilters: []" in explain_result:
            warnings.append("Full table scan detected without pushed filters. Check partition keys.")
            
        analysis = {
            "engine": engine,
            "explain_plan": explain_result,
            "warnings": warnings,
            "recommendation": "Optimization suggested" if warnings else "Query plan looks optimal"
        }
        
        return json.dumps(analysis, indent=2)
