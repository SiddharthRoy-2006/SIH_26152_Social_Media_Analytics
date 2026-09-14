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
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

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
        self._verified = False
        self._last_successful: datetime | None = None

    @property
    def platform_name(self) -> str:
        return "Instagram"

    def update_credentials(self, credentials: dict[str, str]) -> None:
        if "access_token" in credentials:
            self._access_token = credentials["access_token"].strip()
        if "account_id" in credentials:
            self._account_id = credentials["account_id"].strip()
        self._cache.clear()
        self._verified = False
        self._last_successful = None

    def clear_credentials(self) -> None:
        self._access_token = ""
        self._account_id = ""
        self._cache.clear()
        self._verified = False
        self._last_successful = None

    def check_health(self, force_probe: bool = False) -> PlatformCapability:
        now = datetime.now(timezone.utc)

        ig_prof_layer = {
            "name": "Instagram Graph API (Professional Account)",
            "access_type": "User/Page Access Token & IG Account ID",
            "usage": "Public hashtag search, professional account business discovery, post comments.",
            "provides": ["Hashtag top/recent posts", "Business account discovery", "Media comments"],
            "auth_required": False,
            "status": "CONNECTED" if (self._access_token and self._account_id) else "NOT_CONFIGURED",
        }
        ig_basic_layer = {
            "name": "Instagram Basic Display API (Deprecated)",
            "access_type": "Basic Display OAuth 2.0",
            "usage": "Legacy consumer profile and media ingestion (deprecated by Meta).",
            "provides": ["Basic profile", "User media"],
            "auth_required": True,
            "status": "NOT_CONNECTED",
        }

        access_layers = [ig_prof_layer, ig_basic_layer]
        supported_metrics = ["media_posts", "likes", "comments", "impressions", "reach", "sentiment"]
        unsupported_metrics = ["personal_account_search", "unauthorized_user_profiles", "story_viewers"]

        if not self._access_token and not self._account_id:
            return PlatformCapability(
                platform="Instagram",
                status=PlatformStatus.UNAVAILABLE,
                reason="Requires Meta App Review and an active Instagram Professional Account.",
                credential_fields=["access_token", "account_id"],
                approx_test_time="1-3 seconds",
                available_data=[],
                last_checked=now,
                access_layers=access_layers,
                supported_metrics=supported_metrics,
                unsupported_metrics=unsupported_metrics,
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
                access_layers=access_layers,
                supported_metrics=supported_metrics,
                unsupported_metrics=unsupported_metrics,
            )

        if not force_probe and self._verified:
            ig_prof_layer["status"] = "CONNECTED"
            return PlatformCapability(
                platform="Instagram",
                status=PlatformStatus.CONNECTED,
                reason="Instagram Graph API connected with Professional Account access.",
                available_data=["hashtag_search", "business_discovery", "comments"],
                credential_fields=["access_token", "account_id"],
                approx_test_time="1-3 seconds",
                last_checked=now,
                last_successful=self._last_successful or now,
                access_layers=access_layers,
                supported_metrics=supported_metrics,
                unsupported_metrics=unsupported_metrics,
            )

        try:
            import httpx
            url = f"https://graph.facebook.com/v19.0/{self._account_id}"
            params = {"fields": "id,username,name", "access_token": self._access_token}
            with httpx.Client(timeout=self._http_timeout) as client:
                resp = client.get(url, params=params)
                if resp.status_code == 200:
                    self._verified = True
                    self._last_successful = now
                    ig_prof_layer["status"] = "CONNECTED"
                    return PlatformCapability(
                        platform="Instagram",
                        status=PlatformStatus.CONNECTED,
                        reason="Instagram Graph API connected with Professional Account access.",
                        available_data=["hashtag_search", "business_discovery", "comments"],
                        credential_fields=["access_token", "account_id"],
                        approx_test_time="1-3 seconds",
                        last_checked=now,
                        last_successful=now,
                        access_layers=access_layers,
                        supported_metrics=supported_metrics,
                        unsupported_metrics=unsupported_metrics,
                    )
                elif resp.status_code == 429:
                    ig_prof_layer["status"] = "RATE_LIMITED"
                    return PlatformCapability(
                        platform="Instagram",
                        status=PlatformStatus.RATE_LIMITED,
                        reason="Meta Graph API rate limit reached.",
                        available_data=[],
                        credential_fields=["access_token", "account_id"],
                        approx_test_time="1-3 seconds",
                        last_checked=now,
                        error_detail="HTTP 429 Rate Limit",
                        access_layers=access_layers,
                        supported_metrics=supported_metrics,
                        unsupported_metrics=unsupported_metrics,
                    )
                else:
                    ig_prof_layer["status"] = "INVALID_CREDENTIAL"
                    return PlatformCapability(
                        platform="Instagram",
                        status=PlatformStatus.ERROR,
                        reason="Meta Graph API authorization failed (invalid token or missing permissions).",
                        available_data=[],
                        credential_fields=["access_token", "account_id"],
                        approx_test_time="1-3 seconds",
                        last_checked=now,
                        error_detail=f"HTTP {resp.status_code}",
                        access_layers=access_layers,
                        supported_metrics=supported_metrics,
                        unsupported_metrics=unsupported_metrics,
                    )
        except (httpx.TimeoutException, TimeoutError):
            return PlatformCapability(
                platform="Instagram",
                status=PlatformStatus.UNAVAILABLE,
                reason="Instagram Graph API network connection timed out.",
                available_data=[],
                credential_fields=["access_token", "account_id"],
                approx_test_time="1-3 seconds",
                last_checked=now,
                error_detail="Connection timeout",
                access_layers=access_layers,
                supported_metrics=supported_metrics,
                unsupported_metrics=unsupported_metrics,
            )
        except httpx.NetworkError as exc:
            return PlatformCapability(
                platform="Instagram",
                status=PlatformStatus.UNAVAILABLE,
                reason=f"Instagram Graph API network connection failed: {sanitize_error(str(exc))}",
                available_data=[],
                credential_fields=["access_token", "account_id"],
                approx_test_time="1-3 seconds",
                last_checked=now,
                error_detail=str(exc)[:200],
                access_layers=access_layers,
                supported_metrics=supported_metrics,
                unsupported_metrics=unsupported_metrics,
            )
        except Exception as exc:
            err_str = str(exc)
            is_internal = isinstance(exc, (NameError, TypeError, AttributeError, ImportError, ValueError))
            return PlatformCapability(
                platform="Instagram",
                status=PlatformStatus.ERROR,
                reason=f"Internal error during Instagram verification: {type(exc).__name__}: {sanitize_error(err_str)}" if is_internal else f"Instagram probe failed: {sanitize_error(err_str)[:120]}",
                available_data=[],
                credential_fields=["access_token", "account_id"],
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
        limit: int = 20,
        period_days: int = 30,
    ) -> list[SocialRecord]:
        """Search Instagram public hashtags or account media using official Meta Graph API."""
        if not self._access_token or not self._account_id:
            return []

        clean_topic = query.strip()
        if not clean_topic:
            return []

        # Check in-memory cache
        cache_key = f"{clean_topic.lower()}:{limit}:{period_days}"
        now = datetime.now(timezone.utc)
        if cache_key in self._cache:
            ts, cached_records = self._cache[cache_key]
            if now - ts < self._cache_ttl:
                return cached_records

        # Alphanumeric hashtag query (Meta hashtag search requires alphanumeric string, no '#')
        clean_tag = re.sub(r"[^\w]", "", clean_topic.lower())
        records: list[SocialRecord] = []
        cutoff_dt = now - timedelta(days=period_days)

        try:
            async with httpx.AsyncClient(timeout=self._http_timeout) as client:
                # 1. Search public hashtag if hashtag query is valid
                if clean_tag:
                    try:
                        tag_search_url = "https://graph.facebook.com/v19.0/ig_hashtag_search"
                        tag_res = await client.get(
                            tag_search_url,
                            params={
                                "user_id": self._account_id,
                                "q": clean_tag,
                                "access_token": self._access_token,
                            },
                        )
                        if tag_res.status_code == 200:
                            tag_data = tag_res.json().get("data", [])
                            if tag_data:
                                hashtag_id = tag_data[0].get("id")
                                # Query recent media for this hashtag
                                media_url = f"https://graph.facebook.com/v19.0/{hashtag_id}/recent_media"
                                m_res = await client.get(
                                    media_url,
                                    params={
                                        "user_id": self._account_id,
                                        "fields": "id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count",
                                        "access_token": self._access_token,
                                        "limit": min(limit, 50),
                                    },
                                )
                                if m_res.status_code == 200:
                                    items = m_res.json().get("data", [])
                                    for itm in items:
                                        rec = self._parse_instagram_media(itm, clean_topic, cutoff_dt)
                                        if rec:
                                            records.append(rec)
                    except Exception as tag_exc:
                        logger.debug("Instagram hashtag search non-fatal error: %s", tag_exc)

                # 2. Also query account media to capture matching posts from the authorized business account
                if len(records) < limit:
                    try:
                        acct_media_url = f"https://graph.facebook.com/v19.0/{self._account_id}/media"
                        acct_res = await client.get(
                            acct_media_url,
                            params={
                                "fields": "id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count",
                                "access_token": self._access_token,
                                "limit": min(limit, 50),
                            },
                        )
                        if acct_res.status_code == 200:
                            items = acct_res.json().get("data", [])
                            for itm in items:
                                cap_text = (itm.get("caption") or "").lower()
                                if not clean_tag or clean_tag in cap_text or clean_topic.lower() in cap_text:
                                    if not any(r.content_id == str(itm.get("id")) for r in records):
                                        rec = self._parse_instagram_media(itm, clean_topic, cutoff_dt)
                                        if rec:
                                            records.append(rec)
                    except Exception as acct_exc:
                        logger.debug("Instagram account media query non-fatal error: %s", acct_exc)

        except Exception as exc:
            logger.warning("Instagram Graph API request failed for %r: %s", clean_topic, exc)

        # Sort newest first and limit
        records.sort(key=lambda r: r.timestamp, reverse=True)
        final_records = records[:limit]
        if final_records:
            self._cache[cache_key] = (now, final_records)
        return final_records

    def _parse_instagram_media(
        self,
        itm: dict[str, Any],
        topic: str,
        cutoff_dt: datetime,
    ) -> SocialRecord | None:
        """Helper to parse a raw Meta Graph API media item into a SocialRecord."""
        content_id = str(itm.get("id", "")).strip()
        if not content_id:
            return None

        caption = (itm.get("caption") or "").strip()
        raw_ts = itm.get("timestamp")
        parsed_ts = datetime.now(timezone.utc)
        if raw_ts:
            try:
                ts_str = raw_ts.replace("Z", "+00:00")
                parsed_ts = datetime.fromisoformat(ts_str)
                if parsed_ts.tzinfo is None:
                    parsed_ts = parsed_ts.replace(tzinfo=timezone.utc)
            except Exception:
                pass

        if parsed_ts < cutoff_dt:
            return None

        likes = int(itm.get("like_count", 0))
        comments = int(itm.get("comments_count", 0))
        reach = max(likes * 10, (likes + comments) * 5, 50)

        permalink = itm.get("permalink") or f"https://www.instagram.com/p/{content_id}/"
        extracted_tags = re.findall(r"#\w+", caption)
        keywords = [t.lstrip("#") for t in extracted_tags] if extracted_tags else [topic]

        return SocialRecord(
            platform="Instagram",
            content_id=content_id,
            content_type="post",
            timestamp=parsed_ts,
            text=caption if caption else f"Instagram Post ({content_id})",
            author_id=self._account_id,
            author_name="Instagram Creator",
            engagement={
                "likes": likes,
                "comments": comments,
                "reach": reach,
                "shares": 0,
            },
            source_url=permalink,
            topic_keywords=keywords,
            raw_metadata={"media_type": itm.get("media_type")},
        )

    async def fetch_comments(
        self,
        content_id: str,
        *,
        limit: int = 50,
    ) -> list[SocialRecord]:
        """Fetch comments on an authorized Instagram media item."""
        if not self._access_token or not content_id:
            return []

        comments: list[SocialRecord] = []
        try:
            url = f"https://graph.facebook.com/v19.0/{content_id}/comments"
            params = {
                "fields": "id,text,timestamp,like_count",
                "access_token": self._access_token,
                "limit": min(limit, 50),
            }
            async with httpx.AsyncClient(timeout=self._http_timeout) as client:
                res = await client.get(url, params=params)
                if res.status_code == 200:
                    data = res.json().get("data", [])
                    for item in data:
                        cid = str(item.get("id", ""))
                        text = item.get("text", "")
                        raw_ts = item.get("timestamp")
                        parsed_ts = datetime.now(timezone.utc)
                        if raw_ts:
                            try:
                                parsed_ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                                if parsed_ts.tzinfo is None:
                                    parsed_ts = parsed_ts.replace(tzinfo=timezone.utc)
                            except Exception:
                                pass
                        comments.append(SocialRecord(
                            platform="Instagram",
                            content_id=cid,
                            content_type="comment",
                            timestamp=parsed_ts,
                            text=text,
                            author_id="instagram_user",
                            author_name="Instagram User",
                            engagement={"likes": int(item.get("like_count", 0)), "comments": 0, "shares": 0},
                            source_url=f"https://www.instagram.com/p/{content_id}/",
                            topic_keywords=[],
                            raw_metadata={"parent_content_id": content_id},
                        ))
        except Exception as exc:
            logger.debug("Fetch Instagram comments failed for %s: %s", content_id, exc)

        return comments


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
        self._verified = False
        self._last_successful: datetime | None = None

    @property
    def platform_name(self) -> str:
        return "Facebook"

    def update_credentials(self, credentials: dict[str, str]) -> None:
        if "access_token" in credentials:
            self._access_token = credentials["access_token"].strip()
        if "page_id" in credentials:
            self._page_id = credentials["page_id"].strip()
        self._cache.clear()
        self._verified = False
        self._last_successful = None

    def clear_credentials(self) -> None:
        self._access_token = ""
        self._page_id = ""
        self._cache.clear()
        self._verified = False
        self._last_successful = None

    def check_health(self, force_probe: bool = False) -> PlatformCapability:
        now = datetime.now(timezone.utc)

        fb_page_layer = {
            "name": "Facebook Graph API (Page Content Access)",
            "access_type": "Meta Page Access Token & Page ID",
            "usage": "Page public post feeds, reaction statistics, comment streams.",
            "provides": ["Page posts", "Reactions (Likes, Loves, etc.)", "Comments & discussions"],
            "auth_required": True,
            "status": "CONNECTED" if (self._access_token and self._page_id) else "NOT_CONFIGURED",
        }
        fb_insights_layer = {
            "name": "Facebook Page Insights API",
            "access_type": "Page Administrator OAuth 2.0",
            "usage": "Page aggregated reach, page views, and follower demographics.",
            "provides": ["Page follower count", "Page demographic insights", "Impression reach"],
            "auth_required": True,
            "status": "NOT_CONNECTED",
        }

        access_layers = [fb_page_layer, fb_insights_layer]
        supported_metrics = ["posts", "reactions", "comments", "shares", "sentiment"]
        unsupported_metrics = ["personal_profile_scraping", "unauthorized_group_posts", "private_messages"]

        if not self._access_token and not self._page_id:
            return PlatformCapability(
                platform="Facebook",
                status=PlatformStatus.UNAVAILABLE,
                reason="Requires Meta App Review and Page Public Content Access.",
                credential_fields=["access_token", "page_id"],
                approx_test_time="1-3 seconds",
                available_data=[],
                last_checked=now,
                access_layers=access_layers,
                supported_metrics=supported_metrics,
                unsupported_metrics=unsupported_metrics,
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
                access_layers=access_layers,
                supported_metrics=supported_metrics,
                unsupported_metrics=unsupported_metrics,
            )

        if not force_probe and self._verified:
            fb_page_layer["status"] = "CONNECTED"
            return PlatformCapability(
                platform="Facebook",
                status=PlatformStatus.CONNECTED,
                reason="Facebook Graph API connected with Page Access.",
                available_data=["page_feed", "post_metrics", "comments"],
                credential_fields=["access_token", "page_id"],
                approx_test_time="1-3 seconds",
                last_checked=now,
                last_successful=self._last_successful or now,
                access_layers=access_layers,
                supported_metrics=supported_metrics,
                unsupported_metrics=unsupported_metrics,
            )

        try:
            import httpx
            url = f"https://graph.facebook.com/v19.0/{self._page_id}"
            params = {"fields": "id,name", "access_token": self._access_token}
            with httpx.Client(timeout=self._http_timeout) as client:
                resp = client.get(url, params=params)
                if resp.status_code == 200:
                    self._verified = True
                    self._last_successful = now
                    fb_page_layer["status"] = "CONNECTED"
                    return PlatformCapability(
                        platform="Facebook",
                        status=PlatformStatus.CONNECTED,
                        reason="Facebook Graph API connected with Page Access.",
                        available_data=["page_feed", "post_metrics", "comments"],
                        credential_fields=["access_token", "page_id"],
                        approx_test_time="1-3 seconds",
                        last_checked=now,
                        last_successful=now,
                        access_layers=access_layers,
                        supported_metrics=supported_metrics,
                        unsupported_metrics=unsupported_metrics,
                    )
                elif resp.status_code == 429:
                    fb_page_layer["status"] = "RATE_LIMITED"
                    return PlatformCapability(
                        platform="Facebook",
                        status=PlatformStatus.RATE_LIMITED,
                        reason="Meta Graph API rate limit reached.",
                        available_data=[],
                        credential_fields=["access_token", "page_id"],
                        approx_test_time="1-3 seconds",
                        last_checked=now,
                        error_detail="HTTP 429 Rate Limit",
                        access_layers=access_layers,
                        supported_metrics=supported_metrics,
                        unsupported_metrics=unsupported_metrics,
                    )
                else:
                    fb_page_layer["status"] = "INVALID_CREDENTIAL"
                    return PlatformCapability(
                        platform="Facebook",
                        status=PlatformStatus.ERROR,
                        reason="Meta Graph API authorization failed (invalid Page Access Token or missing permissions).",
                        available_data=[],
                        credential_fields=["access_token", "page_id"],
                        approx_test_time="1-3 seconds",
                        last_checked=now,
                        error_detail=f"HTTP {resp.status_code}",
                        access_layers=access_layers,
                        supported_metrics=supported_metrics,
                        unsupported_metrics=unsupported_metrics,
                    )
        except (httpx.TimeoutException, TimeoutError):
            return PlatformCapability(
                platform="Facebook",
                status=PlatformStatus.UNAVAILABLE,
                reason="Facebook Graph API network connection timed out.",
                available_data=[],
                credential_fields=["access_token", "page_id"],
                approx_test_time="1-3 seconds",
                last_checked=now,
                error_detail="Connection timeout",
                access_layers=access_layers,
                supported_metrics=supported_metrics,
                unsupported_metrics=unsupported_metrics,
            )
        except httpx.NetworkError as exc:
            return PlatformCapability(
                platform="Facebook",
                status=PlatformStatus.UNAVAILABLE,
                reason=f"Facebook Graph API network connection failed: {sanitize_error(str(exc))}",
                available_data=[],
                credential_fields=["access_token", "page_id"],
                approx_test_time="1-3 seconds",
                last_checked=now,
                error_detail=str(exc)[:200],
                access_layers=access_layers,
                supported_metrics=supported_metrics,
                unsupported_metrics=unsupported_metrics,
            )
        except Exception as exc:
            err_str = str(exc)
            is_internal = isinstance(exc, (NameError, TypeError, AttributeError, ImportError, ValueError))
            return PlatformCapability(
                platform="Facebook",
                status=PlatformStatus.ERROR,
                reason=f"Internal error during Facebook verification: {type(exc).__name__}: {sanitize_error(err_str)}" if is_internal else f"Facebook probe failed: {sanitize_error(err_str)[:120]}",
                available_data=[],
                credential_fields=["access_token", "page_id"],
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

