import pytest
from mcp_server.engine.metric_engine import MetricEngine
from mcp_server.engine.duckdb_engine import duckdb_engine

def test_metric_engine_initialization():
    engine = MetricEngine()
    catalog = engine.get_catalog()
    assert "total_visits" in catalog
    assert "total_repairs" in catalog
    assert "total_appointments" in catalog

def test_generate_metric_sql_basic():
    engine = MetricEngine()
    sql = engine.generate_metric_sql("total_visits")
    assert "COUNT(JOB_ID) AS TOTAL_VISITS" in sql.upper()
    assert "FROM VISIT_OUTCOME" in sql.upper()

def test_generate_metric_sql_with_dimensions():
    engine = MetricEngine()
    sql = engine.generate_metric_sql("total_visits", dimensions=["visit_status"])
    assert "visit_status" in sql.lower()
    assert "GROUP BY" in sql.upper()

def test_generate_metric_sql_with_time_grain():
    engine = MetricEngine()
    sql = engine.generate_metric_sql("total_visits", time_grain="month")
    assert "DATE_TRUNC" in sql.upper()
    assert "month" in sql.lower()
    assert "GROUP BY" in sql.upper()
    assert "ORDER BY" in sql.upper()
    assert "DESC" in sql.upper()

def test_generate_metric_sql_with_filters():
    engine = MetricEngine()
    sql = engine.generate_metric_sql("total_visits", filters={"visit_status": "Completed"})
    assert "visit_status = 'Completed'" in sql
    assert "WHERE" in sql.upper()

def test_metric_engine_query_execution():
    # Verify that duckdb execution succeeds against real CSV data
    engine = MetricEngine()
    sql = engine.generate_metric_sql("total_visits", time_grain="month")
    
    result = duckdb_engine.execute_query(sql)
    assert "columns" in result
    assert "data" in result
    assert "time_period" in result["columns"]
    assert "total_visits" in result["columns"]
    
    # We should have rows assuming the dataset isn't empty
    if len(result["data"]) > 0:
        assert len(result["data"][0]) == 2
