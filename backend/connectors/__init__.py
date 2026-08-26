# backend/connectors/__init__.py
"""
SocialIQ platform connector layer.

Each connector adapts a specific social-media API into normalised
SocialRecord objects that the analytics pipeline can consume.
"""

from backend.connectors.base import (
    PlatformCapability,
    PlatformConnector,
    PlatformStatus,
    SocialRecord,
)
from backend.connectors.registry import ConnectorRegistry

__all__ = [
    "PlatformCapability",
    "PlatformConnector",
    "PlatformStatus",
    "SocialRecord",
    "ConnectorRegistry",
]
