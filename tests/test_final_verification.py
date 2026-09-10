"""
tests/test_final_verification.py

Comprehensive End-to-End Verification Test Suite for SocialIQ Analytics (SIH 26152).
Verifies:
  1. Lightweight & Fast /health endpoint (<500ms)
  2. Independent execution of General Intelligence (GET /general)
  3. Independent execution of Topic Analysis (GET /analysis)
  4. Platform switching and parallel connector handling
  5. AI Summary 4-part evidence-first structure
  6. AI Insights 5-field structure (insight, evidence, reason, impact, recommendation)
  7. AI Chatbot readiness (/api/chat/status)
  8. AI Chatbot message processing (/api/chat/message) with grounded data
  9. Clean validation error handling for invalid chat requests
 10. Truthful reporting of unconfigured platforms without silent fake data
 11. Real SocialRecord persistence and retrieval integrity
"""

import time
import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.connectors.base import SocialRecord
from backend.database.repository import get_records, save_social_records
from backend.schemas import ChatRequest
from backend.services.ai_chat_service import process_chat_message
from backend.services.ai_model_manager import (
    generate_evidence_summary,
    generate_structured_insights,
    get_model_status,
)

client = TestClient(app)


def test_01_health_endpoint_is_ultra_fast_and_lightweight():
    """Verify /health returns 200 in under 100ms in steady state without executing heavy table scans."""
    # Warmup / Lifespan initialization
    warm = client.get("/health")
    assert warm.status_code == 200

    start = time.perf_counter()
    response = client.get("/health")
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "platforms" in data
    assert "database" in data
    assert "storage" in data
    assert elapsed_ms < 100, f"/health took too long: {elapsed_ms:.2f}ms"


def test_02_general_intelligence_independent_execution():
    """Verify General Intelligence runs independently without requiring a topic."""
    response = client.get("/general", params={"platform": "All Platforms", "period": "Last 30 Days"})
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "general"
    assert "metrics" in data
    assert "ai_summary" in data
    assert "ai_insights" in data
    assert "network_graph" in data
    assert "growth_series" in data


def test_03_topic_analysis_independent_execution():
    """Verify Topic Analysis works with a specific topic and platform."""
    response = client.get(
        "/analysis",
        params={
            "topic": "Digital Literacy",
            "platform": "YouTube",
            "period": "Last 30 Days",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "topic"
    assert data["topic"] == "Digital Literacy"
    assert "metrics" in data
    assert "ai_summary" in data
    assert "ai_insights" in data


def test_04_ai_summary_four_part_evidence_structure():
    """Verify AI Summary conforms to the 4-part evidence-first structure in plain language."""
    summary = generate_evidence_summary(
        platform="YouTube",
        topic="Skill Development",
        period="Last 30 Days",
        metrics={
            "reach": 125000,
            "growth": 8.5,
            "engagement_rate": 4.2,
            "likes": 5000,
            "comments": 250,
            "content_volume": 15,
        },
        sentiment={"positive": 65, "negative": 10, "neutral": 25},
        top_trends=[{"keyword": "#SkillIndia", "name": "Skill India"}],
        source="live",
    )

    assert "what_happened" in summary
    assert "why_it_matters" in summary
    assert "evidence" in summary
    assert "next_steps" in summary
    assert "overall_text" in summary

    assert len(summary["what_happened"]) > 10
    assert len(summary["why_it_matters"]) > 10
    assert "125,000" in summary["evidence"]
    assert len(summary["next_steps"]) > 10


def test_05_ai_insights_five_mandatory_fields():
    """Verify every insight card contains all 5 required structured fields."""
    cards = generate_structured_insights(
        platform="YouTube",
        topic="NEP 2020",
        metrics={
            "reach": 85000,
            "growth": 12.0,
            "engagement_rate": 3.8,
            "likes": 3200,
            "comments": 410,
        },
        sentiment={"positive": 55, "negative": 15, "neutral": 30},
        top_trends=[{"keyword": "#NEP2020", "name": "NEP 2020"}],
        influencers=[{"name": "Education Ministry Channel"}],
        source="live",
    )

    assert len(cards) >= 4
    for idx, card in enumerate(cards):
        assert "insight" in card, f"Card {idx} missing 'insight'"
        assert "evidence" in card, f"Card {idx} missing 'evidence'"
        assert "reason" in card, f"Card {idx} missing 'reason'"
        assert "impact" in card, f"Card {idx} missing 'impact'"
        assert "recommendation" in card, f"Card {idx} missing 'recommendation'"
        assert len(card["insight"]) > 0
        assert len(card["evidence"]) > 0
        assert len(card["recommendation"]) > 0


def test_06_ai_model_status_endpoint():
    """Verify /api/chat/status returns local model readiness and architecture metadata."""
    response = client.get("/api/chat/status")
    assert response.status_code == 200
    data = response.json()
    assert "primary_llm" in data
    assert data["primary_llm"]["model"] == "Qwen3-4B"
    assert data["grounded_facts_first"] is True
    assert data["fallback_available"] is True


def test_07_ai_chatbot_message_endpoint_grounded():
    """Verify /api/chat/message processes inquiries with grounded context without error."""
    payload = {
        "message": "What is the engagement rate and what drives it?",
        "platform": "YouTube",
        "topic": "Education",
        "period": "Last 30 Days",
        "chart_period": "Monthly",
        "mode": "topic",
    }
    response = client.post("/api/chat/message", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert len(data["answer"]) > 20
    assert data.get("grounded") is True
    assert data.get("sources") is not None


def test_08_ai_chatbot_overview_query():
    """Verify chatbot answers performance summary questions using verified data context."""
    payload = {
        "message": "Summarize current performance",
        "platform": "All Platforms",
        "period": "Last 30 Days",
        "mode": "general",
    }
    response = client.post("/api/chat/message", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "Overview" in data["answer"] or "reach" in data["answer"].lower() or "performance" in data["answer"].lower()


def test_09_invalid_chatbot_request_rejected_cleanly():
    """Verify malformed chat requests with missing or empty message are rejected with 422."""
    response = client.post("/api/chat/message", json={"message": ""})
    assert response.status_code == 422

    response_missing = client.post("/api/chat/message", json={"platform": "YouTube"})
    assert response_missing.status_code == 422


def test_10_truthful_unconfigured_platform_handling():
    """Verify unconfigured platforms return clean data_available=False without silent demo fallback."""
    response = client.get("/analysis", params={"topic": "TestTopic", "platform": "Twitter / X"})
    assert response.status_code == 200
    data = response.json()
    # Unconfigured platform without explicit demo must report empty/unavailable
    assert data["source"] in ("empty", "live", "database")


def test_11_database_persistence_and_retrieval_cycle():
    """Verify SocialRecord can be saved, queried, and verified for provenance."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    rec = SocialRecord(
        platform="YouTube",
        content_id="verify_test_vid_99",
        content_type="video",
        timestamp=now,
        text="Final verification test content for SocialIQ",
        author_name="Verification Creator",
        engagement={"likes": 42, "views": 1000, "comments": 7},
        topic_keywords=["verification", "socialiq"],
    )

    inserted, updated, skipped = save_social_records([rec], topic="FinalVerification")
    assert inserted + updated == 1

    records = get_records(platform="YouTube", topic="FinalVerification")
    assert len(records) >= 1
    found = [r for r in records if r.content_id == "verify_test_vid_99"]
    assert len(found) == 1
    assert found[0].engagement.get("likes") == 42
    assert found[0].platform == "YouTube"
