"""
Microsoft Teams Channel Adapter Stub
------------------------------------
Teams requires Azure Bot registration, Microsoft Entra ID app permissions, and
a public HTTPS messaging endpoint. See docs/TEAMS_SETUP.md for administrator setup steps.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from backend.support.adapters import ChannelAdapter, NormalizedChannelMessage
from backend.support.security import sanitize_channel_reply

logger = logging.getLogger("support_channel_teams")


class TeamsAdapterStub(ChannelAdapter):
    """
    Microsoft Teams Bot Framework Activity Adapter Stub.
    Disabled at runtime until Azure Bot + public HTTPS endpoint are provisioned by IT admin.
    """

    channel_name = "teams"

    def is_configured(self) -> bool:
        return False

    def parse_incoming(self, payload: Dict[str, Any]) -> NormalizedChannelMessage:
        sender = payload.get("from") or {}
        user_name = str(sender.get("name") or payload.get("client_name") or "Teams Member")
        user_id = str(sender.get("id") or user_name)
        text = str(payload.get("text") or payload.get("message") or "").strip()
        service_url = payload.get("serviceUrl")
        conv_id = str((payload.get("conversation") or {}).get("id") or payload.get("thread_id") or "")

        return NormalizedChannelMessage(
            sender_name=user_name,
            sender_id=user_id,
            sender_email=f"{user_name.lower().replace(' ', '.')}@msteams.local",
            channel=self.channel_name,
            text=text,
            timestamp=payload.get("timestamp") or datetime.now(timezone.utc).isoformat(),
            thread_id=conv_id or None,
            external_message_id=payload.get("id"),
            metadata={"service_url": service_url, "conversation_id": conv_id},
        )

    def send_reply(
        self,
        thread_id: Optional[str],
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        safe_text = sanitize_channel_reply(text)
        logger.info(f"[TeamsAdapterStub] Outbound reply requires Azure Bot setup (see docs/TEAMS_SETUP.md): {safe_text[:80]}")
        return False
