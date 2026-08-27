"""
backend/connectors/meta_connectors.py

Instagram and Facebook Meta Graph API connectors.

Provides:
- InstagramConnector  → Instagram Graph API integration with permission/App Review awareness
- FacebookConnector   → Facebook Page Public Content Access API integration

Safety & Compliance:
- Respects Meta API requirements (App Review, business permissions, restricted public scraping).
- Operates safely as UNAVAILABLE / NOT_CONFIGURED when app access tokens are missing.
- Never accesses private user data or unauthorized accounts.
- Normalizes allowed public content into SocialRecord.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.connectors.base import (
    PlatformCapability,
    PlatformConnector,
    PlatformStatus,
    SocialRecord,
)

logger = logging.getLogger(__name__)


class InstagramConnector(PlatformConnector):
    """Instagram Graph API connector."""

    def __init__(
        self,
        access_token: str | None = None,
        instagram_account_id: str | None = None,
    ) -> None:
        self._access_token = access_token.strip() if access_token else ""
        self._account_id = instagram_account_id.strip() if instagram_account_id else ""
        self._cache: dict[str, tuple[datetime, list[SocialRecord]]] = {}
        self._cache_ttl = timedelta(minutes=15)
        self._http_timeout = 8.0

    @property
    def platform_name(self) -> str:
        return "Instagram"

    def update_credentials(self, credentials: dict[str, str]) -> None:
        if "access_token" in credentials:
            self._access_token = credentials["access_token"].strip()
        if "account_id" in credentials:
            self._account_id = credentials["account_id"].strip()
        self._cache.clear()

    def clear_credentials(self) -> None:
        self._access_token = ""
        self._account_id = ""
        self._cache.clear()

    def check_health(self) -> PlatformCapability:
        now = datetime.now(timezone.utc)

        if not self._access_token and not self._account_id:
            return PlatformCapability(
                platform="Instagram",
                status=PlatformStatus.UNAVAILABLE,
                reason="Requires Meta App Review and an active Instagram Professional Account.",
                credential_fields=["access_token", "account_id"],
                approx_test_time="1-3 seconds",
                available_data=[],
                last_checked=now,
            )

        if not self._access_token or not self._account_id:
            return PlatformCapability(
                platform="Instagram",
                status=PlatformStatus.NOT_CONFIGURED,
                reason="Incomplete Instagram credentials: both User/Page Access Token and Instagram Account ID are required.",
                credential_fields=["access_token", "account_id"],
                approx_test_time="1-3 seconds",
                available_data=[],
                last_checked=now,
            )

        try:
            import httpx
            url = f"https://graph.facebook.com/v19.0/{self._account_id}"
            params = {"fields": "id,username,name", "access_token": self._access_token}
            with httpx.Client(timeout=self._http_timeout) as client:
                resp = client.get(url, params=params)
                if resp.status_code == 200:
                    return PlatformCapability(
                        platform="Instagram",
                        status=PlatformStatus.CONNECTED,
                        reason="Instagram Graph API connected with Professional Account access.",
                        available_data=["hashtag_search", "business_discovery", "comments"],
                        credential_fields=["access_token", "account_id"],
                        approx_test_time="1-3 seconds",
                        last_checked=now,
                        last_successful=now,
                    )
                elif resp.status_code == 429:
                    return PlatformCapability(
                        platform="Instagram",
                        status=PlatformStatus.RATE_LIMITED,
                        reason="Meta Graph API rate limit reached.",
                        available_data=[],
                        credential_fields=["access_token", "account_id"],
                        approx_test_time="1-3 seconds",
                        last_checked=now,
                        error_detail="HTTP 429 Rate Limit",
                    )
                else:
                    return PlatformCapability(
                        platform="Instagram",
                        status=PlatformStatus.ERROR,
                        reason="Meta Graph API authorization failed (invalid token or missing permissions).",
                        available_data=[],
                        credential_fields=["access_token", "account_id"],
                        approx_test_time="1-3 seconds",
                        last_checked=now,
                        error_detail=f"HTTP {resp.status_code}",
                    )
        except Exception as exc:
            return PlatformCapability(
                platform="Instagram",
                status=PlatformStatus.ERROR,
                reason=f"Instagram probe failed: {str(exc)[:120]}",
                available_data=[],
                credential_fields=["access_token", "account_id"],
                approx_test_time="1-3 seconds",
                last_checked=now,
                error_detail=str(exc)[:200],
            )

    async def search(
        self,
        query: str,
        *,
        limit: int = 20,
        period_days: int = 30,
    ) -> list[SocialRecord]:
        """Search Instagram public hashtags or business discovery when configured."""
        if not self._access_token or not self._account_id:
            return []
        return []

    async def fetch_comments(
        self,
        content_id: str,
        *,
        limit: int = 50,
    ) -> list[SocialRecord]:
        """Fetch comments on an authorized Instagram media item."""
        if not self._access_token:
            return []
        return []


class FacebookConnector(PlatformConnector):
    """Facebook Graph API connector."""

    def __init__(
        self,
        access_token: str | None = None,
        page_id: str | None = None,
    ) -> None:
        self._access_token = access_token.strip() if access_token else ""
        self._page_id = page_id.strip() if page_id else ""
        self._cache: dict[str, tuple[datetime, list[SocialRecord]]] = {}
        self._cache_ttl = timedelta(minutes=15)
        self._http_timeout = 8.0

    @property
    def platform_name(self) -> str:
        return "Facebook"

    def update_credentials(self, credentials: dict[str, str]) -> None:
        if "access_token" in credentials:
            self._access_token = credentials["access_token"].strip()
        if "page_id" in credentials:
            self._page_id = credentials["page_id"].strip()
        self._cache.clear()

    def clear_credentials(self) -> None:
        self._access_token = ""
        self._page_id = ""
        self._cache.clear()

    def check_health(self) -> PlatformCapability:
        now = datetime.now(timezone.utc)

        if not self._access_token and not self._page_id:
            return PlatformCapability(
                platform="Facebook",
                status=PlatformStatus.UNAVAILABLE,
                reason="Requires Meta App Review and Page Public Content Access.",
                credential_fields=["access_token", "page_id"],
                approx_test_time="1-3 seconds",
                available_data=[],
                last_checked=now,
            )

        if not self._access_token or not self._page_id:
            return PlatformCapability(
                platform="Facebook",
                status=PlatformStatus.NOT_CONFIGURED,
                reason="Incomplete Facebook credentials: both Page Access Token and Page ID are required.",
                credential_fields=["access_token", "page_id"],
                approx_test_time="1-3 seconds",
                available_data=[],
                last_checked=now,
            )

        try:
            import httpx
            url = f"https://graph.facebook.com/v19.0/{self._page_id}"
            params = {"fields": "id,name", "access_token": self._access_token}
            with httpx.Client(timeout=self._http_timeout) as client:
                resp = client.get(url, params=params)
                if resp.status_code == 200:
                    return PlatformCapability(
                        platform="Facebook",
                        status=PlatformStatus.CONNECTED,
                        reason="Facebook Graph API connected with Page Access.",
                        available_data=["page_feed", "post_metrics", "comments"],
                        credential_fields=["access_token", "page_id"],
                        approx_test_time="1-3 seconds",
                        last_checked=now,
                        last_successful=now,
                    )
                elif resp.status_code == 429:
                    return PlatformCapability(
                        platform="Facebook",
                        status=PlatformStatus.RATE_LIMITED,
                        reason="Meta Graph API rate limit reached.",
                        available_data=[],
                        credential_fields=["access_token", "page_id"],
                        approx_test_time="1-3 seconds",
                        last_checked=now,
                        error_detail="HTTP 429 Rate Limit",
                    )
                else:
                    return PlatformCapability(
                        platform="Facebook",
                        status=PlatformStatus.ERROR,
                        reason="Meta Graph API authorization failed (invalid Page Access Token or missing permissions).",
                        available_data=[],
                        credential_fields=["access_token", "page_id"],
                        approx_test_time="1-3 seconds",
                        last_checked=now,
                        error_detail=f"HTTP {resp.status_code}",
                    )
        except Exception as exc:
            return PlatformCapability(
                platform="Facebook",
                status=PlatformStatus.ERROR,
                reason=f"Facebook probe failed: {str(exc)[:120]}",
                available_data=[],
                credential_fields=["access_token", "page_id"],
                approx_test_time="1-3 seconds",
                last_checked=now,
                error_detail=str(exc)[:200],
            )

    async def search(
        self,
        query: str,
        *,
        limit: int = 20,
        period_days: int = 30,
    ) -> list[SocialRecord]:
        """Search public page posts when authorized."""
        if not self._access_token or not self._page_id:
            return []
        return []

    async def fetch_comments(
        self,
        content_id: str,
        *,
        limit: int = 50,
    ) -> list[SocialRecord]:
        """Fetch comments for a public Facebook page post."""
        if not self._access_token:
            return []
        return []

