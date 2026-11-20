"""
State definition for autonomous Support Desk agent in LangGraph.
"""

from typing import Dict, Any, List, Optional, TypedDict

class SupportState(TypedDict, total=False):
    ticket_id: str
    client_name: str
    client_email: str
    channel: str
    message: str
    
    # Classification
    classification: str  # 'data_issue' | 'code_bug' | 'question' | 'feature_request'
    confidence: float
    
    # Investigation & Fix
    investigation: Dict[str, Any]
    proposed_fix: Dict[str, Any]
    sandbox_diff: Dict[str, Any]
    test_results: Dict[str, Any]
    retry_count: int
    
    # Human-in-the-Loop Approval
    approval_status: str  # 'pending' | 'approved' | 'rejected'
    approval_token: Optional[str]
    applied_result: Optional[Dict[str, Any]]
    
    # Final Client Communication & Audit
    reply_message: str
    trace: List[Dict[str, Any]]
    status: str  # 'new' | 'investigating' | 'fix_ready' | 'approved' | 'done' | 'rejected'
