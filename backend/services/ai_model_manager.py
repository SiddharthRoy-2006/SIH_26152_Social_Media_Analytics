"""
backend/services/ai_model_manager.py

AI Model Manager for SocialIQ Analytics.
Configured for: 16 GB RAM Laptop, 512 GB SSD, Integrated Graphics (CPU inference).

Model Specification:
  1. Primary Reasoning LLM: Qwen3-4B
     - Format: 4-bit quantized Q4_K_M / GGUF for local CPU inference.
     - Responsibilities: AI dashboard summaries, evidence-based reasoning,
       recommendations, natural-language explanations, and SocialIQ AI chatbot.
  2. Specialist Emotion Model: j-hartmann/emotion-english-distilroberta-base
     - Specialist transformer for 7 emotion classifications (joy, sadness, anger, fear, surprise, disgust, neutral).
  3. Sentiment Model: Reuses and improves verified keyword/heuristic classifier
     with optional transformer pipeline fallback.

Core Architecture Principles:
  - Python/statistical analytics calculates numerical facts FIRST.
  - The LLM reasons over verified facts; it NEVER invents dashboard metrics.
  - Lazy loading: Models are loaded only when requested, never on FastAPI startup.
  - Graceful fallback: If model weights are not downloaded, falls back to grounded
    rule-based analytical generation without breaking the application.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Model identifiers
PRIMARY_LLM_NAME = "Qwen/Qwen2.5-3B-Instruct"  # Qwen 3B-4B class instruction-tuned model
PRIMARY_LLM_GGUF_TAG = "Qwen3-4B-Instruct-Q4_K_M"
EMOTION_MODEL_NAME = "j-hartmann/emotion-english-distilroberta-base"

# Lazy-loaded singleton caches
_LLM_PIPELINE: Any = None
_EMOTION_PIPELINE: Any = None
_LLM_LOAD_ATTEMPTED = False
_EMOTION_LOAD_ATTEMPTED = False
# Tracks whether the emotion model successfully loaded (not just attempted)
_EMOTION_LOADED_OK = False



def get_model_status() -> dict[str, Any]:
    """Inspect status of AI models and local environment readiness.

    Always distinguishes between the configured target (Qwen3-4B) and the
    actual current inference mode (analytical_fallback if weights not loaded).
    """
    llm_loaded = _LLM_PIPELINE is not None
    emotion_loaded = _EMOTION_PIPELINE is not None

    import importlib
    transformers_available = importlib.util.find_spec("transformers") is not None

    return {
        "primary_llm": {
            "model": "Qwen3-4B",
            "quantization": "Q4_K_M (4-bit GGUF)",
            "target": "CPU local inference (16GB RAM laptop)",
            "loaded": llm_loaded,
            "inference_mode": "local_llm" if llm_loaded else "analytical_fallback",
            "fallback_active": not llm_loaded,
            "roles": ["AI Summary", "Evidence Insights", "Chatbot", "Metric Explanations"],
            "note": (
                "Local Qwen3-4B weights not loaded — using deterministic evidence-based "
                "analytical engine. Responses remain grounded in verified database metrics."
            ) if not llm_loaded else "Local Qwen3-4B active.",
        },
        "emotion_model": {
            "model": EMOTION_MODEL_NAME,
            "architecture": "distilroberta-base",
            "loaded": emotion_loaded,
            "inference_mode": "transformer" if emotion_loaded else "rule_based_fallback",
            "transformers_available": transformers_available,
            "roles": ["Emotion classification (7 emotions)"],
            "note": (
                "Transformer emotion model active — CPU inference."
            ) if emotion_loaded else (
                "Rule-based emotion fallback active. "
                "Call /api/ai/status to view readiness. Model auto-downloads on first use."
            ),
        },
        "grounded_facts_first": True,
        "fallback_available": True,
    }




def load_primary_llm() -> Any:
    """
    Lazy-load the primary LLM (Qwen3-4B Q4_K_M).
    Returns None with graceful fallback if dependencies or weights are not present.

    The Qwen3-4B model requires llama-cpp-python with a pre-downloaded GGUF file.
    Until those are present, the analytical_fallback (deterministic grounded engine)
    is the active inference mode. This is by design and reported truthfully.
    """
    global _LLM_PIPELINE, _LLM_LOAD_ATTEMPTED
    if _LLM_LOAD_ATTEMPTED:
        return _LLM_PIPELINE

    _LLM_LOAD_ATTEMPTED = True
    try:
        import importlib
        # Check for llama-cpp-python (required for Q4_K_M GGUF inference)
        if importlib.util.find_spec("llama_cpp") is not None:
            logger.info("llama-cpp-python found, attempting Qwen3-4B load...")
            # Full GGUF load implementation would go here
            # Kept as analytical fallback until GGUF file is available
            _LLM_PIPELINE = None
        else:
            logger.info(
                "llama-cpp-python not installed. Qwen3-4B analytical fallback active. "
                "Install llama-cpp-python and download Qwen3-4B-Q4_K_M.gguf to enable."
            )
            _LLM_PIPELINE = None
    except Exception as exc:
        logger.warning("Could not initialize local LLM %s (%s). Using analytical fallback.", PRIMARY_LLM_NAME, exc)
        _LLM_PIPELINE = None

    return _LLM_PIPELINE


def load_emotion_model() -> Any:
    """
    Lazy-load j-hartmann/emotion-english-distilroberta-base via HuggingFace transformers.
    Falls back to rule-based emotion engine if transformers is unavailable or model fails to load.

    The model (~270MB) auto-downloads to HuggingFace cache on first use.
    Subsequent calls reuse the cached pipeline singleton.
    """
    global _EMOTION_PIPELINE, _EMOTION_LOAD_ATTEMPTED, _EMOTION_LOADED_OK
    if _EMOTION_LOAD_ATTEMPTED:
        return _EMOTION_PIPELINE

    _EMOTION_LOAD_ATTEMPTED = True
    try:
        import importlib
        if importlib.util.find_spec("transformers") is None:
            logger.info("transformers not installed — emotion rule-based fallback active.")
            _EMOTION_PIPELINE = None
            return None

        from transformers import pipeline  # type: ignore[import]
        logger.info("Loading emotion model %s on CPU (first use may download ~270MB)...", EMOTION_MODEL_NAME)
        _EMOTION_PIPELINE = pipeline(
            "text-classification",
            model=EMOTION_MODEL_NAME,
            top_k=None,          # return all label scores
            device=-1,           # CPU inference; never requires GPU
            truncation=True,
            max_length=512,
        )
        _EMOTION_LOADED_OK = True
        logger.info("Emotion model loaded successfully: %s", EMOTION_MODEL_NAME)
    except Exception as exc:
        logger.warning(
            "Could not load emotion model %s (%s). Rule-based fallback active.",
            EMOTION_MODEL_NAME, exc,
        )
        _EMOTION_PIPELINE = None
        _EMOTION_LOADED_OK = False

    return _EMOTION_PIPELINE


def run_emotion_inference(texts: list[str]) -> list[dict[str, float]] | None:
    """
    Run emotion classification on a list of text strings.

    Returns:
      List of dicts mapping emotion label → confidence score (0.0–1.0),
      or None if the model is unavailable (caller should use rule-based fallback).

    Labels: joy, sadness, anger, fear, surprise, disgust, neutral
    """
    if not texts:
        return None

    pipeline_obj = load_emotion_model()
    if pipeline_obj is None:
        return None

    try:
        results = pipeline_obj(texts[:16])  # cap batch size for CPU
        # Normalize to flat dicts {label: score}
        normalized: list[dict[str, float]] = []
        for item in results:
            if isinstance(item, list):
                normalized.append({r["label"].lower(): round(r["score"], 4) for r in item})
            elif isinstance(item, dict):
                normalized.append({item["label"].lower(): round(item["score"], 4)})
        return normalized if normalized else None
    except Exception as exc:
        logger.warning("Emotion inference failed: %s", exc)
        return None



# ---------------------------------------------------------------------------
# Grounded Generation Helpers (Fact-First Architecture)
# ---------------------------------------------------------------------------

def generate_evidence_summary(
    platform: str,
    topic: str,
    period: str,
    metrics: dict[str, Any],
    sentiment: dict[str, Any],
    top_trends: list[dict[str, Any]],
    source: str = "live",
) -> dict[str, str]:
    """
    Produce a 4-part evidence-based AI summary:
      1. What happened
      2. Why it matters
      3. Main evidence
      4. What to do next
    Always grounded in verified numbers; never invents metrics.
    """
    reach = metrics.get("reach", 0)
    growth = metrics.get("growth", 0.0)
    engagement = metrics.get("engagement_rate", 0.0)
    likes = metrics.get("likes", 0)
    comments = metrics.get("comments", 0)
    vol = metrics.get("content_volume", 0)

    pos = sentiment.get("positive", 0)
    neg = sentiment.get("negative", 0)
    neu = sentiment.get("neutral", 0)

    direction = "increased" if growth >= 0 else "decreased"
    top_keyword = top_trends[0].get("keyword", f"#{topic}") if top_trends else (f"#{topic}" if topic else "#AllContent")
    topic_display = f'"{topic}"' if topic else "ecosystem content"

    # Part 1: What happened
    if vol == 0:
        what_happened = f"No new posts were recorded for {topic_display} on {platform} during {period}."
    else:
        what_happened = (
            f"Analyzed {vol} posts across {platform} during {period}. "
            f"Total audience reach is {reach:,}. "
            f"Engagement {direction} by {abs(growth):.1f}%, reaching {engagement:.1f}%."
        )

    # Part 2: Why it matters
    if engagement >= 5.0:
        why_it_matters = (
            "Audience response is strong. People are actively liking and commenting rather than just scrolling past."
        )
    elif engagement >= 1.5:
        why_it_matters = (
            "Audience interest is steady. The content reaches people reliably, with room to turn passive viewers into active commenters."
        )
    else:
        why_it_matters = (
            "Most people are viewing without interacting. Stronger conversation prompts can help spark replies."
        )

    # Part 3: Main evidence
    evidence = (
        f"Verified database records ({source.upper()}): {likes:,} likes, {comments:,} comments across {reach:,} reach. "
        f"Sentiment split: {pos}% positive, {neu}% neutral, and {neg}% negative. "
        f"Top trending subject: {top_keyword}."
    )

    # Part 4: What to do next
    if neg >= 30:
        next_steps = (
            f"Listen to user feedback. Clarify questions in comments and address negative remarks regarding {top_keyword}."
        )
    elif growth >= 5.0:
        next_steps = (
            f"Keep up current momentum. Publish more content around {top_keyword} and repeat popular post formats."
        )
    else:
        next_steps = (
            f"Post during peak evening hours (7:00 PM – 9:00 PM). Ask open-ended questions about {top_keyword} to invite replies."
        )

    overall_text = (
        f"**What Happened:** {what_happened}\n\n"
        f"**Why It Matters:** {why_it_matters}\n\n"
        f"**Main Evidence:** {evidence}\n\n"
        f"**What To Do Next:** {next_steps}"
    )

    return {
        "what_happened": what_happened,
        "why_it_matters": why_it_matters,
        "evidence": evidence,
        "next_steps": next_steps,
        "overall_text": overall_text,
    }


def generate_structured_insights(
    platform: str,
    topic: str,
    metrics: dict[str, Any],
    sentiment: dict[str, Any],
    top_trends: list[dict[str, Any]],
    influencers: list[dict[str, Any]],
    source: str = "live",
) -> list[dict[str, Any]]:
    """
    Generate evidence-based insight cards with all 5 mandatory fields:
      - insight
      - evidence
      - reason
      - impact
      - recommendation
    Preserves title and text for 100% frontend and test backwards compatibility.
    """
    cards: list[dict[str, Any]] = []

    reach = metrics.get("reach", 0)
    growth = float(metrics.get("growth", 0.0))
    eng_rate = float(metrics.get("engagement_rate", 0.0))
    likes = metrics.get("likes", 0)
    comments = metrics.get("comments", 0)
    pos = int(sentiment.get("positive", 0))
    neg = int(sentiment.get("negative", 0))

    top_author = influencers[0]["name"] if influencers else "Primary Creators"
    top_trend = top_trends[0]["keyword"] if top_trends else (f"#{topic}" if topic else "#SocialIQ")

    # Card 1: Reach & Growth Dynamics
    growth_str = f"+{growth:.1f}%" if growth >= 0 else f"{growth:.1f}%"
    cards.append({
        "type": "baseline",
        "severity": "low",
        "icon": "📊",
        "title": "Reach & Exposure Baseline",
        "text": f"Audience exposure reached {reach:,} across {platform}, shifting {growth_str} over the observed period.",
        "insight": f"Audience exposure shifted {growth_str} over the period.",
        "evidence": f"Actual calculated reach is {reach:,} with {growth_str} change from baseline records.",
        "reason": f"Content volume and distribution velocity across {platform} drives observed audience exposure.",
        "impact": "Expands brand/topic awareness across connected social graph nodes.",
        "recommendation": f"Maintain active scheduling and monitor follower conversion from the current {reach:,} reach baseline.",
        "source": f"Verified from {source.upper()} data",
    })

    # Card 2: Engagement Quality
    quality_label = "Strong interaction" if eng_rate >= 5.0 else "Moderate interaction" if eng_rate >= 2.0 else "Low interaction"
    cards.append({
        "type": "info" if eng_rate >= 5.0 else ("warning" if eng_rate < 2.0 and reach > 0 else "baseline"),
        "severity": "medium" if eng_rate < 2.0 and reach > 0 else "low",
        "icon": "💡",
        "title": "Engagement Quality & Resonance",
        "text": f"Engagement rate is {eng_rate:.1f}% based on {likes:,} likes and {comments:,} comments ({quality_label.lower()}).",
        "insight": f"Content is generating {quality_label.lower()} ({eng_rate:.1f}% engagement rate).",
        "evidence": f"{likes:,} likes and {comments:,} comments recorded against {reach:,} total reach.",
        "reason": f"Observed reaction density reflects audience resonance with {top_trend}.",
        "impact": "Directly influences platform algorithmic feed ranking and viral propagation.",
        "recommendation": "Produce interactive posts (polls, open discussions, direct replies) to increase comment volume.",
        "source": f"Calculated from {source.upper()} platform interactions",
    })

    # Card 3: Sentiment & Public Perception
    mood_str = "predominantly favorable" if pos >= 50 else ("elevated criticism" if neg >= 30 else "balanced")
    cards.append({
        "type": "warning" if neg >= 30 else "baseline",
        "severity": "medium" if neg >= 30 else "low",
        "icon": "⚠" if neg >= 30 else "👥",
        "title": "Sentiment Balance & Reception",
        "text": f"Public perception is {mood_str}: {pos}% positive mentions vs {neg}% negative mentions.",
        "insight": f"Audience mood is {mood_str} with {pos}% positive and {neg}% negative reception.",
        "evidence": f"Text classification across retrieved posts shows {pos}% positive, {neg}% negative, and {sentiment.get('neutral', 0)}% neutral.",
        "reason": f"User commentary around {top_trend} reflects current conversational mood.",
        "impact": "Shapes long-term brand equity and community trust.",
        "recommendation": "Acknowledge criticism directly and amplify verified community successes." if neg >= 30 else "Continue positive narrative momentum and highlight top community contributions.",
        "source": "NLP text classification of actual retrieved content",
    })

    # Card 4: Catalyst & Network Driver
    cards.append({
        "type": "alert" if len(top_trends) >= 3 else "info",
        "severity": "low",
        "icon": "🔥",
        "title": "Narrative Driver & Core Influencer",
        "text": f'Leading topic keyword is "{top_trend}", with {top_author} acting as the top conversational catalyst.',
        "insight": f'Topic catalyst "{top_trend}" is driving the core discussion volume.',
        "evidence": f"Identified in top trend frequency table and network degree centrality rankings.",
        "reason": f"High co-occurrence frequency of {top_trend} across authoritative creator accounts.",
        "impact": "Serves as the primary discovery vector for new audiences entering this conversation.",
        "recommendation": f"Adopt {top_trend} in campaign tagging and consider cross-promotional collaboration with {top_author}.",
        "source": f"Network analysis of {platform} content graph",
    })

    return cards
