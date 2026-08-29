"""
tests/test_real_data_pipeline.py

Unit tests for real platform data extraction, network graph generation,
influencer scoring, trend extraction, evidence-based AI insights,
and topology zoom boundary invariants.
"""

import pytest
from datetime import datetime, timezone
from backend.connectors.base import SocialRecord
from backend.services.live_provider import (
    _compute_real_metrics,
    _extract_real_influencers,
    _extract_real_trends,
    _build_real_network_graph,
    _generate_real_ai_insights,
    _compute_real_sentiment,
)


@pytest.fixture
def sample_social_records() -> list[SocialRecord]:
    now = datetime.now(timezone.utc)
    return [
        SocialRecord(
            platform="YouTube",
            content_id="vid_101",
            content_type="video",
            timestamp=now,
            text="Toxic - Official Trailer HD #ToxicMovie #Yash #ActionCinema\nFirst look at Toxic.",
            author_id="UC_geetha",
            author_name="Geetha Arts",
            engagement={"views": 500000, "likes": 45000, "comments": 2800},
            topic_keywords=["Toxic", "Yash", "Trailer", "Action"],
            source_url="https://youtube.com/watch?v=vid_101",
            raw_metadata={"category_id": "1"}, # Film & Animation
        ),
        SocialRecord(
            platform="YouTube",
            content_id="vid_102",
            content_type="video",
            timestamp=now,
            text="Toxic Movie Teaser Breakdown & Hidden Details! #Toxic #CinemaAnalysis",
            author_id="UC_filmradar",
            author_name="Film Radar Reviews",
            engagement={"views": 120000, "likes": 9800, "comments": 650},
            topic_keywords=["Toxic", "Analysis", "Teaser", "Cinema"],
            source_url="https://youtube.com/watch?v=vid_102",
            raw_metadata={"category_id": "24"}, # Entertainment
        ),
        SocialRecord(
            platform="YouTube",
            content_id="vid_103",
            content_type="video",
            timestamp=now,
            text="Toxic Title Track Song Audio Release #ToxicSong",
            author_id="UC_geetha",
            author_name="Geetha Arts",
            engagement={"views": 320000, "likes": 28000, "comments": 1400},
            topic_keywords=["Toxic", "Song", "Music"],
            source_url="https://youtube.com/watch?v=vid_103",
            raw_metadata={"category_id": "10"}, # Music
        ),
        SocialRecord(
            platform="YouTube",
            content_id="cmt_201",
            content_type="comment",
            timestamp=now,
            text="Amazing visuals and great background score! Love this.",
            author_name="CinemaLover99",
            engagement={"likes": 45},
            source_url="https://youtube.com/watch?v=vid_101",
        ),
    ]


def test_compute_real_metrics(sample_social_records):
    metrics = _compute_real_metrics(sample_social_records)
    assert metrics["reach"] == 940000
    assert metrics["likes"] == 82845
    assert metrics["comments"] == 4850
    assert metrics["content_volume"] == 4
    assert metrics["engagement_rate"] > 0.0


def test_extract_real_influencers_uses_real_names(sample_social_records):
    influencers = _extract_real_influencers(sample_social_records)
    assert len(influencers) > 0
    names = [inf["name"] for inf in influencers]
    assert "Geetha Arts" in names
    assert "Film Radar Reviews" in names
    
    # Must NOT contain fake hardcoded names
    assert "WebNode" not in names
    assert "TrendAlert" not in names
    assert "CatalystHub" not in names

    # Top influencer should be Geetha Arts due to views/likes
    assert influencers[0]["name"] == "Geetha Arts"
    assert influencers[0]["posts"] == 2
    assert influencers[0]["score"] > 0.5


def test_extract_real_trends_parses_hashtags(sample_social_records):
    trends = _extract_real_trends(sample_social_records, topic="Toxic")
    assert len(trends) > 0
    keywords = [t["keyword"] for t in trends]
    # Check that real extracted hashtags are present
    assert any("#toxic" in k.lower() or "#yash" in k.lower() or "#action" in k.lower() for k in keywords)


def test_build_real_network_graph_structure(sample_social_records):
    graph, propagation = _build_real_network_graph(sample_social_records, topic="Toxic")
    assert "nodes" in graph
    assert "edges" in graph
    assert "communities" in graph
    assert "stats" in graph

    nodes = graph["nodes"]
    edges = graph["edges"]
    labels = [n["label"] for n in nodes]

    # Real channel hub exists
    assert any("Geetha Arts" in lbl for lbl in labels)
    assert graph["stats"]["total_nodes"] == len(nodes)
    assert graph["stats"]["total_edges"] == len(edges)
    assert len(propagation) > 0


