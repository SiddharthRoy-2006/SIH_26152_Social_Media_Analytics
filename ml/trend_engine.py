"""
ml/trend_engine.py

Simulated real-time trend and topic detection engine.

Generates Top-N trending topics with growth scores, keywords, influencer
associations and directional indicators.  All output is deterministic for a
given (seed, tick) pair so the prototype remains reproducible while
demonstrating gradual drift between refresh cycles.

Future replacement: BERTopic / LDA on live scraped text.
"""

from __future__ import annotations

import math
from typing import Any

# ---------------------------------------------------------------------------
# Topic banks (used to build plausible simulated topic names)
# ---------------------------------------------------------------------------

_TOPIC_BANKS: dict[str, list[str]] = {
    "general": [
        "AI in Education", "Digital Literacy", "Youth Innovation", "Ed-Tech Growth",
        "Online Learning", "STEM Careers", "Digital Inclusion", "Future of Work",
        "Climate Awareness", "Mental Health Advocacy", "Women in Tech",
        "Sustainable Living", "Blockchain in Finance", "Open Source Culture",
        "Cybersecurity Awareness", "Smart Cities", "Health Tech", "Green Energy",
        "Data Privacy", "Social Commerce",
    ],
    "education": [
        "Education Policy", "NEP 2020 Impact", "Higher Education Reform",
        "Digital Classrooms", "Teacher Training", "Student Wellbeing",
        "University Rankings", "Scholarship Access", "Coding for Kids",
        "STEM Education", "Blended Learning", "EdTech Funding",
    ],
    "technology": [
        "Generative AI", "Large Language Models", "Quantum Computing",
        "AR/VR Adoption", "5G Rollout", "Edge Computing", "Open AI Debate",
        "AI Regulation", "Chip Shortage", "Tech Layoffs",
    ],
    "health": [
        "Mental Health Awareness", "Telehealth Growth", "Vaccine Literacy",
        "Nutrition Science", "Fitness Culture", "Sleep Health", "Pandemic Preparedness",
        "AI in Diagnostics", "Healthcare Access", "Drug Pricing",
    ],
    "politics": [
        "Election Integrity", "Policy Debate", "Youth in Politics",
        "Governance Transparency", "Climate Policy", "Economic Reform",
        "Rural Development", "Urban Infrastructure", "Social Justice",
        "Human Rights",
    ],
}

_KEYWORD_BANK: list[str] = [
    "#AIRevolution", "#EdTech2025", "#FutureReady", "#LearnToLead",
    "#YouthPower", "#InnovateIndia", "#DigitalIndia", "#SkillIndia",
    "#TechForGood", "#GreenFuture", "#MentalHealthMatters",
    "#WomenInSTEM", "#OpenSource", "#DataPrivacy", "#ClimateAction",
    "#SmartCities", "#StartupIndia", "#VoicesOfYouth", "#CivicTech",
    "#CommunityFirst",
]

_INFLUENCER_NAMES: list[str] = [
    "Dr. Priya Sharma", "Arjun Mehta", "Sunita Rao", "Kiran Patel",
    "Rahul Verma", "Nisha Gupta", "Amit Singh", "Deepa Krishnan",
    "Vikram Joshi", "Ananya Desai", "Ravi Kumar", "Meera Nair",
    "Sanjay Bhatia", "Pooja Reddy", "Aditya Shah",
]


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def _lcg(seed: int) -> int:
    """Minimal linear congruential generator for deterministic pseudo-random."""
    return (seed * 1664525 + 1013904223) & 0xFFFFFFFF


def _pick(items: list, seed: int) -> Any:
    return items[seed % len(items)]


def _drift(value: int, tick: int, amplitude: int = 15) -> int:
    """Apply a gentle sine-wave drift to a value based on refresh tick."""
    offset = int(math.sin(tick * 0.7 + value * 0.3) * amplitude)
    return max(0, value + offset)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_topic_bank(topic: str) -> list[str]:
    """Return the most relevant topic bank for a given user topic string."""
    t = topic.lower()
    for key in _TOPIC_BANKS:
        if key in t:
            return _TOPIC_BANKS[key]
    return _TOPIC_BANKS["general"]


