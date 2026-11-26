"""
Channel Adapter Abstraction & Factory for Support Desk:
Defines the common normalized inbound/outbound contract shared by all channels
(Email, Slack, Microsoft Teams stub, Webhook, and Simulated).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import logging

from backend.support.security import sanitize_channel_reply

logger = logging.getLogger("support_adapters")


@dataclass
class NormalizedChannelMessage:
    """Normalized ticket input contract produced by every channel adapter."""
    sender_name: str
    sender_id: str
    channel: str
    text: str
    timestamp: str
    thread_id: Optional[str] = None
    sender_email: Optional[str] = None
    external_message_id: Optional[str] = None
    thread_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ChannelAdapter(ABC):
    """Abstract Base Class for Support Desk communication channel adapters."""

    channel_name: str = "base"

    def is_configured(self) -> bool:
        """Returns True if required environment credentials are present."""
        return False

    def is_sender_allowed(self, message: NormalizedChannelMessage) -> bool:
        """Checks whether the sender/chat/channel is permitted by .env allowlists."""
        return True

    @abstractmethod
    def parse_incoming(self, payload: Dict[str, Any]) -> NormalizedChannelMessage:
        """Parses a channel-specific payload into a NormalizedChannelMessage."""
        pass

    @abstractmethod
    def send_reply(
        self,
        thread_id: Optional[str],
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Sends a sanitized status or resolution reply back to the original thread."""
        pass

    def send_notification(
        self,
        destination: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Backwards-compatible alias delegating outbound notifications to send_reply."""
        return self.send_reply(thread_id=destination, text=text, metadata=metadata)


class WebhookAdapter(ChannelAdapter):
    """Standard HTTP JSON Webhook adapter for API integrations."""

    channel_name = "webhook"

    def is_configured(self) -> bool:
        return True

    def parse_incoming(self, payload: Dict[str, Any]) -> NormalizedChannelMessage:
        sender_name = (
            payload.get("client_name")
            or payload.get("sender_name")
            or payload.get("sender")
            or "Client User"
        )
        sender_email = (
            payload.get("client_email")
            or payload.get("sender_email")
            or payload.get("email")
            or "client@example.com"
        )
        text = (
            payload.get("message")
            or payload.get("text")
            or payload.get("query")
            or ""
        ).strip()
        channel = (payload.get("channel") or self.channel_name).lower()
        return NormalizedChannelMessage(
            sender_name=str(sender_name),
            sender_id=str(payload.get("sender_id") or sender_email or sender_name),
            sender_email=str(sender_email),
            channel=channel,
            text=text,
            timestamp=payload.get("timestamp") or datetime.now(timezone.utc).isoformat(),
            thread_id=payload.get("thread_id"),
            external_message_id=payload.get("external_message_id"),
            thread_url=payload.get("thread_url"),
            metadata=payload.get("metadata") or {},
        )

    def send_reply(
        self,
        thread_id: Optional[str],
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        safe_text = sanitize_channel_reply(text)
        logger.info(f"[WebhookAdapter] Reply recorded for thread {thread_id}: {safe_text[:80]}")
        return True


class SimulatedAdapter(WebhookAdapter):
    """Adapter for operator-entered test incidents from the Support Desk UI modal."""

    channel_name = "simulated"


def get_channel_adapter(channel: str = "webhook") -> ChannelAdapter:
    """Factory helper returning the adapter corresponding to a channel identifier."""
    ch = (channel or "webhook").strip().lower()
    if ch == "email":
        from backend.support.channels.email import EmailAdapter
        return EmailAdapter()
    if ch == "slack":
        from backend.support.channels.slack import SlackAdapter
        return SlackAdapter()
    if ch in ("teams", "msteams"):
        from backend.support.channels.teams import TeamsAdapterStub
        return TeamsAdapterStub()
    if ch == "simulated":
        return SimulatedAdapter()
    return WebhookAdapter()


# Re-export channel adapters for backwards-compatible imports
from backend.support.channels.slack import SlackAdapterStub  # noqa: E402, F401
from backend.support.channels.teams import TeamsAdapterStub  # noqa: E402, F401
