"""
backend/services/analysis_service.py

Data providers for the /analysis endpoint.

Providers:
  EmptyDataProvider   - honest zero-state; used when no data source is configured
  DemoDataProvider    - rich deterministic demo data using ml/ simulation engines
  PlatformDataProvider - Protocol that future real-API providers must implement

Data evolution:
  refresh_tick (int) is passed in from the request. When tick=0, the router
  auto-assigns int(time.time() // 60) so demo data drifts on a ~60-second cycle
  without jumping erratically.
"""

from __future__ import annotations

import math
from typing import Protocol

from backend.schemas import AnalysisRequest, AnalysisResponse

# ml engines (simulation layer)
from ml.demographic_engine import (
    generate_age_groups,
    generate_geo_distribution,
    generate_interest_segments,
    generate_language_distribution,
)
from ml.insight_engine import generate_insights
from ml.network_engine import (
    generate_influencers,
    generate_network_graph,
    generate_propagation_path,
)
from ml.sentiment_engine import (
    generate_emotions,
    generate_sentiment,
    generate_sentiment_series,
)
from ml.trend_engine import generate_top_trends


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

class PlatformDataProvider(Protocol):
    """Future authorised platform/API implementations follow this interface."""
    def get_analysis(self, request: AnalysisRequest) -> AnalysisResponse: ...


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_seed(topic: str, query: str, platform: str, period: str, chart_period: str) -> int:
    seed_text = f"{platform}|{topic.strip()}|{query.strip()}|{period}|{chart_period}"
    return sum((i + 1) * ord(c) for i, c in enumerate(seed_text))


def _drift_i(value: int, tick: int, amplitude: int = 10) -> int:
    offset = int(math.sin(tick * 0.7 + value * 0.4) * amplitude)
    return max(0, value + offset)


_PERIOD_MULT = {
    "Today": 0.35, "Last 7 Days": 0.65, "Last 30 Days": 1.0, "1 Year": 2.4,
}

_PLATFORM_MULT = {
    "Instagram": 1.0, "YouTube": 1.15, "Facebook": 0.85,
    "Twitter / X": 0.90, "All Platforms": 2.5,
}


# ---------------------------------------------------------------------------
# Empty response
# ---------------------------------------------------------------------------

def _empty_response(request: AnalysisRequest) -> AnalysisResponse:
    return AnalysisResponse(
        platform=request.platform,
        topic=request.topic,
        query=request.query,
        period=request.period,
        chart_period=request.chart_period,
        data_available=False,
        source="empty",
        metrics={
            "followers": 0, "reach": 0, "likes": 0, "comments": 0,
            "shares": 0, "content_volume": 0, "engagement_rate": 0, "growth": 0,
        },
        audience={"age18_24": 0, "age25_34": 0, "age35_44": 0, "age45": 0},
        sentiment={"positive": 0, "negative": 0, "neutral": 0},
        emotions={
            "happy": 0, "sad": 0, "angry": 0, "fear": 0,
            "surprise": 0, "disgust": 0, "other": 0,
        },
        trending={"topic": "No information", "keyword": "No information", "topics": [], "keywords": []},
        network={"nodes": 0, "connections": 0, "communities": 0},
        activity=[0, 0, 0, 0, 0],
        growth_series=[],
        insights={
            "score_status": "No information", "score_message": "No information",
            "best_posting_time": "No information", "growth_signal": "No information",
            "recommendation": "No information", "activity_window": "No information",
        },
        mode="topic",
        refresh_tick=request.refresh_tick,
    )


# ---------------------------------------------------------------------------
# Empty provider
# ---------------------------------------------------------------------------

class EmptyDataProvider:
    """Default provider: honest zero state until authorised data is connected."""
    def get_analysis(self, request: AnalysisRequest) -> AnalysisResponse:
        return _empty_response(request)


# ---------------------------------------------------------------------------
# Demo provider
# ---------------------------------------------------------------------------

