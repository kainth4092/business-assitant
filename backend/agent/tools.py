"""
LangChain Tool Bindings for Business Assistant
----------------------------------------------
Binds the MCP server tools into standard LangChain BaseTool objects
with clear schemas for Gemini LLM function calling.
"""

import json
from typing import Dict, Any, Optional
from langchain_core.tools import tool

from mcp_server.tools import query_sales, search_docs, get_data_quality_report

@tool
def query_sales_tool(sql_query: str) -> str:
    """
    Executes a read-only SQL SELECT query against the PostgreSQL 'sales' table.
    The table contains cleaned BigMart sales data with columns:
    - item_identifier (VARCHAR): unique product code (e.g. 'FDA15')
    - item_weight (NUMERIC): product weight in kg
    - item_fat_content (VARCHAR): 'Low Fat' or 'Regular'
    - item_visibility (NUMERIC): % display area in store
    - item_type (VARCHAR): product category ('Dairy', 'Soft Drinks', 'Meat', 'Fruits and Vegetables', 'Household', etc.)
    - item_mrp (NUMERIC): maximum retail price
    - outlet_identifier (VARCHAR): outlet code ('OUT049', 'OUT018', 'OUT027', etc.)
    - outlet_establishment_year (INT): year opened
    - outlet_size (VARCHAR): 'Small', 'Medium', 'High'
    - outlet_location_type (VARCHAR): 'Tier 1', 'Tier 2', 'Tier 3'
    - outlet_type (VARCHAR): 'Supermarket Type1', 'Supermarket Type2', 'Supermarket Type3', 'Grocery Store'
    - item_outlet_sales (NUMERIC): total sales revenue for that item in that outlet

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
