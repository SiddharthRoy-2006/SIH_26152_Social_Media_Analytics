"""
tests/test_api.py

API tests for SocialIQ Analytics.

Tests cover:
  - Original 3 tests (preserved, backward-compat check)
  - New endpoints: /health, /general
  - Extended fields in demo mode
  - All Platforms support
  - Demo data evolution (different ticks → different values)
"""

import os

import pytest
from fastapi.testclient import TestClient

# Force demo mode for extended tests
os.environ.setdefault("SOCIALIQ_DATA_MODE", "empty")

from backend.app import app  # noqa: E402

client = TestClient(app)


# ---------------------------------------------------------------------------
# Original tests (must remain passing)
# ---------------------------------------------------------------------------

def test_health_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "SocialIQ Analytics API is running"


@pytest.mark.skipif(
    os.environ.get("SOCIALIQ_DATA_MODE") == "demo",
    reason="Empty-contract test only valid in empty mode",
)
def test_analysis_returns_empty_contract_by_default():
    response = client.get("/analysis", params={"topic": "Education Policy"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["topic"] == "Education Policy"
    assert payload["data_available"] is False
    assert payload["metrics"]["followers"] == 0
    assert payload["trending"]["topic"] == "No information"


def test_analysis_rejects_unknown_platform():
    response = client.get("/analysis", params={"platform": "Unknown"})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# New: /health endpoint
# ---------------------------------------------------------------------------

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "data_mode" in body
    assert "version" in body


# ---------------------------------------------------------------------------
# New: /general endpoint
# ---------------------------------------------------------------------------

def test_general_endpoint_empty_mode():
    response = client.get("/general")
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "general"
    assert payload["topic"] == ""
    assert "metrics" in payload
    assert "sentiment" in payload
    assert "top_trends" in payload


def test_general_accepts_all_platforms():
    response = client.get("/general", params={"platform": "All Platforms"})
    assert response.status_code == 200


def test_general_rejects_unknown_platform():
    response = client.get("/general", params={"platform": "TikTok"})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# New: All Platforms on /analysis
# ---------------------------------------------------------------------------

def test_analysis_accepts_all_platforms():
    response = client.get("/analysis", params={"platform": "All Platforms"})
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Demo mode tests (run separately with SOCIALIQ_DATA_MODE=demo)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    os.environ.get("SOCIALIQ_DATA_MODE") != "demo",
    reason="Demo mode not active",
)
def test_demo_mode_returns_data():
    response = client.get("/analysis", params={"topic": "AI in Education", "platform": "Instagram"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["data_available"] is True
    assert payload["source"] == "demo"
    assert payload["metrics"]["reach"] > 0
    assert len(payload["top_trends"]) == 10
    assert len(payload["influencers"]) > 0
    assert len(payload["ai_insights"]) > 0


@pytest.mark.skipif(
    os.environ.get("SOCIALIQ_DATA_MODE") != "demo",
    reason="Demo mode not active",
)
def test_demo_mode_general():
    response = client.get("/general", params={"platform": "All Platforms"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["data_available"] is True
    assert payload["mode"] == "general"
    assert len(payload["top_trends"]) == 10
    assert len(payload["network_graph"].get("nodes", [])) > 0


@pytest.mark.skipif(
    os.environ.get("SOCIALIQ_DATA_MODE") != "demo",
    reason="Demo mode not active",
)
def test_demo_data_evolves_with_tick():
    """Same topic + different tick → different reach values (drift)."""
    r1 = client.get("/analysis", params={"topic": "Education", "platform": "Instagram", "refresh_tick": 100})
    r2 = client.get("/analysis", params={"topic": "Education", "platform": "Instagram", "refresh_tick": 200})
    assert r1.status_code == 200
    assert r2.status_code == 200
    # Values should differ due to tick-based drift
    reach1 = r1.json()["metrics"]["reach"]
    reach2 = r2.json()["metrics"]["reach"]
    assert reach1 != reach2, "Demo data should drift between ticks"


@pytest.mark.skipif(
    os.environ.get("SOCIALIQ_DATA_MODE") != "demo",
    reason="Demo mode not active",
)
def test_demo_influencers_vary_by_topic():
    """Different topics should produce different leading influencers."""
    r1 = client.get("/analysis", params={"topic": "Education Policy", "platform": "Instagram"})
    r2 = client.get("/analysis", params={"topic": "Climate Change", "platform": "Instagram"})
    inf1 = r1.json()["influencers"][0]["name"] if r1.json()["influencers"] else ""
    inf2 = r2.json()["influencers"][0]["name"] if r2.json()["influencers"] else ""
    # Influencers won't always differ, but top trends should differ
    t1 = r1.json()["top_trends"][0]["name"]
    t2 = r2.json()["top_trends"][0]["name"]
    assert t1 != t2 or inf1 != inf2, "Different topics should produce different top data"


# ---------------------------------------------------------------------------
# CORS and Startup Reliability Tests
# ---------------------------------------------------------------------------

def test_cors_headers_on_get():
    """Verify CORS headers are properly returned for frontend origins."""
    response = client.get(
        "/health",
        headers={"Origin": "http://127.0.0.1:5500"},
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers
    assert response.headers["access-control-allow-origin"] in ["http://127.0.0.1:5500", "*"]


def test_cors_preflight_options():
    """Verify CORS OPTIONS preflight succeeds cleanly for frontend requests."""
    response = client.options(
        "/general",
        headers={
            "Origin": "http://localhost:5500",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers


# ---------------------------------------------------------------------------
# Telegram & Reddit Route Tests
# ---------------------------------------------------------------------------

def test_analysis_accepts_telegram_and_reddit():
    r_tg = client.get("/analysis", params={"topic": "Tech Policy", "platform": "Telegram"})
    assert r_tg.status_code == 200
    assert r_tg.json()["platform"] == "Telegram"

    r_rd = client.get("/analysis", params={"topic": "Tech Policy", "platform": "Reddit"})
    assert r_rd.status_code == 200
    assert r_rd.json()["platform"] == "Reddit"


def test_general_accepts_telegram_and_reddit():
    r_tg = client.get("/general", params={"platform": "Telegram"})
    assert r_tg.status_code == 200
    assert r_tg.json()["platform"] == "Telegram"

    r_rd = client.get("/general", params={"platform": "Reddit"})
    assert r_rd.status_code == 200
    assert r_rd.json()["platform"] == "Reddit"


# ---------------------------------------------------------------------------
# Explicit Demo Fallback Parameter Tests
# ---------------------------------------------------------------------------

def test_analysis_explicit_demo_parameter():
    """Verify ?demo=true returns demo data even when live mode is configured."""
    response = client.get("/analysis", params={"topic": "AI in Education", "platform": "YouTube", "demo": True})
    assert response.status_code == 200
    payload = response.json()
    assert payload["data_available"] is True
    assert payload["source"] == "demo"
    assert payload["metrics"]["reach"] > 0
    assert len(payload["top_trends"]) > 0


def test_general_explicit_demo_parameter():
    """Verify ?demo=true returns demo general data."""
    response = client.get("/general", params={"platform": "All Platforms", "demo": True})
    assert response.status_code == 200
    payload = response.json()
    assert payload["data_available"] is True
    assert payload["source"] == "demo"
    assert payload["mode"] == "general"
    assert len(payload["top_trends"]) == 10


