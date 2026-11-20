"""
MCP Tools Implementation for Business Assistant
------------------------------------------------
Provides secure, audited tools exposed via the Model Context Protocol (MCP):
1. query_sales: Read-only SQL query engine against PostgreSQL with strict sanitization.
2. search_docs: Semantic similarity vector retrieval against pgvector store.
3. get_data_quality_report: Inspection tool for PySpark ETL audit metrics.
"""

import os
import re
import json
import logging
from typing import Dict, Any, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("MCPTools")

# Dangerous SQL operations and DDL keywords strictly blocked
PROHIBITED_SQL_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
    "CREATE", "REPLACE", "EXEC", "EXECUTE", "GRANT", "REVOKE",
    "CALL", "MERGE", "INTO", "LOCK", "VACUUM", "REINDEX",
    "COPY", "ALTERUSER", "CREATEDB", "CREATEROLE"
}

def validate_and_sanitize_sql(sql_query: str) -> str:
    """
    Validates that the SQL query is strictly a single, read-only SELECT statement.
    Enforces LIMIT <= 100, strips comments, and prevents query chaining.
    
    Raises ValueError with descriptive message if validation fails.
    """
    if not sql_query or not sql_query.strip():
        raise ValueError("Invalid query: SQL query cannot be empty.")
        
    cleaned = sql_query.strip()
    
    # 1. Block SQL comments (-- and /* */)
    if "--" in cleaned or "/*" in cleaned or "*/" in cleaned:
        raise ValueError("Security violation: Comments ('--', '/*') are prohibited in queries.")
        
    # 2. Block multiple statements (semicolon chaining)
    if cleaned.endswith(";"):
        cleaned = cleaned[:-1].strip()
    if ";" in cleaned:
        raise ValueError("Security violation: Multiple statements or semicolon chaining are prohibited.")
        
    # 3. Must begin with SELECT or WITH (for CTE queries that execute SELECT)
    tokens = re.findall(r"\b[A-Za-z0-9_]+\b", cleaned)
    if not tokens:
        raise ValueError("Invalid query: No tokens parsed.")
        
    first_token = tokens[0].upper()
    if first_token not in ("SELECT", "WITH"):
        raise ValueError(f"Security violation: Query must begin with SELECT. Found '{first_token}'.")
        
    # 4. Check for prohibited mutation/DDL keywords
    upper_tokens = {t.upper() for t in tokens}
    intersection = upper_tokens.intersection(PROHIBITED_SQL_KEYWORDS)
    if intersection:
        forbidden = ", ".join(sorted(intersection))
        raise ValueError(f"Security violation: Mutation/DDL keyword(s) not allowed: {forbidden}")
        
    # 5. Enforce LIMIT <= 100
    limit_match = re.search(r"\bLIMIT\s+(\d+)\b", cleaned, re.IGNORECASE)
    if limit_match:
        val = int(limit_match.group(1))
        if val > 100:
            cleaned = re.sub(r"\bLIMIT\s+\d+\b", "LIMIT 100", cleaned, flags=re.IGNORECASE)
    else:
        cleaned = f"{cleaned} LIMIT 100"
        
    return cleaned

