"""
Unit Tests for LangGraph Conditional Edge and Retry Cap Termination
"""

import pytest
from backend.agent.nodes import route_next_step, check_node

def test_route_next_step_when_grounded():
    state = {
        "is_grounded": True,
        "retry_count": 0
    }
    assert route_next_step(state) == "end"

def test_route_next_step_first_retry():
    state = {
        "is_grounded": False,
        "retry_count": 0
    }
    assert route_next_step(state) == "agent"

def test_route_next_step_second_retry():
    state = {
        "is_grounded": False,
        "retry_count": 1
    }
    assert route_next_step(state) == "agent"

def test_route_next_step_cap_reached():
    # When retry_count reaches 2, must terminate to END
    state = {
        "is_grounded": False,
        "retry_count": 2
    }
    assert route_next_step(state) == "end"

def test_check_node_increments_retry_on_failure():
    # If ungrounded (empty tool results), check_node should increment retry_count
    state = {
        "user_query": "Random question",
        "draft_answer": "Short ungrounded answer",
        "tool_results": [],
        "retry_count": 0,
        "route": "data",
        "tools_used": []
    }
    res = check_node(state)
    assert res["is_grounded"] is False
    assert res["retry_count"] == 1
    assert "retries" in res["trace"]
    assert res["trace"]["retries"] == 1

def test_check_node_stops_at_cap():
    state = {
        "user_query": "Random question",
        "draft_answer": "Still failing answer",
        "tool_results": [],
        "retry_count": 1,
        "route": "data",
        "tools_used": []
    }
    res = check_node(state)
    assert res["retry_count"] == 2
    # Verify next step will exit to END
    assert route_next_step(res) == "end"
