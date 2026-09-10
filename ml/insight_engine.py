"""
ml/insight_engine.py

Lightweight data-driven simulation AI insight engine.

Reads current analytical metrics and generates structured insight cards.

Output format:
    [
        {
            "type":     "baseline" | "warning" | "alert" | "info",
            "severity": "low" | "medium" | "high",
            "icon":     "↗" | "⚠" | "🔥" | "💡" | "📊" | "👥" | "🌐",
            "title":    str,
            "text":     str,
        },
        ...
    ]

Rules:
  - Always generate 3–4 baseline insights computed from current data.
  - Conditionally add warning/alert insights when thresholds are triggered.
  - Text must use actual computed values (not hardcoded strings).
  - Icon and severity reflect urgency.

Future replacement: LLM-based summarisation with structured output.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Threshold constants
# ---------------------------------------------------------------------------

THRESHOLD_NEGATIVE_SENTIMENT_HIGH   = 30   # % negative → sentiment warning
THRESHOLD_GROWTH_NEGATIVE           = -3   # % growth → negative growth warning
THRESHOLD_GROWTH_VERY_HIGH          = 25   # % growth → emerging trend alert
THRESHOLD_ENGAGEMENT_LOW            = 3.0  # % engagement → low engagement warning
THRESHOLD_ENGAGEMENT_HIGH           = 15.0 # % engagement → strong engagement alert
THRESHOLD_INFLUENCE_CONCENTRATION   = 0.80 # top influencer score → influence alert
THRESHOLD_TREND_ACCELERATION        = 200  # growth_pct of top trend → trend alert
THRESHOLD_NEGATIVE_SENTIMENT_SHIFT  = 15   # pt increase in negative → shift warning


# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------

def _baseline_reach(reach: int, growth: float, topic: str) -> dict:
    direction = "increased" if growth >= 0 else "decreased"
    growth_str = f"+{growth:.1f}%" if growth >= 0 else f"{growth:.1f}%"
    topic_str = f' for "{topic}"' if topic else ""
    return {
        "type": "baseline", "severity": "low", "icon": "📊",
        "title": "Reach Signal",
        "text": (
            f"Total reach{topic_str} is {reach:,}. "
            f"Audience size {direction} by {abs(growth):.1f}% compared to the previous period."
        ),
        "insight": f"Total reach shifted {growth_str} over the observed timeframe.",
        "evidence": f"Calculated reach stands at {reach:,} with a delta of {growth_str} from prior records.",
        "reason": f"Content distribution cadence and organic reach on observed channels.",
        "impact": "Expands potential audience for new campaign messaging.",
        "recommendation": "Maintain consistent release timing to retain newly acquired reach.",
    }


def _baseline_engagement(engagement: float, status: str) -> dict:
    quality = "strong" if engagement >= 10 else "moderate" if engagement >= 5 else "low"
    return {
        "type": "baseline", "severity": "low", "icon": "💡",
        "title": "Engagement Quality",
        "text": (
            f"Engagement rate stands at {engagement:.1f}%, indicating {quality} audience interaction. "
            f"Status: {status}."
        ),
        "insight": f"Audience response represents {quality} interaction quality ({engagement:.1f}%).",
        "evidence": f"Measured engagement rate is {engagement:.1f}%, aligned with status '{status}'.",
        "reason": "Direct reaction and discussion activity on published posts.",
        "impact": "Fosters algorithmic amplification on recommendation feeds.",
        "recommendation": "Replicate high-performing content structures to sustain response rates.",
    }


def _baseline_sentiment(positive: int, negative: int) -> dict:
    mood = "positive" if positive >= 55 else "mixed" if negative < 20 else "tense"
    return {
        "type": "baseline", "severity": "low", "icon": "👥",
        "title": "Audience Sentiment",
        "text": (
            f"Overall sentiment is {mood}. {positive}% of mentions carry positive sentiment; "
            f"{negative}% are negative."
        ),
        "insight": f"Audience reception is {mood} across conversation threads.",
        "evidence": f"{positive}% positive sentiment vs {negative}% negative mentions.",
        "reason": "User tone in feedback, replies, and community discourse.",
        "impact": "Informs brand reputation and community trust levels.",
        "recommendation": "Reinforce topics driving positive feedback while addressing user concerns.",
    }


def _baseline_posting_time(best_time: str, activity_window: str) -> dict:
    return {
        "type": "baseline", "severity": "low", "icon": "⏰",
        "title": "Optimal Posting Window",
        "text": (
            f"Analysis suggests posting between {best_time} for peak reach. "
            f"Audience is most active: {activity_window}."
        ),
        "insight": f"Peak user activity converges between {best_time}.",
        "evidence": f"Activity clustering indicates heaviest engagement during {activity_window}.",
        "reason": "Audience availability patterns and timezone concentration.",
        "impact": "Maximizes initial interaction velocity in the first 2 hours of posting.",
        "recommendation": f"Schedule prime announcements inside the {best_time} window.",
    }


def _baseline_top_trend(trend_name: str, growth_pct: float, influencer: str) -> dict:
    return {
        "type": "baseline", "severity": "low", "icon": "🔍",
        "title": "Leading Trend",
        "text": (
            f'"{trend_name}" is the top trending topic with {growth_pct:.1f}% growth. '
            f"Key influencer driving this narrative: {influencer}."
        ),
        "insight": f'Topic "{trend_name}" represents the core conversational anchor.',
        "evidence": f"Growth acceleration of +{growth_pct:.1f}% with key driver {influencer}.",
        "reason": "High frequency hashtag co-occurrence and creator engagement.",
        "impact": "Directs audience focus and discovery queries.",
        "recommendation": f"Incorporate '{trend_name}' themes into forthcoming content planning.",
    }


# ---------------------------------------------------------------------------
# Conditional warnings / alerts
# ---------------------------------------------------------------------------

def _warn_negative_sentiment(negative: int) -> dict:
    return {
        "type": "warning", "severity": "medium", "icon": "⚠",
        "title": "High Negative Sentiment",
        "text": (
            f"Negative sentiment has reached {negative}%, which is above the alert threshold. "
            "Consider monitoring discussion quality and identifying friction points."
        ),
        "insight": f"Critical commentary has elevated to {negative}%.",
        "evidence": f"Negative tone exceeds threshold with {negative}% of classified mentions.",
        "reason": "Developing friction or dissatisfaction highlighted in user feedback.",
        "impact": "Poses risks to community satisfaction if left unaddressed.",
        "recommendation": "Review recent comment threads to isolate and resolve primary complaints.",
    }


def _warn_negative_growth(growth: float) -> dict:
    return {
        "type": "warning", "severity": "medium", "icon": "⚠",
        "title": "Declining Reach",
        "text": (
            f"Audience reach has declined by {abs(growth):.1f}% this period. "
            "Review content strategy and posting frequency."
        ),
        "insight": f"Audience visibility retracted by {abs(growth):.1f}%.",
        "evidence": f"Calculated growth delta of {growth:.1f}% over the measurement interval.",
        "reason": "Reduced posting frequency or algorithmic distribution shifts.",
        "impact": "Decreases top-of-funnel reach for campaign messaging.",
        "recommendation": "Refresh content themes and test short-form video hooks to regain traction.",
    }


def _alert_emerging_trend(trend_name: str, growth_pct: float) -> dict:
    return {
        "type": "alert", "severity": "high", "icon": "🔥",
        "title": "Emerging Trend Detected",
        "text": (
            f'"{trend_name}" is accelerating rapidly at +{growth_pct:.1f}% growth. '
            "Engage early to capture this trend before saturation."
        ),
        "insight": f'Topic "{trend_name}" is exhibiting breakout growth.',
        "evidence": f"Observed growth velocity of +{growth_pct:.1f}% in keyword volume.",
        "reason": "Viral dissemination across multiple peer creator nodes.",
        "impact": "Presents a high-visibility discovery opportunity.",
        "recommendation": f"Produce dedicated content responding to '{trend_name}' within 24 hours.",
    }


def _alert_influence_concentration(influencer: str, score: float) -> dict:
    return {
        "type": "alert", "severity": "medium", "icon": "🌐",
        "title": "Influence Concentration",
        "text": (
            f"A single node ({influencer}, score {score:.2f}) is driving a disproportionate share "
            "of discussion. This suggests high network dependency on a few key voices."
        ),
        "insight": f"Discussion reach is heavily centralized around {influencer}.",
        "evidence": f"Centrality influence score of {score:.2f} exceeds concentration limits.",
        "reason": "Dominant creator generating majority of conversational impressions.",
        "impact": "Vulnerability to narrative shifts if creator sentiment changes.",
        "recommendation": "Diversify creator outreach across secondary cluster influencers.",
    }


def _alert_low_engagement(engagement: float) -> dict:
    return {
        "type": "warning", "severity": "medium", "icon": "⚠",
        "title": "Low Engagement Rate",
        "text": (
            f"Engagement rate is {engagement:.1f}%, below the expected threshold. "
            "Consider interactive content formats (polls, Q&A, short video) to improve reach."
        ),
        "insight": f"Interaction rate ({engagement:.1f}%) trails expected engagement baselines.",
        "evidence": f"Calculated interaction percentage is {engagement:.1f}%.",
        "reason": "Passive viewing patterns without interactive prompts.",
        "impact": "Lowers platform recommendation ranking over time.",
        "recommendation": "Include explicit discussion prompts and questions in post captions.",
    }


def _alert_high_engagement(engagement: float) -> dict:
    return {
        "type": "info", "severity": "low", "icon": "✨",
        "title": "Strong Engagement Spike",
        "text": (
            f"Engagement rate reached {engagement:.1f}%, well above average. "
            "Content is resonating strongly — consider amplifying current formats."
        ),
        "insight": f"Exceptional audience interaction rate of {engagement:.1f}%.",
        "evidence": f"Engagement metric reached {engagement:.1f}%, well above benchmarks.",
        "reason": "High resonance of active subject matter with target demographics.",
        "impact": "Drives compounding organic propagation and subscriber conversion.",
        "recommendation": "Analyze the specific creative elements of this batch to form a repeatable template.",
    }


def _alert_sentiment_shift(prev_negative: int, curr_negative: int) -> dict:
    delta = curr_negative - prev_negative
    return {
        "type": "warning", "severity": "high", "icon": "⚠",
        "title": "Sentiment Shift Detected",
        "text": (
            f"Negative sentiment increased by {delta} percentage points this period. "
            "A rapid sentiment shift may indicate a developing controversy or public concern."
        ),
        "insight": f"Negative tone spiked by {delta} percentage points.",
        "evidence": f"Negative polarity shifted from {prev_negative}% to {curr_negative}%.",
        "reason": "Sudden conversational shift in community comments.",
        "impact": "Early warning indicator of developing reputational controversy.",
        "recommendation": "Initiate immediate message monitoring and clarify ambiguous messaging.",
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_insights(
    seed: int,
    tick: int,
    metrics: dict[str, Any],
    sentiment: dict[str, Any],
    top_trends: list[dict[str, Any]],
    influencers: list[dict[str, Any]],
    insights_dict: dict[str, Any],
    sentiment_series: list[int],
    topic: str = "",
) -> list[dict[str, Any]]:
    """
    Generate a list of structured insight cards.

    Parameters mirror the keys in AnalysisResponse so the backend can
    pass them directly from the assembled response object.
    """
    cards: list[dict[str, Any]] = []

    # ----- Extract values -----
    reach        = int(metrics.get("reach", metrics.get("followers", 0)))
    growth       = float(metrics.get("growth", 0))
    engagement   = float(metrics.get("engagement_rate", metrics.get("engagement", 0)))
    positive     = int(sentiment.get("positive", 0))
    negative     = int(sentiment.get("negative", 0))
    best_time    = str(insights_dict.get("best_posting_time", "7:00 PM – 9:00 PM"))
    activity_win = str(insights_dict.get("activity_window", "Wednesday – Friday"))
    score_status = str(insights_dict.get("score_status", "Moderate engagement"))

    top_trend_name    = top_trends[0]["name"]    if top_trends else topic or "Unknown"
    top_trend_growth  = top_trends[0]["growth_pct"] if top_trends else growth
    top_influencer    = influencers[0]["name"]   if influencers else "N/A"
    top_inf_score     = influencers[0]["score"]  if influencers else 0.0

    # ----- Baseline (always present) -----
    cards.append(_baseline_reach(reach, growth, topic))
    cards.append(_baseline_engagement(engagement, score_status))
    cards.append(_baseline_sentiment(positive, negative))
    cards.append(_baseline_posting_time(best_time, activity_win))
    if top_trends:
        cards.append(_baseline_top_trend(top_trend_name, top_trend_growth, top_influencer))

    # ----- Conditional -----
    if negative > THRESHOLD_NEGATIVE_SENTIMENT_HIGH:
        cards.append(_warn_negative_sentiment(negative))

    if growth < THRESHOLD_GROWTH_NEGATIVE:
        cards.append(_warn_negative_growth(growth))

    if top_trend_growth > THRESHOLD_TREND_ACCELERATION:
        cards.append(_alert_emerging_trend(top_trend_name, top_trend_growth))

    if top_inf_score > THRESHOLD_INFLUENCE_CONCENTRATION:
        cards.append(_alert_influence_concentration(top_influencer, top_inf_score))

    if engagement < THRESHOLD_ENGAGEMENT_LOW and reach > 0:
        cards.append(_alert_low_engagement(engagement))
    elif engagement > THRESHOLD_ENGAGEMENT_HIGH:
        cards.append(_alert_high_engagement(engagement))

    # Sentiment shift: compare last vs second-to-last sentiment_series
    if len(sentiment_series) >= 2:
        # sentiment_series is positive %; derive negative proxy
        prev_pos = sentiment_series[-2]
        curr_pos = sentiment_series[-1]
        # If positive dropped sharply, negative likely rose
        if (prev_pos - curr_pos) > THRESHOLD_NEGATIVE_SENTIMENT_SHIFT:
            cards.append(_alert_sentiment_shift(
                100 - prev_pos - 20,  # approximate prev negative
                100 - curr_pos - 15,  # approximate curr negative
            ))

    return cards
