import asyncio
import httpx
from typing import Dict, Any, List
from mcp_server.clients.base_client import BaseClient
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

class DatabricksClient(BaseClient):
    def __init__(self):
        self.host = settings.databricks_host
        self.token = settings.databricks_token
        self.warehouse_id = settings.warehouse_id
        
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        self.api_url = f"https://{self.host}/api/2.0/sql/statements"
        self.poll_interval = 2  # seconds

    def _format_markdown_table(self, columns: List[Dict], data: List[List[Any]]) -> str:
        if not columns:
            return ""
        
        headers = [col.get("name", f"col_{i}") for i, col in enumerate(columns)]
        header_row = "| " + " | ".join(headers) + " |"
        sep_row = "| " + " | ".join(["---"] * len(headers)) + " |"
        
        rows = []
        for row in data:
            formatted_row = "| " + " | ".join([str(val) if val is not None else "NULL" for val in row]) + " |"
            rows.append(formatted_row)
            
        return "\n".join([header_row, sep_row] + rows)

    async def execute_query(self, sql_statement: str, row_limit: int = 50) -> Dict[str, Any]:
        actual_limit = min(row_limit, 100) # Enforce max 100 rows
        
        payload = {
            "statement": sql_statement,
            "warehouse_id": self.warehouse_id,
            "wait_timeout": "5s",
            "row_limit": actual_limit
        }
        
        async with httpx.AsyncClient() as client:
            try:
                # Issue the initial request
                response = await client.post(
                    self.api_url, 
                    headers=self.headers, 
                    json=payload,
                    timeout=httpx.Timeout(10.0)
                )
                response.raise_for_status()
                data = response.json()
                
                statement_id = data.get("statement_id")
                state = data.get("status", {}).get("state")
                
                # Poll if running
                while state in ["PENDING", "RUNNING"]:
                    logger.info(f"Query {statement_id} is {state}. Polling...")
                    await asyncio.sleep(self.poll_interval)
                    poll_resp = await client.get(
                        f"{self.api_url}/{statement_id}",
                        headers=self.headers,
                        timeout=httpx.Timeout(10.0)
                    )
                    poll_resp.raise_for_status()
                    data = poll_resp.json()
                    state = data.get("status", {}).get("state")

                if state == "SUCCEEDED":
                    result = data.get("result", {})
                    columns = result.get("schema", {}).get("columns", [])
                    data_array = result.get("data_array", [])
                    
                    markdown_table = self._format_markdown_table(columns, data_array)
                    
                    return {
                        "status": "SUCCEEDED",
                        "statement_id": statement_id,
                        "rows_returned": len(data_array),
                        "data": markdown_table,
                        "raw_data": data_array[:5] # Sample for context
                    }
                else:
                    error = data.get("status", {}).get("error", {})
                    return {
                        "status": "FAILED",
                        "statement_id": statement_id,
                        "error": error.get("message", "Unknown error")
                    }
                    
            except httpx.HTTPError as e:
                logger.error(f"HTTP error communicating with Databricks: {e}")
                return {
                    "status": "ERROR",
                    "error": f"Connection error: {str(e)}",
                    "suggestion": "Check DATABRICKS_HOST and DATABRICKS_TOKEN"
                }
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                return {
                    "status": "ERROR",
                    "error": str(e)
                }

    async def explain_query(self, sql_statement: str) -> str:
        explain_sql = f"EXPLAIN {sql_statement}"
        result = await self.execute_query(explain_sql, row_limit=100)
        
        if result["status"] == "SUCCEEDED":
            return result["data"]
        else:
            return f"Failed to generate explain plan: {result.get('error')}"

databricks_client = DatabricksClient()
