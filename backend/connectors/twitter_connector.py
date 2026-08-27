"""
backend/connectors/twitter_connector.py

X / Twitter API v2 connector.

Provides:
- search(query)        → search recent public tweets → normalised SocialRecord per tweet
- fetch_comments(id)   → retrieves replies / conversation threads → normalised SocialRecord per reply
- check_health()       → lightweight bearer token / API probe

Safety & Quota awareness:
- Operates safely as UNAVAILABLE / NOT_CONFIGURED when bearer token is absent.
- Uses OAuth 2.0 Bearer Token (Application-Only) for read-only public endpoints.
- In-memory caching with 15-minute TTL to protect API credits and rate limits.
- Never exposes bearer tokens in logs or responses.
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


class TwitterConnector(PlatformConnector):
    """X / Twitter API v2 social media connector."""

    def __init__(
        self,
        bearer_token: str | None = None,
        user_agent: str = "SocialIQ-Analytics/0.2.0 (SIH-26152; Research Platform)",
    ) -> None:
        self._bearer_token = bearer_token.strip() if bearer_token else ""
        self._user_agent = user_agent
        self._cache: dict[str, tuple[datetime, list[SocialRecord]]] = {}
        self._cache_ttl = timedelta(minutes=15)
        self._http_timeout = 8.0

    # ------------------------------------------------------------------
    # PlatformConnector interface
    # ------------------------------------------------------------------

    @property
    def platform_name(self) -> str:
        return "Twitter / X"

    def update_credentials(self, credentials: dict[str, str]) -> None:
        if "bearer_token" in credentials:
            self._bearer_token = credentials["bearer_token"].strip()
        self._cache.clear()

    def clear_credentials(self) -> None:
        self._bearer_token = ""
        self._cache.clear()

    def check_health(self) -> PlatformCapability:
        now = datetime.now(timezone.utc)

        if not self._bearer_token:
            return PlatformCapability(
                platform="Twitter / X",
                status=PlatformStatus.UNAVAILABLE,
                reason="X API requires paid credits and a valid Bearer Token. No free tier is available.",
                credential_fields=["bearer_token"],
                approx_test_time="1-3 seconds",
                available_data=[],
                last_checked=now,
            )

        try:
            # Probe with lightweight user lookup
            url = "https://api.twitter.com/2/users/by/username/TwitterDev"
            headers = {
                "Authorization": f"Bearer {self._bearer_token}",
                "User-Agent": self._user_agent,
            }
            with httpx.Client(timeout=self._http_timeout) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    return PlatformCapability(
                        platform="Twitter / X",
                        status=PlatformStatus.CONNECTED,
                        reason="X API v2 bearer token verified and operational.",
                        available_data=["recent_search", "tweet_metrics", "conversations"],
                        credential_fields=["bearer_token"],
                        approx_test_time="1-3 seconds",
                        last_checked=now,
                        last_successful=now,
                    )
                elif resp.status_code == 429:
                    return PlatformCapability(
                        platform="Twitter / X",
                        status=PlatformStatus.RATE_LIMITED,
                        reason="X API rate limit encountered. 15-minute window cooldown active.",
                        available_data=["recent_search"],
                        credential_fields=["bearer_token"],
                        approx_test_time="1-3 seconds",
                        last_checked=now,
                        error_detail="HTTP 429 Rate Limit",
                    )
                elif resp.status_code in (401, 403):
                    # Check if error response mentions credits/billing
                    body = resp.text.lower()
                    if "credit" in body or "usage" in body or "billing" in body:
                        reason = "X API credits exhausted or pay-per-use billing required."
                    else:
                        reason = "X API Bearer Token is invalid or does not have v2 access permissions."
                    return PlatformCapability(
                        platform="Twitter / X",
                        status=PlatformStatus.ERROR,
                        reason=reason,
                        available_data=[],
                        credential_fields=["bearer_token"],
                        approx_test_time="1-3 seconds",
                        last_checked=now,
                        error_detail=f"HTTP {resp.status_code}",
                    )
                else:
                    return PlatformCapability(
                        platform="Twitter / X",
                        status=PlatformStatus.ERROR,
                        reason=f"X API probe returned HTTP {resp.status_code}.",
                        available_data=[],
                        credential_fields=["bearer_token"],
                        approx_test_time="1-3 seconds",
                        last_checked=now,
                        error_detail=f"HTTP {resp.status_code}",
                    )

        except Exception as exc:
            return PlatformCapability(
                platform="Twitter / X",
                status=PlatformStatus.ERROR,
                reason=f"X API connection failed: {str(exc)[:120]}",
                available_data=[],
                credential_fields=["bearer_token"],
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
        """
        Search recent public tweets matching *query*.
        """
        if not self._bearer_token:
            return []

        cache_key = f"x_search:{query}:{limit}:{period_days}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        records: list[SocialRecord] = []
        try:
            url = "https://api.twitter.com/2/tweets/search/recent"
            headers = {
                "Authorization": f"Bearer {self._bearer_token}",
                "User-Agent": self._user_agent,
            }
            params = {
                "query": f"{query} -is:retweet lang:en",
                "max_results": max(10, min(limit, 100)),
                "tweet.fields": "created_at,public_metrics,entities,author_id",
                "expansions": "author_id",
                "user.fields": "username,name",
            }

            async with httpx.AsyncClient(timeout=self._http_timeout) as client:
                resp = await client.get(url, headers=headers, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    records = self._parse_tweets(data)

            self._set_cached(cache_key, records)
            logger.info("X / Twitter search for %r returned %d tweets", query, len(records))
            return records

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                logger.warning("X API rate limit hit during search for %r", query)
            else:
                logger.error("X API search HTTP error: %s", exc)
            return []
        except Exception as exc:
            logger.error("X API search error for %r: %s", query, exc)
            return []

    async def fetch_comments(
        self,
        content_id: str,
        *,
        limit: int = 50,
    ) -> list[SocialRecord]:
        """
        Fetch conversation replies for a specific tweet.
        """
        if not self._bearer_token:
            return []

        tweet_id = content_id.replace("tw_", "")
        cache_key = f"x_comments:{tweet_id}:{limit}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        records: list[SocialRecord] = []
        try:
            url = "https://api.twitter.com/2/tweets/search/recent"
            headers = {
                "Authorization": f"Bearer {self._bearer_token}",
                "User-Agent": self._user_agent,
            }
            params = {
                "query": f"conversation_id:{tweet_id}",
                "max_results": max(10, min(limit, 100)),
                "tweet.fields": "created_at,public_metrics,author_id",
            }

            async with httpx.AsyncClient(timeout=self._http_timeout) as client:
                resp = await client.get(url, headers=headers, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    records = self._parse_tweets(data, is_reply=True)

            self._set_cached(cache_key, records)
            logger.info("X replies for %s: %d comments", tweet_id, len(records))
            return records

        except Exception as exc:
            logger.error("X fetch_comments error for %s: %s", content_id, exc)
            return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_tweets(self, data: dict[str, Any], is_reply: bool = False) -> list[SocialRecord]:
        """Convert X API v2 payload into SocialRecord instances."""
        records: list[SocialRecord] = []
        tweets = data.get("data", [])
        
        # Build user map from includes
        users_list = data.get("includes", {}).get("users", [])
        user_map = {u.get("id"): u.get("username", "user") for u in users_list}

        for tw in tweets:
            tw_id = tw.get("id", "")
            text = tw.get("text", "")
            author_id = tw.get("author_id", "")
            author_name = user_map.get(author_id, "twitter_user")
            
            created_at_str = tw.get("created_at", "")
            try:
                ts = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            except Exception:
                ts = datetime.now(timezone.utc)

            metrics = tw.get("public_metrics", {})
            retweet_count = metrics.get("retweet_count", 0)
            reply_count = metrics.get("reply_count", 0)
            like_count = metrics.get("like_count", 0)
            impression_count = metrics.get("impression_count", (like_count + retweet_count) * 15)

            hashtags = [h.get("tag") for h in tw.get("entities", {}).get("hashtags", []) if h.get("tag")]

            records.append(
                SocialRecord(
                    platform="Twitter / X",
                    content_id=f"tw_{tw_id}",
                    content_type="reply" if is_reply else "post",
                    timestamp=ts,
                    text=text,
                    author_id=author_id,
                    author_name=f"@{author_name}",
                    engagement={
                        "likes": like_count,
                        "shares": retweet_count,
                        "comments": reply_count,
                        "views": impression_count,
                    },
                    topic_keywords=hashtags,
                    source_url=f"https://x.com/{author_name}/status/{tw_id}",
                    raw_metadata={"tweet_id": tw_id},
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
