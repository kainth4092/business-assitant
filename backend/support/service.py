"""
Support Desk Service Layer:
Orchestrates normalized inbound channel messages, allowlist/dedupe/rate-limit/injection safety,
LangGraph triage execution, human approvals, outbound thread notifications, and audit logging.
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
from backend.support.adapters import (
    ChannelAdapter,
    NormalizedChannelMessage,
    WebhookAdapter,
    get_channel_adapter,
)
from backend.support.security import (
    detect_untrusted_injection,
    redact_secrets,
    sanitize_channel_reply,
)
from mcp_server.support_tools import get_db_connection

logger = logging.getLogger("support_service")
logger.setLevel(logging.INFO)

LIVE_EXTERNAL_CHANNELS = {"email", "slack"}
_SCHEMA_MIGRATED = False


class ChannelPermissionError(PermissionError):
    """Raised when an inbound sender/chat/channel is not on the allowlist."""


class RateLimitExceededError(ValueError):
    """Raised when a sender exceeds the hourly ticket creation limit."""


def ensure_support_channel_columns(force: bool = False) -> None:
    """
    Idempotently ensures channel, threading, dedupe, and flagging columns/indexes
    exist on support_tickets for existing databases.
    """
    global _SCHEMA_MIGRATED
    if _SCHEMA_MIGRATED and not force:
        return

    conn = None
    try:
        conn = get_db_connection(readonly=False)
        conn.autocommit = True
        cur = conn.cursor()
        ddl_statements = [
            "ALTER TABLE support_tickets ADD COLUMN IF NOT EXISTS sender_id VARCHAR(128);",
            "ALTER TABLE support_tickets ADD COLUMN IF NOT EXISTS external_message_id VARCHAR(255);",
            "ALTER TABLE support_tickets ADD COLUMN IF NOT EXISTS thread_id VARCHAR(255);",
            "ALTER TABLE support_tickets ADD COLUMN IF NOT EXISTS thread_url TEXT;",
            "ALTER TABLE support_tickets ADD COLUMN IF NOT EXISTS channel_metadata JSONB DEFAULT '{}'::jsonb;",
            "ALTER TABLE support_tickets ADD COLUMN IF NOT EXISTS is_flagged BOOLEAN NOT NULL DEFAULT FALSE;",
            "ALTER TABLE support_tickets ADD COLUMN IF NOT EXISTS flag_reason TEXT;",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_support_tickets_channel_ext_id ON support_tickets(channel, external_message_id) WHERE external_message_id IS NOT NULL;",
            "CREATE INDEX IF NOT EXISTS idx_support_tickets_sender_rate ON support_tickets(channel, sender_id, created_at);",
        ]
        for stmt in ddl_statements:
            cur.execute(stmt)
        cur.close()
        _SCHEMA_MIGRATED = True
    except Exception as e:
        logger.warning(f"Could not verify support_tickets channel columns: {redact_secrets(str(e))}")
    finally:
        if conn:
            conn.close()


def _max_tickets_per_hour() -> int:
    try:
        val = int(os.environ.get("SUPPORT_RATE_LIMIT_PER_HOUR", "10").strip() or "10")
        return max(1, val)
    except ValueError:
        return 10


def _dispatch_channel_reply(
    ticket: Dict[str, Any],
    text: str,
    adapter: Optional[ChannelAdapter] = None,
) -> bool:
    """
    Sends a sanitized status reply on the ticket's original channel and thread.
    Only external configured channels dispatch network replies unless an explicit adapter is provided.
    """
    channel = (ticket.get("channel") or "webhook").lower()
    if adapter is None:
        if channel not in LIVE_EXTERNAL_CHANNELS:
            return False
        adapter = get_channel_adapter(channel)
        if not adapter.is_configured():
            return False

    meta = ticket.get("channel_metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}

    thread_id = ticket.get("thread_id")
    safe_text = sanitize_channel_reply(text)
    if not safe_text:
        return False

    try:
        return bool(adapter.send_reply(thread_id=thread_id, text=safe_text, metadata=meta))
    except Exception as e:
        logger.error(f"Error sending reply on {channel}: {redact_secrets(str(e))}")
        return False


def _format_post_triage_reply(ticket: Dict[str, Any]) -> str:
    """Builds a concise, secret-free, SQL-free summary reply after triage/sandbox test."""
    ticket_id = ticket.get("id")
    status_val = ticket.get("status")

    if ticket.get("is_flagged"):
        return (
            f"Ticket #{ticket_id} created and flagged for security review. "
            "No automated actions were run."
        )

    if status_val == "fix_ready":
        inv = ticket.get("investigation") or {}
        if isinstance(inv, str):
            try:
                inv = json.loads(inv)
            except Exception:
                inv = {}
        finding = inv.get("root_cause") or f"Diagnosed {ticket.get('classification', 'issue').replace('_', ' ')}."
        return (
            f"Ticket #{ticket_id}: {finding} "
            "Proposed fix passed sandbox testing and is ready, waiting for approval in the Support Desk UI."
        )

    reply = (ticket.get("reply_message") or "").strip()
    if reply:
        return f"Ticket #{ticket_id}: {reply}"

    return f"Ticket #{ticket_id} logged ({status_val})."


def _to_normalized(
    payload: NormalizedChannelMessage | Dict[str, Any],
    channel_hint: Optional[str] = None,
) -> NormalizedChannelMessage:
    if isinstance(payload, NormalizedChannelMessage):
        return payload
    ch = (channel_hint or payload.get("channel") or "webhook").lower()
    adapter = get_channel_adapter(ch) if ch in LIVE_EXTERNAL_CHANNELS | {"teams", "simulated", "webhook"} else WebhookAdapter()
    return adapter.parse_incoming(payload)


# =============================================================================
# 1. Unified Channel Ingestion (Called by /support/messages & all channel workers)
# =============================================================================
def ingest_channel_message(
    incoming: NormalizedChannelMessage | Dict[str, Any],
    enforce_allowlist: bool = False,
    adapter: Optional[ChannelAdapter] = None,
    notify_on_channel: bool = True,
) -> Dict[str, Any]:
    """
    Central entry point for ALL support messages (UI, Webhook API, Email, Slack):
    1. Normalizes payload into NormalizedChannelMessage.
    2. Checks allowlist (when enforce_allowlist=True).
    3. Deduplicates by (channel, external_message_id).
    4. Enforces per-sender hourly rate limiting.
    5. Checks untrusted message text for prompt injection / destructive directives.
    6. Inserts ticket and executes support_graph (up to approval gate or reply).
    7. Sends concise status notification back to the originating thread.
    """
    ensure_support_channel_columns()
    msg = _to_normalized(incoming)
    if not msg.text or not msg.text.strip():
        raise ValueError("Incoming message text cannot be empty.")

    resolved_adapter = adapter or get_channel_adapter(msg.channel)
    is_external = (msg.channel in LIVE_EXTERNAL_CHANNELS) or (adapter is not None)

    if enforce_allowlist and not resolved_adapter.is_sender_allowed(msg):
        raise ChannelPermissionError(f"Sender '{msg.sender_id}' is not allowlisted for channel '{msg.channel}'.")

    conn = None
    ticket_id = f"tick_{uuid.uuid4().hex[:12]}"
    try:
        conn = get_db_connection(readonly=False)
        conn.autocommit = True
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Deduplication check by (channel, external_message_id)
        if msg.external_message_id:
            cur.execute(
                "SELECT id FROM support_tickets WHERE channel = %s AND external_message_id = %s LIMIT 1;",
                (msg.channel, msg.external_message_id),
            )
            existing = cur.fetchone()
            if existing:
                cur.close()
                logger.info(f"Deduplicated {msg.channel} message '{msg.external_message_id}' -> ticket {existing['id']}")
                existing_ticket = get_support_ticket(existing["id"]) or {"id": existing["id"]}
                existing_ticket["_deduplicated"] = True
                return existing_ticket

        # Per-sender hourly rate limit check
        sender_key = (msg.sender_id or msg.sender_email or msg.sender_name or "unknown").lower()
        limit = _max_tickets_per_hour()
        cur.execute(
            """
            SELECT count(*) AS recent_count
            FROM support_tickets
            WHERE channel = %s
              AND LOWER(COALESCE(sender_id, client_email, client_name)) = %s
              AND created_at >= NOW() - INTERVAL '1 hour';
            """,
            (msg.channel, sender_key),
        )
        recent_count = int((cur.fetchone() or {}).get("recent_count", 0))
        if recent_count >= limit:
            cur.close()
            logger.warning(
                f"Rate limit exceeded for channel='{msg.channel}' sender='{sender_key}' ({recent_count}/{limit} per hour)"
            )
            raise RateLimitExceededError(
                f"Rate limit reached ({limit} tickets per hour). Please wait before sending more requests."
            )

        # Untrusted text inspection for prompt injection / destructive SQL / bypass attempts
        flag_reason = detect_untrusted_injection(msg.text)
        client_email = msg.sender_email or f"{sender_key}@{msg.channel}.local"

        if flag_reason:
            safe_reply = (
                f"Ticket #{ticket_id} created and flagged for manual security review. "
                "No automated actions were executed."
            )
            cur.execute(
                """
                INSERT INTO support_tickets (
                    id, client_name, client_email, sender_id, channel, message,
                    status, classification, confidence, reply_message,
                    external_message_id, thread_id, thread_url, channel_metadata,
                    is_flagged, flag_reason
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'flagged', 'security_flagged', 1.000, %s, %s, %s, %s, %s, TRUE, %s)
                RETURNING *;
                """,
                (
                    ticket_id,
                    msg.sender_name,
                    client_email,
                    sender_key,
                    msg.channel,
                    msg.text,
                    safe_reply,
                    msg.external_message_id,
                    msg.thread_id,
                    msg.thread_url,
                    json.dumps(msg.metadata or {}, default=str),
                    flag_reason,
                ),
            )
            flagged_ticket = dict(cur.fetchone())
            cur.execute(
                """
                INSERT INTO audit_log (ticket_id, action, performed_by, details)
                VALUES (%s, 'SECURITY_FLAGGED', %s, %s);
                """,
                (
                    ticket_id,
                    f"{msg.channel}:{sender_key}",
                    json.dumps({"reason": flag_reason, "channel": msg.channel}),
                ),
            )
            cur.close()

            if notify_on_channel and is_external:
                _dispatch_channel_reply(flagged_ticket, safe_reply, adapter=resolved_adapter)
            return get_support_ticket(ticket_id) or flagged_ticket

        # Insert clean ticket into PostgreSQL
        cur.execute(
            """
            INSERT INTO support_tickets (
                id, client_name, client_email, sender_id, channel, message, status,
                external_message_id, thread_id, thread_url, channel_metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, 'new', %s, %s, %s, %s)
            RETURNING *;
            """,
            (
                ticket_id,
                msg.sender_name,
                client_email,
                sender_key,
                msg.channel,
                msg.text,
                msg.external_message_id,
                msg.thread_id,
                msg.thread_url,
                json.dumps(msg.metadata or {}, default=str),
            ),
        )
        created_ticket = dict(cur.fetchone())

        cur.execute(
            """
            INSERT INTO audit_log (ticket_id, action, performed_by, details)
            VALUES (%s, 'TICKET_CREATED', %s, %s);
            """,
            (
                ticket_id,
                f"client:{client_email}",
                json.dumps({"channel": msg.channel, "message": msg.text[:100]}),
            ),
        )
        cur.close()

        # Notify originating channel immediately that ticket was created
        if notify_on_channel and is_external:
            _dispatch_channel_reply(
                created_ticket,
                f"Ticket #{ticket_id} created. Investigating your request now...",
                adapter=resolved_adapter,
            )

        # Execute existing LangGraph support workflow (untouched approval gate & sandbox)
        initial_state = {
            "ticket_id": ticket_id,
            "client_name": msg.sender_name,
            "client_email": client_email,
            "channel": msg.channel,
            "message": msg.text,
            "retry_count": 0,
            "trace": [],
        }
        config = {"configurable": {"thread_id": ticket_id}}
        support_graph.invoke(initial_state, config=config)

        final_ticket = get_support_ticket(ticket_id)
        if final_ticket and notify_on_channel and is_external:
            status_msg = _format_post_triage_reply(final_ticket)
            _dispatch_channel_reply(final_ticket, status_msg, adapter=resolved_adapter)

        return final_ticket or created_ticket
    except (ChannelPermissionError, RateLimitExceededError, ValueError):
        raise
    except Exception as e:
        logger.error(f"Error ingesting support message: {redact_secrets(str(e))}", exc_info=True)
        raise
    finally:
        if conn:
            conn.close()


def submit_support_message(
    message: str,
    client_name: str = "Client User",
    client_email: str = "client@example.com",
    channel: str = "webhook",
) -> Dict[str, Any]:
    """
    Backwards-compatible wrapper used by /support/messages and tests.
    Routes through the unified ingest_channel_message pipeline.
    """
    normalized = NormalizedChannelMessage(
        sender_name=client_name or "Client User",
        sender_id=(client_email or client_name or "client").lower(),
        sender_email=client_email or "client@example.com",
        channel=(channel or "webhook").lower(),
        text=message,
        timestamp=datetime.utcnow().isoformat(),
    )
    return ingest_channel_message(normalized, enforce_allowlist=False, notify_on_channel=False)


# =============================================================================
# 2. List Support Tickets
# =============================================================================
def list_support_tickets() -> List[Dict[str, Any]]:
    """Returns all support tickets ordered by creation time descending."""
    ensure_support_channel_columns()
    conn = None
    try:
        conn = get_db_connection(readonly=True)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT id, client_name, client_email, sender_id, channel, message, status,
                   classification, confidence, approval_token, thread_id, thread_url,
                   is_flagged, flag_reason, created_at, updated_at
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
    ensure_support_channel_columns()
    conn = None
    try:
        conn = get_db_connection(readonly=True)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("SELECT * FROM support_tickets WHERE id = %s;", (ticket_id,))
        ticket = cur.fetchone()
        if not ticket:
            return None

        ticket_data = dict(ticket)

        cur.execute("""
            SELECT id, ticket_id, action, performed_by, timestamp, before_counts, after_counts, details
            FROM audit_log
            WHERE ticket_id = %s
            ORDER BY timestamp ASC;
        """, (ticket_id,))
        ticket_data["audit_trail"] = [dict(r) for r in cur.fetchall()]

        cur.close()
        return ticket_data
    except Exception as e:
        logger.error(f"Error fetching ticket {ticket_id}: {e}")
        return None
    finally:
        if conn:
            conn.close()


# =============================================================================
# 4. Approve Support Ticket (Resumes LangGraph Checkpoint - Unchanged Gate)
# =============================================================================
def approve_support_ticket(
    ticket_id: str,
    operator_name: str = "human_operator",
    adapter: Optional[ChannelAdapter] = None,
) -> Dict[str, Any]:
    """
    Approves a pending remediation proposal (Web UI human operator only):
    1. Validates that the ticket is in 'fix_ready' status and has an approval_token
    2. Resumes the paused support_graph execution via checkpointer
    3. Runs apply_fix and notify nodes
    4. Records approval in audit_log and sends concise confirmation to original channel thread
    """
    ticket = get_support_ticket(ticket_id)
    if not ticket:
        raise ValueError(f"Ticket '{ticket_id}' not found.")

    if ticket.get("is_flagged"):
        raise PermissionError("Flagged security tickets cannot be auto-applied.")

    if ticket.get("status") not in ("fix_ready", "approved"):
        raise ValueError(f"Cannot approve ticket in status '{ticket.get('status')}'. Must be 'fix_ready'.")

    approval_token = ticket.get("approval_token")
    if not approval_token:
        raise ValueError("Ticket is missing an approval token. Cannot verify safety gate.")

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
            json.dumps({"approval_token": approval_token, "timestamp": datetime.now().isoformat()}),
        ))
        cur.close()
    finally:
        if conn:
            conn.close()

    config = {"configurable": {"thread_id": ticket_id}}
    state_values = support_graph.get_state(config).values

    if state_values:
        support_graph.update_state(config, {"approval_status": "approved", "approval_token": approval_token})
        support_graph.invoke(None, config=config)
    else:
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
            "trace": [],
        }
        res_state = apply_fix_node(resume_state)
        notify_node(res_state)

    updated = get_support_ticket(ticket_id)
    if updated:
        _dispatch_channel_reply(
            updated,
            f"Ticket #{ticket_id}: Fix approved by operator and applied successfully.",
            adapter=adapter,
        )
    return updated


# =============================================================================
# 5. Reject Support Ticket
# =============================================================================
def reject_support_ticket(
    ticket_id: str,
    reason: str = "",
    operator_name: str = "human_operator",
    adapter: Optional[ChannelAdapter] = None,
) -> Dict[str, Any]:
    """
    Rejects the proposed remediation, logs to audit_log, and replies on original thread.
    """
    ticket = get_support_ticket(ticket_id)
    if not ticket:
        raise ValueError(f"Ticket '{ticket_id}' not found.")

    rejection_note = reason.strip() or "Remediation was reviewed and rejected by an administrator."
    reply = (
        f"Hello {ticket.get('client_name')}, our operations team reviewed ticket #{ticket_id} "
        f"and rejected the proposed fix ({rejection_note}). No production changes were made."
    )

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
            json.dumps({"reason": rejection_note, "timestamp": datetime.now().isoformat()}),
        ))
        cur.close()
    finally:
        if conn:
            conn.close()

    updated = get_support_ticket(ticket_id)
    if updated:
        _dispatch_channel_reply(
            updated,
            f"Ticket #{ticket_id}: Proposed fix rejected by operator. ({rejection_note})",
            adapter=adapter,
        )
    return updated
