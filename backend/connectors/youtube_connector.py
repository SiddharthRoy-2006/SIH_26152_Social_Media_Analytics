"""
backend/connectors/youtube_connector.py

YouTube Data API v3 connector.

Provides:
- search(query)        → search.list → normalised SocialRecord per video
- fetch_comments(id)   → commentThreads.list → normalised SocialRecord per comment
- check_health()       → lightweight channels.list probe

Quota awareness:
- search.list costs 100 units (max ~100/day on the default 10K quota)
- commentThreads.list costs 1 unit per call
- videos.list costs 1 unit per call

The connector is designed to be quota-conscious: searches are limited,
results are cached in-memory for the current server lifecycle, and
unnecessary calls are avoided.
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
    sanitize_error,
)

logger = logging.getLogger(__name__)


class YouTubeConnector(PlatformConnector):
    """YouTube Data API v3 connector."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key
        self._service: Any = None
        self._cache: dict[str, tuple[datetime, list[SocialRecord]]] = {}
        self._cache_ttl = timedelta(minutes=15)

    # ------------------------------------------------------------------
    # PlatformConnector interface
    # ------------------------------------------------------------------

    @property
    def platform_name(self) -> str:
        return "YouTube"

    def update_credentials(self, credentials: dict[str, str]) -> None:
        if "api_key" in credentials:
            self._api_key = credentials["api_key"].strip()
            self._service = None
            self._cache.clear()

    def clear_credentials(self) -> None:
        self._api_key = ""
        self._service = None
        self._cache.clear()

    def check_health(self) -> PlatformCapability:
        now = datetime.now(timezone.utc)

        data_api_layer = {
            "name": "YouTube Data API v3",
            "access_type": "API Key",
            "usage": "Public video search, video metadata, engagement statistics, and comment threads.",
            "provides": ["Search results", "Views, Likes, Comments", "Video categories & tags", "Top-level comment threads"],
            "auth_required": False,
            "status": "CONNECTED" if self._api_key else "NOT_CONFIGURED",
        }
        analytics_api_layer = {
            "name": "YouTube Analytics API",
            "access_type": "Google OAuth 2.0",
            "usage": "Channel owner audience retention, viewer demographics, and estimated watch time.",
            "provides": ["Viewer demographics", "Audience retention", "Geographic watch time"],
            "auth_required": True,
            "status": "NOT_CONNECTED",
        }
        reporting_api_layer = {
            "name": "YouTube Reporting API",
            "access_type": "Google OAuth 2.0",
            "usage": "Bulk scheduled historical channel reporting datasets.",
            "provides": ["Scheduled bulk reporting jobs", "Historical daily aggregated stats"],
            "auth_required": True,
            "status": "NOT_CONNECTED",
        }

        access_layers = [data_api_layer, analytics_api_layer, reporting_api_layer]
        supported_metrics = ["views", "likes", "comments", "video_metadata", "channel_title", "tags", "sentiment", "network_topology"]
        unsupported_metrics = ["shares", "audience_demographics", "direct_subscriber_stream"]

        if not self._api_key:
            return PlatformCapability(
                platform="YouTube",
                status=PlatformStatus.NOT_CONFIGURED,
                reason="YouTube Data API v3 API Key is not configured.",
                credential_fields=["api_key"],
                approx_test_time="1-3 seconds",
                last_checked=now,
                access_layers=access_layers,
                supported_metrics=supported_metrics,
                unsupported_metrics=unsupported_metrics,
            )

        try:
            svc = self._get_service()
            # Cheapest possible probe: 1 quota unit
            svc.channels().list(part="id", id="UC_x5XG1OV2P6uZZ5FSM9Ttw", maxResults=1).execute()
            data_api_layer["status"] = "CONNECTED"
            return PlatformCapability(
                platform="YouTube",
                status=PlatformStatus.CONNECTED,
                reason="YouTube Data API v3 API Key is valid and operational.",
                available_data=["search", "video_details", "comments"],
                credential_fields=["api_key"],
                approx_test_time="1-3 seconds",
                last_checked=now,
                last_successful=now,
                access_layers=access_layers,
                supported_metrics=supported_metrics,
                unsupported_metrics=unsupported_metrics,
            )
        except Exception as exc:
            error_msg = sanitize_error(str(exc)) or str(exc)
            status = PlatformStatus.ERROR
            reason = "YouTube API key is invalid or request failed."

            if "quota" in error_msg.lower() or "rateLimitExceeded" in error_msg:
                status = PlatformStatus.RATE_LIMITED
                reason = "YouTube daily quota has been exceeded. Resets at midnight PT."
                data_api_layer["status"] = "QUOTA_LIMITED"
            elif "forbidden" in error_msg.lower() or "accessNotConfigured" in error_msg or "keyInvalid" in error_msg or "API key not valid" in error_msg:
                status = PlatformStatus.ERROR
                reason = "YouTube API key is invalid or YouTube Data API v3 is not enabled."
                data_api_layer["status"] = "INVALID_CREDENTIAL"

            return PlatformCapability(
                platform="YouTube",
                status=status,
                reason=reason,
                credential_fields=["api_key"],
                approx_test_time="1-3 seconds",
                last_checked=now,
                error_detail=error_msg[:200],
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
        """
        Search YouTube for videos matching *query*.

        Uses search.list (100 quota units per call) then enriches
        with videos.list (1 unit) for engagement stats.
        """
        if not self._api_key:
            return []

        cache_key = f"search:{query}:{limit}:{period_days}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            svc = self._get_service()

            # Calculate published-after date
            after = (datetime.now(timezone.utc) - timedelta(days=period_days)).strftime(
                "%Y-%m-%dT00:00:00Z"
            )

            # search.list — 100 quota units
            search_resp = (
                svc.search()
                .list(
                    part="snippet",
                    q=query,
                    type="video",
                    order="relevance",
                    publishedAfter=after,
                    maxResults=min(limit, 50),
                    relevanceLanguage="en",
                )
                .execute()
            )

            video_ids = [
                item["id"]["videoId"]
                for item in search_resp.get("items", [])
                if item.get("id", {}).get("videoId")
            ]

            if not video_ids:
                self._set_cached(cache_key, [])
                return []

            # videos.list for engagement stats — 1 quota unit
            stats_resp = (
                svc.videos()
                .list(
                    part="snippet,statistics",
                    id=",".join(video_ids),
                )
                .execute()
            )

            stats_map: dict[str, dict] = {}
            for item in stats_resp.get("items", []):
                stats_map[item["id"]] = item

            records: list[SocialRecord] = []
            for vid_id in video_ids:
                item = stats_map.get(vid_id)
                if not item:
                    continue

                snippet = item.get("snippet", {})
                stats = item.get("statistics", {})

                published = snippet.get("publishedAt", "")
                try:
                    ts = datetime.fromisoformat(published.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    ts = datetime.now(timezone.utc)

                title = snippet.get("title", "")
                desc = snippet.get("description", "")
                text = f"{title}\n{desc}" if desc else title

                records.append(
                    SocialRecord(
                        platform="YouTube",
                        content_id=vid_id,
                        content_type="video",
                        timestamp=ts,
                        text=text,
                        author_id=snippet.get("channelId"),
                        author_name=snippet.get("channelTitle"),
                        engagement={
                            "views": int(stats.get("viewCount", 0)),
                            "likes": int(stats.get("likeCount", 0)),
                            "comments": int(stats.get("commentCount", 0)),
                        },
                        topic_keywords=snippet.get("tags", [])[:10] if snippet.get("tags") else [],
                        source_url=f"https://www.youtube.com/watch?v={vid_id}",
                        raw_metadata={
                            "thumbnail": snippet.get("thumbnails", {}).get("medium", {}).get("url"),
                            "category_id": snippet.get("categoryId"),
                        },
                    )
                )

            self._set_cached(cache_key, records)
            logger.info("YouTube search for %r returned %d videos", query, len(records))
            return records

        except Exception as exc:
            logger.error("YouTube search error: %s", exc)
            return []

    async def fetch_comments(
        self,
        content_id: str,
        *,
        limit: int = 100,
    ) -> list[SocialRecord]:
        """
        Fetch top-level comments for a YouTube video.

        Uses commentThreads.list (1 quota unit per call), paginating
        up to *limit* comments.
        """
        if not self._api_key:
            return []

        cache_key = f"comments:{content_id}:{limit}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            svc = self._get_service()
            records: list[SocialRecord] = []
            page_token: str | None = None
            remaining = limit

            while remaining > 0:
                per_page = min(remaining, 100)
                req_params: dict[str, Any] = {
                    "part": "snippet",
                    "videoId": content_id,
                    "maxResults": per_page,
                    "textFormat": "plainText",
                    "order": "relevance",
                }
                if page_token:
                    req_params["pageToken"] = page_token

                resp = svc.commentThreads().list(**req_params).execute()

                for item in resp.get("items", []):
                    snippet = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
                    comment_id = item.get("id", "")
                    text = snippet.get("textDisplay", "")
                    author = snippet.get("authorDisplayName", "")

                    published = snippet.get("publishedAt", "")
                    try:
                        ts = datetime.fromisoformat(published.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        ts = datetime.now(timezone.utc)

                    records.append(
                        SocialRecord(
                            platform="YouTube",
                            content_id=comment_id,
                            content_type="comment",
                            timestamp=ts,
                            text=text,
                            author_name=author,
                            engagement={
                                "likes": int(snippet.get("likeCount", 0)),
                            },
                            source_url=f"https://www.youtube.com/watch?v={content_id}",
                        )
                    )

                page_token = resp.get("nextPageToken")
                remaining -= per_page
                if not page_token:
                    break

            self._set_cached(cache_key, records)
            logger.info("YouTube comments for %s: %d comments", content_id, len(records))
            return records

        except Exception as exc:
            logger.error("YouTube comments error for %s: %s", content_id, exc)
            return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_service(self) -> Any:
        """Lazily build the Google API service object."""
        if self._service is None:
            from googleapiclient.discovery import build

            self._service = build("youtube", "v3", developerKey=self._api_key)
        return self._service

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
