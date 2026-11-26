"""
Unit & Security Tests for SQL Sanitization and Read-Only Enforcement
"""

import os
import pytest
from mcp_server.tools import validate_and_sanitize_sql, query_sales

def test_valid_select_query():
    query = "SELECT item_identifier, item_mrp FROM sales WHERE item_type = 'Dairy' LIMIT 10"
    sanitized = validate_and_sanitize_sql(query)
    assert "SELECT" in sanitized
    assert "LIMIT 10" in sanitized

def test_auto_append_limit():
    query = "SELECT item_type, avg(item_outlet_sales) FROM sales GROUP BY item_type"
    sanitized = validate_and_sanitize_sql(query)
    assert sanitized.endswith("LIMIT 100")

def test_clamp_excessive_limit():
    query = "SELECT * FROM sales LIMIT 500"
    sanitized = validate_and_sanitize_sql(query)
    assert "LIMIT 100" in sanitized
    assert "LIMIT 500" not in sanitized

def test_reject_drop_table():
    with pytest.raises(ValueError, match="Query must begin with SELECT"):
        validate_and_sanitize_sql("DROP TABLE sales")

def test_reject_update():
    with pytest.raises(ValueError, match="Query must begin with SELECT"):
        validate_and_sanitize_sql("UPDATE sales SET item_mrp = 0")

def test_reject_delete():
    with pytest.raises(ValueError, match="Query must begin with SELECT"):
        validate_and_sanitize_sql("DELETE FROM sales")

def test_reject_insert():
    with pytest.raises(ValueError, match="Query must begin with SELECT"):
        validate_and_sanitize_sql("INSERT INTO sales (item_identifier) VALUES ('TEST')")

def test_reject_multiple_statements_semicolon():
    with pytest.raises(ValueError, match="Multiple statements"):
        validate_and_sanitize_sql("SELECT * FROM sales; DROP TABLE sales;")

def test_reject_sql_comments_dash():
    with pytest.raises(ValueError, match="Comments"):
        validate_and_sanitize_sql("SELECT * FROM sales -- bypass check")

def test_reject_sql_comments_block():
    with pytest.raises(ValueError, match="Comments"):
        validate_and_sanitize_sql("SELECT * FROM sales /* comment */")

def test_reject_embedded_mutation_keywords():
    with pytest.raises(ValueError, match="Mutation/DDL keyword"):
        validate_and_sanitize_sql("SELECT * FROM sales WHERE item_type = 'Dairy' AND (SELECT count(*) FROM (TRUNCATE sales)) > 0")

def test_live_query_sales_execution():
    import psycopg2
    test_db = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres_password@localhost:5434/fixdesk_test")
    conn = psycopg2.connect(test_db)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO sales (item_identifier, item_type, item_outlet_sales, item_fat_content, outlet_identifier, outlet_establishment_year, outlet_location_type, outlet_type, item_mrp)
        VALUES ('test_item_1', 'Dairy', 100.0, 'Regular', 'OUT001', 2020, 'Tier 1', 'Supermarket', 50.0);
    """)
    conn.commit()
    cur.close()
    conn.close()

    res = query_sales("SELECT item_type, count(*) as count FROM sales GROUP BY item_type LIMIT 2")
    assert res["status"] == "SUCCESS"
    assert res["row_count"] <= 2
    assert len(res["data"]) > 0

def test_live_query_sales_mutation_rejection():
    res = query_sales("DROP TABLE sales")
    assert res["status"] == "ERROR"
    assert "Security violation" in res["error"]
