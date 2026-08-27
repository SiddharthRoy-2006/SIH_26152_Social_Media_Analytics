"""
tests/test_connectors.py

Unit tests for Stage 3B real-data ingestion foundation:
- SocialRecord data model
- PlatformStatus and PlatformCapability
- ConnectorRegistry and platform capability tracking
- YouTubeConnector resilience and safety with/without credentials
- LiveAnalysisProvider and LiveGeneralProvider integration
- /health platform status response
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from backend.connectors.base import (
    PlatformCapability,
    PlatformStatus,
    SocialRecord,
)
from backend.connectors.registry import ConnectorRegistry, get_registry
from backend.connectors.youtube_connector import YouTubeConnector
from backend.schemas import AnalysisRequest, GeneralRequest
from backend.services.live_provider import (
    LiveAnalysisProvider,
    LiveGeneralProvider,
    _compute_real_metrics,
    _compute_real_sentiment,
)


# ---------------------------------------------------------------------------
# 1. SocialRecord & Data Models
# ---------------------------------------------------------------------------

def test_social_record_creation():
    rec = SocialRecord(
        platform="YouTube",
        content_id="test12345",
        content_type="video",
        timestamp=datetime.now(timezone.utc),
        text="Exploring AI in education and youth innovation",
        author_name="EduTech Channel",
        engagement={"views": 15000, "likes": 850, "comments": 120},
        topic_keywords=["AI", "Education"],
        source_url="https://youtube.com/watch?v=test12345",
    )
    assert rec.platform == "YouTube"
    assert rec.content_id == "test12345"
    assert rec.engagement["views"] == 15000
    assert "AI" in rec.topic_keywords


def test_platform_capability_to_dict():
    cap = PlatformCapability(
        platform="YouTube",
        status=PlatformStatus.NOT_CONFIGURED,
        reason="API key missing",
        available_data=["search", "comments"],
    )
    d = cap.to_dict()
    assert d["platform"] == "YouTube"
    assert d["status"] == "not_configured"
    assert d["reason"] == "API key missing"
    assert "search" in d["available_data"]


# ---------------------------------------------------------------------------
# 2. ConnectorRegistry
# ---------------------------------------------------------------------------

def test_connector_registry_defaults():
    reg = ConnectorRegistry()
    caps = reg.all_capabilities()
    assert "YouTube" in caps
    assert "Telegram" in caps
    assert "Reddit" in caps
    assert "Twitter / X" in caps
    assert "Instagram" in caps
    assert "Facebook" in caps
    assert caps["Twitter / X"].status == PlatformStatus.UNAVAILABLE
    assert caps["Instagram"].status == PlatformStatus.UNAVAILABLE


def test_connector_registry_registration():
    reg = ConnectorRegistry()
    conn = YouTubeConnector(api_key="")
    reg.register(conn)
    cap = reg.get_capability("YouTube")
    assert cap.status == PlatformStatus.NOT_CONFIGURED
    assert reg.get_connector("YouTube") is not None


def test_get_global_registry():
    reg = get_registry()
    assert isinstance(reg, ConnectorRegistry)
    assert "YouTube" in reg.all_capabilities()


# ---------------------------------------------------------------------------
# 3. YouTubeConnector Without Credentials (Safe Degradation)
# ---------------------------------------------------------------------------

def test_youtube_connector_unconfigured():
    conn = YouTubeConnector(api_key="")
    health = conn.check_health()
    assert health.status == PlatformStatus.NOT_CONFIGURED
    assert "not configured" in health.reason.lower()


def test_youtube_search_without_credentials_returns_empty():
    import asyncio

    conn = YouTubeConnector(api_key="")
    records = asyncio.run(conn.search("AI in Education"))
    assert records == []


def test_youtube_comments_without_credentials_returns_empty():
    import asyncio

    conn = YouTubeConnector(api_key="")
    comments = asyncio.run(conn.fetch_comments("dQw4w9WgXcQ"))
    assert comments == []



# ---------------------------------------------------------------------------
# 4. Metrics and Sentiment Computation from Real Records
# ---------------------------------------------------------------------------

def test_compute_real_metrics():
    records = [
        SocialRecord(
            platform="YouTube",
            content_id="1",
            content_type="video",
            timestamp=datetime.now(timezone.utc),
            text="First video on this topic with great insights",
            author_name="Creator A",
            engagement={"views": 10000, "likes": 500, "comments": 50, "shares": 25},
        ),
        SocialRecord(
            platform="YouTube",
            content_id="vid2",
            content_type="video",
            timestamp=datetime.now(timezone.utc),
            text="Second video",
            engagement={"views": 2000, "likes": 200, "comments": 30, "shares": 10},
        ),
    ]
    metrics = _compute_real_metrics(records)
    assert metrics["reach"] == 12000
    assert metrics["likes"] == 700
    assert metrics["comments"] == 80
    assert metrics["content_volume"] == 2
    assert metrics["engagement_rate"] > 0


def test_compute_real_sentiment():
    records = [
        SocialRecord(platform="YT", content_id="1", content_type="comment", timestamp=datetime.now(timezone.utc), text="This is great and amazing, love it!"),
        SocialRecord(platform="YT", content_id="2", content_type="comment", timestamp=datetime.now(timezone.utc), text="Very helpful and wonderful resource"),
        SocialRecord(platform="YT", content_id="3", content_type="comment", timestamp=datetime.now(timezone.utc), text="Terrible and bad quality"),
    ]
    sentiment = _compute_real_sentiment(records)
    assert sentiment["positive"] > sentiment["negative"]
    assert sentiment["positive"] + sentiment["negative"] + sentiment["neutral"] == 100


# ---------------------------------------------------------------------------
# 5. Live Providers Integration
# ---------------------------------------------------------------------------

def test_live_analysis_provider_empty_topic():
    reg = ConnectorRegistry()
    provider = LiveAnalysisProvider(reg)
    req = AnalysisRequest(topic="", platform="YouTube")
    resp = provider.get_analysis(req)
    assert resp.data_available is False
    assert resp.source == "empty"


def test_live_analysis_provider_unconfigured_connector():
    reg = ConnectorRegistry()
    conn = YouTubeConnector(api_key="")
    reg.register(conn)
    provider = LiveAnalysisProvider(reg)
    req = AnalysisRequest(topic="Education Policy", platform="YouTube")
    resp = provider.get_analysis(req)
    # Unconfigured connector returns no records → honest empty response
    assert resp.data_available is False
    assert resp.source == "empty"


def test_live_general_provider_unconfigured():
    reg = ConnectorRegistry()
    provider = LiveGeneralProvider(reg)
    req = GeneralRequest(platform="All Platforms")
    resp = provider.get_general(req)
    assert resp.data_available is False
    assert resp.source == "empty"


# ---------------------------------------------------------------------------
# 6. /health Endpoint Includes Platform Status
# ---------------------------------------------------------------------------

def test_health_endpoint_returns_platforms():
    from fastapi.testclient import TestClient
    from backend.app import app

    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "platforms" in data
    assert "YouTube" in data["platforms"]
    assert "Telegram" in data["platforms"]
    assert "Reddit" in data["platforms"]
    assert "Twitter / X" in data["platforms"]
    assert "Instagram" in data["platforms"]
    assert "Facebook" in data["platforms"]


# ---------------------------------------------------------------------------
# 7. TelegramConnector Tests (Stage 3C)
# ---------------------------------------------------------------------------

def test_telegram_connector_unconfigured():
    from backend.connectors.telegram_connector import TelegramConnector

    conn = TelegramConnector(api_id="", api_hash="")
    health = conn.check_health()
    assert health.status == PlatformStatus.NOT_CONFIGURED
    assert "not configured" in health.reason.lower()


def test_telegram_connector_incomplete_credentials():
    from backend.connectors.telegram_connector import TelegramConnector

    conn = TelegramConnector(api_id="123456", api_hash="")
    health = conn.check_health()
    assert health.status == PlatformStatus.NOT_CONFIGURED
    assert "incomplete" in health.reason.lower()


def test_telegram_connector_valid_mtproto_format():
    from backend.connectors.telegram_connector import TelegramConnector

    conn = TelegramConnector(api_id="12345678", api_hash="abcdef0123456789abcdef0123456789")
    health = conn.check_health()
    assert health.status == PlatformStatus.CONNECTED
    assert "MTProto" in health.reason


def test_telegram_search_unconfigured_returns_empty():
    import asyncio
    from backend.connectors.telegram_connector import TelegramConnector

    conn = TelegramConnector(api_id="", api_hash="")
    records = asyncio.run(conn.search("technology news"))
    assert records == []


def test_telegram_comments_unconfigured_returns_empty():
    import asyncio
    from backend.connectors.telegram_connector import TelegramConnector

    conn = TelegramConnector(api_id="", api_hash="")
    records = asyncio.run(conn.fetch_comments("channel_123"))
    assert records == []


def test_telegram_html_parsing_to_social_records():
    from backend.connectors.telegram_connector import TelegramConnector

    sample_html = '''
    <div class="tgme_widget_message_wrap">
      <div data-post="tech_news/101">
        <div class="tgme_widget_message_owner_name"><span>Tech Daily</span></div>
        <div class="tgme_widget_message_text">Exciting breakthrough in #quantum computing! Full report here.</div>
        <time datetime="2026-08-27T08:30:00Z"></time>
        <span class="tgme_widget_message_views">12.5K</span>
      </div>
    </div>
    '''
    conn = TelegramConnector(api_id="12345678", api_hash="abcdef0123456789abcdef0123456789")
    records = conn._parse_public_channel_html(sample_html, channel_name="tech_news", limit=10)
    assert len(records) == 1
    rec = records[0]
    assert rec.platform == "Telegram"
    assert rec.content_id == "tech_news/101"
    assert "quantum" in rec.text.lower()
    assert rec.author_name == "Tech Daily"
    assert rec.engagement["views"] == 12500
    assert rec.engagement["forwards"] > 0
    assert "#quantum" in rec.topic_keywords


# ---------------------------------------------------------------------------
# 8. RedditConnector Tests (Stage 3C)
# ---------------------------------------------------------------------------

def test_reddit_connector_unconfigured():
    from backend.connectors.reddit_connector import RedditConnector

    conn = RedditConnector(client_id="", client_secret="")
    health = conn.check_health()
    assert health.status == PlatformStatus.NOT_CONFIGURED
    assert "not configured" in health.reason.lower()


def test_reddit_connector_incomplete_credentials():
    from backend.connectors.reddit_connector import RedditConnector

    conn = RedditConnector(client_id="my_client_id", client_secret="")
    health = conn.check_health()
    assert health.status == PlatformStatus.NOT_CONFIGURED
    assert "incomplete" in health.reason.lower()


def test_reddit_search_unconfigured_returns_empty():
    import asyncio
    from backend.connectors.reddit_connector import RedditConnector

    conn = RedditConnector(client_id="", client_secret="")
    records = asyncio.run(conn.search("machine learning"))
    assert records == []


def test_reddit_comments_unconfigured_returns_empty():
    import asyncio
    from backend.connectors.reddit_connector import RedditConnector

    conn = RedditConnector(client_id="", client_secret="")
    records = asyncio.run(conn.fetch_comments("t3_xyz123"))
    assert records == []


def test_reddit_listing_parsing_to_social_records():
    from backend.connectors.reddit_connector import RedditConnector

    sample_listing = {
        "kind": "Listing",
        "data": {
            "children": [
                {
                    "kind": "t3",
                    "data": {
                        "id": "abc789",
                        "title": "New AI Education Framework Released",
                        "selftext": "Discussion on the latest policy for digital schools.",
                        "author": "edu_researcher",
                        "score": 450,
                        "ups": 450,
                        "num_comments": 82,
                        "num_crossposts": 15,
                        "subreddit": "education",
                        "link_flair_text": "Discussion",
                        "permalink": "/r/education/comments/abc789/new_ai_education_framework/",
                        "created_utc": 1756281600,
                    }
                }
            ]
        }
    }

    conn = RedditConnector(client_id="id", client_secret="secret")
    records = conn._parse_reddit_listing(sample_listing)
    assert len(records) == 1
    rec = records[0]
    assert rec.platform == "Reddit"
    assert rec.content_id == "t3_abc789"
    assert "Education Framework" in rec.text
    assert rec.author_name == "edu_researcher"
    assert rec.engagement["score"] == 450
    assert rec.engagement["comments"] == 82
    assert "r/education" in rec.topic_keywords
    assert rec.source_url.startswith("https://reddit.com")


def test_reddit_comments_parsing_to_social_records():
    from backend.connectors.reddit_connector import RedditConnector

    sample_comments = {
        "kind": "Listing",
        "data": {
            "children": [
                {
                    "kind": "t1",
                    "data": {
                        "id": "comm101",
                        "body": "This framework could really help rural institutions.",
                        "author": "teacher_alex",
                        "score": 45,
                        "ups": 45,
                        "permalink": "/r/education/comments/abc789/_/comm101/",
                        "created_utc": 1756283000,
                    }
                }
            ]
        }
    }

    conn = RedditConnector(client_id="id", client_secret="secret")
    records = conn._parse_reddit_comments(sample_comments, post_id="abc789")
    assert len(records) == 1
    rec = records[0]
    assert rec.platform == "Reddit"
    assert rec.content_id == "t1_comm101"
    assert "rural institutions" in rec.text
    assert rec.author_name == "teacher_alex"
    assert rec.engagement["upvotes"] == 45


# ---------------------------------------------------------------------------
# 9. Multi-Platform Metric Aggregation
# ---------------------------------------------------------------------------

def test_compute_real_metrics_multi_platform():
    records = [
        SocialRecord(
            platform="YouTube",
            content_id="yt1",
            content_type="video",
            timestamp=datetime.now(timezone.utc),
            text="YouTube Video",
            engagement={"views": 50000, "likes": 2500, "comments": 300, "shares": 100},
        ),
        SocialRecord(
            platform="Telegram",
            content_id="tg1",
            content_type="message",
            timestamp=datetime.now(timezone.utc),
            text="Telegram Post",
            engagement={"views": 15000, "forwards": 750, "replies": 150},
        ),
        SocialRecord(
            platform="Reddit",
            content_id="t3_rd1",
            content_type="post",
            timestamp=datetime.now(timezone.utc),
            text="Reddit Discussion",
            engagement={"score": 850, "upvotes": 850, "comments": 220, "shares": 40},
        ),
    ]

    metrics = _compute_real_metrics(records)
    assert metrics["reach"] == 65000  # 50000 + 15000
    assert metrics["likes"] == 3350   # 2500 + 850
    assert metrics["comments"] == 670 # 300 + 150 + 220
    assert metrics["shares"] == 890   # 100 + 750 + 40
    assert metrics["content_volume"] == 3
    assert metrics["engagement_rate"] > 0


# ---------------------------------------------------------------------------
# 10. Twitter / X Connector Tests (Stage 3D)
# ---------------------------------------------------------------------------

def test_twitter_connector_unconfigured():
    from backend.connectors.twitter_connector import TwitterConnector

    conn = TwitterConnector(bearer_token="")
    health = conn.check_health()
    assert health.status == PlatformStatus.UNAVAILABLE
    assert "paid credits" in health.reason.lower() or "bearer token" in health.reason.lower()


def test_twitter_search_unconfigured_returns_empty():
    import asyncio
    from backend.connectors.twitter_connector import TwitterConnector

    conn = TwitterConnector(bearer_token="")
    records = asyncio.run(conn.search("AI innovation"))
    assert records == []


def test_twitter_comments_unconfigured_returns_empty():
    import asyncio
    from backend.connectors.twitter_connector import TwitterConnector

    conn = TwitterConnector(bearer_token="")
    records = asyncio.run(conn.fetch_comments("1234567890"))
    assert records == []


def test_twitter_tweet_parsing_to_social_records():
    from backend.connectors.twitter_connector import TwitterConnector

    sample_payload = {
        "data": [
            {
                "id": "1892837465",
                "text": "Exciting updates in #AI and higher education reform! Check it out.",
                "author_id": "98765",
                "created_at": "2026-08-27T07:15:00.000Z",
                "public_metrics": {
                    "retweet_count": 45,
                    "reply_count": 12,
                    "like_count": 280,
                    "impression_count": 4500,
                },
                "entities": {
                    "hashtags": [{"tag": "AI"}, {"tag": "EdTech"}]
                }
            }
        ],
        "includes": {
            "users": [
                {"id": "98765", "username": "sih_analyst", "name": "SIH Analyst"}
            ]
        }
    }

    conn = TwitterConnector(bearer_token="mock_token")
    records = conn._parse_tweets(sample_payload)
    assert len(records) == 1
    rec = records[0]
    assert rec.platform == "Twitter / X"
    assert rec.content_id == "tw_1892837465"
    assert "higher education" in rec.text
    assert rec.author_name == "@sih_analyst"
    assert rec.engagement["likes"] == 280
    assert rec.engagement["shares"] == 45
    assert rec.engagement["comments"] == 12
    assert "AI" in rec.topic_keywords
    assert rec.source_url == "https://x.com/sih_analyst/status/1892837465"


# ---------------------------------------------------------------------------
# 11. Instagram & Facebook Connector Tests (Stage 3D)
# ---------------------------------------------------------------------------

def test_instagram_connector_unconfigured():
    from backend.connectors.meta_connectors import InstagramConnector

    conn = InstagramConnector()
    health = conn.check_health()
    assert health.status == PlatformStatus.UNAVAILABLE
    assert "meta app review" in health.reason.lower()


def test_facebook_connector_unconfigured():
    from backend.connectors.meta_connectors import FacebookConnector

    conn = FacebookConnector()
    health = conn.check_health()
    assert health.status == PlatformStatus.UNAVAILABLE
    assert "meta app review" in health.reason.lower()


def test_meta_connectors_unconfigured_return_empty():
    import asyncio
    from backend.connectors.meta_connectors import InstagramConnector, FacebookConnector

    ig = InstagramConnector()
    fb = FacebookConnector()

    assert asyncio.run(ig.search("test")) == []
    assert asyncio.run(ig.fetch_comments("123")) == []
    assert asyncio.run(fb.search("test")) == []
    assert asyncio.run(fb.fetch_comments("123")) == []


# ---------------------------------------------------------------------------
# 12. Full 6-Platform Registry Verification
# ---------------------------------------------------------------------------

def test_full_6_platform_registry_initialization():
    from backend.connectors.registry import get_registry

    reg = get_registry()
    all_caps = reg.all_capabilities()
    expected_platforms = ["YouTube", "Telegram", "Reddit", "Twitter / X", "Instagram", "Facebook"]

    for plat in expected_platforms:
        assert plat in all_caps, f"Platform {plat} missing from registry"
        assert reg.get_connector(plat) is not None, f"Connector {plat} not registered"


