"""
backend/services/general_service.py

Data providers for the /general endpoint (ecosystem-wide intelligence).

GeneralDataProvider uses the ml/ engines to produce a broad cross-platform
aggregate view that does not require a specific topic.
"""

from __future__ import annotations

import math
from typing import Protocol

from backend.schemas import GeneralRequest, GeneralResponse
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


class GeneralDataProvider(Protocol):
    def get_general(self, request: GeneralRequest) -> GeneralResponse: ...


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_seed(platform: str, period: str, chart_period: str) -> int:
    text = f"GENERAL|{platform}|{period}|{chart_period}"
    return sum((i + 1) * ord(c) for i, c in enumerate(text))


def _drift_i(value: int, tick: int, amplitude: int = 15) -> int:
    offset = int(math.sin(tick * 0.7 + value * 0.4) * amplitude)
    return max(0, value + offset)


_PERIOD_MULT = {
    "Today": 0.45, "Last 7 Days": 0.70, "Last 30 Days": 1.0, "1 Year": 3.0,
}
_PLATFORM_MULT = {
    "All Platforms": 4.5, "Instagram": 1.0, "YouTube": 1.2,
    "Facebook": 0.9, "Twitter / X": 0.85,
}


class EmptyGeneralProvider:
    def get_general(self, request: GeneralRequest) -> GeneralResponse:
        return GeneralResponse(
            platform=request.platform,
            topic="", query="",
            period=request.period, chart_period=request.chart_period,
            data_available=False, source="empty",
            metrics={"followers":0,"reach":0,"likes":0,"comments":0,"shares":0,"content_volume":0,"engagement_rate":0,"growth":0},
            audience={"age18_24":0,"age25_34":0,"age35_44":0,"age45":0},
            sentiment={"positive":0,"negative":0,"neutral":0},
            emotions={"happy":0,"sad":0,"angry":0,"fear":0,"surprise":0,"disgust":0,"other":0},
            trending={"topic":"No information","keyword":"No information","topics":[],"keywords":[]},
            network={"nodes":0,"connections":0,"communities":0},
            activity=[0,0,0,0,0], growth_series=[],
            insights={"score_status":"No information","score_message":"No information","best_posting_time":"No information","growth_signal":"No information","recommendation":"No information","activity_window":"No information"},
            mode="general", refresh_tick=request.refresh_tick,
        )


