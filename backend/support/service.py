"""
Support Desk Service Layer: Orchestrates tickets, LangGraph execution,
human approvals, and audit log generation.
"""

import os
import json
import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

from backend.agent.support_graph import support_graph
from mcp_server.support_tools import get_db_connection, apply_fix

logger = logging.getLogger("support_service")
logger.setLevel(logging.INFO)

# =============================================================================
# 1. Submit Support Message (Creates ticket & triggers graph)
# =============================================================================
def submit_support_message(
    message: str,
    client_name: str = "Client User",
    client_email: str = "client@example.com",
    channel: str = "webhook"
) -> Dict[str, Any]:
    """
    Submits a new client problem message:
    1. Inserts a new record into `support_tickets`
    2. Runs `support_graph` up to the approval gate (or through notify for questions)
    3. Records initial action in `audit_log`
    4. Returns the created ticket with current trace & diagnostics
    """
    ticket_id = f"tick_{uuid.uuid4().hex[:12]}"
    conn = None
    try:
        conn = get_db_connection(readonly=False)
        conn.autocommit = True
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Insert initial ticket
        cur.execute("""
            INSERT INTO support_tickets (id, client_name, client_email, channel, message, status)
            VALUES (%s, %s, %s, %s, %s, 'new')
            RETURNING *;
        """, (ticket_id, client_name, client_email, channel, message))
        ticket = dict(cur.fetchone())

        # Record TICKET_CREATED in audit_log
        cur.execute("""
            INSERT INTO audit_log (ticket_id, action, performed_by, details)
            VALUES (%s, 'TICKET_CREATED', %s, %s);
        """, (
            ticket_id,
            f"client:{client_email}",
            json.dumps({"channel": channel, "message": message[:100]})
        ))
        cur.close()

        # Execute LangGraph support workflow
        initial_state = {
            "ticket_id": ticket_id,
            "client_name": client_name,
            "client_email": client_email,
            "channel": channel,
            "message": message,
            "retry_count": 0,
            "trace": []
        }
        config = {"configurable": {"thread_id": ticket_id}}

        # Invokes graph: pauses before apply_fix if code/data fix, or finishes notify if question
        final_state = support_graph.invoke(initial_state, config=config)

        # Fetch updated ticket record
        return get_support_ticket(ticket_id)
    except Exception as e:
        logger.error(f"Error submitting support message: {e}", exc_info=True)
        raise
    finally:
        if conn:
            conn.close()