def query_sales(sql_query: str) -> Dict[str, Any]:
    """
    Executes a read-only SQL query against the PostgreSQL 'sales' table using
    the dedicated 'sales_readonly' role.
    
    Args:
        sql_query: A single SELECT statement.
        
    Returns:
        Dict with keys:
            - status: "SUCCESS" or "ERROR"
            - query_executed: The sanitized query
            - row_count: Number of rows returned
            - data: List of dicts representing row records
            - error: Error description if failed
    """
    try:
        sanitized_sql = validate_and_sanitize_sql(sql_query)
    except ValueError as ve:
        return {
            "status": "ERROR",
            "error": str(ve),
            "data": [],
            "row_count": 0
        }
        
    # Connect using the read-only role
    readonly_url = os.environ.get(
        "READONLY_DATABASE_URL",
        "postgresql://sales_readonly:readonly_password@localhost:5434/business_assistant"
    )
    
    conn = None
    try:
        conn = psycopg2.connect(readonly_url)
        # Ensure session is read-only at the PostgreSQL session level
        conn.set_session(readonly=True, autocommit=True)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute(sanitized_sql)
        rows = cursor.fetchall()
        
        # Format decimal / numeric types to standard float for JSON serialization
        results = []
        for r in rows:
            clean_row = {}
            for k, v in r.items():
                if hasattr(v, "is_finite") or type(v).__name__ == "Decimal":
                    clean_row[k] = float(v)
                else:
                    clean_row[k] = v
            results.append(clean_row)
            
        cursor.close()
        return {
            "status": "SUCCESS",
            "query_executed": sanitized_sql,
            "row_count": len(results),
            "data": results
        }
    except Exception as e:
        logger.error(f"Error executing sales query: {e}")
        return {
            "status": "ERROR",
            "error": f"Database error: {str(e)}",
            "query_attempted": sanitized_sql,
            "data": [],
            "row_count": 0
        }
    finally:
        if conn:
            conn.close()

def search_docs(query: str, top_k: int = 3) -> Dict[str, Any]:
    """
    Searches indexed company policy documents using pgvector semantic cosine similarity.
    
    Args:
        query: Natural language query (e.g. "What is the return window for dairy?")
        top_k: Number of relevant chunks to retrieve (default: 3, max: 10)
        
    Returns:
        Dict with keys:
            - status: "SUCCESS" or "ERROR"
            - query: Original query
            - matches_count: Number of chunks retrieved
            - results: List of chunks with source_file, title, content, similarity
    """
    try:
        from backend.rag.retrieval import search_documents
        safe_k = max(1, min(int(top_k), 10))
        results = search_documents(query=query, top_k=safe_k)
        return {
            "status": "SUCCESS",
            "query": query,
            "matches_count": len(results),
            "results": results
        }
    except Exception as e:
        logger.error(f"Error searching documents: {e}")
        return {
            "status": "ERROR",
            "error": str(e),
            "query": query,
            "matches_count": 0,
            "results": []
        }

def get_data_quality_report() -> Dict[str, Any]:
    """
    Retrieves the PySpark data quality audit report generated during the ETL pipeline.
    Queries the persistent PostgreSQL 'quality_reports' table, with fallback to local JSON.
    """
    # 1. Attempt retrieval from PostgreSQL quality_reports table
    readonly_url = os.environ.get(
        "READONLY_DATABASE_URL",
        "postgresql://sales_readonly:readonly_password@localhost:5434/business_assistant"
    )
    conn = None
    try:
        conn = psycopg2.connect(readonly_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT report_id, raw_rows, cleaned_rows, duplicates_removed, report_data, created_at
            FROM quality_reports
            ORDER BY created_at DESC
            LIMIT 1;
        """)
        row = cur.fetchone()
        cur.close()
        if row and row.get("report_data"):
            report = row["report_data"]
            if isinstance(report, str):
                report = json.loads(report)
            return {
                "status": "SUCCESS",
                "report": report,
                "report_id": row["report_id"],
                "created_at": row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else str(row["created_at"])
            }
    except Exception as db_err:
        logger.warning(f"Could not read quality report from PostgreSQL: {db_err}")
    finally:
        if conn:
            conn.close()

    # 2. Fallback to filesystem JSON report
    report_file = os.environ.get("DATA_QUALITY_REPORT", "data/data_quality_report.json")
    if not os.path.exists(report_file):
        return {
            "status": "ERROR",
            "error": f"Data quality report not found in PostgreSQL or filesystem ({report_file}). Run PySpark pipeline first."
        }
        
    try:
        with open(report_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "status": "SUCCESS",
            "report": data
        }
    except Exception as e:
        logger.error(f"Error reading data quality report: {e}")
        return {
            "status": "ERROR",
            "error": str(e)
        }
