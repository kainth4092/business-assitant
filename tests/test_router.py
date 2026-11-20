"""
Unit Tests for Intent Routing (Data vs. Docs vs. Both)
"""

import pytest
from backend.agent.nodes import heuristic_route, router_node

def test_route_data_queries():
    assert heuristic_route("What are the top 5 item types by total sales?") == "data"
    assert heuristic_route("Which outlet has the highest revenue?") == "data"
    assert heuristic_route("Average MRP for dairy products?") == "data"
    assert heuristic_route("What is the average sales per item across all outlets?") == "data"

def test_route_docs_queries():
    assert heuristic_route("What is the company return policy for perishables?") == "docs"
    assert heuristic_route("What are the store operating hours on weekends?") == "docs"
    assert heuristic_route("How does the BigMart Rewards loyalty program work?") == "docs"
    assert heuristic_route("What are the cold chain storage guidelines?") == "docs"

def test_route_both_queries():
    assert heuristic_route("Which outlet sells the most dairy and what return policy applies?") == "both"
    assert heuristic_route("What are the sales numbers for low fat items and what promotion discount covers them?") == "both"
    assert heuristic_route("Highest revenue outlet guidelines and total sales?") == "both"

def test_router_node_state_update():
    state = {
        "user_query": "What are the top 5 item types by total outlet sales?",
        "messages": [],
        "retry_count": 0
    }
    result = router_node(state)
    assert result["route"] == "data"
    assert result["retry_count"] == 0
