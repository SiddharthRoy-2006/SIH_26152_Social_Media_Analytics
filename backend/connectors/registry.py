"""
backend/connectors/registry.py

Central connector registry.

The registry holds all configured connectors and exposes:
- per-platform health/capability queries
- aggregated status for the "All Platforms" popup
- connector lookup by platform name
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.connectors.base import (
    PlatformCapability,
    PlatformConnector,
    PlatformStatus,
)


# Default capability entries for platforms before real connector registration
_DEFAULT_CAPABILITIES: dict[str, PlatformCapability] = {
    "YouTube": PlatformCapability(
        platform="YouTube",
        status=PlatformStatus.NOT_CONFIGURED,
        reason="YouTube Data API key is not configured. Set YOUTUBE_API_KEY.",
        available_data=["search", "video_details", "comments"],
    ),
    "Telegram": PlatformCapability(
        platform="Telegram",
        status=PlatformStatus.NOT_CONFIGURED,
        reason="Telegram MTProto credentials not configured. Set TELEGRAM_API_ID and TELEGRAM_API_HASH.",
        available_data=["public_channel_search", "messages"],
    ),
    "Reddit": PlatformCapability(
        platform="Reddit",
        status=PlatformStatus.NOT_CONFIGURED,
        reason="Reddit API credentials not configured. Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET.",
        available_data=["subreddit_search", "posts", "comments"],
    ),
    "Twitter / X": PlatformCapability(
        platform="Twitter / X",
        status=PlatformStatus.UNAVAILABLE,
        reason="X API requires paid credits. No free tier is available.",
        available_data=[],
    ),
    "Instagram": PlatformCapability(
        platform="Instagram",
        status=PlatformStatus.UNAVAILABLE,
        reason="Requires Meta App Review and a Business/Creator account.",
        available_data=[],
    ),
    "Facebook": PlatformCapability(
        platform="Facebook",
        status=PlatformStatus.UNAVAILABLE,
        reason="Requires Meta App Review and Page Public Content Access.",
        available_data=[],
    ),
}


class ConnectorRegistry:
    """
    Singleton-style registry of all platform connectors.

    Usage:
        registry = ConnectorRegistry()
        registry.register(YouTubeConnector(api_key="…"))
        cap = registry.get_capability("YouTube")
        all_caps = registry.all_capabilities()
    """

    def __init__(self) -> None:
        self._connectors: dict[str, PlatformConnector] = {}
        self._capabilities: dict[str, PlatformCapability] = dict(_DEFAULT_CAPABILITIES)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, connector: PlatformConnector) -> None:
        """Register a connector and probe its health."""
        name = connector.platform_name
        self._connectors[name] = connector
        try:
            cap = connector.check_health()
            self._capabilities[name] = cap
        except Exception as exc:
            self._capabilities[name] = PlatformCapability(
                platform=name,
                status=PlatformStatus.ERROR,
                reason=f"Health check failed: {exc}",
                last_checked=datetime.now(timezone.utc),
                error_detail=str(exc),
            )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_connector(self, platform: str) -> PlatformConnector | None:
        """Return the connector for *platform*, or None."""
        return self._connectors.get(platform)

    def get_capability(self, platform: str) -> PlatformCapability:
        """Return the capability record for *platform*."""
        return self._capabilities.get(
            platform,
            PlatformCapability(
                platform=platform,
                status=PlatformStatus.NOT_CONFIGURED,
                reason="No connector registered for this platform.",
            ),
        )

    def all_capabilities(self) -> dict[str, PlatformCapability]:
        """Return a copy of all known platform capabilities."""
        return dict(self._capabilities)

    def refresh_health(self, platform: str) -> PlatformCapability:
        """Re-probe a single connector and update its capability."""
        connector = self._connectors.get(platform)
        if connector is None:
            return self.get_capability(platform)
        try:
            cap = connector.check_health()
            self._capabilities[platform] = cap
            return cap
        except Exception as exc:
            cap = PlatformCapability(
                platform=platform,
                status=PlatformStatus.ERROR,
                reason=f"Health check failed: {exc}",
                last_checked=datetime.now(timezone.utc),
                error_detail=str(exc),
            )
            self._capabilities[platform] = cap
            return cap

    def update_credentials(self, platform: str, credentials: dict[str, str]) -> PlatformCapability:
        """Update credentials for *platform* connector and probe health immediately."""
        connector = self._connectors.get(platform)
        if connector is None:
            cap = PlatformCapability(
                platform=platform,
                status=PlatformStatus.NOT_CONFIGURED,
                reason=f"No connector registered for {platform}.",
                last_checked=datetime.now(timezone.utc),
            )
            self._capabilities[platform] = cap
            return cap

        try:
            connector.update_credentials(credentials)
            cap = connector.check_health()
            self._capabilities[platform] = cap
            return cap
        except Exception as exc:
            cap = PlatformCapability(
                platform=platform,
                status=PlatformStatus.ERROR,
                reason=f"Credential test failed: {exc}",
                last_checked=datetime.now(timezone.utc),
                error_detail=str(exc),
            )
            self._capabilities[platform] = cap
            return cap

    def clear_credentials(self, platform: str) -> PlatformCapability:
        """Clear credentials for *platform* connector and probe health."""
        connector = self._connectors.get(platform)
        if connector is None:
            return self.get_capability(platform)

        try:
            connector.clear_credentials()
            cap = connector.check_health()
            self._capabilities[platform] = cap
            return cap
        except Exception as exc:
            cap = PlatformCapability(
                platform=platform,
                status=PlatformStatus.ERROR,
                reason=f"Error clearing credentials: {exc}",
                last_checked=datetime.now(timezone.utc),
                error_detail=str(exc),
            )
            self._capabilities[platform] = cap
            return cap

    def test_credentials(self, platform: str, credentials: dict[str, str] | None = None) -> PlatformCapability:
        """Test credentials for *platform*."""
        if credentials:
            return self.update_credentials(platform, credentials)
        return self.refresh_health(platform)

    def connected_platforms(self) -> list[str]:
        """Return names of platforms with CONNECTED or LIMITED status."""
        return [
            name
            for name, cap in self._capabilities.items()
            if cap.status in (PlatformStatus.CONNECTED, PlatformStatus.LIMITED)
        ]

    def to_dict(self) -> dict[str, Any]:
        """Serialise all capabilities for API responses."""
        return {
            name: cap.to_dict()
            for name, cap in self._capabilities.items()
        }


_global_registry: ConnectorRegistry | None = None


def get_registry() -> ConnectorRegistry:
    """Return or initialize the global connector registry singleton."""
    global _global_registry
    if _global_registry is None:
        from backend.connectors.youtube_connector import YouTubeConnector
        from backend.connectors.telegram_connector import TelegramConnector
        from backend.connectors.reddit_connector import RedditConnector
        from backend.connectors.twitter_connector import TwitterConnector
        from backend.connectors.meta_connectors import InstagramConnector, FacebookConnector
        from backend.core.config import settings

        reg = ConnectorRegistry()
        youtube_conn = YouTubeConnector(api_key=settings.youtube_api_key)
        telegram_conn = TelegramConnector(
            api_id=settings.telegram_api_id,
            api_hash=settings.telegram_api_hash,
            bot_token=settings.telegram_bot_token,
        )
        reddit_conn = RedditConnector(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
        )
        twitter_conn = TwitterConnector(
            bearer_token=settings.twitter_bearer_token,
        )
        instagram_conn = InstagramConnector(
            access_token=settings.instagram_access_token,
            instagram_account_id=settings.instagram_account_id,
        )
        facebook_conn = FacebookConnector(
            access_token=settings.facebook_access_token,
            page_id=settings.facebook_page_id,
        )

        reg.register(youtube_conn)
        reg.register(telegram_conn)
        reg.register(reddit_conn)
        reg.register(twitter_conn)
        reg.register(instagram_conn)
        reg.register(facebook_conn)
        _global_registry = reg
    return _global_registry




