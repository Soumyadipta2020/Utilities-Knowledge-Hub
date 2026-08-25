import pytest
from mcp_server.cache.duckdb_cache import duckdb_cache
from mcp_server.cache.catalog_sync import catalog_syncer

def test_cache_initialization():
    assert duckdb_cache.conn is not None

def test_catalog_sync_and_lookup():
    catalog_syncer.trigger_sync()
    
    schema = duckdb_cache.lookup_schema("meter_reads_raw")
    assert schema["table_name"] == "meter_reads_raw"
    assert len(schema["columns"]) == 3
    assert "reading_time" in schema["partition_keys"]
    
    metric = duckdb_cache.lookup_metric("avg_half_hourly_kwh")
    assert metric["metric_name"] == "avg_half_hourly_kwh"
    assert metric["grain"] == "half_hourly"
