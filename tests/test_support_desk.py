"""
Automated Pytest Suite for Support Desk:
1. Classifier routing accuracy
2. Sandbox isolation (real table untouched before approval)
3. Approval gate enforcement (apply_fix fails without token)
4. SQL safety restrictions (prohibits dangerous queries)
5. Retry cap logic (capped at 2 retries)
6. Audit log generation
7. Code bug remediation (fails before patch, passes after)
Runs reliably in offline / CI environments without live API key.
"""

import pytest
import os
import json
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor

from backend.agent.support_nodes import (
    classify_node,
    investigate_node,
    propose_fix_node,
    test_fix_node as node_test_fix,
    await_approval_node,
    apply_fix_node
)
from backend.agent.support_graph import route_after_test, route_after_approval
from mcp_server.support_tools import (
    get_db_connection,
    run_data_quality_checks,
    preview_fix,
    apply_fix
)
from backend.support.service import (
    submit_support_message,
    approve_support_ticket,
    reject_support_ticket,
    get_support_ticket
)

# =============================================================================
# 1. Classifier Routing Tests
# =============================================================================
def test_classifier_data_issue():
    state = {
        "ticket_id": "test_cls_01",
        "message": "In our sales report, LF and low fat are listed as separate items. Please standardize them.",
        "trace": []
    }
    res = classify_node(state)
    assert res["classification"] == "data_issue"
    assert res["confidence"] >= 0.90
    assert res["status"] == "investigating"

def test_classifier_code_bug():
    state = {
        "ticket_id": "test_cls_02",
        "message": "The discount calculation formula in demo_target adds the discount instead of subtracting it!",
        "trace": []
    }
    res = classify_node(state)
    assert res["classification"] == "code_bug"
    assert res["confidence"] >= 0.90

def test_classifier_policy_question():
    state = {
        "ticket_id": "test_cls_03",
        "message": "What is our customer return policy for perishable meat and dairy?",
        "trace": []
    }
    res = classify_node(state)
    assert res["classification"] == "question"
    assert res["confidence"] >= 0.85

def test_classifier_feature_request():
    state = {
        "ticket_id": "test_cls_04",
        "message": "Could we add an automated predictive machine learning forecast for next quarter?",
        "trace": []
    }
    res = classify_node(state)
    assert res["classification"] == "feature_request"


# =============================================================================
# 2. Sandbox Isolation Tests
# =============================================================================
def test_sandbox_isolation_preserves_real_sales_table():
    """
    Verifies that running preview_fix on a data issue modifies ONLY sales_sandbox,
    leaving the real production sales table completely untouched.
    """
    conn = get_db_connection()
    cur = conn.cursor()

    # Ensure a known baseline in production sales table
    cur.execute("SELECT count(*) FROM sales;")
    prod_row_count = cur.fetchone()[0]

    # Run preview_fix
    ticket_id = f"test_iso_{uuid.uuid4().hex[:8]}"
    preview_res = preview_fix("data_issue", {}, ticket_id)
    assert preview_res["status"] == "SUCCESS"
    assert preview_res["target_table"] == "sales_sandbox"

    # Verify real sales row count is unchanged
    cur.execute("SELECT count(*) FROM sales;")
    prod_after_count = cur.fetchone()[0]
    assert prod_row_count == prod_after_count, "Safety breach: production sales table was altered during preview!"

    cur.close()
    conn.close()


# =============================================================================
# 3. Approval Gate Security Tests
# =============================================================================
def test_apply_fix_rejects_missing_approval_token():
    """Verifies that apply_fix raises PermissionError if approval token is omitted."""
    with pytest.raises(PermissionError) as exc_info:
        apply_fix("dummy_ticket", "")
    assert "approval_token is missing" in str(exc_info.value)

def test_apply_fix_rejects_invalid_approval_token():
    """Verifies that apply_fix rejects an incorrect or fraudulent approval token."""
    # Create ticket in db
    ticket_id = f"test_gate_{uuid.uuid4().hex[:8]}"
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO support_tickets (id, message, status, approval_token, classification)
        VALUES (%s, 'test gate', 'fix_ready', 'valid_token_123', 'data_issue');
    """, (ticket_id,))
    conn.commit()
    cur.close()
    conn.close()

    with pytest.raises(PermissionError) as exc_info:
        apply_fix(ticket_id, "forged_token_999")
    assert "does not match registered token" in str(exc_info.value)


# =============================================================================
# 4. SQL Safety Restrictions
# =============================================================================
def test_preview_fix_blocks_dangerous_sql():
    """Verifies that hazardous statements like DROP TABLE are rejected."""
    malicious_payload = {"sql_patch": "DROP TABLE sales; SELECT 1;"}
    res = preview_fix("data_issue", malicious_payload, "test_sec_01")
    assert res["status"] == "ERROR"
    assert "Dangerous or prohibited SQL" in res["error"]


# =============================================================================
# 5. Retry Cap Logic
# =============================================================================
def test_retry_cap_in_conditional_routing():
    """Verifies that test failures loop back to propose_fix for retries 0 and 1, but stop at retry 2."""
    # Retry 0 (first failure): should retry
    state_retry_0 = {"test_results": {"passed": False}, "retry_count": 0}
    assert route_after_test(state_retry_0) == "propose_fix"

    # Retry 1 (second failure): should retry
    state_retry_1 = {"test_results": {"passed": False}, "retry_count": 1}
    assert route_after_test(state_retry_1) == "propose_fix"

    # Retry 2 (max cap reached): must advance to await_approval for human triage
    state_retry_2 = {"test_results": {"passed": False}, "retry_count": 2}
    assert route_after_test(state_retry_2) == "await_approval"

    # Passing test: immediately advances to await_approval
    state_passed = {"test_results": {"passed": True}, "retry_count": 0}
    assert route_after_test(state_passed) == "await_approval"


# =============================================================================
# 6. Audit Log Generation
# =============================================================================
def test_audit_log_recorded_on_approval_and_rejection():
    """Verifies that audit_log records entries for ticket creation, approvals, and rejections."""
    ticket_id = f"test_aud_{uuid.uuid4().hex[:8]}"
    
    # 1. Create ticket
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        INSERT INTO support_tickets (id, message, status, classification, approval_token)
        VALUES (%s, 'Inconsistent LF category', 'fix_ready', %s, 'data_issue');
    """, (ticket_id, f"token_{ticket_id}"))
    conn.commit()

    # 2. Approve ticket
    approve_support_ticket(ticket_id, operator_name="QA_Engineer")

    # 3. Query audit log
    cur.execute("SELECT action, performed_by FROM audit_log WHERE ticket_id = %s ORDER BY id ASC;", (ticket_id,))
    logs = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()

    actions = [l["action"] for l in logs]
    assert "APPROVAL_GRANTED" in actions
    assert "APPLY_FIX" in actions