class DemoDataProvider:
    """Dynamic local mock data for the hackathon prototype."""

    def get_analysis(self, request: AnalysisRequest) -> AnalysisResponse:
        seed = _make_seed(
            request.topic, request.query,
            request.platform, request.period, request.chart_period,
        )
        tick = request.refresh_tick

        pm = _PERIOD_MULT.get(request.period, 1.0)
        plat_m = _PLATFORM_MULT.get(request.platform, 1.0)
        scale = pm * plat_m

        topic = request.topic.strip() or "Digital Education"
        keyword = f"#{''.join(topic.split())[:18]}"

        # ----- core metrics -----
        reach        = _drift_i(int((18000 + seed % 12000) * scale), tick, 800)
        followers    = _drift_i(int(reach * (0.55 + (seed % 30) / 100)), tick + 1, 400)
        likes        = _drift_i(int(reach * (0.08 + (seed % 50) / 1000)), tick + 2, 200)
        comments     = _drift_i(int(likes * (0.08 + (seed % 30) / 1000)), tick + 3, 50)
        shares       = _drift_i(int(likes * (0.04 + (seed % 20) / 1000)), tick + 4, 30)
        content_vol  = 8 + (seed % 25)
        engagement   = round(((likes + comments + shares) / max(reach, 1)) * 100, 1)
        growth       = round(5 + (seed % 220) / 10 + math.sin(tick * 0.5) * 3, 1)

        # ----- audience (legacy 4-bucket for backward compat) -----
        age18_24 = 20 + (seed % 15)
        age25_34 = 30 + ((seed // 3) % 12)
        age35_44 = 20 + ((seed // 5) % 10)
        age45    = max(0, 100 - age18_24 - age25_34 - age35_44)

        # ----- sentiment -----
        topic_modifier = 0.2 if "education" in topic.lower() else 0.0
        sentiment_dict  = generate_sentiment(seed, tick, request.period, topic_modifier)
        emotions_dict   = generate_emotions(seed, tick)

        # Full 11-emotion breakdown (all keys explicit)
        legacy_emotions = dict(emotions_dict)  # copy all 11 keys
        # Normalise to 100
        total_emo = sum(legacy_emotions.values())
        if total_emo != 100 and total_emo > 0:
            diff = 100 - total_emo
            legacy_emotions["happy"] = max(0, legacy_emotions.get("happy", 0) + diff)

        # ----- activity series -----
        activity_5 = [
            _drift_i(35 + (seed % 30), tick, 8),
            _drift_i(45 + ((seed // 2) % 35), tick + 1, 8),
            _drift_i(55 + ((seed // 3) % 40), tick + 2, 8),
            _drift_i(65 + ((seed // 5) % 30), tick + 3, 8),
            _drift_i(50 + ((seed // 7) % 35), tick + 4, 8),
        ]

        # ----- growth series (7 points for chart) -----
        growth_series = [
            _drift_i(int(reach * r), tick, 300)
            for r in [0.45, 0.55, 0.63, 0.72, 0.82, 0.92, 1.0]
        ]

        # ----- trending -----
        top_trends = generate_top_trends(seed, tick, topic, request.platform, request.period, n=10)
        topic_variants = [t["name"] for t in top_trends[:3]]
        keywords = [t["keyword"] for t in top_trends[:3]]

        # ----- network -----
        n_nodes_base = 80 + (seed % 90)
        net_graph = generate_network_graph(seed, tick, topic, n_nodes=min(n_nodes_base, 55))
        influencers = generate_influencers(seed, tick, net_graph, top_n=8)
        propagation = generate_propagation_path(seed, tick, topic, net_graph, steps=5)

        network_legacy = {
            "nodes": net_graph["stats"]["total_nodes"],
            "connections": net_graph["stats"]["total_edges"],
            "communities": net_graph["stats"]["n_communities"],
        }

        # ----- insights dict (legacy format) -----
        engagement_label = "Strong engagement" if engagement >= 12 else "Moderate engagement"
        positive = sentiment_dict["positive"]
        negative = sentiment_dict["negative"]

        insights_dict = {
            "score_status":      engagement_label,
            "score_message":     f"{topic} is showing {engagement_label.lower()}.",
            "best_posting_time": "7:00 PM – 9:00 PM",
            "growth_signal":     f"Reach is up {growth:.1f}% from the previous period.",
            "recommendation":    f"Focus on high-engagement content around {topic}.",
            "activity_window":   "Most active Wednesday to Friday",
        }

        # ----- extended fields -----
        sentiment_series = generate_sentiment_series(seed, tick, length=12, base_positive=positive)
        age_groups = generate_age_groups(seed, tick)
        geo_dist   = generate_geo_distribution(seed, tick, request.platform)
        lang_dist  = generate_language_distribution(seed, tick)
        interests  = generate_interest_segments(seed, tick, topic)

        activity_series = [
            _drift_i(int(reach * r / 100), tick, 150)
            for r in [40, 48, 57, 63, 72, 80, 88, 92, 95, 92, 87, 80]
        ]
        engagement_series = [
            round(engagement * (0.7 + 0.05 * i) + math.sin(i * 0.8 + tick * 0.3) * 1.2, 1)
            for i in range(12)
        ]

        ai_insights = generate_insights(
            seed=seed, tick=tick,
            metrics={"reach": reach, "growth": growth, "engagement_rate": engagement},
            sentiment=sentiment_dict,
            top_trends=top_trends,
            influencers=influencers,
            insights_dict=insights_dict,
            sentiment_series=sentiment_series,
            topic=topic,
        )

        return AnalysisResponse(
            platform=request.platform,
            topic=request.topic,
            query=request.query,
            period=request.period,
            chart_period=request.chart_period,
            data_available=True,
            source="demo",
            refresh_tick=tick,
            mode="topic",
            # legacy keys
            metrics={
                "followers": followers, "reach": reach, "likes": likes,
                "comments": comments, "shares": shares,
                "content_volume": content_vol,
                "engagement_rate": engagement, "growth": growth,
            },
            audience={"age18_24": age18_24, "age25_34": age25_34, "age35_44": age35_44, "age45": age45},
            sentiment=sentiment_dict,
            emotions=legacy_emotions,
            trending={
                "topic": topic, "keyword": keywords[0] if keywords else keyword,
                "topics": topic_variants, "keywords": keywords,
            },
            network=network_legacy,
            activity=activity_5,
            growth_series=growth_series,
            insights=insights_dict,
            # extended keys
            ai_insights=ai_insights,
            sentiment_series=sentiment_series,
            top_trends=top_trends,
            influencers=influencers,
            network_graph={
                "nodes": net_graph["nodes"],
                "edges": net_graph["edges"],
                "communities": net_graph["communities"],
                "stats": net_graph["stats"],
                "propagation": propagation,
            },
            geo_distribution=geo_dist,
            language_distribution=lang_dist,
            interest_segments=interests,
            activity_series=activity_series,
            engagement_series=engagement_series,
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_provider(data_mode: str) -> PlatformDataProvider:
    if data_mode == "demo":
        return DemoDataProvider()
    return EmptyDataProvider()
