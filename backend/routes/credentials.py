"""
backend/routes/credentials.py

Secure REST API endpoints for testing, saving, clearing, and querying
social media platform credentials and connection health states.

Security Rules:
- Never returns secrets, tokens, hashes, or passwords in API responses.
- Performs truthful live API probes.
- Sanitizes error messages for human-friendly display.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from backend.connectors.base import PlatformCapability, PlatformStatus, sanitize_error
from backend.connectors.registry import get_registry
from backend.schemas import (
    AllCredentialsStatusResponse,
    CredentialClearRequest,
    CredentialSaveRequest,
    CredentialStatusResponse,
    CredentialTestRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/credentials", tags=["credentials"])


def _capability_to_response(cap: PlatformCapability) -> CredentialStatusResponse:
    """Convert PlatformCapability to safe CredentialStatusResponse (no secrets)."""
    is_live = cap.status in (PlatformStatus.CONNECTED, PlatformStatus.LIMITED)
    is_configured = cap.status != PlatformStatus.NOT_CONFIGURED

    source_map = {
        PlatformStatus.CONNECTED: "live",
        PlatformStatus.LIMITED: "live",
        PlatformStatus.NOT_CONFIGURED: "empty",
        PlatformStatus.UNAVAILABLE: "unavailable",
        PlatformStatus.ERROR: "error",
        PlatformStatus.RATE_LIMITED: "live",
        PlatformStatus.DEMO: "demo",
    }
    source = source_map.get(cap.status, "empty")

    return CredentialStatusResponse(
        platform=cap.platform,
        status=cap.status.value,
        source=source,
        configured=is_configured,
        live=is_live,
        message=cap.reason,
        detail=sanitize_error(cap.error_detail),
        available_data=cap.available_data,
        credential_fields=cap.credential_fields,
        approx_test_time=cap.approx_test_time,
        last_checked=cap.last_checked.isoformat() if cap.last_checked else None,
        last_successful=cap.last_successful.isoformat() if cap.last_successful else None,
    )



@router.get("/status", response_model=AllCredentialsStatusResponse)
def get_credentials_status() -> AllCredentialsStatusResponse:
    """Return status of all 6 platform connectors without exposing secrets."""
    registry = get_registry()
    all_caps = registry.all_capabilities()
    
    result: dict[str, CredentialStatusResponse] = {}
    for platform_name, cap in all_caps.items():
        result[platform_name] = _capability_to_response(cap)

    return AllCredentialsStatusResponse(platforms=result)


@router.post("/test", response_model=CredentialStatusResponse)
def test_credential(req: CredentialTestRequest) -> CredentialStatusResponse:
    """
    Test platform credentials with an actual live API probe.
    Does NOT permanently store if credentials dict is provided purely for testing.
    """
    platform = req.platform.strip()
    registry = get_registry()

    # If credentials supplied, test directly via registry update & health check
    cap = registry.test_credentials(platform, req.credentials if req.credentials else None)
    return _capability_to_response(cap)


@router.post("/save", response_model=CredentialStatusResponse)
def save_credential(req: CredentialSaveRequest) -> CredentialStatusResponse:
    """
    Save / update runtime credentials for a platform and perform an actual API test.
    """
    platform = req.platform.strip()
    registry = get_registry()

    cap = registry.update_credentials(platform, req.credentials)
    return _capability_to_response(cap)


@router.post("/clear", response_model=CredentialStatusResponse)
def clear_credential(req: CredentialClearRequest) -> CredentialStatusResponse:
    """
    Clear credentials for a platform and reset connection status.
    """
    platform = req.platform.strip()
    registry = get_registry()

    cap = registry.clear_credentials(platform)
    return _capability_to_response(cap)
