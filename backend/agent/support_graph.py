"""
Compiled LangGraph Graph for Support Desk:
Classify -> Investigate -> Propose_Fix -> Test_Fix (Retry Loop <= 2) -> Await_Approval (Pause) -> Apply_Fix -> Notify -> END
Uses LangGraph MemorySaver checkpointer for Human-in-the-Loop approval pausing.
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from backend.agent.support_state import SupportState
from backend.agent.support_nodes import (
    classify_node,
    investigate_node,
    propose_fix_node,
    test_fix_node,
    await_approval_node,
    apply_fix_node,
    notify_node
)

def route_after_test(state: SupportState) -> str:
    """
    Decides whether to retry fix proposal (capped at 2 retries) or advance to approval gate.
    """
    test_res = state.get("test_results", {})
    passed = test_res.get("passed", False)
    retries = state.get("retry_count", 0)

    if passed:
        return "await_approval"
    
    if retries < 2:
        return "propose_fix"
    
    return "await_approval"

def route_after_approval(state: SupportState) -> str:
    """
    If ticket was classified as a question or is pre-approved, routes directly to notify.
    Otherwise, pauses at Human-in-the-Loop gateway before apply_fix.
    """
    classification = state.get("classification")
    if classification == "question":
        return "notify"
    return "apply_fix"

def create_support_graph(checkpointer=None):
    """
    Builds and compiles the Support Desk LangGraph workflow.
    Configures interrupt_before=['apply_fix'] to ensure code/data changes pause for approval.
    """
    workflow = StateGraph(SupportState)

    # 1. Register Nodes
    workflow.add_node("classify", classify_node)
    workflow.add_node("investigate", investigate_node)
    workflow.add_node("propose_fix", propose_fix_node)
    workflow.add_node("test_fix", test_fix_node)
    workflow.add_node("await_approval", await_approval_node)
    workflow.add_node("apply_fix", apply_fix_node)
    workflow.add_node("notify", notify_node)

    # 2. Sequential Edges
    workflow.set_entry_point("classify")
    workflow.add_edge("classify", "investigate")
    workflow.add_edge("investigate", "propose_fix")
    workflow.add_edge("propose_fix", "test_fix")

    # 3. Conditional Retry Loop Edge (Retry cap = 2)
    workflow.add_conditional_edges(
        "test_fix",
        route_after_test,
        {
            "propose_fix": "propose_fix",
            "await_approval": "await_approval"
        }
    )

    # 4. Approval Routing Edge
    workflow.add_conditional_edges(
        "await_approval",
        route_after_approval,
        {
            "notify": "notify",
            "apply_fix": "apply_fix"
        }
    )

    workflow.add_edge("apply_fix", "notify")
    workflow.add_edge("notify", END)

    # Compile with checkpointer and human-in-the-loop interruption
    memory = checkpointer or MemorySaver()
    compiled_app = workflow.compile(
        checkpointer=memory,
        interrupt_before=["apply_fix"]
    )
    return compiled_app

# Singleton instance of compiled support graph
support_memory = MemorySaver()
support_graph = create_support_graph(support_memory)
