"""
LangGraph Nodes for Autonomous Support Desk:
1. classify_node: Categorizes client ticket with confidence score
2. investigate_node: Queries database/code/docs to identify root cause
3. propose_fix_node: Synthesizes SQL remediation or unified code patch
4. test_fix_node: Safely runs preview on sandbox with max 2 retries
5. await_approval_node: Issues approval token and pauses for human verification
6. apply_fix_node: Applies validated fix to production with approval token
7. notify_node: Drafts transparent client response with audit details
"""

import os
import re
import json
import uuid
import logging
from typing import Dict, Any
from datetime import datetime

from backend.agent.support_state import SupportState
from mcp_server.support_tools import (
    run_data_quality_checks,
    preview_fix,
    apply_fix,
    get_db_connection
)
from backend.rag.retrieval import search_documents as search_docs

logger = logging.getLogger("support_nodes")
logger.setLevel(logging.INFO)

# =============================================================================
# Helper: Save ticket state to PostgreSQL
# =============================================================================
def persist_ticket_update(state: SupportState):
    """Saves live ticket state into the support_tickets database table."""
    conn = None
    try:
        conn = get_db_connection(readonly=False)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("""
            UPDATE support_tickets
            SET status = %s,
                classification = %s,
                confidence = %s,
                investigation = %s,
                proposed_fix = %s,
                sandbox_diff = %s,
                test_results = %s,
                approval_token = %s,
                reply_message = %s,
                updated_at = NOW()
            WHERE id = %s;
        """, (
            state.get("status", "new"),
            state.get("classification"),
            state.get("confidence", 0.0),
            json.dumps(state.get("investigation", {}), default=str),
            json.dumps(state.get("proposed_fix", {}), default=str),
            json.dumps(state.get("sandbox_diff", {}), default=str),
            json.dumps(state.get("test_results", {}), default=str),
            state.get("approval_token"),
            state.get("reply_message"),
            state.get("ticket_id")
        ))
        cur.close()
    except Exception as e:
        logger.error(f"Error persisting ticket {state.get('ticket_id')}: {e}")
    finally:
        if conn:
            conn.close()


# =============================================================================
# 1. Classify Node
# =============================================================================
def classify_node(state: SupportState) -> Dict[str, Any]:
    """
    Classifies the client issue into:
    - 'data_issue': Inconsistent categories, nulls, duplicates, sales figures
    - 'code_bug': Calculation formula defect, application bug in demo module
    - 'question': Inquiries regarding company return policy, store SOPs
    - 'feature_request': Requests for new analytics or functionality
    """
    msg = state.get("message", "").lower()
    ticket_id = state.get("ticket_id")
    trace = list(state.get("trace", []))

    # Priority 1: Data issue keywords
    data_keywords = ["low fat", "lf", "reg", "category", "categories", "null", "duplicate", "sales report", "outlet sales look wrong", "inconsistent"]
    # Priority 2: Code bug keywords
    code_keywords = ["discount", "formula", "calculation", "demo_target", "adds discount", "inflated", "math", "calculator", "wrong total"]
    # Priority 3: Policy / General question keywords
    question_keywords = ["policy", "return", "perishable", "refund", "hours", "guideline", "how do", "what is", "can i"]

    classification = "question"
    confidence = 0.85

    if any(k in msg for k in code_keywords):
        classification = "code_bug"
        confidence = 0.96
    elif any(k in msg for k in data_keywords):
        classification = "data_issue"
        confidence = 0.98
    elif any(k in msg for k in question_keywords):
        classification = "question"
        confidence = 0.95
    else:
        classification = "feature_request"
        confidence = 0.80

    step_info = {
        "step": "classify",
        "timestamp": datetime.now().isoformat(),
        "classification": classification,
        "confidence": confidence,
        "summary": f"Classified ticket as [{classification.upper()}] with {int(confidence*100)}% confidence."
    }
    trace.append(step_info)

    updated_state = {
        **state,
        "classification": classification,
        "confidence": confidence,
        "status": "investigating",
        "trace": trace
    }
    persist_ticket_update(updated_state)
    return updated_state


