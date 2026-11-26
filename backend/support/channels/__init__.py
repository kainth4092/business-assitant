"""
Channel Adapter Package for Business Assistant Support Desk
"""

from backend.support.channels.email import EmailAdapter
from backend.support.channels.slack import SlackAdapter, SlackAdapterStub
from backend.support.channels.teams import TeamsAdapterStub

__all__ = [
    "EmailAdapter",
    "SlackAdapter",
    "SlackAdapterStub",
    "TeamsAdapterStub",
]