def generate_top_trends(
    seed: int,
    tick: int,
    topic: str = "",
    platform: str = "All Platforms",
    period: str = "Last 30 Days",
    n: int = 10,
) -> list[dict[str, Any]]:
    """
    Generate top-N trending topics with full metadata.

    Each trend includes:
        rank, name, score, growth_pct, direction, keyword,
        influencer_name, influencer_score, mentions, activity_series
    """
    bank = get_topic_bank(topic)

    # If user gave a topic, inject it as rank-1 or rank-2
    inject_user_topic = bool(topic.strip())

    period_multiplier = {
        "Today": 0.4, "Last 7 Days": 0.7, "Last 30 Days": 1.0, "1 Year": 2.2,
    }.get(period, 1.0)

    trends: list[dict[str, Any]] = []
    used_names: set[str] = set()
    used_influencers: set[str] = set()

    if inject_user_topic:
        user_name = topic.strip()[:40]
        used_names.add(user_name)
        u_seed = seed
        u_score = int((850 + u_seed % 150) * period_multiplier)
        u_growth = round(180 + (u_seed % 120), 1)
        u_inf_idx = u_seed % len(_INFLUENCER_NAMES)
        u_inf_name = _INFLUENCER_NAMES[u_inf_idx]
        used_influencers.add(u_inf_name)
        trends.append({
            "rank": 1,
            "name": user_name,
            "score": _drift(u_score, tick, 40),
            "growth_pct": round(_drift(int(u_growth * 10), tick, 100) / 10, 1),
            "direction": "rising",
            "keyword": f"#{(''.join(user_name.split()))[:18]}",
            "influencer_name": u_inf_name,
            "influencer_score": round(0.82 + (u_seed % 15) / 100, 2),
            "mentions": _drift(int(12000 * period_multiplier + u_seed % 4000), tick, 500),
            "activity_series": _generate_activity_series(u_seed, tick, 7),
        })

    for i in range(n - len(trends)):
        s = _lcg(seed + i * 397 + 1)

        # Pick a unique topic name
        attempts = 0
        while attempts < 30:
            name = _pick(bank, s + attempts)
            if name not in used_names:
                break
            attempts += 1
        used_names.add(name)

        base_score = int((700 - i * 55 + s % 120) * period_multiplier)
        growth = round((160 - i * 14 + s % 60), 1)
        direction = "rising" if growth > 30 else ("falling" if growth < 0 else "stable")

        # Pick a unique influencer
        inf_attempts = 0
        while inf_attempts < len(_INFLUENCER_NAMES):
            inf_name = _INFLUENCER_NAMES[(s + inf_attempts) % len(_INFLUENCER_NAMES)]
            if inf_name not in used_influencers:
                break
            inf_attempts += 1
        used_influencers.add(inf_name)

        inf_score = round(0.92 - i * 0.04 + (s % 10) / 100, 2)
        keyword = _KEYWORD_BANK[(s + i) % len(_KEYWORD_BANK)]
        mentions = _drift(int((9000 - i * 700 + s % 2000) * period_multiplier), tick, 300)

        trends.append({
            "rank": len(trends) + 1,
            "name": name,
            "score": _drift(max(50, base_score), tick, 30),
            "growth_pct": round(_drift(int(max(-20, growth) * 10), tick, 80) / 10, 1),
            "direction": direction,
            "keyword": keyword,
            "influencer_name": inf_name,
            "influencer_score": max(0.30, min(0.99, inf_score)),
            "mentions": max(100, mentions),
            "activity_series": _generate_activity_series(s, tick, 7),
        })

    # Re-sort by score (user topic may shift with drift)
    trends.sort(key=lambda t: t["score"], reverse=True)
    for idx, t in enumerate(trends):
        t["rank"] = idx + 1

    return trends[:n]


def _generate_activity_series(seed: int, tick: int, length: int = 7) -> list[int]:
    """Generate a short activity time-series for sparklines."""
    base = 40 + seed % 40
    return [
        max(5, _drift(int(base * (0.6 + 0.1 * i + (seed % 30) / 100)), tick + i, 10))
        for i in range(length)
    ]
