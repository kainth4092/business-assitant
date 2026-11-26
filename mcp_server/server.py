"""
MCP Server Entrypoint for Fixdesk
--------------------------------------------
Implements an MCP server exposing 3 enterprise tools:
- query_sales: Read-only SELECT queries on the PostgreSQL dataset (`sales` table) with strict safety validation.
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
from mcp_server.code_tools import (
    search_code as _search_code,
    get_file_outline as _get_file_outline,
    find_symbol as _find_symbol,
    list_projects as _list_projects,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MCPServer")

# Initialize MCP Server instance
app = MCPServer("fixdesk-mcp")

@app.tool()
def tool_query_sales(sql_query: str) -> str:
    """
    Executes a read-only SQL SELECT query on the PostgreSQL sales table.
    Enforces single statement, blocks comments/mutations, and caps results to 100 rows.
    
    Args:
        sql_query: Valid SQL query starting with SELECT (e.g. 'SELECT category, SUM(amount) FROM sales GROUP BY category')
    """
    result = query_sales(sql_query)
    return json.dumps(result, indent=2)

@app.tool()
def tool_search_docs(query: str, top_k: int = 3) -> str:
    """
    Performs semantic vector search over uploaded company documents using pgvector embeddings.
    
    Args:
        query: Natural language query against your indexed documentation
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


@app.tool()
def list_projects() -> str:
    """
    List all projects configured in projects.yaml along with their indexing status,
    last commit SHA, file count, chunk count, and skipped-file count (read-only).
    """
    return _list_projects()


@app.tool()
def search_code(project: str, query: str, top_k: int = 6) -> str:
    """
    Hybrid vector and keyword/symbol search across an indexed project's codebase (read-only).
    Never accesses paths outside the project root or on the sensitive-file skip list.
    """
    return _search_code(project=project, query=query, top_k=top_k)


@app.tool()
def get_file_outline(project: str, file_path: str) -> str:
    """
    Return imports, functions, classes, and line bounds for a safe file inside the project (read-only).
    Blocks path traversal and sensitive/skipped files.
    """
    return _get_file_outline(project=project, file_path=file_path)


@app.tool()
def find_symbol(project: str, symbol_name: str, limit: int = 15) -> str:
    """
    Find symbol definitions (functions, classes, methods, SQL tables, headings) in an indexed project (read-only).
    """
    return _find_symbol(project=project, symbol_name=symbol_name, limit=limit)


if __name__ == "__main__":
    logger.info("Starting Fixdesk MCP Server on stdio...")
    app.run()
