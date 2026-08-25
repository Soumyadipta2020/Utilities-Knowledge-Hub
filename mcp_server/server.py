from fastmcp import FastMCP
from mcp_server.resources.catalog_resources import register_catalog_resources
from mcp_server.resources.doc_resources import register_doc_resources
from mcp_server.tools.federated_query import register_federated_query_tool
from mcp_server.tools.query_profiler import register_query_profiler_tool
from mcp_server.tools.code_generators import register_code_generators_tool
from mcp_server.prompts.energy_workflows import register_energy_prompts
from mcp_server.cache.catalog_sync import catalog_syncer
import logging
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastMCP Server
mcp = FastMCP(
    name="Enterprise Utilities MCP",
    dependencies=["duckdb", "sqlglot", "httpx", "pydantic-settings"]
)

# Register Resources
register_catalog_resources(mcp)
register_doc_resources(mcp)

# Register Tools
register_federated_query_tool(mcp)
register_query_profiler_tool(mcp)
register_code_generators_tool(mcp)

# Register Prompts
register_energy_prompts(mcp)

# Lifecycle Event (Startup)
# FastMCP doesn't have a direct @mcp.on_startup yet in this context, 
# but we can trigger the sync before running.
def initialize():
    logger.info("Initializing Enterprise MCP Server...")
    catalog_syncer.trigger_sync()

if __name__ == "__main__":
    initialize()
    logger.info("Starting FastMCP server loop...")
    mcp.run()
