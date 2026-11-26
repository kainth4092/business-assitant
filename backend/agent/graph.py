"""
LangGraph Workflow Graph Definition for Fixdesk
-----------------------------------------------------------
Assembles the complete state machine:
Router -> Agent (Tools) -> Answer -> Check (Groundedness)
with a retry loop capped at 2 retries and a MemorySaver checkpointer for chat memory.
"""

import logging
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from backend.agent.state import AgentState
from backend.agent.nodes import (
    router_node, agent_node, answer_node, check_node, route_next_step
)

logger = logging.getLogger("AgentGraph")

def build_agent_graph():
    """
    Constructs and compiles the LangGraph StateGraph.
    """
    workflow = StateGraph(AgentState)
    
    # Register nodes
    workflow.add_node("router", router_node)
    workflow.add_node("agent", agent_node)
    workflow.add_node("answer", answer_node)
    workflow.add_node("check", check_node)
    
    # Establish direct linear edges
    workflow.add_edge(START, "router")
    workflow.add_edge("router", "agent")
    workflow.add_edge("agent", "answer")
    workflow.add_edge("answer", "check")
    
    # Conditional edge from check node (retry loop or exit)
    workflow.add_conditional_edges(
        "check",
        route_next_step,
        {
            "end": END,
            "agent": "agent"
        }
    )
    
    # Attach memory checkpointer for multi-turn conversational context
    checkpointer = MemorySaver()
    compiled_app = workflow.compile(checkpointer=checkpointer)
    
    logger.info("LangGraph workflow compiled successfully with MemorySaver checkpointer.")
    return compiled_app

# Singleton instance of compiled agent graph
agent_graph = build_agent_graph()
