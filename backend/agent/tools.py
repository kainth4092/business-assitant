"""
LangChain Tool Bindings for Business Assistant
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
    Searches internal company policy documents via semantic vector search in pgvector.
    Available documents cover:
    1. return_policy.md: return windows (30 days non-perishables, 7 days perishables/dairy), condition requirements, refunds, store credit.
    2. faq.md: operating hours (Supermarkets 7am-10pm, Grocery 8am-8pm), BigMart Rewards loyalty program (1 pt/$1, double points on Tuesdays), home delivery rules.
    3. promotion_policy.md: 15% discount on Low Fat items, category bundles, Tier 3 bulk discounts, coupon stacking rules.
    4. outlet_guidelines.md: Tier 1/2/3 definitions, cold chain storage (-2C to 4C for dairy/meat, -18C for frozen), FIFO stock rotation.
    5. pricing_policy.md: strict MRP adherence, competitor price match within 5 miles, freshness markdown schedule (10% at 14d, 25% at 7d, 50% at 2d), wholesale discounts.
    """
    result = search_docs(query, top_k=top_k)
    return json.dumps(result)

@tool
def get_data_quality_report_tool() -> str:
    """
    Retrieves the PySpark data quality report showing before/after row counts,
    null imputations, label cleanups, and summary metrics for the BigMart sales dataset.
    """
    result = get_data_quality_report()
    return json.dumps(result)

ALL_TOOLS = [query_sales_tool, search_docs_tool, get_data_quality_report_tool]
