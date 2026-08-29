"""
backend/connectors/reddit_connector.py

Reddit social-data connector for public posts, discussions, and comment trees.

Provides:
- search(query)        → search public Reddit submissions → normalised SocialRecord per post
- fetch_comments(id)   → retrieves comment trees → normalised SocialRecord per comment
- check_health()       → lightweight credential / API probe

Safety & Quota awareness:
- Operates safely as NOT_CONFIGURED when credentials are not supplied.
- Uses OAuth2 client_credentials grant or public JSON endpoint with dedicated User-Agent.
- In-memory caching with 15-minute TTL to respect Reddit's 60 req/min rate limits.
- Never exposes client secrets in logs or payloads.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
import urllib.parse

import httpx

from backend.connectors.base import (
    PlatformCapability,
    PlatformConnector,
    PlatformStatus,
    SocialRecord,
)

logger = logging.getLogger(__name__)

_REDDIT_TIME_FILTER = {
    1: "day",
    7: "week",
    30: "month",
    365: "year",
}


class RedditConnector(PlatformConnector):
    """Reddit public submission and comment connector."""

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        user_agent: str = "SocialIQ-Analytics/0.2.0 (SIH-26152; Educational Platform)",
    ) -> None:
        self._client_id = client_id.strip() if client_id else ""
        self._client_secret = client_secret.strip() if client_secret else ""
        self._user_agent = user_agent
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None
        self._cache: dict[str, tuple[datetime, list[SocialRecord]]] = {}
        self._cache_ttl = timedelta(minutes=15)
        self._http_timeout = 8.0

    # ------------------------------------------------------------------
    # PlatformConnector interface
    # ------------------------------------------------------------------

    @property
    def platform_name(self) -> str:
        return "Reddit"

    def update_credentials(self, credentials: dict[str, str]) -> None:
        if "client_id" in credentials:
            self._client_id = credentials["client_id"].strip()
        if "client_secret" in credentials:
            self._client_secret = credentials["client_secret"].strip()
        self._access_token = None
        self._token_expires_at = None
        self._cache.clear()

    def clear_credentials(self) -> None:
        self._client_id = ""
        self._client_secret = ""
        self._access_token = None
        self._token_expires_at = None
        self._cache.clear()

    def check_health(self) -> PlatformCapability:
        now = datetime.now(timezone.utc)

        app_layer = {
            "name": "Reddit OAuth2 App (Read-Only Script/App)",
            "access_type": "OAuth 2.0 Client ID & Client Secret",
            "usage": "Subreddit public submission search, post score tracking, comment tree retrieval.",
            "provides": ["Subreddit submissions", "Upvotes & score distribution", "Comment trees & replies"],
            "auth_required": False,
            "status": "CONNECTED" if (self._client_id and self._client_secret) else "NOT_CONFIGURED",
        }
        user_layer = {
            "name": "Reddit User Authorization",
            "access_type": "OAuth 2.0 User Access Token",
            "usage": "Authenticated user subscribed feed and moderation telemetry.",
            "provides": ["User subreddit feeds", "Vote stream ingestion"],
            "auth_required": True,
            "status": "NOT_CONNECTED",
        }

        access_layers = [app_layer, user_layer]
        supported_metrics = ["posts", "upvotes", "score", "comments", "sentiment", "subreddit_metadata"]
        unsupported_metrics = ["direct_shares", "private_messages", "age_demographics"]

        if not self._client_id and not self._client_secret:
            return PlatformCapability(
                platform="Reddit",
                status=PlatformStatus.NOT_CONFIGURED,
                reason="Reddit OAuth Client ID and Client Secret are not configured.",
                credential_fields=["client_id", "client_secret"],
                approx_test_time="1-3 seconds",
                available_data=["subreddit_search", "posts", "comments"],
                last_checked=now,
                access_layers=access_layers,
                supported_metrics=supported_metrics,
                unsupported_metrics=unsupported_metrics,
            )

        if (self._client_id and not self._client_secret) or (self._client_secret and not self._client_id):
            return PlatformCapability(
                platform="Reddit",
                status=PlatformStatus.NOT_CONFIGURED,
                reason="Incomplete Reddit credentials: both Reddit OAuth Client ID and Client Secret are required.",
                credential_fields=["client_id", "client_secret"],
                approx_test_time="1-3 seconds",
                available_data=["subreddit_search", "posts", "comments"],
                last_checked=now,
                access_layers=access_layers,
                supported_metrics=supported_metrics,
                unsupported_metrics=unsupported_metrics,
            )

        try:
            token = self._get_access_token_sync()
            if token:
                app_layer["status"] = "CONNECTED"
                return PlatformCapability(
                    platform="Reddit",
                    status=PlatformStatus.CONNECTED,
                    reason="Reddit OAuth2 API connected and operational.",
                    available_data=["subreddit_search", "posts", "comments"],
                    credential_fields=["client_id", "client_secret"],
                    approx_test_time="1-3 seconds",
                    last_checked=now,
                    last_successful=now,
                    access_layers=access_layers,
                    supported_metrics=supported_metrics,
                    unsupported_metrics=unsupported_metrics,
                )
            else:
                app_layer["status"] = "INVALID_CREDENTIAL"
                return PlatformCapability(
                    platform="Reddit",
                    status=PlatformStatus.ERROR,
                    reason="Reddit OAuth2 authentication failed with provided Client ID / Secret.",
                    available_data=["subreddit_search", "posts", "comments"],
                    credential_fields=["client_id", "client_secret"],
                    approx_test_time="1-3 seconds",
                    last_checked=now,
                    error_detail="Authentication token request returned no token",
                    access_layers=access_layers,
                    supported_metrics=supported_metrics,
                    unsupported_metrics=unsupported_metrics,
                )
        except httpx.HTTPStatusError as exc:
            status = PlatformStatus.ERROR
            reason = f"Reddit API probe returned HTTP {exc.response.status_code}."
            if exc.response.status_code == 429:
                status = PlatformStatus.RATE_LIMITED
                reason = "Reddit API rate limit reached (60 req/min limit)."
                app_layer["status"] = "RATE_LIMITED"
            elif exc.response.status_code in (401, 403):
                reason = "Reddit API credentials rejected (invalid Client ID or Secret)."
                app_layer["status"] = "INVALID_CREDENTIAL"

            return PlatformCapability(
                platform="Reddit",
                status=status,
                reason=reason,
                available_data=["subreddit_search", "posts", "comments"],
                credential_fields=["client_id", "client_secret"],
                approx_test_time="1-3 seconds",
                last_checked=now,
                error_detail=f"HTTP {exc.response.status_code}",
                access_layers=access_layers,
                supported_metrics=supported_metrics,
                unsupported_metrics=unsupported_metrics,
            )
        except Exception as exc:
            return PlatformCapability(
                platform="Reddit",
                status=PlatformStatus.ERROR,
                reason=f"Reddit probe failed: {str(exc)[:120]}",
                available_data=["subreddit_search", "posts", "comments"],
                credential_fields=["client_id", "client_secret"],
                approx_test_time="1-3 seconds",
                last_checked=now,
                error_detail=str(exc)[:200],
                access_layers=access_layers,
                supported_metrics=supported_metrics,
                unsupported_metrics=unsupported_metrics,
            )


    async def search(
        self,
        query: str,
        *,
        limit: int = 25,
        period_days: int = 30,
    ) -> list[SocialRecord]:
        """
        Search Reddit submissions matching *query*.
        """
        if not self._is_configured():
            return []

        cache_key = f"reddit_search:{query}:{limit}:{period_days}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        records: list[SocialRecord] = []
        try:
            t_filter = _REDDIT_TIME_FILTER.get(period_days, "month")
            token = await self._get_access_token_async()
            
            headers = {"User-Agent": self._user_agent}
            if token:
                headers["Authorization"] = f"bearer {token}"
                base_url = "https://oauth.reddit.com/search"
            else:
                base_url = "https://www.reddit.com/search.json"

            params = {
                "q": query,
                "sort": "relevance",
                "t": t_filter,
                "limit": min(limit, 50),
                "type": "link",
            }

            async with httpx.AsyncClient(timeout=self._http_timeout) as client:
                resp = await client.get(base_url, headers=headers, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    records = self._parse_reddit_listing(data)

            self._set_cached(cache_key, records)
            logger.info("Reddit search for %r returned %d submissions", query, len(records))
            return records

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                logger.warning("Reddit rate limit hit during search for %r", query)
            else:
                logger.error("Reddit search HTTP error: %s", exc)
            return []
        except Exception as exc:
            logger.error("Reddit search error for %r: %s", query, exc)
            return []

    async def fetch_comments(
        self,
        content_id: str,
        *,
        limit: int = 50,
    ) -> list[SocialRecord]:
        """
        Fetch top comments for a specific Reddit post.
        content_id: e.g. "t3_12345" or "12345"
        """
        if not self._is_configured():
            return []

        post_id = content_id.replace("t3_", "")
        cache_key = f"reddit_comments:{post_id}:{limit}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        records: list[SocialRecord] = []
        try:
            token = await self._get_access_token_async()
            headers = {"User-Agent": self._user_agent}
            if token:
                headers["Authorization"] = f"bearer {token}"
                base_url = f"https://oauth.reddit.com/comments/{post_id}"
            else:
                base_url = f"https://www.reddit.com/comments/{post_id}.json"

            params = {"limit": min(limit, 50), "depth": 2, "sort": "top"}

            async with httpx.AsyncClient(timeout=self._http_timeout) as client:
                resp = await client.get(base_url, headers=headers, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    # Reddit returns a 2-element list: [0]=post listing, [1]=comments listing
                    if isinstance(data, list) and len(data) > 1:
                        comments_listing = data[1]
                        records = self._parse_reddit_comments(comments_listing, post_id, limit)

            self._set_cached(cache_key, records)
            logger.info("Reddit comments for %s: %d comments", post_id, len(records))
            return records

        except Exception as exc:
            logger.error("Reddit fetch_comments error for %s: %s", content_id, exc)
            return []

    # ------------------------------------------------------------------
    # Internal parsers & token management
    # ------------------------------------------------------------------

    def _is_configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    def _get_access_token_sync(self) -> str | None:
        """Obtain OAuth2 application-only bearer token synchronously."""
        now = datetime.now(timezone.utc)
        if self._access_token and self._token_expires_at and now < self._token_expires_at:
            return self._access_token

        if not self._is_configured():
            return None

        url = "https://www.reddit.com/api/v1/access_token"
        auth = (self._client_id, self._client_secret)
        headers = {"User-Agent": self._user_agent}
        data = {"grant_type": "client_credentials"}

        with httpx.Client(timeout=self._http_timeout) as client:
            resp = client.post(url, auth=auth, headers=headers, data=data)
            resp.raise_for_status()
            payload = resp.json()
            token = payload.get("access_token")
            expires_in = payload.get("expires_in", 3600)
            if token:
                self._access_token = token
                self._token_expires_at = now + timedelta(seconds=max(60, expires_in - 60))
                return token
        return None

    async def _get_access_token_async(self) -> str | None:
        """Obtain OAuth2 application-only bearer token asynchronously."""
        now = datetime.now(timezone.utc)
        if self._access_token and self._token_expires_at and now < self._token_expires_at:
            return self._access_token

        if not self._is_configured():
            return None

        url = "https://www.reddit.com/api/v1/access_token"
        auth = (self._client_id, self._client_secret)
        headers = {"User-Agent": self._user_agent}
        data = {"grant_type": "client_credentials"}

        async with httpx.AsyncClient(timeout=self._http_timeout) as client:
            resp = await client.post(url, auth=auth, headers=headers, data=data)
            if resp.status_code == 200:
                payload = resp.json()
                token = payload.get("access_token")
                expires_in = payload.get("expires_in", 3600)
                if token:
                    self._access_token = token
                    self._token_expires_at = now + timedelta(seconds=max(60, expires_in - 60))
                    return token
        return None

    def _parse_reddit_listing(self, data: dict[str, Any]) -> list[SocialRecord]:
        """Convert a Reddit Listing JSON object into SocialRecords."""
        records: list[SocialRecord] = []
        children = data.get("data", {}).get("children", [])
        
        for item in children:
            if item.get("kind") != "t3":
                continue
            p = item.get("data", {})
            post_id = p.get("id", "")
            title = p.get("title", "")
            selftext = p.get("selftext", "")
            text = f"{title}\n{selftext}" if selftext else title

            created_utc = p.get("created_utc", 0)
            try:
                ts = datetime.fromtimestamp(created_utc, tz=timezone.utc)
            except Exception:
                ts = datetime.now(timezone.utc)

            keywords = []
            if p.get("subreddit"):
                keywords.append(f"r/{p['subreddit']}")
            if p.get("link_flair_text"):
                keywords.append(p["link_flair_text"])

            records.append(
                SocialRecord(
                    platform="Reddit",
                    content_id=f"t3_{post_id}",
                    content_type="post",
                    timestamp=ts,
                    text=text,
                    author_name=p.get("author", "[deleted]"),
                    engagement={
                        "score": int(p.get("score", 0)),
                        "upvotes": int(p.get("ups", 0)),
                        "comments": int(p.get("num_comments", 0)),
                        "shares": int(p.get("num_crossposts", 0)),
                    },
                    topic_keywords=keywords,
                    source_url=f"https://reddit.com{p.get('permalink', '')}",
                    raw_metadata={
                        "subreddit": p.get("subreddit"),
                        "upvote_ratio": p.get("upvote_ratio"),
                        "over_18": p.get("over_18", False),
                    },
                )
            )
        return records

    def _parse_reddit_comments(
        self,
        listing: dict[str, Any],
        post_id: str,
        limit: int = 50,
    ) -> list[SocialRecord]:
        """Convert a Reddit Comments Listing into SocialRecords."""
        records: list[SocialRecord] = []
        children = listing.get("data", {}).get("children", [])

        for item in children:
            if len(records) >= limit:
                break
            if item.get("kind") != "t1":
                continue
            c = item.get("data", {})
            body = c.get("body", "")
            if not body or body == "[deleted]" or body == "[removed]":
                continue

            created_utc = c.get("created_utc", 0)
            try:
                ts = datetime.fromtimestamp(created_utc, tz=timezone.utc)
            except Exception:
                ts = datetime.now(timezone.utc)

            records.append(
                SocialRecord(
                    platform="Reddit",
                    content_id=f"t1_{c.get('id', '')}",
                    content_type="comment",
                    timestamp=ts,
                    text=body,
                    author_name=c.get("author", "[deleted]"),
                    engagement={
                        "score": int(c.get("score", 0)),
                        "upvotes": int(c.get("ups", 0)),
                    },
                    source_url=f"https://reddit.com{c.get('permalink', '')}",
                    raw_metadata={"parent_id": c.get("parent_id", f"t3_{post_id}")},
                )
            )

        return records

    def _get_cached(self, key: str) -> list[SocialRecord] | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        cached_at, records = entry
        if datetime.now(timezone.utc) - cached_at > self._cache_ttl:
            del self._cache[key]
            return None
        return records

    def _set_cached(self, key: str, records: list[SocialRecord]) -> None:
        self._cache[key] = (datetime.now(timezone.utc), records)
