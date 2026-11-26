"""
Background Channel Worker Manager for Support Desk
--------------------------------------------------
Orchestrates Email (30s IMAP polling), Slack (Socket Mode),
and Microsoft Teams (stub). Starts automatically with FastAPI or standalone via:
    make channels
    python -m backend.support.channel_manager
"""

import os
import sys
import time
import signal
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from dotenv import load_dotenv

# Ensure project root is importable when invoked as python -m backend.support.channel_manager
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.support.adapters import get_channel_adapter
from backend.support.security import redact_secrets
from backend.support.service import (
    ChannelPermissionError,
    RateLimitExceededError,
    ingest_channel_message,
)

load_dotenv()
logger = logging.getLogger("support_channel_manager")


class ChannelManager:
    """Thread-safe lifecycle & telemetry manager for Support Desk channel workers."""

    CHANNEL_METADATA = {
        "email": {
            "id": "email",
            "name": "Email (IMAP/SMTP)",
            "mode": "IMAP 30s Poll",
            "docs_hint": "docs/CHANNELS_SETUP.md#email",
        },
        "slack": {
            "id": "slack",
            "name": "Slack",
            "mode": "Socket Mode",
            "docs_hint": "docs/CHANNELS_SETUP.md#slack",
        },
        "teams": {
            "id": "teams",
            "name": "Microsoft Teams",
            "mode": "Webhook Stub",
            "docs_hint": "docs/TEAMS_SETUP.md",
        },
    }

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stop_events: Dict[str, threading.Event] = {}
        self._threads: Dict[str, threading.Thread] = {}
        self._state: Dict[str, Dict[str, Any]] = {
            cid: {
                "id": cid,
                "name": meta["name"],
                "mode": meta["mode"],
                "docs_hint": meta["docs_hint"],
                "configured": False,
                "enabled": True,
                "status": "not_configured",
                "error_reason": None,
                "last_message_at": None,
                "allowlist_count": 0,
            }
            for cid, meta in self.CHANNEL_METADATA.items()
        }

    def _refresh_config_flags(self, channel_id: str) -> Any:
        adapter = get_channel_adapter(channel_id)
        configured = adapter.is_configured()
        allow_count = len(adapter.allowlist()) if hasattr(adapter, "allowlist") else 0
        with self._lock:
            st = self._state[channel_id]
            st["configured"] = configured
            st["allowlist_count"] = allow_count
            if channel_id == "teams":
                st["status"] = "not_configured"
                st["error_reason"] = "Requires Azure Bot registration & public HTTPS endpoint (see docs/TEAMS_SETUP.md)."
            elif not configured:
                st["status"] = "not_configured"
                st["error_reason"] = None
        return adapter

    def _set_status(self, channel_id: str, status_val: str, error_reason: Optional[str] = None) -> None:
        with self._lock:
            st = self._state[channel_id]
            if not st["enabled"] and status_val != "not_configured":
                st["status"] = "paused"
            else:
                st["status"] = status_val
            st["error_reason"] = redact_secrets(error_reason) if error_reason else None

    def _handle_incoming(self, channel_id: str, raw_payload: Dict[str, Any]) -> None:
        adapter = get_channel_adapter(channel_id)
        try:
            normalized = adapter.parse_incoming(raw_payload)
            if not normalized.text:
                return
            ticket = ingest_channel_message(
                normalized,
                enforce_allowlist=True,
                adapter=adapter,
                notify_on_channel=True,
            )
            with self._lock:
                self._state[channel_id]["last_message_at"] = datetime.now(timezone.utc).isoformat()
            logger.info(f"[{channel_id}] Processed inbound message -> ticket {ticket.get('id')} (status={ticket.get('status')})")
        except ChannelPermissionError as perm_err:
            logger.warning(f"[{channel_id}] Blocked non-allowlisted sender: {redact_secrets(str(perm_err))}")
        except RateLimitExceededError as rate_err:
            logger.warning(f"[{channel_id}] Rate limit triggered: {redact_secrets(str(rate_err))}")
        except Exception as e:
            logger.error(f"[{channel_id}] Failed processing inbound message: {redact_secrets(str(e))}", exc_info=True)

    def start_channel(self, channel_id: str) -> None:
        if channel_id not in self._state:
            return
        adapter = self._refresh_config_flags(channel_id)

        if channel_id == "teams":
            logger.info("Microsoft Teams channel skipped: stub only (see docs/TEAMS_SETUP.md).")
            return

        if not adapter.is_configured():
            logger.info(f"{self.CHANNEL_METADATA[channel_id]['name']} channel skipped: credentials not configured in .env.")
            return

        with self._lock:
            if not self._state[channel_id]["enabled"]:
                self._state[channel_id]["status"] = "paused"
                return
            existing_thread = self._threads.get(channel_id)
            if existing_thread and existing_thread.is_alive():
                return
            stop_ev = threading.Event()
            self._stop_events[channel_id] = stop_ev

        def _runner() -> None:
            on_msg = lambda payload: self._handle_incoming(channel_id, payload)
            on_stat = lambda s, err=None: self._set_status(channel_id, s, err)
            if channel_id == "email":
                adapter.run_polling_loop(stop_ev, on_msg, on_stat)
            elif channel_id == "slack":
                adapter.run_socket_loop(stop_ev, on_msg, on_stat)

        t = threading.Thread(target=_runner, name=f"channel-worker-{channel_id}", daemon=True)
        with self._lock:
            self._threads[channel_id] = t
        t.start()

    def stop_channel(self, channel_id: str) -> None:
        with self._lock:
            ev = self._stop_events.get(channel_id)
            if ev:
                ev.set()
            st = self._state.get(channel_id)
            if st and st.get("configured"):
                st["status"] = "paused"

    def toggle_channel(self, channel_id: str, enabled: bool) -> Dict[str, Any]:
        if channel_id not in self._state:
            raise ValueError(f"Unknown channel '{channel_id}'.")
        with self._lock:
            self._state[channel_id]["enabled"] = bool(enabled)

        if enabled:
            self.start_channel(channel_id)
        else:
            self.stop_channel(channel_id)
        return self.get_channel_status(channel_id)

    def start_all(self) -> None:
        for cid in self.CHANNEL_METADATA:
            self.start_channel(cid)

    def stop_all(self) -> None:
        for cid in list(self._stop_events.keys()):
            self.stop_channel(cid)

    def get_channel_status(self, channel_id: str) -> Dict[str, Any]:
        self._refresh_config_flags(channel_id)
        with self._lock:
            return dict(self._state[channel_id])

    def get_all_statuses(self) -> List[Dict[str, Any]]:
        for cid in self.CHANNEL_METADATA:
            self._refresh_config_flags(cid)
        with self._lock:
            return [dict(self._state[cid]) for cid in ("email", "slack", "teams")]


channel_manager = ChannelManager()


def main() -> None:
    """Standalone CLI entrypoint for `make channels` / `python -m backend.support.channel_manager`."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logger.info("Starting Support Desk channel workers...")
    channel_manager.start_all()

    stop_requested = threading.Event()

    def _handle_sig(_sig, _frame):
        logger.info("Shutting down Support Desk channel workers...")
        stop_requested.set()

    signal.signal(signal.SIGINT, _handle_sig)
    signal.signal(signal.SIGTERM, _handle_sig)

    while not stop_requested.is_set():
        time.sleep(1.0)

    channel_manager.stop_all()


if __name__ == "__main__":
    main()
