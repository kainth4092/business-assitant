"""
MCP Server Entrypoint for Business Assistant
--------------------------------------------
Implements an MCP server exposing 3 enterprise tools:
- query_sales: Read-only SELECT queries on BigMart sales dataset with strict safety validation.
- search_docs: Semantic search over company policies and guidelines using pgvector embeddings.
- get_data_quality_report: Inspection of the PySpark data cleaning audit metrics.

Can be run standalone via stdio or imported by client applications.
"""

import os
import sys
import json
import logging

# Ensure project root is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.mcpserver import MCPServer
from mcp_server.tools import query_sales, search_docs, get_data_quality_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MCPServer")

# Initialize MCP Server instance
app = MCPServer("business-assistant-mcp")

@app.tool()
def tool_query_sales(sql_query: str) -> str:
    """
    Executes a read-only SQL SELECT query on the PostgreSQL sales table.
    Enforces single statement, blocks comments/mutations, and caps results to 100 rows.
    
    Args:
        sql_query: Valid SQL query starting with SELECT (e.g. 'SELECT item_type, SUM(item_outlet_sales) FROM sales GROUP BY item_type')
    """
    result = query_sales(sql_query)
    return json.dumps(result, indent=2)

@app.tool()
def tool_search_docs(query: str, top_k: int = 3) -> str:
    """
    Performs semantic vector search over company documents (return policy, FAQ, promotions, guidelines, pricing).
    
    Args:
        query: Natural language query (e.g. 'What is the return window for perishables?')
        top_k: Number of relevant snippets to return (default: 3)
    """
    result = search_docs(query, top_k)
    return json.dumps(result, indent=2)

@app.tool()
def tool_get_data_quality_report() -> str:
    """
    Retrieves the PySpark data quality audit report showing before/after row counts,
    null imputations, label standardizations, and sales summaries.
    """
    result = get_data_quality_report()
    return json.dumps(result, indent=2)

if __name__ == "__main__":
    logger.info("Starting Business Assistant MCP Server on stdio...")
    app.run()
