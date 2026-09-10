"""
backend/routes/auth.py

FastAPI router implementing the OAuth 2.0 authorization start and callback endpoints.

Security & Integrity Rules:
- Matches exact frontend-referenced callback: http://127.0.0.1:8001/api/auth/callback
- Zero leakage of secrets, client secrets, access tokens, or refresh tokens.
- Strict anti-CSRF state token validation with expiration.
- Truthful reporting of CONFIGURATION_REQUIRED, user cancellation, and API errors.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from backend.core.config import settings
from backend.services.oauth_service import get_oauth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _render_html_result(
    title: str,
    heading: str,
    message: str,
    status_type: str = "success",  # "success" | "error" | "warning"
) -> HTMLResponse:
    """Render a clean, secure HTML response page for the OAuth callback flow."""
    accent_color = "#22c55e" if status_type == "success" else "#ef4444" if status_type == "error" else "#f59e0b"
    icon = "✓" if status_type == "success" else "✕" if status_type == "error" else "!"

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — SocialIQ</title>
  <style>
    :root {{
      --bg: #0b0f19;
      --card-bg: #111827;
      --border: #1f2937;
      --text: #f9fafb;
      --text-muted: #9ca3af;
      --accent: {accent_color};
    }}
    body {{
      margin: 0;
      padding: 0;
      background: var(--bg);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      color: var(--text);
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
    }}
    .card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 36px 40px;
      max-width: 480px;
      text-align: center;
      box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
    }}
    .icon-badge {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 56px;
      height: 56px;
      border-radius: 50%;
      background: rgba(34, 197, 94, 0.1);
      color: var(--accent);
      font-size: 26px;
      font-weight: bold;
      margin-bottom: 20px;
      border: 2px solid var(--accent);
    }}
    h1 {{
      font-size: 20px;
      margin: 0 0 12px 0;
      color: var(--text);
    }}
    p {{
      font-size: 14px;
      line-height: 1.6;
      color: var(--text-muted);
      margin: 0 0 24px 0;
    }}
    .close-btn {{
      background: #3b82f6;
      color: white;
      border: none;
      padding: 10px 24px;
      font-size: 14px;
      font-weight: 500;
      border-radius: 6px;
      cursor: pointer;
      transition: opacity 0.2s;
    }}
    .close-btn:hover {{
      opacity: 0.9;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon-badge">{icon}</div>
    <h1>{heading}</h1>
    <p>{message}</p>
    <button class="close-btn" onclick="window.close()">Close This Tab</button>
  </div>
</body>
</html>"""
    return HTMLResponse(content=html_content, status_code=200 if status_type == "success" else 400)


@router.get("/youtube/authorize")
def authorize_youtube(
    redirect: bool = Query(
        default=False,
        description="If True, immediately redirects to Google OAuth consent. If False, returns JSON with authorization URL.",
    ),
) -> Any:
    """
    Initiate the YouTube OAuth 2.0 authorization handshake.
    Generates a secure state parameter and authorization URL.
    Returns 400 if Google OAuth credentials are not configured in backend environment.
    """
    oauth_service = get_oauth_service()

    if not oauth_service.is_configured():
        return JSONResponse(
            status_code=400,
            content={
                "status": "CONFIGURATION_REQUIRED",
                "platform": "YouTube",
                "message": (
                    "Google OAuth credentials not configured. "
                    "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in backend environment (.env)."
                ),
                "redirect_uri": settings.google_redirect_uri,
            },
        )

    try:
        url, state = oauth_service.build_authorization_url(platform="YouTube")
    except Exception as exc:
        logger.error("Failed to construct authorization URL: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    if redirect:
        return RedirectResponse(url=url, status_code=307)

    return {
        "status": "READY",
        "platform": "YouTube",
        "authorization_url": url,
        "state": state,
        "redirect_uri": settings.google_redirect_uri,
    }


@router.get("/callback")
async def oauth_callback(
    code: str | None = Query(default=None, description="Google OAuth authorization code"),
    state: str | None = Query(default=None, description="Anti-CSRF state token"),
    error: str | None = Query(default=None, description="OAuth error code returned by Google"),
    error_description: str | None = Query(default=None, description="OAuth error description"),
) -> HTMLResponse:
    """
    Handle Google OAuth 2.0 redirect callback:
    http://127.0.0.1:8001/api/auth/callback

    Performs server-side token exchange and stores tokens securely.
    Never exposes tokens in the response or URL parameters.
    """
    oauth_service = get_oauth_service()

    # 1. Handle user cancellation or Google authorization denial
    if error:
        logger.warning("OAuth authorization rejected by Google or user: %s - %s", error, error_description)
        user_msg = (
            "Access was denied or canceled during the Google account authorization process."
            if error == "access_denied"
            else f"Google returned an authorization error: {error}"
        )
        return _render_html_result(
            title="Authorization Denied",
            heading="Authorization Not Completed",
            message=user_msg,
            status_type="warning",
        )

    # 2. Enforce valid state parameter (Anti-CSRF)
    if not state:
        logger.warning("OAuth callback rejected: state parameter missing.")
        return _render_html_result(
            title="Invalid State",
            heading="Security Validation Failed",
            message="State parameter was missing from the callback. Please re-initiate authorization.",
            status_type="error",
        )

    pending_state = oauth_service.validate_and_consume_state(state)
    if not pending_state:
        logger.warning("OAuth callback rejected: state parameter invalid or expired.")
        return _render_html_result(
            title="Expired or Invalid State",
            heading="State Validation Failed",
            message="The authorization session expired or was already used. Please initiate a new handshake.",
            status_type="error",
        )

    # 3. Enforce valid authorization code
    if not code:
        logger.warning("OAuth callback rejected: authorization code missing.")
        return _render_html_result(
            title="Missing Code",
            heading="Authorization Code Missing",
            message="Google did not return an authorization code. Please try again.",
            status_type="error",
        )

    # 4. Perform server-side token exchange
    try:
        await oauth_service.exchange_code_for_tokens(
            code=code,
            platform=pending_state.platform,
        )
    except Exception as exc:
        logger.error("Token exchange failed: %s", exc)
        return _render_html_result(
            title="Token Exchange Failed",
            heading="Authorization Failed",
            message=f"Failed to complete secure token handshake with Google: {exc}",
            status_type="error",
        )

    logger.info("Successfully completed server-side OAuth exchange for %s.", pending_state.platform)
    return _render_html_result(
        title="Authorization Successful",
        heading="Google Account Connected",
        message="Your Google account has been authorized for YouTube Analytics. You can now close this window and return to SocialIQ.",
        status_type="success",
    )


@router.get("/youtube/status")
def get_youtube_auth_status() -> dict[str, Any]:
    """
    Check the current server-side OAuth connection state for YouTube.
    Safely reports configuration, expiration, and scopes with ZERO secret leakage.
    """
    oauth_service = get_oauth_service()
    return oauth_service.get_safe_status(platform="YouTube")


@router.post("/youtube/revoke")
def revoke_youtube_auth() -> dict[str, Any]:
    """
    Disconnect and clear stored OAuth tokens for YouTube on the backend.
    """
    oauth_service = get_oauth_service()
    cleared = oauth_service.clear_tokens(platform="YouTube")
    return {
        "platform": "YouTube",
        "status": "NOT_CONNECTED",
        "cleared": cleared,
        "message": "YouTube OAuth tokens have been successfully cleared from server memory.",
    }