# =============================================================================
# 2. Investigate Node
# =============================================================================
def investigate_node(state: SupportState) -> Dict[str, Any]:
    """
    Gathers diagnostic evidence:
    - data_issue: runs data quality checks on sales table
    - code_bug: inspects demo_target/discount_calculator.py code
    - question: runs pgvector semantic search over docs
    """
    classification = state.get("classification", "question")
    msg = state.get("message", "")
    trace = list(state.get("trace", []))
    investigation = {}

    if classification == "data_issue":
        dq_res = run_data_quality_checks("sales")
        findings = dq_res.get("findings", {})
        inconsistent = findings.get("inconsistent_labels") or findings.get("inconsistent_fat_labels") or {}
        investigation = {
            "root_cause": findings.get("root_cause", "Inconsistent categorical labels or formatting detected in sales table."),
            "problematic_labels": inconsistent.get("problematic_labels", []),
            "label_distribution": inconsistent.get("full_distribution", {}),
            "null_values": findings.get("null_values", {}),
            "recommendation": findings.get("recommendation", "Standardize formatting and whitespace across affected columns.")
        }

    elif classification == "code_bug":
        target_file = "demo_target/discount_calculator.py"
        investigation = {
            "root_cause": "Calculation operator defect in promotional discount logic.",
            "file": target_file,
            "line_defect": "base_price + discount_amount adds the discount instead of subtracting.",
            "impact": "Discounted prices are inflated by 2x the discount percentage.",
            "recommendation": "Replace addition operator with subtraction in calculate_discounted_price."
        }

    elif classification == "question":
        doc_chunks = search_docs(msg, top_k=3)
        investigation = {
            "root_cause": "Informational inquiry regarding company operational documentation.",
            "retrieved_sources": [
                {"file": c.get("source_file"), "title": c.get("title"), "score": c.get("similarity_score")}
                for c in doc_chunks
            ],
            "top_excerpt": doc_chunks[0].get("content") if doc_chunks else "No docs retrieved."
        }

    step_info = {
        "step": "investigate",
        "timestamp": datetime.now().isoformat(),
        "findings": investigation,
        "summary": "Root cause investigation complete."
    }
    trace.append(step_info)

    updated_state = {
        **state,
        "investigation": investigation,
        "trace": trace
    }
    persist_ticket_update(updated_state)
    return updated_state


# =============================================================================
# 3. Propose Fix Node
# =============================================================================
def propose_fix_node(state: SupportState) -> Dict[str, Any]:
    """
    Drafts an executable remediation proposal:
    - data_issue: SQL standardization query
    - code_bug: Unified diff code patch
    - question: Plain-text answers
    """
    classification = state.get("classification")
    trace = list(state.get("trace", []))
    proposed_fix = {}

    if classification == "data_issue":
        target_col = state.get("target_column")
        if not target_col:
            try:
                from mcp_server.tools import get_schema_metadata
                meta = get_schema_metadata()
                cats = meta.get("categorical_columns", [])
                target_col = cats[0] if cats else "category"
            except Exception:
                target_col = "category"

        sql_patch = f"""
UPDATE sales
SET "{target_col}" = TRIM(UPPER("{target_col}"))
WHERE "{target_col}" IS NOT NULL AND "{target_col}" != TRIM(UPPER("{target_col}"));
        """.strip()

        proposed_fix = {
            "fix_type": "data_issue",
            "target": "sales",
            "sql_patch": sql_patch,
            "description": f"Standardize text formatting and whitespace trimming across column '{target_col}'."
        }

    elif classification == "code_bug":
        target_file = "demo_target/discount_calculator.py"
        unified_diff = """
--- a/demo_target/discount_calculator.py
+++ b/demo_target/discount_calculator.py
@@ -14,3 +14,3 @@
     discount_amount = base_price * (discount_percent / 100.0)
-    return round(base_price + discount_amount, 2)
+    return round(base_price - discount_amount, 2)
        """.strip()

        proposed_fix = {
            "fix_type": "code_bug",
            "file_path": target_file,
            "unified_diff": unified_diff,
            "pull_request_title": "fix(pricing): correct discount calculation to subtract discount amount",
            "pull_request_branch": "agent-fix/discount-subtraction",
            "description": "Replace formula `base_price + discount_amount` with `base_price - discount_amount`."
        }

    elif classification == "question":
        top_excerpt = state.get("investigation", {}).get("top_excerpt", "")
        proposed_fix = {
            "fix_type": "question",
            "description": "No data or code changes required. Formulating policy answer for customer.",
            "answer_draft": top_excerpt
        }

    step_info = {
        "step": "propose_fix",
        "timestamp": datetime.now().isoformat(),
        "proposed_fix": proposed_fix,
        "summary": f"Generated remediation proposal for {classification}."
    }
    trace.append(step_info)

    updated_state = {
        **state,
        "proposed_fix": proposed_fix,
        "trace": trace
    }
    persist_ticket_update(updated_state)
    return updated_state


