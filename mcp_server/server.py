import logging
from fastmcp import FastMCP
from mcp_server.resources.doc_resources import register_doc_resources
from mcp_server.tools.analytics_query import register_analytics_query_tool
from mcp_server.resources.metric_resources import register_metric_resources
from mcp_server.tools.metric_query import register_metric_query_tool
from mcp_server.engine.duckdb_engine import duckdb_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastMCP Server
mcp = FastMCP(
    name="Enterprise Utilities MCP"
)

# Register Resources
register_doc_resources(mcp)
register_metric_resources(mcp)

# Register Tools
register_analytics_query_tool(mcp)
register_metric_query_tool(mcp)

def initialize():
    logger.info("Initializing Enterprise MCP Server with DuckDB CSV engine...")
    # duckdb_engine initializes on import via the singleton, but we can verify it here
    if duckdb_engine.conn is not None:
        logger.info("DuckDB engine connected.")

if __name__ == "__main__":
    initialize()
    logger.info("Starting FastMCP server loop...")
    mcp.run()
