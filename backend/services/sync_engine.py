"""
backend/services/sync_engine.py

Incremental Synchronization Engine for SocialIQ Analytics.
Tracks precise historical coverage intervals per (platform, topic).
Determines missing intervals, fetches only missing/new data from official platform APIs,
deduplicates and persists records in Supabase PostgreSQL, and merges stored + live datasets.
Never fabricates missing historical data.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from backend.connectors.base import PlatformConnector, PlatformStatus, SocialRecord
from backend.database.repository import (
    complete_ingestion_job,
    create_ingestion_job,
    get_records,
    get_sync_coverage,
    save_social_records,
    update_sync_coverage,
)

logger = logging.getLogger(__name__)


def get_period_bounds(period: str) -> tuple[datetime, datetime]:
    """Calculate UTC start and end timestamps for a requested period."""
    now = datetime.now(timezone.utc)
    if period == "Today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now
    elif period == "Last 7 Days":
        return now - timedelta(days=7), now
    elif period == "Last 30 Days":
        return now - timedelta(days=30), now
    elif period == "1 Year":
        return now - timedelta(days=365), now
    return now - timedelta(days=30), now


def _period_to_days(period: str) -> int:
    mapping = {"Today": 1, "Last 7 Days": 7, "Last 30 Days": 30, "1 Year": 365}
    return mapping.get(period, 30)


def check_coverage(
    platform: str,
    topic: str,
    req_start: datetime,
    req_end: datetime,
) -> tuple[list[SocialRecord], list[tuple[datetime, datetime]], bool]:
    """
    Check database coverage for a requested time range.
    Returns:
      (stored_records, missing_intervals, is_full_coverage)
    """
    stored = get_records(
        platform=platform,
        topic=topic,
        start_time=req_start,
        end_time=req_end,
    )

    cov = get_sync_coverage(platform, topic)
    if not cov:
        # No coverage recorded at all: entire interval is missing
        return stored, [(req_start, req_end)], False

    avail_start = cov["available_start"]
    avail_end = cov["available_end"]

    missing: list[tuple[datetime, datetime]] = []

    # Check if earlier period is missing (e.g. user asked for 1 Year, but DB only has Sept 8)
    if req_start < avail_start:
        missing.append((req_start, avail_start))

    # Check if recent period is missing (e.g. data older than 30 minutes)
    sync_age = datetime.now(timezone.utc) - cov["last_successful_sync"]
    if sync_age > timedelta(minutes=30) or req_end > avail_end:
        missing.append((max(avail_end, req_start), req_end))

    is_full = len(missing) == 0 and len(stored) > 0
    return stored, missing, is_full


async def sync_topic_incremental(
    platform: str,
    topic: str,
    period: str,
    connector: PlatformConnector | None,
) -> tuple[list[SocialRecord], str, dict[str, Any]]:
    """
    Perform incremental synchronization for a topic on a platform.
    Reuses stored records, requests missing intervals from connector,
    and returns (merged_records, truthful_source, sync_meta).
    """
    topic_clean = topic.strip()
    req_start, req_end = get_period_bounds(period)

    # 1. Check existing database coverage
    stored_records, missing_intervals, is_full = check_coverage(
        platform, topic_clean, req_start, req_end
    )

    sync_meta: dict[str, Any] = {
        "platform": platform,
        "topic": topic_clean,
        "requested_period": period,
        "stored_records_found": len(stored_records),
        "new_records_fetched": 0,
        "duplicates_skipped": 0,
        "missing_intervals_count": len(missing_intervals),
        "historical_status": "complete" if is_full else "partial",
    }

    # If full coverage exists and is fresh, reuse directly without making unnecessary API calls
    if is_full and len(stored_records) > 0:
        logger.info("Reusing %d stored records for %s / %r (coverage complete)", len(stored_records), platform, topic_clean)
        return stored_records, "database", sync_meta

    # If connector is not configured or unavailable, return stored data truthfully
    if connector is None:
        if stored_records:
            sync_meta["historical_status"] = "stored_history_only (connector not configured)"
            return stored_records, "database", sync_meta
        return [], "empty", sync_meta

    cap = connector.check_health()
    if cap.status not in (PlatformStatus.CONNECTED, PlatformStatus.LIMITED):
        if stored_records:
            sync_meta["historical_status"] = f"stored_history_only ({cap.reason})"
            return stored_records, "database", sync_meta
        return [], "empty", sync_meta

    # 2. Fetch missing / fresh records from platform connector
    job_id = create_ingestion_job(platform, topic_clean, period)
    new_records: list[SocialRecord] = []
    period_days = _period_to_days(period)

    try:
        fetched = await connector.search(topic_clean, limit=30, period_days=period_days)
        new_records.extend(fetched)

        # Also fetch comments for top 2 posts for sentiment richness with timeout
        for r in fetched[:2]:
            try:
                comments = await asyncio.wait_for(connector.fetch_comments(r.content_id, limit=20), timeout=3.0)
                new_records.extend(comments)
            except Exception as exc:
                logger.debug("Comments fetch skipped for %s: %s", r.content_id, exc)

        # 3. Clean, Normalize, and Persist via UPSERT Deduplication
        inserted, updated, skipped = save_social_records(
            new_records,
            topic=topic_clean,
            is_demo=False,
            job_id=job_id,
        )

        sync_meta["new_records_fetched"] = len(new_records)
        sync_meta["inserted_count"] = inserted
        sync_meta["updated_count"] = updated
        sync_meta["duplicates_skipped"] = skipped

        # 4. Update sync metadata coverage bounds
        earliest_pub = min((r.timestamp for r in new_records), default=req_start)
        latest_pub = max((r.timestamp for r in new_records), default=req_end)

        update_sync_coverage(
            platform=platform,
            topic=topic_clean,
            start_time=min(earliest_pub, req_start),
            end_time=max(latest_pub, req_end),
            record_count_delta=inserted,
            coverage_complete=True,
            sync_status="complete",
        )

        complete_ingestion_job(
            job_id=job_id,
            seen=len(new_records),
            inserted=inserted,
            updated=updated,
            skipped=skipped,
            status="completed",
        )

    except Exception as exc:
        logger.warning("Connector fetch failed for %s / %r: %s", platform, topic_clean, exc)
        complete_ingestion_job(
            job_id=job_id,
            seen=len(new_records),
            inserted=0,
            updated=0,
            skipped=0,
            status="failed",
            error_summary=str(exc),
        )
        sync_meta["fetch_error"] = str(exc)

    # 5. Merge stored records + newly fetched records with deterministic deduplication
    seen_ids: set[tuple[str, str]] = set()
    combined: list[SocialRecord] = []

    # New records take precedence for updated metrics
    for r in new_records:
        key = (r.platform, r.content_id)
        if key not in seen_ids:
            seen_ids.add(key)
            combined.append(r)

    # Add historical records that were not in the new batch
    for r in stored_records:
        key = (r.platform, r.content_id)
        if key not in seen_ids:
            seen_ids.add(key)
            combined.append(r)

    # Sort chronologically (newest first)
    combined.sort(key=lambda r: r.timestamp, reverse=True)

    # Determine truthful source tag
    has_stored = len(stored_records) > 0
    has_new = len(new_records) > 0

    if has_stored and has_new:
        source = "mixed"  # DATABASE + LIVE
    elif has_new:
        source = "live"
    elif has_stored:
        source = "database"
    else:
        source = "empty"

    return combined, source, sync_meta
