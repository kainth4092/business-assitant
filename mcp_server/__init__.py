"""
Model Context Protocol (MCP) Server for Fixdesk
Exposes query_sales, search_docs, and get_data_quality_report.
"""

from mcp_server.tools import query_sales, search_docs, get_data_quality_report

__all__ = ["query_sales", "search_docs", "get_data_quality_report"]
