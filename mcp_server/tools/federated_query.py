import json
import sqlglot
from sqlglot import exp
from typing import Literal
from fastmcp import FastMCP
from mcp_server.clients.databricks_client import databricks_client
from mcp_server.clients.trino_snowflake import trino_snowflake_client
import logging

logger = logging.getLogger(__name__)

# List of destructive operations
DESTRUCTIVE_OPERATIONS = (
    exp.Drop,
    exp.Delete,
    exp.TruncateTable,
    exp.Alter,
    exp.Insert,
    exp.Update
)

def _validate_and_sanitize_sql(sql_statement: str, row_limit: int) -> str:
    try:
        parsed = sqlglot.parse_one(sql_statement)
    except Exception as e:
        raise ValueError(f"Failed to parse SQL statement: {e}")

    # Check for destructive operations
    for node in parsed.find_all(DESTRUCTIVE_OPERATIONS):
        raise ValueError("Destructive DDL/DML operations are not allowed.")

    # Check for partition filter on meter_reads_raw
    has_meter_reads_raw = False
    has_partition_filter = False
    
    for table in parsed.find_all(exp.Table):
        if table.name.lower() == "meter_reads_raw":
            has_meter_reads_raw = True
            break
            
    if has_meter_reads_raw:
        # Simple heuristic to check if a WHERE clause exists
        where_clause = parsed.find(exp.Where)
        if where_clause:
            # Check if reading_time (partition key) is in WHERE clause
            for column in where_clause.find_all(exp.Column):
                if column.name.lower() == "reading_time":
                    has_partition_filter = True
                    break
        
        if not has_partition_filter:
            raise ValueError("Query on meter_reads_raw must include a partition filter on 'reading_time'.")

    # Enforce LIMIT
    limit_clause = parsed.find(exp.Limit)
    if not limit_clause:
        parsed = parsed.limit(row_limit)
    else:
        # If there is a limit, we might want to cap it
        try:
            current_limit = int(limit_clause.expression.name)
            if current_limit > row_limit:
                limit_clause.set("expression", exp.Literal.number(row_limit))
        except:
            pass

    return parsed.sql(dialect="databricks")


def register_federated_query_tool(mcp: FastMCP):
    
    @mcp.tool()
    async def run_federated_analytics_query(
        sql_statement: str, 
        target_engine: Literal['databricks', 'snowflake', 'trino'], 
        row_limit: int = 50
    ) -> str:
        """
        Execute a federated analytics query safely against the target engine.
        """
        try:
            safe_sql = _validate_and_sanitize_sql(sql_statement, row_limit)
        except ValueError as e:
            return json.dumps({
                "status": "VALIDATION_ERROR",
                "error": str(e)
            })

        logger.info(f"Executing SQL on {target_engine}: {safe_sql}")
        
        if target_engine == 'databricks':
            client = databricks_client
        else:
            client = trino_snowflake_client
            
        result = await client.execute_query(safe_sql, row_limit=row_limit)
        
        if result["status"] == "SUCCEEDED":
            return json.dumps({
                "status": "SUCCEEDED",
                "statement_id": result["statement_id"],
                "rows_returned": result["rows_returned"],
                "preview_data": result["data"]
            }, indent=2)
        else:
            return json.dumps(result, indent=2)
