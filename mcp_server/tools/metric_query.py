import json
from typing import List, Dict, Any, Optional
from fastmcp import FastMCP
from mcp_server.engine.metric_engine import metric_engine
from mcp_server.engine.duckdb_engine import duckdb_engine
from mcp_server.tools.analytics_query import _format_markdown_table
import logging

logger = logging.getLogger(__name__)

def register_metric_query_tool(mcp: FastMCP):
    @mcp.tool()
    def query_business_metric(
        metric_name: str, 
        dimensions: Optional[List[str]] = None, 
        time_grain: Optional[str] = None, 
        filters: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Compute a business metric dynamically.
        
        Args:
            metric_name: Name of the metric to compute (e.g., total_visits, total_repairs)
            dimensions: List of dimension column names to group the metric by.
            time_grain: Time grouping grain (e.g., 'day', 'week', 'month', 'year').
            filters: Dictionary of equality filters (e.g., {"visit_status": "Completed"}).
        """
        try:
            sql_query = metric_engine.generate_metric_sql(
                metric_name=metric_name,
                dimensions=dimensions,
                time_grain=time_grain,
                filters=filters
            )
            logger.info(f"Generated metric SQL: {sql_query}")
        except Exception as e:
            return json.dumps({
                "status": "VALIDATION_ERROR",
                "error": str(e)
            }, indent=2)

        try:
            result = duckdb_engine.execute_query(sql_query)
            markdown_table = _format_markdown_table(result["columns"], result["data"])
            
            return json.dumps({
                "status": "SUCCEEDED",
                "metric_name": metric_name,
                "rows_returned": len(result["data"]),
                "data": markdown_table,
                "sql_used": sql_query
            }, indent=2)
        except Exception as e:
            return json.dumps({
                "status": "EXECUTION_ERROR",
                "error": str(e),
                "sql_used": sql_query
            }, indent=2)