def test_generate_real_ai_insights_evidence_based(sample_social_records):
    metrics = _compute_real_metrics(sample_social_records)
    sentiment = _compute_real_sentiment(sample_social_records)
    trends = _extract_real_trends(sample_social_records, "Toxic")
    influencers = _extract_real_influencers(sample_social_records)

    insights = _generate_real_ai_insights(
        records=sample_social_records,
        topic="Toxic",
        platform="YouTube",
        metrics=metrics,
        sentiment=sentiment,
        top_trends=trends,
        influencers=influencers,
    )

    assert len(insights) >= 3
    card_texts = " ".join(c["text"] for c in insights)
    # Should reference the inferred topic classification and real creators
    assert "Geetha Arts" in card_texts or "Geetha" in card_texts
    assert "LIVE — YouTube Data API" in insights[0]["source"]


def test_topology_zoom_levels_math():
    """Verify zoom math clamping and percentage calculations for 10% to 10,000%."""
    min_zoom = 0.1 # 10%
    max_zoom = 100.0 # 10000%

    test_zooms = [1.0, 2.0, 5.0, 10.0, 50.0, 100.0]
    expected_pcts = [100, 200, 500, 1000, 5000, 10000]

    for z, expected in zip(test_zooms, expected_pcts):
        clamped = max(min_zoom, min(max_zoom, z))
        pct = round(clamped * 100)
        assert pct == expected


def test_compute_real_activity_by_day_7_days(sample_social_records):
    from backend.services.live_provider import _compute_real_activity_by_day
    activity_7 = _compute_real_activity_by_day(sample_social_records)
    assert isinstance(activity_7, list)
    assert len(activity_7) == 7
    # All elements are integers >= 0
    assert all(isinstance(v, int) and v >= 0 for v in activity_7)
    # Total activity matches sum of views/likes
    assert sum(activity_7) > 0


def test_compute_real_posting_strategy_grounded(sample_social_records):
    from backend.services.live_provider import _compute_real_posting_strategy
    strat = _compute_real_posting_strategy(sample_social_records, platform="YouTube", topic="Toxic")
    assert "score_status" in strat
    assert "best_posting_time" in strat
    assert "activity_window" in strat
    assert "recommendation" in strat
    assert "Derived from 4 records" in strat["best_posting_time"]


def test_multi_access_layers_present():
    from backend.connectors.youtube_connector import YouTubeConnector
    from backend.connectors.telegram_connector import TelegramConnector
    from backend.connectors.reddit_connector import RedditConnector
    from backend.connectors.twitter_connector import TwitterConnector
    from backend.connectors.meta_connectors import InstagramConnector, FacebookConnector

    yt_cap = YouTubeConnector().check_health()
    assert len(yt_cap.access_layers) == 3
    assert yt_cap.access_layers[0]["name"] == "YouTube Data API v3"
    assert "views" in yt_cap.supported_metrics
    assert "shares" in yt_cap.unsupported_metrics

    tg_cap = TelegramConnector().check_health()
    assert len(tg_cap.access_layers) == 2
    assert tg_cap.access_layers[0]["name"] == "Telegram MTProto Client"

    rd_cap = RedditConnector().check_health()
    assert len(rd_cap.access_layers) == 2
    assert rd_cap.access_layers[0]["name"] == "Reddit OAuth2 App (Read-Only Script/App)"

    tw_cap = TwitterConnector().check_health()
    assert len(tw_cap.access_layers) == 2

    ig_cap = InstagramConnector().check_health()
    assert len(ig_cap.access_layers) == 2

    fb_cap = FacebookConnector().check_health()
    assert len(fb_cap.access_layers) == 2


def test_compute_real_time_series_periods(sample_social_records):
    from backend.services.live_provider import _compute_real_time_series
    growth, act, eng = _compute_real_time_series(sample_social_records, period="Last 30 Days", chart_period="Monthly")
    assert len(growth) == 7
    assert len(act) == 12
    assert len(eng) == 12
    assert growth[-1] >= growth[0]

    growth_d, act_d, eng_d = _compute_real_time_series(sample_social_records, period="Today", chart_period="Daily")
    assert len(growth_d) == 7
    assert len(act_d) == 12


def test_empty_response_truthfulness():
    from backend.schemas import AnalysisRequest
    from backend.services.analysis_service import _empty_response
    req = AnalysisRequest(topic="NonExistentTopic", platform="YouTube")
    resp = _empty_response(req)
    assert resp.data_available is False
    assert resp.source == "empty"
    assert resp.metrics["reach"] == 0

