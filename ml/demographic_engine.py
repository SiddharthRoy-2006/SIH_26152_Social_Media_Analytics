"""
ml/demographic_engine.py

Simulated audience demographic profiling engine.

Generates aggregate (anonymised-style) demographic intelligence:
  - Age group distribution
  - Geographic distribution (country/region)
  - Language distribution
  - Interest/professional segments

All values are deterministic for a given (seed, tick) pair.

Future replacement: real demographic inference from authenticated API data.
"""

from __future__ import annotations

import math
from typing import Any


def _drift_i(value: int, tick: int, amplitude: int = 6) -> int:
    offset = int(math.sin(tick * 0.6 + value * 0.7) * amplitude)
    return max(0, value + offset)


def _normalise_to_100(raw: dict[str, int]) -> dict[str, int]:
    """Scale a dict of ints to sum to 100, preserving key order."""
    total = sum(raw.values())
    if total == 0:
        return raw
    factor = 100 / total
    result: dict[str, int] = {}
    running = 0
    keys = list(raw.keys())
    for idx, key in enumerate(keys):
        if idx == len(keys) - 1:
            result[key] = 100 - running
        else:
            v = max(0, round(raw[key] * factor))
            result[key] = v
            running += v
    return result


def generate_age_groups(seed: int, tick: int) -> dict[str, int]:
    raw = {
        "13–17":  4 + (seed % 5),
        "18–24": 22 + (seed % 14),
        "25–34": 32 + (seed // 3 % 12),
        "35–44": 20 + (seed // 5 % 10),
        "45–54": 12 + (seed // 7 % 8),
        "55+":    6 + (seed // 11 % 6),
    }
    for key in raw:
        raw[key] = max(1, _drift_i(raw[key], tick + hash(key) % 50, 3))
    return _normalise_to_100(raw)


def generate_geo_distribution(
    seed: int,
    tick: int,
    platform: str = "All Platforms",
) -> dict[str, int]:
    """Top countries/regions by audience share."""
    base = {
        "India":          35 + (seed % 20),
        "United States":  18 + (seed // 3 % 10),
        "United Kingdom":  8 + (seed // 5 % 6),
        "Australia":       5 + (seed // 7 % 5),
        "Canada":          4 + (seed // 11 % 4),
        "Germany":         4 + (seed // 13 % 4),
        "Singapore":       3 + (seed // 17 % 3),
        "UAE":             3 + (seed // 19 % 3),
        "Others":         12 + (seed // 23 % 8),
    }
    # Platform-specific skew
    if platform == "YouTube":
        base["India"] = min(60, base["India"] + 8)
    elif platform == "Twitter / X":
        base["United States"] = min(40, base["United States"] + 8)
    elif platform == "Instagram":
        base["United States"] = min(35, base["United States"] + 5)
        base["India"] = min(50, base["India"] + 3)

    for key in base:
        base[key] = max(1, _drift_i(base[key], tick + hash(key) % 60, 2))
    return _normalise_to_100(base)


def generate_language_distribution(seed: int, tick: int) -> dict[str, int]:
    base = {
        "English": 52 + (seed % 18),
        "Hindi":   18 + (seed // 3 % 10),
        "Spanish":  6 + (seed // 5 % 5),
        "French":   4 + (seed // 7 % 4),
        "Arabic":   4 + (seed // 11 % 4),
        "Others":  10 + (seed // 13 % 6),
    }
    for key in base:
        base[key] = max(1, _drift_i(base[key], tick + hash(key) % 40, 2))
    return _normalise_to_100(base)


def generate_interest_segments(seed: int, tick: int, topic: str = "") -> dict[str, int]:
    base = {
        "Education & Learning": 28 + (seed % 14),
        "Technology":           20 + (seed // 3 % 12),
        "Career & Jobs":        16 + (seed // 5 % 10),
        "News & Politics":      12 + (seed // 7 % 8),
        "Entertainment":        10 + (seed // 11 % 7),
        "Health & Wellness":     8 + (seed // 13 % 6),
        "Finance":               6 + (seed // 17 % 5),
    }

    # Boost relevant segment if topic hint matches
    t = topic.lower()
    if any(w in t for w in ["education", "school", "learn", "study", "nep"]):
        base["Education & Learning"] = min(60, base["Education & Learning"] + 15)
    elif any(w in t for w in ["tech", "ai", "digital", "code", "software"]):
        base["Technology"] = min(55, base["Technology"] + 12)
    elif any(w in t for w in ["health", "mental", "wellness", "medical"]):
        base["Health & Wellness"] = min(50, base["Health & Wellness"] + 12)
    elif any(w in t for w in ["politic", "policy", "govern", "election"]):
        base["News & Politics"] = min(50, base["News & Politics"] + 12)

    for key in base:
        base[key] = max(1, _drift_i(base[key], tick + hash(key) % 45, 2))
    return _normalise_to_100(base)
