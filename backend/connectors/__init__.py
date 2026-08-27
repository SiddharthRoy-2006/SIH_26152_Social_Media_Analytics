# backend/connectors/__init__.py
"""
SocialIQ platform connector layer.

Each connector adapts a specific social-media API into normalised
SocialRecord objects that the analytics pipeline can consume.
"""

from backend.connectors.base import (
    PlatformCapability,
    PlatformConnector,
    PlatformStatus,
    SocialRecord,
)
from backend.connectors.registry import ConnectorRegistry, get_registry
from backend.connectors.youtube_connector import YouTubeConnector
from backend.connectors.telegram_connector import TelegramConnector
from backend.connectors.reddit_connector import RedditConnector
from backend.connectors.twitter_connector import TwitterConnector
from backend.connectors.meta_connectors import InstagramConnector, FacebookConnector

__all__ = [
    "PlatformCapability",
    "PlatformConnector",
    "PlatformStatus",
    "SocialRecord",
    "ConnectorRegistry",
    "get_registry",
    "YouTubeConnector",
    "TelegramConnector",
    "RedditConnector",
    "TwitterConnector",
    "InstagramConnector",
    "FacebookConnector",
]


