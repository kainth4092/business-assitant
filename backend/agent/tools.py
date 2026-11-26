"""
LangChain Tool Bindings for Fixdesk
----------------------------------------------
Binds the MCP server tools into standard LangChain BaseTool objects
with clear schemas for Gemini LLM function calling.
"""

import json
from typing import Dict, Any, Optional
from langchain_core.tools import tool

from mcp_server.tools import query_sales, search_docs, get_data_quality_report, get_schema_metadata

def build_sales_tool_docstring() -> str:
    meta = get_schema_metadata()
    cols = meta.get("columns", [])
    col_str = "\n".join([f"    - {c['name']} ({c['type']})" for c in cols]) if cols else "    - Table schema introspected dynamically."
    return f"""Executes a read-only SQL SELECT query against the PostgreSQL 'sales' table.
Discovered Table Schema:
{col_str}

Safety: ONLY SELECT queries are permitted. Semicolons, comments, and mutations are blocked.
"""

@tool
def query_sales_tool(sql_query: str) -> str:
    """
    Executes a read-only SQL SELECT query against the PostgreSQL 'sales' table.
    The table contains cleaned records with dynamically discovered schema.
    Safety: ONLY SELECT queries are permitted. Semicolons, comments, and mutations are blocked.
    """
    result = query_sales(sql_query)
    return json.dumps(result)

@tool
def search_docs_tool(query: str, top_k: int = 3) -> str:
    """
    Searches internal company policy and operational documents via semantic vector search in pgvector.
    Returns the most relevant chunks with similarity scores and document citations.
    """
    result = search_docs(query, top_k=top_k)
    return json.dumps(result)

@tool
def get_data_quality_report_tool() -> str:
    """
    Retrieves the PySpark data quality report showing record profiles, null imputations,
    column profiles, and summary metrics for the uploaded dataset.
    """
    result = get_data_quality_report()
    return json.dumps(result)

ALL_TOOLS = [query_sales_tool, search_docs_tool, get_data_quality_report_tool]