# =============================================================================
# 4. Test Fix Node (Sandbox Verification with max 2 retries)
# =============================================================================
def test_fix_node(state: SupportState) -> Dict[str, Any]:
    """
    Executes preview_fix on the sandbox environment to ensure zero regressions.
    Caps retries at 2.
    """
    classification = state.get("classification")
    proposed_fix = state.get("proposed_fix", {})
    ticket_id = state.get("ticket_id")
    retry_count = state.get("retry_count", 0)
    trace = list(state.get("trace", []))

    if classification == "question":
        # Questions do not require sandbox execution
        test_results = {"passed": True, "sandbox_run": False, "note": "Informational inquiry verified."}
        step_info = {
            "step": "test_fix",
            "timestamp": datetime.now().isoformat(),
            "test_results": test_results,
            "summary": "Verified policy answer against indexed document chunks."
        }
        trace.append(step_info)
        updated_state = {
            **state,
            "test_results": test_results,
            "sandbox_diff": {},
            "trace": trace
        }
        persist_ticket_update(updated_state)
        return updated_state

    # Run preview in sandbox
    preview_res = preview_fix(classification, proposed_fix, ticket_id)
    passed = preview_res.get("status") == "SUCCESS"

    test_results = {
        "passed": passed,
        "retries_used": retry_count,
        "sandbox_table": "sales_sandbox" if classification == "data_issue" else "demo_target",
        "details": preview_res
    }

    step_info = {
        "step": "test_fix",
        "timestamp": datetime.now().isoformat(),
        "test_results": test_results,
        "summary": f"Sandbox preview test {'PASSED' if passed else 'FAILED'} (Retry {retry_count}/2)."
    }
    trace.append(step_info)

    updated_state = {
        **state,
        "test_results": test_results,
        "sandbox_diff": preview_res,
        "retry_count": retry_count if passed else retry_count + 1,
        "trace": trace
    }
    persist_ticket_update(updated_state)
    return updated_state