class DemoGeneralProvider:
    """Ecosystem-wide demo data provider."""

    def get_general(self, request: GeneralRequest) -> GeneralResponse:
        seed = _make_seed(request.platform, request.period, request.chart_period)
        tick = request.refresh_tick
        pm = _PERIOD_MULT.get(request.period, 1.0)
        plat_m = _PLATFORM_MULT.get(request.platform, 4.5)
        scale = pm * plat_m

        # ----- aggregate metrics (much larger than topic-level) -----
        reach      = _drift_i(int((220000 + seed % 80000) * scale), tick, 5000)
        followers  = _drift_i(int(reach * 0.60), tick + 1, 2000)
        likes      = _drift_i(int(reach * 0.09), tick + 2, 1000)
        comments   = _drift_i(int(likes * 0.09), tick + 3, 200)
        shares     = _drift_i(int(likes * 0.05), tick + 4, 100)
        content_vol = 150 + (seed % 100)
        engagement  = round(((likes + comments + shares) / max(reach, 1)) * 100, 1)
        growth      = round(8 + (seed % 180) / 10 + math.sin(tick * 0.5) * 2, 1)

        # ----- legacy audience -----
        age18_24 = 22 + (seed % 14)
        age25_34 = 31 + ((seed // 3) % 11)
        age35_44 = 20 + ((seed // 5) % 9)
        age45    = max(0, 100 - age18_24 - age25_34 - age35_44)

        # ----- sentiment -----
        sentiment_dict = generate_sentiment(seed, tick, request.period, 0.1)
        emotions_dict  = generate_emotions(seed, tick)
        # Full 11-emotion breakdown
        legacy_emotions = dict(emotions_dict)
        total_emo = sum(legacy_emotions.values())
        if total_emo != 100 and total_emo > 0:
            diff = 100 - total_emo
            legacy_emotions["happy"] = max(0, legacy_emotions.get("happy", 0) + diff)

        # ----- activity -----
        activity_5 = [
            _drift_i(55 + (seed % 25), tick, 10),
            _drift_i(62 + ((seed // 2) % 20), tick + 1, 10),
            _drift_i(70 + ((seed // 3) % 20), tick + 2, 10),
            _drift_i(75 + ((seed // 5) % 15), tick + 3, 10),
            _drift_i(68 + ((seed // 7) % 20), tick + 4, 10),
        ]
        growth_series = [
            _drift_i(int(reach * r), tick, 2000)
            for r in [0.42, 0.52, 0.61, 0.70, 0.81, 0.91, 1.0]
        ]

        # ----- trends (10 for general) -----
        top_trends = generate_top_trends(seed, tick, "", request.platform, request.period, n=10)
        topic_variants = [t["name"] for t in top_trends[:5]]
        keywords = [t["keyword"] for t in top_trends[:5]]

        # ----- network -----
        net_graph    = generate_network_graph(seed, tick, "", n_nodes=55, n_communities=6)
        influencers  = generate_influencers(seed, tick, net_graph, top_n=10)
        propagation  = generate_propagation_path(seed, tick, "Trending Narrative", net_graph, steps=5)
        network_legacy = {
            "nodes": net_graph["stats"]["total_nodes"],
            "connections": net_graph["stats"]["total_edges"],
            "communities": net_graph["stats"]["n_communities"],
        }

        # ----- insights dict -----
        positive  = sentiment_dict["positive"]
        negative  = sentiment_dict["negative"]
        eng_label = "Strong engagement" if engagement >= 12 else "Moderate engagement"
        insights_dict = {
            "score_status":      eng_label,
            "score_message":     f"Overall ecosystem showing {eng_label.lower()} across platforms.",
            "best_posting_time": "8:00 PM – 10:00 PM",
            "growth_signal":     f"Ecosystem reach grew {growth:.1f}% vs previous period.",
            "recommendation":    "Cross-platform content strategy recommended for maximum reach.",
            "activity_window":   "Tuesday to Saturday, peak hours 7–11 PM",
        }

        # ----- extended fields -----
        sentiment_series   = generate_sentiment_series(seed, tick, 12, positive)
        age_groups         = generate_age_groups(seed, tick)
        geo_dist           = generate_geo_distribution(seed, tick, request.platform)
        lang_dist          = generate_language_distribution(seed, tick)
        interests          = generate_interest_segments(seed, tick, "")
        activity_series    = [
            _drift_i(int(reach * r / 100), tick, 300)
            for r in [38,46,54,61,70,79,86,91,94,90,85,78]
        ]
        engagement_series  = [
            round(engagement * (0.65 + 0.04 * i) + math.sin(i * 0.8 + tick * 0.3) * 1.0, 1)
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
            topic="",
        )

        return GeneralResponse(
            platform=request.platform,
            topic="", query="",
            period=request.period, chart_period=request.chart_period,
            data_available=True, source="demo",
            refresh_tick=tick, mode="general",
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
                "topic": top_trends[0]["name"] if top_trends else "No information",
                "keyword": keywords[0] if keywords else "No information",
                "topics": topic_variants, "keywords": keywords,
            },
            network=network_legacy,
            activity=activity_5,
            growth_series=growth_series,
            insights=insights_dict,
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


def get_general_provider(data_mode: str) -> GeneralDataProvider:
    if data_mode == "live":
        from backend.connectors.registry import get_registry
        from backend.services.live_provider import LiveGeneralProvider
        return LiveGeneralProvider(get_registry())
    if data_mode == "demo":
        return DemoGeneralProvider()
    return EmptyGeneralProvider()

