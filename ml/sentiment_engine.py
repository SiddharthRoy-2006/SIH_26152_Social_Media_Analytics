"""
ml/sentiment_engine.py

Extended sentiment and emotion distribution generator.

Produces:
  - 3-way sentiment split (positive / negative / neutral)
  - 11-emotion breakdown
  - Sentiment time-series (for trend charts)

All values are deterministic for a given (seed, tick) pair.

Future replacement: HuggingFace transformers sentiment + emotion classifiers
applied to live scraped text.
"""

from __future__ import annotations

import math
from typing import Any


def _drift_i(value: int, tick: int, amplitude: int = 8) -> int:
    offset = int(math.sin(tick * 0.8 + value * 0.5) * amplitude)
    return max(0, value + offset)


def generate_sentiment(
    seed: int,
    tick: int,
    period: str = "Last 30 Days",
    topic_modifier: float = 0.0,  # -1.0 (very negative) to +1.0 (very positive)
) -> dict[str, int]:
    """
    Generate a 3-way sentiment split that sums to 100.

    topic_modifier shifts the positive/negative balance.
    """
    # Base positive skewed toward optimistic for education/tech topics
    base_positive = 48 + int(topic_modifier * 18) + (seed % 22)
    base_positive = max(20, min(75, base_positive))
    base_positive = _drift_i(base_positive, tick, 6)

    base_negative = 10 + (seed // 7 % 14) - int(topic_modifier * 5)
    base_negative = max(5, min(40, base_negative))
    base_negative = _drift_i(base_negative, tick + 13, 4)

    # Clamp so they fit
    if base_positive + base_negative > 95:
        base_negative = 95 - base_positive

    neutral = 100 - base_positive - base_negative
    return {"positive": base_positive, "negative": base_negative, "neutral": neutral}


def generate_emotions(seed: int, tick: int) -> dict[str, int]:
    """
    Generate an 11-emotion distribution that sums to 100.

    Emotions:
        happy, sad, angry, fear, surprise, disgust,
        anxiety, excitement, supportive, opposition, sarcasm
    """
    raw = {
        "happy":       30 + (seed % 20),
        "excited":     10 + (seed // 3 % 12),
        "supportive":  12 + (seed // 5 % 10),
        "surprise":     6 + (seed // 7 % 9),
        "sad":          4 + (seed // 2 % 7),
        "anxious":      4 + (seed // 11 % 6),
        "angry":        3 + (seed // 13 % 6),
        "opposition":   3 + (seed // 17 % 5),
        "fear":         2 + (seed // 19 % 5),
        "disgust":      2 + (seed // 23 % 4),
        "sarcasm":      1 + (seed // 29 % 3),
    }

    # Apply tick drift to each emotion
    for key in raw:
        raw[key] = max(0, _drift_i(raw[key], tick + hash(key) % 100, 3))

    total = sum(raw.values())
    if total == 0:
        raw["happy"] = 100
        return raw

    # Normalise to 100
    factor = 100 / total
    normalised: dict[str, int] = {}
    running = 0
    for idx, (key, value) in enumerate(raw.items()):
        if idx == len(raw) - 1:
            normalised[key] = 100 - running
        else:
            v = max(0, round(value * factor))
            normalised[key] = v
            running += v

    return normalised


def generate_sentiment_series(
    seed: int,
    tick: int,
    length: int = 12,
    base_positive: int = 55,
) -> list[int]:
    """
    Generate a sentiment-over-time series (positive sentiment % per period).
    Values drift naturally between refresh cycles.
    """
    series = []
    for i in range(length):
        # Gentle upward trend + noise
        trend = base_positive + int(i * 1.2)
        noise = int(math.sin(i * 1.3 + tick * 0.4 + seed * 0.001) * 7)
        val = max(15, min(90, trend + noise))
        series.append(val)
    return series