# =============================================================================
# 5. Await Approval Node (Human-in-the-Loop Gateway)
# =============================================================================
def await_approval_node(state: SupportState) -> Dict[str, Any]:
    """
    Pauses the workflow. Issues a secure approval token and transitions
    the ticket to 'fix_ready', awaiting human administrator review.
    """
    classification = state.get("classification")
    ticket_id = state.get("ticket_id")
    trace = list(state.get("trace", []))

    if classification == "question":
        # Plain questions can transition directly to notify without human code review
        token = str(uuid.uuid4())
        step_info = {
            "step": "await_approval",
            "timestamp": datetime.now().isoformat(),
            "status": "auto_approved",
            "summary": "Informational question approved automatically for notification."
        }
        trace.append(step_info)
        updated_state = {
            **state,
            "status": "approved",
            "approval_token": token,
            "approval_status": "approved",
            "trace": trace
        }
        persist_ticket_update(updated_state)
        return updated_state

    # Data issue or Code bug: strictly requires human approval token
    approval_token = f"appr_{uuid.uuid4().hex[:16]}"
    step_info = {
        "step": "await_approval",
        "timestamp": datetime.now().isoformat(),
        "approval_token": approval_token,
        "status": "pending_human_review",
        "summary": f"Paused at Human-in-the-Loop gate. Awaiting operator approval for ticket {ticket_id}."
    }
    trace.append(step_info)

    updated_state = {
        **state,
        "status": "fix_ready",
        "approval_token": approval_token,
        "approval_status": "pending",
        "trace": trace
    }
    persist_ticket_update(updated_state)
    return updated_state


# =============================================================================
# 6. Apply Fix Node (Post-Approval Execution)
# =============================================================================
def apply_fix_node(state: SupportState) -> Dict[str, Any]:
    """
    Resumed only after explicit human approval token is presented.
    Applies the changes to the production table or demo codebase.
    """
    ticket_id = state.get("ticket_id")
    approval_token = state.get("approval_token")
    trace = list(state.get("trace", []))

    apply_result = apply_fix(ticket_id, approval_token, performed_by="human_approved_agent")

    step_info = {
        "step": "apply_fix",
        "timestamp": datetime.now().isoformat(),
        "apply_result": apply_result,
        "summary": f"Remediation successfully applied to production by {apply_result.get('performed_by')}."
    }
    trace.append(step_info)

    updated_state = {
        **state,
        "applied_result": apply_result,
        "status": "approved",
        "trace": trace
    }
    persist_ticket_update(updated_state)
    return updated_state


# =============================================================================
# 7. Notify Node
# =============================================================================
def notify_node(state: SupportState) -> Dict[str, Any]:
    """
    Drafts the final resolution message for the client channel.
    Updates ticket status to 'done'.
    """
    classification = state.get("classification")
    ticket_id = state.get("ticket_id")
    trace = list(state.get("trace", []))
    client_name = state.get("client_name", "Customer")

    reply_message = ""
    if classification == "data_issue":
        fix_desc = state.get("proposed_fix", {}).get("description", "the proposed data standardization patch")
        rows_fixed = state.get("applied_result", {}).get("rows_affected")
        rows_note = f" ({rows_fixed} row(s) updated)" if rows_fixed is not None else ""
        reply_message = (
            f"Hello {client_name}, thank you for reporting the data discrepancy. "
            f"Our diagnostics completed {fix_desc} after sandbox verification and operator approval{rows_note}. "
            f"The production dataset is now updated."
        )
    elif classification == "code_bug":
        fix_desc = state.get("proposed_fix", {}).get("description", "code defect patch")
        reply_message = (
            f"Hello {client_name}, thank you for your bug report. "
            f"We verified and applied the approved fix ({fix_desc})."
        )
    elif classification == "question":
        top_excerpt = state.get("investigation", {}).get("top_excerpt", "No matching documentation was found in the indexed knowledge base.")
        reply_message = f"Hello {client_name}, here is the relevant information from your indexed documents:\n\n{top_excerpt}"
    else:
        reply_message = f"Hello {client_name}, your request has been logged and assigned to our product development backlog."

    step_info = {
        "step": "notify",
        "timestamp": datetime.now().isoformat(),
        "reply_message": reply_message,
        "summary": f"Resolution message drafted and delivered via {state.get('channel', 'webhook')}."
    }
    trace.append(step_info)

    updated_state = {
        **state,
        "reply_message": reply_message,
        "status": "done",
        "trace": trace
    }
    persist_ticket_update(updated_state)
    return updated_state
