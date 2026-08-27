"""
tests/test_credentials.py

Unit tests for backend credential management endpoints:
- GET  /api/credentials/status
- POST /api/credentials/test
- POST /api/credentials/save
- POST /api/credentials/clear
- Security checks: zero secret leakage in responses
"""

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.connectors.registry import get_registry

client = TestClient(app)


def test_get_credentials_status():
    """Verify GET /api/credentials/status returns status for all 6 platforms."""
    response = client.get("/api/credentials/status")
    assert response.status_code == 200
    payload = response.json()
    assert "platforms" in payload

    platforms = payload["platforms"]
    expected_platforms = ["YouTube", "Telegram", "Reddit", "Twitter / X", "Instagram", "Facebook"]
    for p in expected_platforms:
        assert p in platforms
        data = platforms[p]
        assert "status" in data
        assert "source" in data
        assert "configured" in data
        assert "live" in data
        assert "message" in data
        assert "credential_fields" in data
        assert isinstance(data["credential_fields"], list)
        assert len(data["credential_fields"]) > 0


def test_credential_response_security():
    """Verify that credentials status/test endpoints never return secret keys in values."""
    secret_key = "test_secret_key_12345678"
    response = client.post(
        "/api/credentials/test",
        json={"platform": "YouTube", "credentials": {"api_key": secret_key}},
    )
    assert response.status_code == 200
    raw_text = response.text
    # Secret must never appear in response JSON
    assert secret_key not in raw_text


def test_test_youtube_invalid_key():
    """Testing an invalid YouTube key should return error without crashing."""
    response = client.post(
        "/api/credentials/test",
        json={"platform": "YouTube", "credentials": {"api_key": "invalid_fake_key_9999"}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["platform"] == "YouTube"
    assert data["status"] in ("error", "rate_limited", "not_configured")


def test_test_telegram_incomplete_credentials():
    """Testing Telegram with only api_id should report not_configured / incomplete."""
    response = client.post(
        "/api/credentials/test",
        json={"platform": "Telegram", "credentials": {"api_id": "123456"}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["platform"] == "Telegram"
    assert data["status"] == "not_configured"
    assert "both" in data["message"].lower() or "incomplete" in data["message"].lower()


def test_save_and_clear_credentials():
    """Verify saving credentials updates the connector and clearing resets it."""
    # Save dummy credentials
    save_resp = client.post(
        "/api/credentials/save",
        json={"platform": "Reddit", "credentials": {"client_id": "dummy_id", "client_secret": "dummy_secret"}},
    )
    assert save_resp.status_code == 200
    save_data = save_resp.json()
    assert save_data["platform"] == "Reddit"
    assert save_data["configured"] is True

    # Clear credentials
    clear_resp = client.post(
        "/api/credentials/clear",
        json={"platform": "Reddit"},
    )
    assert clear_resp.status_code == 200
    clear_data = clear_resp.json()
    assert clear_data["platform"] == "Reddit"
    assert clear_data["status"] == "not_configured"
    assert clear_data["configured"] is False


def test_meta_credentials_testing():
    """Verify Instagram and Facebook credential probes report truthful errors on invalid tokens."""
    ig_resp = client.post(
        "/api/credentials/test",
        json={"platform": "Instagram", "credentials": {"access_token": "fake_token", "account_id": "fake_id"}},
    )
    assert ig_resp.status_code == 200
    assert ig_resp.json()["status"] == "error"

    fb_resp = client.post(
        "/api/credentials/test",
        json={"platform": "Facebook", "credentials": {"access_token": "fake_token", "page_id": "fake_page"}},
    )
    assert fb_resp.status_code == 200
    assert fb_resp.json()["status"] == "error"
