"""
backend/services/oauth_service.py

Production-correct server-side OAuth 2.0 service for YouTube Analytics / Google OAuth.

Security Architecture:
- Generates cryptographically secure state parameters with expiration (anti-CSRF).
- Exclusively uses server-side token exchange against Google's token endpoint.
- Secure backend token storage (in-memory with zero leakage in logs, responses, or client).
- Enforces truthful status: never claims LIVE without real successful authorized probe.
- Never leaks, prints, or exposes client_secret, access_token, or refresh_token.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx

from backend.core.config import settings

logger = logging.getLogger(__name__)

# Standard Google OAuth 2.0 Endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"

# Required read-only YouTube Analytics scope
DEFAULT_YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


@dataclass
class PendingOAuthState:
    platform: str
    created_at: datetime
    expires_at: datetime
    scopes: list[str]


@dataclass
class OAuthTokens:
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    token_type: str = "Bearer"
    scopes: list[str] | None = None
    created_at: datetime | None = None


class OAuthService:
    """
    Manages server-side Google OAuth 2.0 lifecycle for YouTube:
    - State creation and single-use verification
    - Authorization URL construction
    - Server-to-server token exchange
    - Secure in-memory token retention (never exposed to client)
    - Safe status reporting
    """

    def __init__(self) -> None:
        # In-memory storage for active pending states: state -> PendingOAuthState
        self._pending_states: dict[str, PendingOAuthState] = {}
        # Backend token storage by platform: platform -> OAuthTokens
        self._tokens: dict[str, OAuthTokens] = {}
        # State validity TTL (10 minutes)
        self._state_ttl = timedelta(minutes=10)

    # ------------------------------------------------------------------
    # Configuration Checks
    # ------------------------------------------------------------------

    def is_configured(self) -> bool:
        """Check whether Google OAuth client credentials are configured."""
        return bool(settings.google_client_id.strip() and settings.google_client_secret.strip())

    # ------------------------------------------------------------------
    # State Management (Anti-CSRF)
    # ------------------------------------------------------------------

    def create_state(self, platform: str = "YouTube", scopes: list[str] | None = None) -> str:
        """Generate a cryptographically secure, time-limited state string."""
        self._cleanup_expired_states()
        state = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        self._pending_states[state] = PendingOAuthState(
            platform=platform,
            created_at=now,
            expires_at=now + self._state_ttl,
            scopes=scopes or DEFAULT_YOUTUBE_SCOPES,
        )
        return state

    def validate_and_consume_state(self, state: str) -> PendingOAuthState | None:
        """
        Validate and consume a state parameter.
        States are single-use and expire after TTL.
        """
        self._cleanup_expired_states()
        pending = self._pending_states.pop(state, None)
        if not pending:
            return None
        now = datetime.now(timezone.utc)
        if now > pending.expires_at:
            return None
        return pending

    def _cleanup_expired_states(self) -> None:
        """Remove expired pending states from memory."""
        now = datetime.now(timezone.utc)
        expired = [s for s, data in self._pending_states.items() if now > data.expires_at]
        for s in expired:
            self._pending_states.pop(s, None)

    # ------------------------------------------------------------------
    # Authorization URL
    # ------------------------------------------------------------------

    def build_authorization_url(
        self,
        platform: str = "YouTube",
        scopes: list[str] | None = None,
        redirect_uri: str | None = None,
    ) -> tuple[str, str]:
        """
        Build Google OAuth 2.0 authorization URL.
        Returns (authorization_url, state).
        Raises ValueError if Google OAuth is not configured.
        """
        if not self.is_configured():
            raise ValueError(
                "CONFIGURATION REQUIRED: Google OAuth Client ID and Secret are not configured in backend environment."
            )

        target_scopes = scopes or DEFAULT_YOUTUBE_SCOPES
        state = self.create_state(platform=platform, scopes=target_scopes)
        effective_redirect = (redirect_uri or settings.google_redirect_uri).strip()

        params = {
            "client_id": settings.google_client_id.strip(),
            "redirect_uri": effective_redirect,
            "response_type": "code",
            "scope": " ".join(target_scopes),
            "access_type": "offline",  # Requests a refresh token
            "prompt": "consent",       # Ensures refresh token returned on re-auth
            "state": state,
            "include_granted_scopes": "true",
        }

        url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
        return url, state

    # ------------------------------------------------------------------
    # Token Exchange (Server-Side)
    # ------------------------------------------------------------------

    async def exchange_code_for_tokens(
        self,
        code: str,
        redirect_uri: str | None = None,
        platform: str = "YouTube",
    ) -> dict[str, Any]:
        """
        Exchange an authorization code with Google for tokens.
        Tokens are retained strictly on the backend.
        Never returns secret tokens to the caller.
        """
        if not self.is_configured():
            raise ValueError(
                "CONFIGURATION REQUIRED: Google OAuth Client ID and Secret are not configured in backend environment."
            )

        effective_redirect = (redirect_uri or settings.google_redirect_uri).strip()

        payload = {
            "client_id": settings.google_client_id.strip(),
            "client_secret": settings.google_client_secret.strip(),
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": effective_redirect,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(GOOGLE_TOKEN_URL, data=payload)
        except Exception as exc:
            logger.error("OAuth token exchange network error: %s", exc)
            raise RuntimeError(f"Failed to communicate with Google token endpoint: {exc}") from exc

        if resp.status_code != 200:
            error_data = {}
            try:
                error_data = resp.json()
            except Exception:
                pass
            err_msg = error_data.get("error_description") or error_data.get("error") or resp.text
            logger.warning("Google token exchange returned HTTP %d: %s", resp.status_code, err_msg)
            raise RuntimeError(f"Google OAuth token exchange failed: {err_msg}")

        token_data = resp.json()
        access_token = token_data.get("access_token", "")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in")
        scope_str = token_data.get("scope", "")

        if not access_token:
            raise RuntimeError("Google OAuth response missing access_token.")

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=expires_in) if expires_in else None
        scopes = scope_str.split(" ") if scope_str else DEFAULT_YOUTUBE_SCOPES

        # Store tokens securely in backend memory
        self._tokens[platform] = OAuthTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            token_type=token_data.get("token_type", "Bearer"),
            scopes=scopes,
            created_at=now,
        )

        return {
            "status": "AUTHORIZED",
            "platform": platform,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "scopes": scopes,
        }

    # ------------------------------------------------------------------
    # Backend Token Access & Status (Safe, No Leakage)
    # ------------------------------------------------------------------

    def get_safe_status(self, platform: str = "YouTube") -> dict[str, Any]:
        """
        Return safe status metadata about platform OAuth connection.
        Never reveals access_token, refresh_token, or client_secret.
        """
        configured = self.is_configured()
        tokens = self._tokens.get(platform)
        now = datetime.now(timezone.utc)

        if not configured:
            return {
                "platform": platform,
                "status": "CONFIGURATION_REQUIRED",
                "configured": False,
                "authorized": False,
                "message": "Google OAuth credentials (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET) not configured in backend environment.",
                "redirect_uri": settings.google_redirect_uri,
            }

        if not tokens:
            return {
                "platform": platform,
                "status": "NOT_CONNECTED",
                "configured": True,
                "authorized": False,
                "message": "OAuth client configured. User authorization required.",
                "redirect_uri": settings.google_redirect_uri,
            }

        is_expired = tokens.expires_at is not None and now >= tokens.expires_at
        return {
            "platform": platform,
            "status": "EXPIRED" if is_expired else "AUTHORIZED",
            "configured": True,
            "authorized": not is_expired,
            "is_expired": is_expired,
            "expires_at": tokens.expires_at.isoformat() if tokens.expires_at else None,
            "scopes": tokens.scopes or [],
            "has_refresh_token": bool(tokens.refresh_token),
            "redirect_uri": settings.google_redirect_uri,
        }

    def clear_tokens(self, platform: str = "YouTube") -> bool:
        """Remove stored OAuth tokens for the given platform."""
        return self._tokens.pop(platform, None) is not None

    def get_access_token_internal(self, platform: str = "YouTube") -> str | None:
        """Internal method for connectors to get the raw access token. Never expose via API."""
        tokens = self._tokens.get(platform)
        if not tokens:
            return None
        now = datetime.now(timezone.utc)
        if tokens.expires_at and now >= tokens.expires_at:
            # Token expired
            return None
        return tokens.access_token


_oauth_service_instance: OAuthService | None = None


def get_oauth_service() -> OAuthService:
    """Singleton getter for OAuthService."""
    global _oauth_service_instance
    if _oauth_service_instance is None:
        _oauth_service_instance = OAuthService()
    return _oauth_service_instance
