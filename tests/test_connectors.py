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
from datetime import datetime
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
        timestamp=datetime.utcnow(),
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
            timestamp=datetime.utcnow(),
            text="Great tutorial on AI",
            engagement={"views": 1000, "likes": 100, "comments": 20, "shares": 5},
        ),
        SocialRecord(
            platform="YouTube",
            content_id="2",
            content_type="video",
            timestamp=datetime.utcnow(),
            text="Second video",
            engagement={"views": 2000, "likes": 200, "comments": 30, "shares": 10},
        ),
    ]
    metrics = _compute_real_metrics(records)
    assert metrics["reach"] == 3000
    assert metrics["likes"] == 300
    assert metrics["comments"] == 50
    assert metrics["content_volume"] == 2
    assert metrics["engagement_rate"] > 0


def test_compute_real_sentiment():
    records = [
        SocialRecord(platform="YT", content_id="1", content_type="comment", timestamp=datetime.utcnow(), text="This is great and amazing, love it!"),
        SocialRecord(platform="YT", content_id="2", content_type="comment", timestamp=datetime.utcnow(), text="Very helpful and wonderful resource"),
        SocialRecord(platform="YT", content_id="3", content_type="comment", timestamp=datetime.utcnow(), text="Terrible and bad quality"),
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