# =============================================================================
# 2. List Support Tickets
# =============================================================================
def list_support_tickets() -> List[Dict[str, Any]]:
    """Returns all support tickets ordered by creation time descending."""
    conn = None
    try:
        conn = get_db_connection(readonly=True)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT id, client_name, client_email, channel, message, status,
                   classification, confidence, approval_token, created_at, updated_at
            FROM support_tickets
            ORDER BY created_at DESC;
        """)
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return rows
    except Exception as e:
        logger.error(f"Error listing tickets: {e}")
        return []
    finally:
        if conn:
            conn.close()


# =============================================================================
# 3. Get Support Ticket Detail (with Audit Log)
# =============================================================================
def get_support_ticket(ticket_id: str) -> Optional[Dict[str, Any]]:
    """Fetches full ticket details, investigation, fix proposal, and audit history."""
    conn = None
    try:
        conn = get_db_connection(readonly=True)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("SELECT * FROM support_tickets WHERE id = %s;", (ticket_id,))
        ticket = cur.fetchone()
        if not ticket:
            return None

        ticket_data = dict(ticket)

        # Fetch audit trail
        cur.execute("""
            SELECT id, ticket_id, action, performed_by, timestamp, before_counts, after_counts, details
            FROM audit_log
            WHERE ticket_id = %s
            ORDER BY timestamp ASC;
        """, (ticket_id,))
        audit_trail = [dict(r) for r in cur.fetchall()]
        ticket_data["audit_trail"] = audit_trail

        cur.close()
        return ticket_data
    except Exception as e:
        logger.error(f"Error fetching ticket {ticket_id}: {e}")
        return None
    finally:
        if conn:
            conn.close()


# =============================================================================
# 4. Approve Support Ticket (Resumes LangGraph Checkpoint)
# =============================================================================
def approve_support_ticket(ticket_id: str, operator_name: str = "human_operator") -> Dict[str, Any]:
    """
    Approves a pending remediation proposal:
    1. Validates that the ticket is in 'fix_ready' status and has an approval_token
    2. Resumes the paused support_graph execution via checkpointer
    3. Runs apply_fix and notify nodes
    4. Records approval in audit_log
    """
    ticket = get_support_ticket(ticket_id)
    if not ticket:
        raise ValueError(f"Ticket '{ticket_id}' not found.")

    if ticket.get("status") not in ("fix_ready", "approved"):
        raise ValueError(f"Cannot approve ticket in status '{ticket.get('status')}'. Must be 'fix_ready'.")

    approval_token = ticket.get("approval_token")
    if not approval_token:
        raise ValueError("Ticket is missing an approval token. Cannot verify safety gate.")

    # Record APPROVAL_GRANTED in audit_log
    conn = None
    try:
        conn = get_db_connection(readonly=False)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO audit_log (ticket_id, action, performed_by, details)
            VALUES (%s, 'APPROVAL_GRANTED', %s, %s);
        """, (
            ticket_id,
            operator_name,
            json.dumps({"approval_token": approval_token, "timestamp": datetime.now().isoformat()})
        ))
        cur.close()
    finally:
        if conn:
            conn.close()

    # Resume graph execution using LangGraph checkpointer
    config = {"configurable": {"thread_id": ticket_id}}
    state_values = support_graph.get_state(config).values

    if state_values:
        support_graph.update_state(config, {"approval_status": "approved", "approval_token": approval_token})
        support_graph.invoke(None, config=config)
    else:
        # Reconstruct state from database record if process restarted
        from backend.agent.support_nodes import apply_fix_node, notify_node
        proposed_fix = ticket.get("proposed_fix") or {}
        if isinstance(proposed_fix, str):
            try:
                proposed_fix = json.loads(proposed_fix)
            except Exception:
                proposed_fix = {}

        resume_state = {
            "ticket_id": ticket_id,
            "client_name": ticket.get("client_name", "Client User"),
            "client_email": ticket.get("client_email", "client@example.com"),
            "channel": ticket.get("channel", "webhook"),
            "message": ticket.get("message", ""),
            "classification": ticket.get("classification", "data_issue"),
            "confidence": float(ticket.get("confidence") or 1.0),
            "proposed_fix": proposed_fix,
            "approval_token": approval_token,
            "approval_status": "approved",
            "retry_count": 0,
            "trace": []
        }
        res_state = apply_fix_node(resume_state)
        notify_node(res_state)

    return get_support_ticket(ticket_id)


# =============================================================================
# 5. Reject Support Ticket
# =============================================================================
def reject_support_ticket(ticket_id: str, reason: str = "", operator_name: str = "human_operator") -> Dict[str, Any]:
    """
    Rejects the proposed remediation and notifies the client channel.
    """
    ticket = get_support_ticket(ticket_id)
    if not ticket:
        raise ValueError(f"Ticket '{ticket_id}' not found.")

    rejection_note = reason.strip() or "Remediation was reviewed and rejected by an administrator."
    reply = f"Hello {ticket.get('client_name')}, our operations team reviewed the proposed remediation but concluded: {rejection_note}. A specialist will follow up directly."

    conn = None
    try:
        conn = get_db_connection(readonly=False)
        conn.autocommit = True
        cur = conn.cursor()

        cur.execute("""
            UPDATE support_tickets
            SET status = 'rejected',
                reply_message = %s,
                updated_at = NOW()
            WHERE id = %s;
        """, (reply, ticket_id))

        cur.execute("""
            INSERT INTO audit_log (ticket_id, action, performed_by, details)
            VALUES (%s, 'TICKET_REJECTED', %s, %s);
        """, (
            ticket_id,
            operator_name,
            json.dumps({"reason": rejection_note, "timestamp": datetime.now().isoformat()})
        ))
        cur.close()
    finally:
        if conn:
            conn.close()

    return get_support_ticket(ticket_id)
