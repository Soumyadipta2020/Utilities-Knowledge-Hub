# Enterprise Utilities MCP Server

This directory contains the Enterprise Data Platform Model Context Protocol (MCP) Server for the Utilities Knowledge Hub.

## Architecture

The architecture eliminates synchronous big-data transfer bottlenecks by shifting from local file reading to **Federated Compute Pushdown** and **Local In-Memory Semantic Caching**.

*   **Zero Raw Data Transfer (Pushdown Only):** The MCP server never loads large datasets into host memory. All queries are pushed to Databricks/Snowflake/Trino.
*   **High-Speed Metadata Layer (DuckDB):** Table DDLs, statistics, partitions, and metrics are cached locally in DuckDB for `<15ms` resolution by LLMs.
*   **Guardrails & Token Budgeting:** Strict SQL validation (blocking DDL/DML, enforcing limits and partition filters) and Markdown-formatted tabular responses ensure context window stability and system safety.

## Configuration

Required Environment Variables:

*   `DATABRICKS_HOST`: The Databricks workspace URL (e.g., `dbc-1234.cloud.databricks.com`).
*   `DATABRICKS_TOKEN`: Databricks Personal Access Token.
*   `WAREHOUSE_ID`: The Databricks SQL Warehouse ID.
*   *(Optional)* `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`

These should be defined in a `.env` file at the root of the project.

## Running the Server

### Installation
```bash
pip install -e .[dev]
```

### Running FastMCP
```bash
python -m mcp_server.server
```

## Client Configuration JSONs

### Claude Desktop
Add the following to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "utilities-knowledge-hub": {
      "command": "python",
      "args": [
        "-m",
        "mcp_server.server"
      ],
      "env": {
        "DATABRICKS_HOST": "<YOUR_HOST>",
        "DATABRICKS_TOKEN": "<YOUR_TOKEN>",
        "WAREHOUSE_ID": "<YOUR_WAREHOUSE_ID>"
      }
    }
  }
}
```

## Testing

Run unit tests via `pytest`:
```bash
pytest tests/
```
