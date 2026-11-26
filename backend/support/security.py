"""
Security Guardrails for Support Desk Communication Channels
---------------------------------------------------------
Enforces:
1. Secret & credential redaction (tokens, passwords, DB URLs never logged or sent).
2. Untrusted client-message inspection (prompt injection, destructive SQL, bypass attempts).
3. Reply sanitization (strips raw SQL, stack traces, and sensitive patterns from outbound replies).
4. Allowlist parsing helpers.
"""

import os
import re
from typing import Optional, Set

# Patterns indicating prompt injection, destructive SQL execution attempts, or approval bypasses
_INJECTION_PATTERNS = [
    (r"\bignore\s+(?:all\s+|your\s+|previous\s+|the\s+)*(?:rules|instructions|prompts|guardrails|safety)\b",
     "Prompt-injection instruction override attempt"),
    (r"\bdisregard\s+(?:all\s+|your\s+|previous\s+)*(?:rules|instructions|system)\b",
     "Prompt-injection instruction override attempt"),
    (r"\boverride\s+(?:safety|approval|rules|policy|gate)\b",
     "Safety or approval gate bypass attempt"),
    (r"\bbypass\s+(?:approval|hitl|human|safety|gate)\b",
     "Approval gate bypass attempt"),
    (r"\b(?:drop|truncate|alter)\s+(?:the\s+)?(?:table\s+)?(?:sales|sales_sandbox|support_tickets|audit_log|document_embeddings|users)\b",
     "Destructive database DDL command detected in client message"),
    (r"\b(?:drop|truncate)\s+table\b",
     "Destructive DROP/TRUNCATE TABLE directive detected in client message"),
    (r"\bdelete\s+from\s+(?:sales|support_tickets|audit_log)\b",
     "Destructive DELETE directive detected in client message"),
    (r"\b(?:reveal|print|dump|show|expose)\s+(?:your\s+)?(?:system\s+prompt|api\s+key|bot\s+token|\.env|secrets?|password)\b",
     "Secret extraction attempt detected in client message"),
    (r"\b(?:auto[- ]?approve|self[- ]?approve|apply\s+fix\s+without\s+approval|execute\s+apply_fix)\b",
     "Unauthorized approval execution attempt from channel"),
]

_APPROVAL_COMMAND_PATTERNS = [
    r"^\s*/?approve\b",
    r"\bapprove\s+ticket\s+#?tick_[a-z0-9]+\b",
]

_SECRET_REDACTION_PATTERNS = [
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), "[REDACTED_SLACK_TOKEN]"),
    (re.compile(r"\bxapp-\d-[A-Za-z0-9-]{10,}\b"), "[REDACTED_SLACK_APP_TOKEN]"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{15,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\bAQ\.A[0-9A-Za-z_.-]{15,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"postgresql(?:\+psycopg2)?://[^\s\"']+", re.IGNORECASE), "[REDACTED_DB_URL]"),
    (re.compile(r"(?i)(password|app_password|token|secret|api_key)\s*[:=]\s*\S+"), r"\1=[REDACTED]"),
]

_RAW_SQL_LINE_RE = re.compile(
    r"^\s*(?:SELECT|UPDATE|INSERT|DELETE|DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE)\b.*$",
    re.IGNORECASE | re.MULTILINE,
)
_TRACEBACK_RE = re.compile(r"Traceback \(most recent call last\):[\s\S]*", re.IGNORECASE)


def parse_allowlist(env_var: str) -> Set[str]:
    """Parses a comma-separated allowlist from environment variables into normalized lowercase entries."""
    raw = os.environ.get(env_var, "").strip()
    if not raw:
        return set()
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def redact_secrets(text: str) -> str:
    """Removes tokens, passwords, API keys, and connection strings from text or error messages."""
    if not text:
        return ""
    cleaned = str(text)
    for pattern, replacement in _SECRET_REDACTION_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    return cleaned


def detect_untrusted_injection(text: str) -> Optional[str]:
    """
    Inspects untrusted client text for prompt injection, destructive SQL directives,
    secret extraction, or unauthorized channel-based approval triggers.
    Returns a concise human-readable reason if flagged, else None.
    """
    if not text:
        return None
    normalized = text.strip()
    for pattern, reason in _INJECTION_PATTERNS:
        if re.search(pattern, normalized, re.IGNORECASE):
            return reason
    for pattern in _APPROVAL_COMMAND_PATTERNS:
        if re.search(pattern, normalized, re.IGNORECASE):
            return "Channel messages cannot approve or apply fixes; approval must happen in the web UI."
    return None


def sanitize_channel_reply(text: str, max_length: int = 900) -> str:
    """
    Sanitizes outbound channel replies so secrets, raw SQL statements,
    and stack traces are never leaked back to external messaging threads.
    """
    if not text:
        return ""
    cleaned = redact_secrets(text)
    cleaned = _TRACEBACK_RE.sub("", cleaned)
    cleaned = _RAW_SQL_LINE_RE.sub("[SQL details available in Support Desk UI]", cleaned)
    # Collapse excessive whitespace/newlines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    if len(cleaned) > max_length:
        cleaned = cleaned[: max_length - 3].rstrip() + "..."
    return cleaned
