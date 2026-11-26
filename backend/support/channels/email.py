"""
Email Channel Adapter (IMAP Polling + SMTP Reply)
-------------------------------------------------
Polls a dedicated IMAP folder/INBOX every 30 seconds for unread messages,
creates tickets via the normalized Support Desk pipeline, and sends replies
back via SMTP threading with In-Reply-To / References headers.

Environment variables (from .env):
- IMAP_HOST
- IMAP_USER
- IMAP_APP_PASSWORD
- IMAP_FOLDER (optional, defaults to INBOX)
- SMTP_HOST
- SMTP_PORT (optional, defaults to 587)
- EMAIL_ALLOWED_SENDERS (comma-separated emails or @domain rules)
"""

import os
import hashlib
import imaplib
import smtplib
import logging
import threading
import email
from email.message import EmailMessage
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime
from datetime import datetime, timezone
from urllib.parse import quote
from typing import Dict, Any, Optional, Callable

from backend.support.adapters import ChannelAdapter, NormalizedChannelMessage
from backend.support.security import parse_allowlist, redact_secrets, sanitize_channel_reply

logger = logging.getLogger("support_channel_email")


def _decode_header_value(raw_val: Optional[str]) -> str:
    if not raw_val:
        return ""
    parts = []
    for chunk, charset in decode_header(raw_val):
        if isinstance(chunk, bytes):
            parts.append(chunk.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(str(chunk))
    return "".join(parts).strip()


def _extract_plain_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "").lower()
            if content_type == "text/plain" and "attachment" not in disp:
                raw_bytes = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                return raw_bytes.decode(charset, errors="replace").strip()
        for part in msg.walk():
            if part.get_content_type().startswith("text/"):
                raw_bytes = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                return raw_bytes.decode(charset, errors="replace").strip()
        return ""
    raw_bytes = msg.get_payload(decode=True) or b""
    charset = msg.get_content_charset() or "utf-8"
    return raw_bytes.decode(charset, errors="replace").strip()


