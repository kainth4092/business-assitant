"""
MCP Tools Implementation for Fixdesk
------------------------------------------------
Provides secure, audited tools exposed via the Model Context Protocol (MCP):
1. query_sales: Read-only SQL query engine against active SalesStore (PostgreSQL or BigQuery).
2. search_docs: Semantic similarity vector retrieval against active VectorStore (pgvector or BigQuery Vector Search).
3. get_data_quality_report: Inspection tool for PySpark ETL audit metrics.
4. get_schema_metadata: Dynamic schema metadata for the active sales table.
"""

import logging
from typing import Dict, Any
from dotenv import load_dotenv

from backend.cloud.factories import get_sales_store
from backend.cloud.sql_guard import PROHIBITED_SQL_KEYWORDS, validate_and_sanitize_sql

load_dotenv()
logger = logging.getLogger("MCPTools")

__all__ = [
    "PROHIBITED_SQL_KEYWORDS",
    "validate_and_sanitize_sql",
    "query_sales",
    "search_docs",
    "get_data_quality_report",
    "get_schema_metadata",
]


def query_sales(sql_query: str) -> Dict[str, Any]:
    """
    Executes a validated read-only SQL query against the active SalesStore
    (PostgreSQL `sales_readonly` locally or cost-guarded BigQuery on GCP).
    """
    return get_sales_store().query_sales(sql_query)


def search_docs(query: str, top_k: int = 3) -> Dict[str, Any]:
    """
    Searches indexed company policy documents using the active VectorStore
    (pgvector locally or BigQuery Vector Search on GCP).
    """
    try:
        from backend.rag.retrieval import search_documents

        safe_k = max(1, min(int(top_k), 10))
        results = search_documents(query=query, top_k=safe_k)
        return {
            "status": "SUCCESS",
            "query": query,
            "matches_count": len(results),
            "results": results,
        }
    except Exception as e:
        logger.error(f"Error searching documents: {e}")
        return {
            "status": "ERROR",
            "error": str(e),
            "query": query,
            "matches_count": 0,
            "results": [],
        }


def get_data_quality_report() -> Dict[str, Any]:
    """Retrieves the PySpark data quality audit report from the active SalesStore."""
    return get_sales_store().get_data_quality_report()


def get_schema_metadata() -> Dict[str, Any]:
    """Returns dynamic schema metadata for the active `sales` table."""
    return get_sales_store().get_schema_metadata()
