import pytest
from mcp_server.tools.federated_query import _validate_and_sanitize_sql

def test_sql_sanitization_destructive():
    with pytest.raises(ValueError, match="Destructive DDL/DML operations are not allowed"):
        _validate_and_sanitize_sql("DROP TABLE my_table", 50)
        
    with pytest.raises(ValueError, match="Destructive DDL/DML operations are not allowed"):
        _validate_and_sanitize_sql("DELETE FROM my_table", 50)

def test_sql_sanitization_partition_filter():
    with pytest.raises(ValueError, match="must include a partition filter"):
        _validate_and_sanitize_sql("SELECT * FROM meter_reads_raw", 50)
        
    # Should pass
    _validate_and_sanitize_sql("SELECT * FROM meter_reads_raw WHERE reading_time = '2023-01-01'", 50)

def test_sql_sanitization_limit_injection():
    sql = _validate_and_sanitize_sql("SELECT * FROM normal_table", 10)
    assert "LIMIT 10" in sql.upper()
    
    # Check limit cap
    sql = _validate_and_sanitize_sql("SELECT * FROM normal_table LIMIT 1000", 50)
    assert "LIMIT 50" in sql.upper()
