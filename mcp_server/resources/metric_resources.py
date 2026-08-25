import json
from fastmcp import FastMCP
from mcp_server.engine.metric_engine import metric_engine
import logging

logger = logging.getLogger(__name__)

def register_metric_resources(mcp: FastMCP):
    @mcp.resource("metrics://catalog")
    def get_metrics_catalog() -> str:
        """Get the catalog of available business metrics."""
        catalog = metric_engine.get_catalog()
        return json.dumps(catalog, indent=2)
