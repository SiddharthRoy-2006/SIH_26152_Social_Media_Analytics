"""
backend/connectors/base.py

Core types for the platform connector layer:

- SocialRecord      – Normalised representation of one piece of social content.
- PlatformStatus    – Health/availability enum for a connector.
- PlatformCapability– Runtime snapshot of what a connector can provide.
- PlatformConnector – Abstract base class all connectors implement.
"""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# ---------------------------------------------------------------------------
# Normalised social record
# ---------------------------------------------------------------------------

@dataclass
class SocialRecord:
    """One piece of social-media content in normalised form."""

    platform: str                           # "YouTube", "Telegram", "Reddit", …
    content_id: str                         # Platform-specific unique ID
    content_type: str                       # "video", "comment", "post", "message", "reply"
    timestamp: datetime                     # Original publish/post time
    text: str                               # Main textual content

    author_id: str | None = None            # Anonymised where appropriate
    author_name: str | None = None          # Display name where publicly available
    engagement: dict[str, int] = field(default_factory=dict)  # likes, views, comments, …
    topic_keywords: list[str] = field(default_factory=list)    # Tags / extracted keywords
    source_url: str | None = None           # Direct link where appropriate
    retrieval_time: datetime = field(default_factory=datetime.utcnow)
    raw_metadata: dict[str, Any] = field(default_factory=dict) # Platform-specific extras


# ---------------------------------------------------------------------------
# Platform status & capability
# ---------------------------------------------------------------------------

class PlatformStatus(str, enum.Enum):
    """Health state of a platform connector."""

    CONNECTED      = "connected"       # Live data actively flowing
    LIMITED        = "limited"         # Partial access (rate limited, incomplete scope)
    NOT_CONFIGURED = "not_configured"  # Credentials missing / not set up
    UNAVAILABLE    = "unavailable"     # API not accessible (paid req., review pending, …)
    ERROR          = "error"           # Temporary failure (network, auth expired, …)
    RATE_LIMITED   = "rate_limited"    # Temporarily throttled
    DEMO           = "demo"            # Demo/simulation data (explicitly labelled)


@dataclass
class PlatformCapability:
    """Runtime snapshot of what a connector can (or cannot) currently provide."""

    platform: str
    status: PlatformStatus
    reason: str                                # Human-readable explanation
    available_data: list[str] = field(default_factory=list)  # e.g. ["search", "comments"]
    last_checked: datetime | None = None
    last_successful: datetime | None = None
    error_detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "status": self.status.value,
            "reason": self.reason,
            "available_data": self.available_data,
            "last_checked": self.last_checked.isoformat() if self.last_checked else None,
            "last_successful": self.last_successful.isoformat() if self.last_successful else None,
            "error_detail": self.error_detail,
        }


# ---------------------------------------------------------------------------
# Abstract connector
# ---------------------------------------------------------------------------

class PlatformConnector(ABC):
    """
    Abstract base for all social-media connectors.

    Each subclass wraps one platform's API and produces normalised
    SocialRecord objects.  The connector also reports its own capability
    so the registry can surface per-platform status to the API/frontend.
    """

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Canonical platform label (must match the Platform enum)."""
        ...

    @abstractmethod
    def check_health(self) -> PlatformCapability:
        """
        Probe the platform API and return current capability.

        This should be a lightweight check (e.g. verify credentials,
        test a health endpoint) — not a full data fetch.
        """
        ...

    @abstractmethod
    async def search(
        self,
        query: str,
        *,
        limit: int = 50,
        period_days: int = 30,
    ) -> list[SocialRecord]:
        """
        Search/retrieve public content matching *query*.

        Returns normalised SocialRecord objects.
        Raises on unrecoverable errors; returns [] on no results.
        """
        ...

    @abstractmethod
    async def fetch_comments(
        self,
        content_id: str,
        *,
        limit: int = 100,
    ) -> list[SocialRecord]:
        """
        Fetch comments/replies for a specific piece of content.

        Returns normalised SocialRecord objects.
        """
        ...
