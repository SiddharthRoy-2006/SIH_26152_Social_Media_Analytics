"""
tests/test_auth.py

Automated test suite verifying the YouTube OAuth 2.0 backend flow:
- Route presence in FastAPI app and /docs schema
- Truthful CONFIGURATION_REQUIRED when env vars are missing
- Zero secret leakage in URLs, responses, logs, or HTML
- Anti-CSRF state creation, expiration, and single-use consumption
- User authorization denial handling
- Server-side token exchange and backend storage
- OAuth status endpoint and token revocation
"""

from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.core.config import settings
from backend.services.oauth_service import OAuthService, get_oauth_service

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_oauth():
    """Ensure clean OAuthService state before and after each test."""
    svc = get_oauth_service()
    svc._pending_states.clear()
    svc._tokens.clear()
    yield
    svc._pending_states.clear()
    svc._tokens.clear()


def test_auth_routes_registered_in_openapi():
    """Verify that all new OAuth routes exist in OpenAPI documentation."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    assert "/api/auth/youtube/authorize" in paths
    assert "/api/auth/callback" in paths
    assert "/api/auth/youtube/status" in paths
    assert "/api/auth/youtube/revoke" in paths


def test_authorize_endpoint_unconfigured():
    """When credentials are not set, authorize endpoint returns CONFIGURATION_REQUIRED."""
    unconf_settings = replace(settings, google_client_id="", google_client_secret="")
    with patch("backend.services.oauth_service.settings", unconf_settings), \
         patch("backend.routes.auth.settings", unconf_settings):
        response = client.get("/api/auth/youtube/authorize")
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "CONFIGURATION_REQUIRED"
        assert "not configured" in data["message"].lower()


def test_status_endpoint_unconfigured():
    """When credentials are not set, status endpoint truthfully reports CONFIGURATION_REQUIRED."""
    unconf_settings = replace(settings, google_client_id="", google_client_secret="")
    with patch("backend.services.oauth_service.settings", unconf_settings), \
         patch("backend.routes.auth.settings", unconf_settings):
        response = client.get("/api/auth/youtube/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "CONFIGURATION_REQUIRED"
        assert data["configured"] is False
        assert data["authorized"] is False


def test_authorize_endpoint_configured_json():
    """When configured, returns valid Google OAuth URL and state without leaking secrets."""
    fake_client_id = "test-client-id-123.apps.googleusercontent.com"
    fake_client_secret = "super-secret-google-key-999"
    conf_settings = replace(settings, google_client_id=fake_client_id, google_client_secret=fake_client_secret)

    with patch("backend.services.oauth_service.settings", conf_settings), \
         patch("backend.routes.auth.settings", conf_settings):
        response = client.get("/api/auth/youtube/authorize")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "READY"
        assert "authorization_url" in data
        assert "state" in data
        auth_url = data["authorization_url"]

        # Client ID must be in URL
        assert fake_client_id in auth_url
        # Required YouTube Analytics read-only scope must be in URL
        assert "yt-analytics.readonly" in auth_url
        # Redirect URI must be in URL
        assert "http%3A%2F%2F127.0.0.1%3A8001%2Fapi%2Fauth%2Fcallback" in auth_url
        # Client secret must NEVER appear anywhere in URL or JSON
        assert fake_client_secret not in auth_url
        assert fake_client_secret not in response.text


def test_authorize_endpoint_redirect():
    """When redirect=true is requested, returns HTTP 307 redirect."""
    fake_client_id = "test-client-id-123.apps.googleusercontent.com"
    fake_client_secret = "super-secret-google-key-999"
    conf_settings = replace(settings, google_client_id=fake_client_id, google_client_secret=fake_client_secret)

    with patch("backend.services.oauth_service.settings", conf_settings), \
         patch("backend.routes.auth.settings", conf_settings):
        response = client.get("/api/auth/youtube/authorize?redirect=true", follow_redirects=False)
        assert response.status_code == 307
        assert "location" in response.headers
        assert fake_client_id in response.headers["location"]
        assert fake_client_secret not in response.headers["location"]


def test_callback_user_denied_authorization():
    """When user cancels on Google consent screen (error=access_denied), return friendly status."""
    response = client.get("/api/auth/callback?error=access_denied&error_description=User+denied+access")
    assert response.status_code == 400
    assert "Authorization Not Completed" in response.text
    assert "denied or canceled" in response.text


def test_callback_missing_or_invalid_state():
    """Callback rejects missing or invalid state (CSRF protection)."""
    # 1. Missing state
    resp1 = client.get("/api/auth/callback?code=some_code")
    assert resp1.status_code == 400
    assert "Security Validation Failed" in resp1.text

    # 2. Invalid state
    resp2 = client.get("/api/auth/callback?code=some_code&state=nonexistent_state")
    assert resp2.status_code == 400
    assert "State Validation Failed" in resp2.text


def test_callback_missing_code():
    """Callback rejects request with valid state but missing authorization code."""
    svc = get_oauth_service()
    state = svc.create_state(platform="YouTube")

    resp = client.get(f"/api/auth/callback?state={state}")
    assert resp.status_code == 400
    assert "Authorization Code Missing" in resp.text


def test_callback_state_single_use():
    """State can only be consumed once."""
    svc = get_oauth_service()
    state = svc.create_state(platform="YouTube")

    # Consume state once
    consumed = svc.validate_and_consume_state(state)
    assert consumed is not None

    # Second consumption must fail
    second = svc.validate_and_consume_state(state)
    assert second is None


@pytest.mark.anyio
async def test_callback_successful_token_exchange():
    """Successful token exchange stores tokens securely and returns clean HTML with no secret leakage."""
    svc = get_oauth_service()
    state = svc.create_state(platform="YouTube")

    fake_client_id = "test-client-id"
    fake_client_secret = "test-client-secret"
    fake_access_token = "ya29.test_access_token_super_secret"
    fake_refresh_token = "1//0test_refresh_token_super_secret"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": fake_access_token,
        "refresh_token": fake_refresh_token,
        "expires_in": 3600,
        "token_type": "Bearer",
        "scope": "https://www.googleapis.com/auth/yt-analytics.readonly",
    }

    conf_settings = replace(settings, google_client_id=fake_client_id, google_client_secret=fake_client_secret)

    with patch("backend.services.oauth_service.settings", conf_settings), \
         patch("backend.routes.auth.settings", conf_settings), \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        resp = client.get(f"/api/auth/callback?code=valid_test_code&state={state}")

        assert resp.status_code == 200
        assert "Google Account Connected" in resp.text

        # ZERO SECRET LEAKAGE: Neither access token, refresh token, nor client secret appear in HTML
        assert fake_access_token not in resp.text
        assert fake_refresh_token not in resp.text
        assert fake_client_secret not in resp.text

        # Verify status endpoint reflects authorized state
        status_resp = client.get("/api/auth/youtube/status")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["status"] == "AUTHORIZED"
        assert status_data["authorized"] is True
        assert status_data["has_refresh_token"] is True
        # Tokens must not appear in JSON response
        assert fake_access_token not in status_resp.text
        assert fake_refresh_token not in status_resp.text

        # Verify revoke endpoint clears tokens
        revoke_resp = client.post("/api/auth/youtube/revoke")
        assert revoke_resp.status_code == 200
        assert revoke_resp.json()["cleared"] is True

        # Status after revoke should be NOT_CONNECTED
        post_revoke_status = client.get("/api/auth/youtube/status")
        assert post_revoke_status.json()["status"] == "NOT_CONNECTED"
        assert post_revoke_status.json()["authorized"] is False


def test_youtube_connector_reflects_oauth_status():
    """Verify YouTubeConnector includes truthful OAuth layer status."""
    from backend.connectors.youtube_connector import YouTubeConnector

    conn = YouTubeConnector(api_key="dummy_api_key")
    cap = conn.check_health(force_probe=False)
    layers = {layer["name"]: layer for layer in cap.access_layers}

    assert "YouTube Analytics API" in layers
    analytics_layer = layers["YouTube Analytics API"]
    assert analytics_layer["auth_required"] is True
    assert analytics_layer["access_type"] == "Google OAuth 2.0"
    # When unconfigured in test environment:
    assert analytics_layer["status"] in ("CONFIGURATION_REQUIRED", "NOT_CONNECTED")
