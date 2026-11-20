"""
Channel Adapters for Support Desk:
Provides an extensible adapter architecture supporting Webhooks, Slack, and Microsoft Teams.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger("support_adapters")

class ChannelAdapter(ABC):
    """Abstract Base Class for Support Channel Adapters."""

    @abstractmethod
    def parse_incoming(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parses channel-specific webhook payload into normalized support message."""
        pass

    @abstractmethod
    def send_notification(self, destination: str, text: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Dispatches outbound response or notification back to the client channel."""
        pass


class WebhookAdapter(ChannelAdapter):
    """Standard HTTP JSON Webhook adapter for web applications and client portals."""

    def parse_incoming(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "client_name": payload.get("client_name") or payload.get("sender_name") or "Client User",
            "client_email": payload.get("client_email") or payload.get("email") or "client@example.com",
            "channel": "webhook",
            "message": payload.get("message") or payload.get("text") or payload.get("query", "").strip(),
            "metadata": payload.get("metadata", {})
        }

    def send_notification(self, destination: str, text: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        logger.info(f"[WebhookAdapter] Dispatched notification to {destination}: {text[:80]}...")
        return True


class SlackAdapterStub(ChannelAdapter):
    """
    Slack Event API & Slash Command Adapter Stub.
    
    Enterprise Configuration Reference:
    - Inbound Endpoint: POST /support/messages?channel=slack
    - Header Verification: X-Slack-Signature & X-Slack-Request-Timestamp
    - Payload format: urlencoded form (command, text, user_name, response_url)
    """

    def parse_incoming(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Normalizes Slack slash command or message action payload
        event = payload.get("event", {})
        user = payload.get("user_name") or event.get("user") or "Slack User"
        text = payload.get("text") or event.get("text", "")
        response_url = payload.get("response_url")

        return {
            "client_name": user,
            "client_email": f"{user.lower().replace(' ', '.')}@slack-tenant.internal",
            "channel": "slack",
            "message": text.strip(),
            "metadata": {"response_url": response_url, "channel_id": payload.get("channel_id")}
        }

    def send_notification(self, destination: str, text: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        # In production: POST to metadata['response_url'] or chat.postMessage with Block Kit
        logger.info(f"[SlackAdapterStub] Simulated Slack BlockKit delivery to {destination}: {text[:80]}...")
        return True


class TeamsAdapterStub(ChannelAdapter):
    """
    Microsoft Teams Bot Framework Activity Adapter Stub.
    
    Enterprise Configuration Reference:
    - Inbound Endpoint: POST /support/messages?channel=teams
    - Header Verification: Authorization: Bearer <JWT from login.microsoftonline.com>
    - Payload format: JSON Activity schema (type: 'message', from: {id, name}, text)
    """

    def parse_incoming(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        sender = payload.get("from", {})
        user_name = sender.get("name", "Teams Member")
        text = payload.get("text", "")
        service_url = payload.get("serviceUrl")

        return {
            "client_name": user_name,
            "client_email": f"{user_name.lower().replace(' ', '.')}@msteams.internal",
            "channel": "teams",
            "message": text.strip(),
            "metadata": {"service_url": service_url, "conversation_id": payload.get("conversation", {}).get("id")}
        }

    def send_notification(self, destination: str, text: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        # In production: POST AdaptiveCard JSON to Bot Framework serviceUrl
        logger.info(f"[TeamsAdapterStub] Simulated MS Teams AdaptiveCard delivery to {destination}: {text[:80]}...")
        return True


def get_channel_adapter(channel: str = "webhook") -> ChannelAdapter:
    """Factory helper to obtain the corresponding channel adapter."""
    ch = (channel or "webhook").lower()
    if ch == "slack":
        return SlackAdapterStub()
    if ch in ("teams", "msteams"):
        return TeamsAdapterStub()
    return WebhookAdapter()
