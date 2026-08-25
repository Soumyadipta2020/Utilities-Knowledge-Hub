import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from mcp_server.clients.databricks_client import DatabricksClient

@pytest.mark.asyncio
@patch('httpx.AsyncClient')
async def test_databricks_client_execute(mock_client_cls):
    mock_client = AsyncMock()
    mock_client_cls.return_value.__aenter__.return_value = mock_client
    
    # Mock the response for execute_query
    mock_post_resp = MagicMock()
    mock_post_resp.json.return_value = {
        "statement_id": "test_stmt",
        "status": {"state": "SUCCEEDED"},
        "result": {
            "schema": {"columns": [{"name": "id"}]},
            "data_array": [[1], [2]]
        }
    }
    mock_client.post.return_value = mock_post_resp
    
    client = DatabricksClient()
    result = await client.execute_query("SELECT 1 AS id", row_limit=10)
    
    assert result["status"] == "SUCCEEDED"
    assert result["statement_id"] == "test_stmt"
    assert "id" in result["data"]
