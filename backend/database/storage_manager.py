"""
backend/database/storage_manager.py

Configurable storage management and multi-tier retention policy.
Enforces the 4-tier cleanup hierarchy:
  Priority 1: Temporary / Waste / Processing data
  Priority 2: Duplicate / redundant copies
  Priority 3: Archived / low-value records
  Priority 4: FIFO oldest historical records (last resort only)
Never deletes active/recent critical data first.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any

import psycopg
from psycopg import sql

from backend.core.config import settings
from backend.database.connection import get_pool
from backend.database.repository import get_mem_store

import time

logger = logging.getLogger(__name__)

_STORAGE_CACHE: tuple[float, dict[str, Any]] | None = None


def get_storage_usage(cached: bool = True, ttl: float = 300.0, fast: bool = False) -> dict[str, Any]:
    """
    Inspect current database storage size and record counts.
    Uses 300s TTL cache by default to keep health-check responses instant (<1ms).
    When fast=True and not yet cached, returns lightweight stats immediately without blocking table scans.
    """
    global _STORAGE_CACHE
    now = time.monotonic()
    if cached and _STORAGE_CACHE is not None:
        cache_time, cached_result = _STORAGE_CACHE
        if now - cache_time < ttl:
            return dict(cached_result)

    pool = get_pool()
    soft_limit = settings.storage_soft_limit_mb
    critical_limit = settings.storage_critical_limit_mb

    if fast and _STORAGE_CACHE is None:
        result = {
            "connected": pool is not None,
            "database_size_mb": 0.0,
            "total_records": 0,
            "soft_limit_mb": soft_limit,
            "critical_limit_mb": critical_limit,
            "is_critical": False,
            "is_soft_warning": False,
        }
        return result

    if pool is None:
        mem = get_mem_store()
        total_records = len(mem.records)
        waste_count = sum(1 for r in mem.records.values() if r.get("is_waste"))
        archived_count = sum(1 for r in mem.records.values() if r.get("is_archived"))
        # Approximate size: 1KB per record for in-memory tracking
        estimated_mb = round((total_records * 1024) / (1024 * 1024), 3)

        result = {
            "connected": False,
            "database_size_mb": estimated_mb,
            "total_records": total_records,
            "waste_records": waste_count,
            "archived_records": archived_count,
            "soft_limit_mb": soft_limit,
            "critical_limit_mb": critical_limit,
            "is_critical": estimated_mb >= critical_limit,
            "is_soft_warning": estimated_mb >= soft_limit,
        }
        _STORAGE_CACHE = (now, result)
        return dict(result)

    query = """
        SELECT
            ROUND((pg_database_size(current_database()) / (1024.0 * 1024.0))::numeric, 2) AS db_size_mb,
            (SELECT COUNT(*) FROM social_records) AS total_records,
            (SELECT COUNT(*) FROM social_records WHERE is_waste = TRUE) AS waste_records,
            (SELECT COUNT(*) FROM social_records WHERE is_archived = TRUE) AS archived_records;
    """
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                row = cur.fetchone()
                if not row:
                    result = {
                        "connected": True,
                        "database_size_mb": 0.0,
                        "total_records": 0,
                        "soft_limit_mb": soft_limit,
                        "critical_limit_mb": critical_limit,
                    }
                    _STORAGE_CACHE = (now, result)
                    return dict(result)
                db_size = float(row["db_size_mb"])
                result = {
                    "connected": True,
                    "database_size_mb": db_size,
                    "total_records": int(row["total_records"]),
                    "waste_records": int(row["waste_records"]),
                    "archived_records": int(row["archived_records"]),
                    "soft_limit_mb": soft_limit,
                    "critical_limit_mb": critical_limit,
                    "is_critical": db_size >= critical_limit,
                    "is_soft_warning": db_size >= soft_limit,
                }
                _STORAGE_CACHE = (now, result)
                return dict(result)
    except Exception as exc:
        logger.error("Failed to query database storage metrics: %s", exc)
        result = {
            "connected": True,
            "error": str(exc),
            "soft_limit_mb": soft_limit,
            "critical_limit_mb": critical_limit,
        }
        _STORAGE_CACHE = (now, result)
        return dict(result)


def purge_tier_1_waste(dry_run: bool = False) -> int:
    """Priority 1: Remove temporary, waste, and incomplete ingestion records."""
    pool = get_pool()
    if pool is None:
        mem = get_mem_store()
        to_remove = [k for k, r in mem.records.items() if r.get("is_waste")]
        if not dry_run:
            for k in to_remove:
                del mem.records[k]
        return len(to_remove)

    query = "DELETE FROM social_records WHERE is_waste = TRUE;" if not dry_run else "SELECT COUNT(*) FROM social_records WHERE is_waste = TRUE;"
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            if dry_run:
                count = cur.fetchone()["count"]
            else:
                count = cur.rowcount
                _log_retention_event(conn, tier=1, tier_name="waste", records_removed=count, reason="Purge priority 1 temporary/waste data")
        conn.commit()
    return count


def purge_tier_2_duplicates(dry_run: bool = False) -> int:
    """
    Priority 2: Deduplicate redundant records.
    Since unique constraint (platform, platform_record_id) enforces canonical rows,
    this cleans any orphaned or duplicated legacy records by ID hash.
    """
    pool = get_pool()
    if pool is None:
        return 0

    # Clean duplicates preserving latest ID
    query = """
        DELETE FROM social_records a
        USING social_records b
        WHERE a.platform = b.platform
          AND a.platform_record_id = b.platform_record_id
          AND a.id < b.id;
    """
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            count = cur.rowcount
            if count > 0 and not dry_run:
                _log_retention_event(conn, tier=2, tier_name="duplicates", records_removed=count, reason="Deduplicate redundant copies")
        conn.commit()
    return count


def purge_tier_3_archived(older_than_days: int = 180, dry_run: bool = False) -> int:
    """Priority 3: Remove low-value / archived records."""
    pool = get_pool()
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)

    if pool is None:
        mem = get_mem_store()
        to_remove = [
            k for k, r in mem.records.items()
            if r.get("is_archived") and r["published_at"] < cutoff
        ]
        if not dry_run:
            for k in to_remove:
                del mem.records[k]
        return len(to_remove)

    query = """
        DELETE FROM social_records
        WHERE is_archived = TRUE AND published_at < %s;
    """
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (cutoff,))
            count = cur.rowcount
            if count > 0 and not dry_run:
                _log_retention_event(conn, tier=3, tier_name="archive", records_removed=count, reason=f"Trim archived records older than {older_than_days} days")
        conn.commit()
    return count


def purge_tier_4_fifo_oldest(
    batch_size: int = 100,
    preserve_recent_days: int = 30,
    dry_run: bool = False,
    topic: str | None = None,
) -> int:
    """
    Priority 4 (Last resort): FIFO removal of oldest historical records.
    Never deletes active/recent critical records (within preserve_recent_days).
    Optionally scopes cleanup to a specific topic if provided.
    """
    pool = get_pool()
    cutoff = datetime.now(timezone.utc) - timedelta(days=preserve_recent_days)

    if pool is None:
        mem = get_mem_store()
        eligible = [
            (k, r) for k, r in mem.records.items()
            if r["published_at"] < cutoff
            and not r.get("is_demo")
            and (topic is None or r.get("topic") == topic)
        ]
        eligible.sort(key=lambda x: x[1]["published_at"])
        to_remove = [k for k, _ in eligible[:batch_size]]
        if not dry_run:
            for k in to_remove:
                del mem.records[k]
        return len(to_remove)

    if topic:
        query = """
            DELETE FROM social_records
            WHERE id IN (
                SELECT id FROM social_records
                WHERE published_at < %s AND is_demo = FALSE AND topic = %s
                ORDER BY published_at ASC
                LIMIT %s
            );
        """
        params = (cutoff, topic, batch_size)
    else:
        query = """
            DELETE FROM social_records
            WHERE id IN (
                SELECT id FROM social_records
                WHERE published_at < %s AND is_demo = FALSE
                ORDER BY published_at ASC
                LIMIT %s
            );
        """
        params = (cutoff, batch_size)

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            count = cur.rowcount
            if count > 0 and not dry_run:
                _log_retention_event(
                    conn,
                    tier=4,
                    tier_name="fifo_history",
                    records_removed=count,
                    reason=f"FIFO cleanup of oldest history beyond {preserve_recent_days} days" + (f" for topic {topic}" if topic else ""),
                )
        conn.commit()
    return count


def enforce_storage_policy(force_check: bool = False) -> list[dict[str, Any]]:
    """
    Check database capacity and trigger stepped retention cleanup only if needed.
    Returns audit trail of cleanup actions taken.
    """
    usage = get_storage_usage()
    actions: list[dict[str, Any]] = []

    # If below soft limit and not forced, no cleanup necessary
    if not force_check and not usage.get("is_soft_warning", False):
        return actions

    logger.warning("Storage limit threshold reached (DB size: %s MB, soft limit: %s MB). Initiating stepped retention...",
                   usage.get("database_size_mb"), usage.get("soft_limit_mb"))

    # Priority 1: Waste & Incomplete data
    removed_1 = purge_tier_1_waste()
    if removed_1 > 0:
        actions.append({"tier": 1, "name": "waste", "removed": removed_1})
        usage = get_storage_usage()
        if not usage.get("is_soft_warning", False):
            return actions

    # Priority 2: Redundant / Duplicates
    removed_2 = purge_tier_2_duplicates()
    if removed_2 > 0:
        actions.append({"tier": 2, "name": "duplicates", "removed": removed_2})
        usage = get_storage_usage()
        if not usage.get("is_soft_warning", False):
            return actions

    # Priority 3: Low-value archived records
    removed_3 = purge_tier_3_archived()
    if removed_3 > 0:
        actions.append({"tier": 3, "name": "archive", "removed": removed_3})
        usage = get_storage_usage()
        if not usage.get("is_soft_warning", False):
            return actions

    # Priority 4: FIFO oldest historical records (only as last resort)
    removed_4 = purge_tier_4_fifo_oldest(batch_size=200, preserve_recent_days=30)
    if removed_4 > 0:
        actions.append({"tier": 4, "name": "fifo_history", "removed": removed_4})

    return actions


def _log_retention_event(conn: psycopg.Connection, tier: int, tier_name: str, records_removed: int, reason: str) -> None:
    """Record retention audit log entry."""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO retention_events (
                    cleanup_tier, tier_name, records_removed, reason
                ) VALUES (%s, %s, %s, %s);
            """, (tier, tier_name, records_removed, reason))
    except Exception as exc:
        logger.warning("Could not log retention event: %s", exc)
