import sys
from pathlib import Path
import json
import asyncio

# Ensure the root of the project is in the Python path
repo_root = Path(__file__).resolve().parents[1]
sys.path.append(str(repo_root))

from mcp_server.server import mcp, initialize
from mcp_server.engine.duckdb_engine import duckdb_engine
from mcp_server.tools.analytics_query import _validate_and_sanitize_sql

async def verify():
    print("=== 1. Initializing DuckDB Engine (Loading CSVs) ===")
    initialize()
    
    # Check if a view exists (e.g., boiler_master if that CSV existed)
    result = duckdb_engine.execute_query("SELECT count(*) as cnt FROM boiler_master")
    print(f"boiler_master rows: {result['data'][0][0]}")

    print("\n=== 2. Testing Safe Query Execution ===")
    
    # We invoke the tool directly for testing
    try:
        response = await mcp.call_tool("run_analytics_query", {"sql_statement": "SELECT * FROM boiler_master LIMIT 5"})
        # response is likely a list of TextContent or similar, depending on FastMCP version.
        # But for FastMCP simplified local calls, it returns the string output usually.
        print("Successful query response (truncated):")
        print(str(response)[:500] + "...\n")
    except Exception as e:
        print(f"Error calling tool: {e}")
    
    print("\n=== 3. Testing Unsafe Query Rejection ===")
    try:
        _validate_and_sanitize_sql("DROP TABLE boiler_master")
        print("FAIL: DROP TABLE was allowed!")
    except ValueError as e:
        print(f"PASS: Caught destructive query -> {e}")

    print("\n=== 4. Testing Document Fetching ===")
    try:
        doc_content = await mcp.read_resource("docs://knowledge_base/smart_meter_dcc")
        print(f"Fetched document (first 100 chars): {str(doc_content)[:100]}")
        
        # Test path traversal
        traversal_content = await mcp.read_resource("docs://knowledge_base/../../config/settings.py")
        print(f"Path traversal response: {str(traversal_content)}")
    except Exception as e:
        print(f"Resource read error (or expected traversal block): {e}")

    print("\n=== 5. FastMCP Schema Inspection ===")
    tools = mcp.list_tools()
    print("Tools registered:", [t.name for t in tools])
    resources = mcp.list_resources()
    print("Resources registered:", [r.uri for r in resources])

if __name__ == "__main__":
    asyncio.run(verify())
