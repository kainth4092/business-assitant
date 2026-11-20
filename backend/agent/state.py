"""
LangGraph State Definition for Business Assistant
------------------------------------------------
Maintains conversational context, agent routing decision, tool execution results,
source attributions, groundedness evaluation, and retry loop counters.
"""

from typing import List, Dict, Any, Optional, Annotated
from typing_extensions import TypedDict
import operator

class AgentState(TypedDict):
    # Core user input
    user_query: str
    
    # Conversation messages (accumulated across turns via operator.add)
    messages: Annotated[List[Dict[str, Any]], operator.add]
    
    # Routing decision: "data", "docs", or "both"
    route: str
    
    # Audit trail of tools executed in this turn
    tools_used: List[str]
    
    # Detailed tool execution records (inputs, outputs, SQL queries)
    tool_results: List[Dict[str, Any]]
    
    # Attribution sources (files, snippets, row counts)
    sources: List[Dict[str, Any]]
    
    # Current synthesized answer
    draft_answer: str
    
    # Final verified answer presented to user
    final_answer: str
    
    # Groundedness evaluation status & feedback for refinement
    is_grounded: bool
    evaluation_feedback: str
    
    # Retry loop counter (strictly capped at 2)
    retry_count: int
    
    # Execution trace summary for transparency panel
    trace: Dict[str, Any]