class EmailAdapter(ChannelAdapter):
    """IMAP + SMTP Email support channel adapter."""

    channel_name = "email"

    def _config(self) -> Dict[str, Any]:
        imap_host = os.environ.get("IMAP_HOST", "").strip()
        imap_user = os.environ.get("IMAP_USER", "").strip()
        imap_pass = os.environ.get("IMAP_APP_PASSWORD", "").strip()
        imap_folder = os.environ.get("IMAP_FOLDER", "INBOX").strip() or "INBOX"
        smtp_host = os.environ.get("SMTP_HOST", "").strip() or imap_host.replace("imap.", "smtp.")
        try:
            smtp_port = int(os.environ.get("SMTP_PORT", "587").strip() or "587")
        except ValueError:
            smtp_port = 587
        return {
            "imap_host": imap_host,
            "imap_user": imap_user,
            "imap_pass": "" if imap_pass.startswith(("your_", "placeholder_")) else imap_pass,
            "imap_folder": imap_folder,
            "smtp_host": smtp_host,
            "smtp_port": smtp_port,
        }

    def is_configured(self) -> bool:
        cfg = self._config()
        return bool(cfg["imap_host"] and cfg["imap_user"] and cfg["imap_pass"] and cfg["smtp_host"])

    def allowlist(self) -> set[str]:
        return parse_allowlist("EMAIL_ALLOWED_SENDERS")

    def is_sender_allowed(self, message: NormalizedChannelMessage) -> bool:
        allowed = self.allowlist()
        if not allowed:
            logger.warning("[Email] Rejected email: EMAIL_ALLOWED_SENDERS is empty.")
            return False
        addr = (message.sender_email or message.sender_id or "").strip().lower()
        if not addr or "@" not in addr:
            return False
        domain = "@" + addr.split("@", 1)[1]
        ok = addr in allowed or domain in allowed
        if not ok:
            logger.warning(f"[Email] Ignored unauthorized sender '{addr}'.")
        return ok

    def parse_incoming(self, payload: Dict[str, Any]) -> NormalizedChannelMessage:
        raw_bytes = payload.get("raw_bytes")
        if isinstance(raw_bytes, str):
            raw_bytes = raw_bytes.encode("utf-8", errors="replace")

        if isinstance(raw_bytes, (bytes, bytearray)):
            msg = email.message_from_bytes(bytes(raw_bytes))
            from_header = _decode_header_value(msg.get("From"))
            sender_name, sender_email = parseaddr(from_header)
            subject = _decode_header_value(msg.get("Subject")) or "Support Request"
            message_id = _decode_header_value(msg.get("Message-ID"))
            references = _decode_header_value(msg.get("References"))
            date_hdr = msg.get("Date")
            try:
                ts_iso = parsedate_to_datetime(date_hdr).astimezone(timezone.utc).isoformat() if date_hdr else datetime.now(timezone.utc).isoformat()
            except Exception:
                ts_iso = datetime.now(timezone.utc).isoformat()
            body = _extract_plain_body(msg)
        else:
            from_header = str(payload.get("from") or payload.get("sender_email") or "")
            parsed_name, parsed_email = parseaddr(from_header)
            sender_name = str(payload.get("sender_name") or parsed_name or parsed_email or "Email Sender")
            sender_email = str(payload.get("sender_email") or parsed_email or from_header)
            subject = str(payload.get("subject") or "Support Request")
            message_id = str(payload.get("message_id") or payload.get("external_message_id") or "")
            references = str(payload.get("references") or "")
            ts_iso = payload.get("timestamp") or datetime.now(timezone.utc).isoformat()
            body = str(payload.get("body") or payload.get("text") or "").strip()

        sender_email_clean = sender_email.strip().lower()
        sender_name_clean = sender_name.strip() or sender_email_clean or "Email Sender"
        text = f"{subject}\n\n{body}".strip() if subject and subject.lower() not in body.lower() else body
        if not text:
            text = subject

        ext_id = message_id.strip() if message_id else "email_" + hashlib.sha256(
            f"{sender_email_clean}:{subject}:{body[:120]}".encode("utf-8")
        ).hexdigest()[:24]

        thread_id = message_id.strip() or ext_id
        thread_url = f"mailto:{sender_email_clean}?subject=Re:%20{quote(subject)}" if sender_email_clean else None

        return NormalizedChannelMessage(
            sender_name=sender_name_clean,
            sender_id=sender_email_clean or sender_name_clean,
            sender_email=sender_email_clean or "client@example.com",
            channel=self.channel_name,
            text=text,
            timestamp=ts_iso,
            thread_id=thread_id,
            external_message_id=ext_id,
            thread_url=thread_url,
            metadata={
                "to_email": sender_email_clean,
                "subject": subject,
                "message_id": message_id.strip(),
                "references": references.strip(),
            },
        )

    def send_reply(
        self,
        thread_id: Optional[str],
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        cfg = self._config()
        if not (cfg["imap_user"] and cfg["imap_pass"] and cfg["smtp_host"]):
            return False

        meta = metadata or {}
        to_email = meta.get("to_email") or meta.get("sender_email")
        if not to_email:
            logger.warning("[Email] Cannot send reply: missing recipient address.")
            return False

        orig_subject = meta.get("subject") or "Support Request"
        subject = orig_subject if orig_subject.lower().startswith("re:") else f"Re: {orig_subject}"
        msg_id = meta.get("message_id") or thread_id or ""
        refs = " ".join(p for p in (meta.get("references", ""), msg_id) if p).strip()

        outbound = EmailMessage()
        outbound["From"] = cfg["imap_user"]
        outbound["To"] = to_email
        outbound["Subject"] = subject
        if msg_id:
            outbound["In-Reply-To"] = msg_id
        if refs:
            outbound["References"] = refs
        outbound.set_content(sanitize_channel_reply(text))

        try:
            if cfg["smtp_port"] == 465:
                with smtplib.SMTP_SSL(cfg["smtp_host"], cfg["smtp_port"], timeout=15) as server:
                    server.login(cfg["imap_user"], cfg["imap_pass"])
                    server.send_message(outbound)
            else:
                with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"], timeout=15) as server:
                    server.starttls()
                    server.login(cfg["imap_user"], cfg["imap_pass"])
                    server.send_message(outbound)
            return True
        except Exception as e:
            logger.error(f"[Email] Failed to send SMTP reply: {redact_secrets(str(e))}")
            return False

    def poll_once(self, on_message: Callable[[Dict[str, Any]], None]) -> int:
        """Polls IMAP folder for UNSEEN messages once and dispatches each to on_message."""
        cfg = self._config()
        processed = 0
        mail = imaplib.IMAP4_SSL(cfg["imap_host"], timeout=15)
        try:
            mail.login(cfg["imap_user"], cfg["imap_pass"])
            sel_status, _ = mail.select(cfg["imap_folder"])
            if sel_status != "OK":
                raise RuntimeError(f"Could not select IMAP folder '{cfg['imap_folder']}'")

            search_status, data = mail.search(None, "UNSEEN")
            if search_status != "OK" or not data or not data[0]:
                return 0

            for num in data[0].split():
                fetch_status, msg_data = mail.fetch(num, "(RFC822)")
                if fetch_status != "OK" or not msg_data:
                    continue
                raw_bytes = None
                for part in msg_data:
                    if isinstance(part, tuple) and len(part) >= 2:
                        raw_bytes = part[1]
                        break
                if raw_bytes:
                    on_message({"raw_bytes": raw_bytes})
                    mail.store(num, "+FLAGS", "\\Seen")
                    processed += 1
        finally:
            try:
                mail.logout()
            except Exception:
                pass
        return processed

    def run_polling_loop(
        self,
        stop_event: threading.Event,
        on_message: Callable[[Dict[str, Any]], None],
        on_status: Optional[Callable[[str, Optional[str]], None]] = None,
        poll_interval_seconds: float = 30.0,
    ) -> None:
        """Polls IMAP inbox every 30 seconds until stop_event is set."""
        if not self.is_configured():
            logger.info("Email channel skipped: IMAP/SMTP credentials not configured.")
            if on_status:
                on_status("not_configured", None)
            return

        logger.info(f"[Email] IMAP polling started (folder='{self._config()['imap_folder']}', every {int(poll_interval_seconds)}s)")
        while not stop_event.is_set():
            try:
                self.poll_once(on_message)
                if on_status:
                    on_status("connected", None)
            except Exception as e:
                err = redact_secrets(str(e))
                logger.error(f"[Email] IMAP polling error: {err}")
                if on_status:
                    on_status("error", err)
            stop_event.wait(poll_interval_seconds)
