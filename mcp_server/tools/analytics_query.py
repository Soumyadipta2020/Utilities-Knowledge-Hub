import json
import sqlglot
from sqlglot import exp
from fastmcp import FastMCP
from mcp_server.engine.duckdb_engine import duckdb_engine
import logging

logger = logging.getLogger(__name__)

# List of destructive operations
DESTRUCTIVE_OPERATIONS = (
    exp.Drop,
    exp.Delete,
    exp.TruncateTable,
    exp.Alter,
    exp.Insert,
    exp.Update,
    exp.Create
)

def _validate_and_sanitize_sql(sql_statement: str, row_limit: int = 100) -> str:
    try:
        # Strip trailing semicolons or whitespace that might trip up simple parsers
        clean_sql = sql_statement.strip().rstrip(';')
        parsed = sqlglot.parse_one(clean_sql)
    except Exception as e:
        raise ValueError(f"Failed to parse SQL statement: {e}")

    # Check for destructive operations
    for node in parsed.find_all(DESTRUCTIVE_OPERATIONS):
        raise ValueError("Destructive DDL/DML operations are not allowed.")

    # Enforce LIMIT
    limit_clause = parsed.find(exp.Limit)
    if not limit_clause:
        parsed = parsed.limit(row_limit)
    else:
        # Cap existing limit
        try:
            current_limit = int(limit_clause.expression.name)
            if current_limit > row_limit:
                limit_clause.set("expression", exp.Literal.number(row_limit))
        except:
            pass

    return parsed.sql(dialect="duckdb")

def _format_markdown_table(columns: list, data: list) -> str:
    if not columns:
        return ""
    
    header_row = "| " + " | ".join(str(c) for c in columns) + " |"
    sep_row = "| " + " | ".join(["---"] * len(columns)) + " |"
    
    rows = []
    for row in data:
        formatted_row = "| " + " | ".join([str(val) if val is not None else "NULL" for val in row]) + " |"
        rows.append(formatted_row)
        
    return "\n".join([header_row, sep_row] + rows)

def register_analytics_query_tool(mcp: FastMCP):
    
    @mcp.tool()
    def run_analytics_query(sql_statement: str) -> str:
        """
        Execute a read-only analytics query safely against the local DuckDB engine.
        CSVs in the data/ directory are automatically exposed as views (e.g. boiler_master).
        """
        try:
            safe_sql = _validate_and_sanitize_sql(sql_statement, row_limit=100)
        except ValueError as e:
            return json.dumps({
                "status": "VALIDATION_ERROR",
                "error": str(e)
            })

        logger.info(f"Executing SQL: {safe_sql}")
        
        try:
            result = duckdb_engine.execute_query(safe_sql)
            markdown_table = _format_markdown_table(result["columns"], result["data"])
            
            return json.dumps({
                "status": "SUCCEEDED",
                "rows_returned": len(result["data"]),
                "preview_data": markdown_table
            }, indent=2)
        except Exception as e:
            return json.dumps({
                "status": "EXECUTION_ERROR",
                "error": str(e)
            }, indent=2)
