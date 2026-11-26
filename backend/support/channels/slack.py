"""
Slack App Channel Adapter (Socket Mode)
-------------------------------------
Receives Slack channel mentions, channel messages, and direct messages over
Socket Mode (no public HTTPS URL required), and replies in the exact Slack thread.

Environment variables (from .env):
- SLACK_BOT_TOKEN (xoxb-...)
- SLACK_APP_TOKEN (xapp-...)
- SLACK_ALLOWED_CHANNELS (comma-separated channel IDs C.../G.../D..., user IDs U..., or 'dm')
"""

import os
import re
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Callable

from backend.support.adapters import ChannelAdapter, NormalizedChannelMessage
from backend.support.security import parse_allowlist, redact_secrets, sanitize_channel_reply

logger = logging.getLogger("support_channel_slack")


class SlackAdapter(ChannelAdapter):
    """Slack Socket Mode adapter using slack_sdk."""

    channel_name = "slack"

    def _tokens(self) -> tuple[str, str]:
        bot = os.environ.get("SLACK_BOT_TOKEN", "").strip()
        app = os.environ.get("SLACK_APP_TOKEN", "").strip()
        if bot.startswith(("your_", "placeholder_")):
            bot = ""
        if app.startswith(("your_", "placeholder_")):
            app = ""
        return bot, app

    def is_configured(self) -> bool:
        bot, app = self._tokens()
        return bool(bot and app)

    def allowlist(self) -> set[str]:
        return parse_allowlist("SLACK_ALLOWED_CHANNELS")

    def is_sender_allowed(self, message: NormalizedChannelMessage) -> bool:
        allowed = self.allowlist()
        if not allowed:
            logger.warning("[Slack] Rejected message: SLACK_ALLOWED_CHANNELS is empty.")
            return False

        ch_id = str(message.metadata.get("channel_id") or "").lower()
        ch_type = str(message.metadata.get("channel_type") or "").lower()
        sender_id = str(message.sender_id or "").lower()

        if ch_id and ch_id in allowed:
            return True
        if sender_id and sender_id in allowed:
            return True
        if (ch_type == "im" or ch_id.startswith("d")) and ("dm" in allowed or "im" in allowed):
            return True

        logger.warning(f"[Slack] Ignored unauthorized message from channel='{ch_id}' user='{sender_id}'.")
        return False

    def _resolve_user_name(self, user_id: str, client: Any = None) -> str:
        if not user_id:
            return "Slack User"
        if client is not None:
            try:
                info = client.users_info(user=user_id)
                user_obj = info.get("user") or {}
                profile = user_obj.get("profile") or {}
                return profile.get("display_name") or profile.get("real_name") or user_obj.get("name") or user_id
            except Exception:
                pass
        return user_id

    def parse_incoming(self, payload: Dict[str, Any]) -> NormalizedChannelMessage:
        event = payload.get("event") if isinstance(payload.get("event"), dict) else payload
        channel_id = str(event.get("channel") or payload.get("channel_id") or "")
        channel_type = str(event.get("channel_type") or payload.get("channel_type") or ("im" if channel_id.startswith("D") else "channel"))
        user_id = str(event.get("user") or payload.get("user_id") or payload.get("user_name") or "Slack User")
        raw_text = str(event.get("text") or payload.get("text") or "")
        clean_text = re.sub(r"<@[A-Za-z0-9_]+>\s*", "", raw_text).strip()

        ts = str(event.get("ts") or payload.get("ts") or "")
        thread_ts = str(event.get("thread_ts") or ts or "")
        thread_id = f"{channel_id}:{thread_ts}" if channel_id and thread_ts else (channel_id or None)
        ext_id = f"slack_{channel_id}_{ts}" if channel_id and ts else None

        try:
            ts_iso = datetime.fromtimestamp(float(ts.split(".")[0]), tz=timezone.utc).isoformat() if ts else datetime.now(timezone.utc).isoformat()
        except Exception:
            ts_iso = datetime.now(timezone.utc).isoformat()

        sender_name = str(payload.get("user_name") or event.get("user_name") or user_id)
        thread_url = payload.get("permalink") or event.get("permalink")

        return NormalizedChannelMessage(
            sender_name=sender_name,
            sender_id=user_id,
            sender_email=f"{user_id.lower()}@slack.local",
            channel=self.channel_name,
            text=clean_text,
            timestamp=ts_iso,
            thread_id=thread_id,
            external_message_id=ext_id,
            thread_url=thread_url,
            metadata={
                "channel_id": channel_id,
                "channel_type": channel_type,
                "ts": ts,
                "thread_ts": thread_ts,
            },
        )

    def send_reply(
        self,
        thread_id: Optional[str],
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        bot_token, _ = self._tokens()
        if not bot_token:
            return False

        meta = metadata or {}
        channel_id = meta.get("channel_id")
        thread_ts = meta.get("thread_ts") or meta.get("ts")
        if thread_id and ":" in thread_id:
            ch_part, ts_part = thread_id.split(":", 1)
            channel_id = channel_id or ch_part
            thread_ts = thread_ts or ts_part
        elif thread_id and not channel_id:
            channel_id = thread_id

        if not channel_id:
            logger.warning("[Slack] Cannot send reply: missing channel_id.")
            return False

        try:
            from slack_sdk import WebClient
            client = WebClient(token=bot_token)
            kwargs: Dict[str, Any] = {
                "channel": channel_id,
                "text": sanitize_channel_reply(text),
            }
            if thread_ts:
                kwargs["thread_ts"] = thread_ts
            resp = client.chat_postMessage(**kwargs)
            return bool(resp.get("ok"))
        except Exception as e:
            logger.error(f"[Slack] Failed to send reply: {redact_secrets(str(e))}")
            return False

    def run_socket_loop(
        self,
        stop_event: threading.Event,
        on_message: Callable[[Dict[str, Any]], None],
        on_status: Optional[Callable[[str, Optional[str]], None]] = None,
    ) -> None:
        """Connects via Slack Socket Mode without requiring a public webhook URL."""
        bot_token, app_token = self._tokens()
        if not (bot_token and app_token):
            logger.info("Slack channel skipped: SLACK_BOT_TOKEN or SLACK_APP_TOKEN not configured.")
            if on_status:
                on_status("not_configured", None)
            return

        try:
            from slack_sdk import WebClient
            from slack_sdk.socket_mode import SocketModeClient
            from slack_sdk.socket_mode.request import SocketModeRequest
            from slack_sdk.socket_mode.response import SocketModeResponse

            web_client = WebClient(token=bot_token)
            auth = web_client.auth_test()
            bot_user_id = auth.get("user_id", "")

            socket_client = SocketModeClient(app_token=app_token, web_client=web_client)

            def process_request(client: SocketModeClient, req: SocketModeRequest):
                # Acknowledge receipt within 3 seconds per Slack requirement
                client.send_socket_mode_response(SocketModeResponse(envelope_id=req.envelope_id))
                if req.type != "events_api":
                    return
                event = (req.payload or {}).get("event") or {}
                ev_type = event.get("type")
                if ev_type not in ("message", "app_mention"):
                    return
                if event.get("bot_id") or event.get("subtype") in ("bot_message", "message_changed", "message_deleted"):
                    return
                if bot_user_id and event.get("user") == bot_user_id:
                    return
                if not (event.get("text") or "").strip():
                    return

                enriched = dict(req.payload or {})
                user_id = str(event.get("user") or "")
                enriched["user_name"] = self._resolve_user_name(user_id, web_client)
                try:
                    link_resp = web_client.chat_getPermalink(
                        channel=event.get("channel"),
                        message_ts=event.get("thread_ts") or event.get("ts"),
                    )
                    if link_resp.get("ok"):
                        enriched["permalink"] = link_resp.get("permalink")
                except Exception:
                    pass
                threading.Thread(target=on_message, args=(enriched,), daemon=True).start()

            socket_client.socket_mode_request_listeners.append(process_request)
            socket_client.connect()
            logger.info("[Slack] Socket Mode connected.")
            if on_status:
                on_status("connected", None)

            while not stop_event.is_set():
                stop_event.wait(2.0)

            try:
                socket_client.close()
            except Exception:
                pass
        except Exception as e:
            err = redact_secrets(str(e))
            logger.error(f"[Slack] Socket Mode connection failed: {err}")
            if on_status:
                on_status("error", err)


# Backwards-compatible alias
SlackAdapterStub = SlackAdapter
