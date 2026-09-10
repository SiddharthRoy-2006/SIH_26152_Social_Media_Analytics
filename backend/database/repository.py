"""
backend/database/repository.py

Repository layer for social_records, sync_metadata, ingestion_jobs, and storage metrics.
Provides atomic UPSERT operations, time-range querying, provenance tracking, and deduplication.
Preserves nullability (null vs 0) and strictly isolates demo records.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from typing import Any
import uuid

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from backend.connectors.base import SocialRecord
from backend.database.connection import get_pool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# In-Memory Storage Fallback (used when database credentials are not configured)
# ---------------------------------------------------------------------------

class _InMemoryRepository:
    """Hermetic in-memory store ensuring tests pass even without live PostgreSQL."""

    def __init__(self) -> None:
        self.records: dict[tuple[str, str], dict[str, Any]] = {}
        self.sync_meta: dict[tuple[str, str], dict[str, Any]] = {}
        self.ingestion_jobs: dict[str, dict[str, Any]] = {}
        self.retention_events: list[dict[str, Any]] = []
        self.blockchain_audits: dict[str, dict[str, Any]] = {}

    def reset(self) -> None:
        self.records.clear()
        self.sync_meta.clear()
        self.ingestion_jobs.clear()
        self.retention_events.clear()
        self.blockchain_audits.clear()


_MEM_STORE = _InMemoryRepository()


def get_mem_store() -> _InMemoryRepository:
    return _MEM_STORE


# ---------------------------------------------------------------------------
# Conversion Helpers
# ---------------------------------------------------------------------------

def _row_to_social_record(row: dict[str, Any]) -> SocialRecord:
    """Convert database row to normalized SocialRecord."""
    engagement: dict[str, int] = {}
    if row.get("likes") is not None:
        engagement["likes"] = int(row["likes"])
    if row.get("views") is not None:
        engagement["views"] = int(row["views"])
    if row.get("comments") is not None:
        engagement["comments"] = int(row["comments"])
    if row.get("shares") is not None:
        engagement["shares"] = int(row["shares"])
    if row.get("followers") is not None:
        engagement["followers"] = int(row["followers"])

    raw_meta = row.get("raw_metadata") or {}
    if isinstance(raw_meta, str):
        try:
            raw_meta = json.loads(raw_meta)
        except Exception:
            raw_meta = {}

    topic_keywords = row.get("topic_keywords") or []
    if isinstance(topic_keywords, str):
        topic_keywords = [k.strip() for k in topic_keywords.split(",") if k.strip()]

    return SocialRecord(
        platform=row["platform"],
        content_id=row["platform_record_id"],
        content_type=row.get("content_type", "post"),
        timestamp=row["published_at"],
        text=row["text"],
        author_id=row.get("author_id"),
        author_name=row.get("author_name"),
        engagement=engagement,
        topic_keywords=list(topic_keywords),
        source_url=row.get("source_url"),
        retrieval_time=row.get("retrieved_at") or datetime.now(timezone.utc),
        raw_metadata=raw_meta,
    )


# ---------------------------------------------------------------------------
# Social Records Operations
# ---------------------------------------------------------------------------

def save_social_records(
    records: list[SocialRecord],
    topic: str = "",
    *,
    is_demo: bool = False,
    is_waste: bool = False,
    is_archived: bool = False,
    job_id: str | None = None,
) -> tuple[int, int, int]:
    """
    Persist records using atomic UPSERT (INSERT ... ON CONFLICT).
    Returns (inserted_count, updated_count, skipped_count).
    Preserves exact NULL values for unavailable metrics (does not convert to 0).
    """
    if not records:
        return 0, 0, 0

    pool = get_pool()
    if pool is None:
        # Fallback to in-memory store
        inserted = 0
        updated = 0
        for r in records:
            key = (r.platform, r.content_id)
            row = {
                "platform": r.platform,
                "platform_record_id": r.content_id,
                "content_type": r.content_type,
                "topic": topic.strip(),
                "author_id": r.author_id,
                "author_name": r.author_name,
                "text": r.text,
                "published_at": r.timestamp,
                "retrieved_at": r.retrieval_time,
                "views": r.engagement.get("views"),
                "likes": r.engagement.get("likes"),
                "comments": r.engagement.get("comments"),
                "shares": r.engagement.get("shares"),
                "followers": r.engagement.get("followers"),
                "topic_keywords": r.topic_keywords or [],
                "source_url": r.source_url,
                "raw_metadata": r.raw_metadata or {},
                "provenance": {"job_id": job_id, "topic": topic},
                "is_demo": is_demo,
                "is_waste": is_waste,
                "is_archived": is_archived,
            }
            if key in _MEM_STORE.records:
                _MEM_STORE.records[key].update(row)
                updated += 1
            else:
                _MEM_STORE.records[key] = row
                inserted += 1
        return inserted, updated, 0

    # PostgreSQL Atomic UPSERT
    upsert_sql = """
        INSERT INTO social_records (
            platform, platform_record_id, content_type, topic,
            author_id, author_name, text, published_at, retrieved_at,
            views, likes, comments, shares, followers,
            topic_keywords, source_url, raw_metadata, provenance,
            is_demo, is_waste, is_archived
        ) VALUES (
            %(platform)s, %(platform_record_id)s, %(content_type)s, %(topic)s,
            %(author_id)s, %(author_name)s, %(text)s, %(published_at)s, %(retrieved_at)s,
            %(views)s, %(likes)s, %(comments)s, %(shares)s, %(followers)s,
            %(topic_keywords)s, %(source_url)s, %(raw_metadata)s, %(provenance)s,
            %(is_demo)s, %(is_waste)s, %(is_archived)s
        )
        ON CONFLICT (platform, platform_record_id)
        DO UPDATE SET
            topic = CASE WHEN EXCLUDED.topic <> '' THEN EXCLUDED.topic ELSE social_records.topic END,
            views = COALESCE(EXCLUDED.views, social_records.views),
            likes = COALESCE(EXCLUDED.likes, social_records.likes),
            comments = COALESCE(EXCLUDED.comments, social_records.comments),
            shares = COALESCE(EXCLUDED.shares, social_records.shares),
            followers = COALESCE(EXCLUDED.followers, social_records.followers),
            retrieved_at = EXCLUDED.retrieved_at,
            updated_at = NOW(),
            raw_metadata = EXCLUDED.raw_metadata,
            provenance = EXCLUDED.provenance
        RETURNING (xmax = 0) AS is_insert;
    """

    inserted = 0
    updated = 0

    with pool.connection() as conn:
        with conn.cursor() as cur:
            for r in records:
                params = {
                    "platform": r.platform,
                    "platform_record_id": r.content_id,
                    "content_type": r.content_type,
                    "topic": topic.strip(),
                    "author_id": r.author_id,
                    "author_name": r.author_name,
                    "text": r.text,
                    "published_at": r.timestamp,
                    "retrieved_at": r.retrieval_time,
                    "views": r.engagement.get("views"),
                    "likes": r.engagement.get("likes"),
                    "comments": r.engagement.get("comments"),
                    "shares": r.engagement.get("shares"),
                    "followers": r.engagement.get("followers"),
                    "topic_keywords": r.topic_keywords or [],
                    "source_url": r.source_url,
                    "raw_metadata": Jsonb(r.raw_metadata or {}),
                    "provenance": Jsonb({"job_id": job_id, "topic": topic, "collected_at": datetime.now(timezone.utc).isoformat()}),
                    "is_demo": is_demo,
                    "is_waste": is_waste,
                    "is_archived": is_archived,
                }
                cur.execute(upsert_sql, params)
                res = cur.fetchone()
                if res and res.get("is_insert"):
                    inserted += 1
                else:
                    updated += 1
        conn.commit()

    return inserted, updated, 0


def get_records(
    platform: str = "All Platforms",
    topic: str = "",
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = 1000,
    include_demo: bool = False,
) -> list[SocialRecord]:
    """Query stored social records matching filters."""
    pool = get_pool()
    if pool is None:
        # In-memory store filter
        results: list[SocialRecord] = []
        for row in _MEM_STORE.records.values():
            if not include_demo and row.get("is_demo"):
                continue
            if platform != "All Platforms" and row["platform"] != platform:
                continue
            if topic:
                row_topic = (row.get("topic") or "").lower()
                kws = [k.lower() for k in (row.get("topic_keywords") or [])]
                t_lower = topic.strip().lower()
                if row_topic != t_lower and t_lower not in kws:
                    continue
            pub = row["published_at"]
            if start_time and pub < start_time:
                continue
            if end_time and pub > end_time:
                continue
            results.append(_row_to_social_record(row))
        results.sort(key=lambda r: r.timestamp, reverse=True)
        return results[:limit]

    # PostgreSQL query with parameterized conditions
    query = """
        SELECT * FROM social_records
        WHERE (is_demo = FALSE OR %(include_demo)s = TRUE)
    """
    params: dict[str, Any] = {"include_demo": include_demo, "limit": limit}

    if platform != "All Platforms":
        query += " AND platform = %(platform)s"
        params["platform"] = platform

    if topic.strip():
        query += " AND (LOWER(topic) = LOWER(%(topic)s) OR %(topic)s = ANY(topic_keywords))"
        params["topic"] = topic.strip()

    if start_time:
        query += " AND published_at >= %(start_time)s"
        params["start_time"] = start_time

    if end_time:
        query += " AND published_at <= %(end_time)s"
        params["end_time"] = end_time

    query += " ORDER BY published_at DESC LIMIT %(limit)s;"

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
            return [_row_to_social_record(row) for row in rows]


# ---------------------------------------------------------------------------
# Sync Metadata / Coverage Tracking
# ---------------------------------------------------------------------------

def get_sync_coverage(platform: str, topic: str) -> dict[str, Any] | None:
    """Retrieve recorded coverage interval for a (platform, topic) pair."""
    pool = get_pool()
    if pool is None:
        key = (platform, topic.strip().lower())
        return _MEM_STORE.sync_meta.get(key)

    query = """
        SELECT * FROM sync_metadata
        WHERE platform = %(platform)s AND LOWER(topic) = LOWER(%(topic)s);
    """
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, {"platform": platform, "topic": topic.strip()})
            row = cur.fetchone()
            if not row:
                return None
            return {
                "available_start": row["available_start"],
                "available_end": row["available_end"],
                "last_successful_sync": row["last_successful_sync"],
                "last_attempt": row["last_attempt"],
                "sync_status": row["sync_status"],
                "coverage_complete": row["coverage_complete"],
                "record_count": row["record_count"],
            }


def update_sync_coverage(
    platform: str,
    topic: str,
    start_time: datetime,
    end_time: datetime,
    record_count_delta: int = 0,
    coverage_complete: bool = False,
    sync_status: str = "complete",
) -> None:
    """Expand or insert coverage interval for (platform, topic)."""
    pool = get_pool()
    if pool is None:
        key = (platform, topic.strip().lower())
        existing = _MEM_STORE.sync_meta.get(key)
        if existing:
            new_start = min(existing["available_start"], start_time)
            new_end = max(existing["available_end"], end_time)
            existing["available_start"] = new_start
            existing["available_end"] = new_end
            existing["record_count"] += record_count_delta
            existing["coverage_complete"] = existing["coverage_complete"] or coverage_complete
            existing["last_successful_sync"] = datetime.now(timezone.utc)
            existing["sync_status"] = sync_status
        else:
            _MEM_STORE.sync_meta[key] = {
                "platform": platform,
                "topic": topic.strip(),
                "available_start": start_time,
                "available_end": end_time,
                "record_count": record_count_delta,
                "coverage_complete": coverage_complete,
                "last_successful_sync": datetime.now(timezone.utc),
                "sync_status": sync_status,
            }
        return

    upsert_sql = """
        INSERT INTO sync_metadata (
            platform, topic, available_start, available_end,
            last_successful_sync, last_attempt, sync_status,
            coverage_complete, record_count
        ) VALUES (
            %(platform)s, %(topic)s, %(start_time)s, %(end_time)s,
            NOW(), NOW(), %(sync_status)s, %(coverage_complete)s, %(record_count_delta)s
        )
        ON CONFLICT (platform, topic)
        DO UPDATE SET
            available_start = LEAST(sync_metadata.available_start, EXCLUDED.available_start),
            available_end = GREATEST(sync_metadata.available_end, EXCLUDED.available_end),
            last_successful_sync = NOW(),
            last_attempt = NOW(),
            sync_status = EXCLUDED.sync_status,
            coverage_complete = sync_metadata.coverage_complete OR EXCLUDED.coverage_complete,
            record_count = sync_metadata.record_count + EXCLUDED.record_count,
            updated_at = NOW();
    """
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                upsert_sql,
                {
                    "platform": platform,
                    "topic": topic.strip(),
                    "start_time": start_time,
                    "end_time": end_time,
                    "sync_status": sync_status,
                    "coverage_complete": coverage_complete,
                    "record_count_delta": record_count_delta,
                },
            )
        conn.commit()


# ---------------------------------------------------------------------------
# Ingestion Job Tracking
# ---------------------------------------------------------------------------

def create_ingestion_job(
    platform: str,
    topic: str,
    period: str,
    job_id: str | None = None,
) -> str:
    """Register a new ingestion job."""
    jid = job_id or str(uuid.uuid4())
    pool = get_pool()
    if pool is None:
        _MEM_STORE.ingestion_jobs[jid] = {
            "job_id": jid,
            "platform": platform,
            "topic": topic,
            "requested_period": period,
            "started_at": datetime.now(timezone.utc),
            "status": "running",
            "records_seen": 0,
            "records_inserted": 0,
            "records_updated": 0,
            "duplicates_skipped": 0,
        }
        return jid

    query = """
        INSERT INTO ingestion_jobs (
            job_id, platform, topic, requested_period, status
        ) VALUES (
            %(job_id)s, %(platform)s, %(topic)s, %(requested_period)s, 'running'
        );
    """
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                {
                    "job_id": jid,
                    "platform": platform,
                    "topic": topic,
                    "requested_period": period,
                },
            )
        conn.commit()
    return jid


def complete_ingestion_job(
    job_id: str,
    seen: int,
    inserted: int,
    updated: int,
    skipped: int,
    status: str = "completed",
    error_summary: str | None = None,
) -> None:
    """Record completion stats for an ingestion job."""
    pool = get_pool()
    if pool is None:
        job = _MEM_STORE.ingestion_jobs.get(job_id)
        if job:
            job.update({
                "completed_at": datetime.now(timezone.utc),
                "status": status,
                "records_seen": seen,
                "records_inserted": inserted,
                "records_updated": updated,
                "duplicates_skipped": skipped,
                "error_summary": error_summary,
            })
        return

    query = """
        UPDATE ingestion_jobs SET
            completed_at = NOW(),
            status = %(status)s,
            records_seen = %(seen)s,
            records_inserted = %(inserted)s,
            records_updated = %(updated)s,
            duplicates_skipped = %(skipped)s,
            error_summary = %(error_summary)s
        WHERE job_id = %(job_id)s;
    """
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                {
                    "job_id": job_id,
                    "status": status,
                    "seen": seen,
                    "inserted": inserted,
                    "updated": updated,
                    "skipped": skipped,
                    "error_summary": error_summary,
                },
            )
        conn.commit()


# ---------------------------------------------------------------------------
# Blockchain Audit Metadata Operations
# ---------------------------------------------------------------------------

def save_blockchain_audit(
    *,
    audit_id: str,
    report_id: str,
    report_hash: str,
    blockchain_network: str,
    chain_id: int,
    contract_address: str,
    transaction_hash: str | None,
    block_number: int | None,
    verification_status: str = "RECORDED",
    audited_by: str | None = None,
    report_metadata: dict[str, Any] | None = None,
    report_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Persist or update blockchain audit metadata in PostgreSQL or in-memory fallback.
    Never stores private keys or secrets.
    """
    pool = get_pool()
    now_iso = datetime.now(timezone.utc)
    meta = report_metadata or {}
    payload = report_payload or {}

    record = {
        "audit_id": audit_id,
        "report_id": report_id,
        "report_hash": report_hash,
        "blockchain_network": blockchain_network,
        "chain_id": chain_id,
        "contract_address": contract_address,
        "transaction_hash": transaction_hash,
        "block_number": block_number,
        "verification_status": verification_status,
        "audited_by": audited_by,
        "report_metadata": meta,
        "report_payload": payload,
        "recorded_at": now_iso,
        "verified_at": now_iso if verification_status == "VERIFIED" else None,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    _MEM_STORE.blockchain_audits[report_id] = record

    if pool is None:
        return record

    try:
        query = """
            INSERT INTO blockchain_audits (
                audit_id,
                report_id,
                report_hash,
                blockchain_network,
                chain_id,
                contract_address,
                transaction_hash,
                block_number,
                verification_status,
                audited_by,
                report_metadata,
                report_payload,
                recorded_at
            ) VALUES (
                %(audit_id)s,
                %(report_id)s,
                %(report_hash)s,
                %(blockchain_network)s,
                %(chain_id)s,
                %(contract_address)s,
                %(transaction_hash)s,
                %(block_number)s,
                %(verification_status)s,
                %(audited_by)s,
                %(report_metadata)s,
                %(report_payload)s,
                %(recorded_at)s
            )
            ON CONFLICT (audit_id) DO UPDATE SET
                report_hash = EXCLUDED.report_hash,
                transaction_hash = EXCLUDED.transaction_hash,
                block_number = EXCLUDED.block_number,
                verification_status = EXCLUDED.verification_status,
                report_metadata = EXCLUDED.report_metadata,
                report_payload = EXCLUDED.report_payload,
                updated_at = NOW()
            RETURNING *;
        """
        with pool.connection(timeout=3.0) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    {
                        "audit_id": audit_id,
                        "report_id": report_id,
                        "report_hash": report_hash,
                        "blockchain_network": blockchain_network,
                        "chain_id": chain_id,
                        "contract_address": contract_address,
                        "transaction_hash": transaction_hash,
                        "block_number": block_number,
                        "verification_status": verification_status,
                        "audited_by": audited_by,
                        "report_metadata": Jsonb(meta),
                        "report_payload": Jsonb(payload),
                        "recorded_at": now_iso,
                    },
                )
                row = cur.fetchone()
            conn.commit()

        if row:
            db_dict = dict(row)
            _MEM_STORE.blockchain_audits[report_id] = db_dict
            return db_dict
    except Exception as exc:
        logger.warning("PostgreSQL audit save failed; using in-memory store: %s", exc)

    return record


def get_blockchain_audit(report_id: str) -> dict[str, Any] | None:
    """Retrieve audit record by report_id."""
    pool = get_pool()
    if pool is None:
        return _MEM_STORE.blockchain_audits.get(report_id)

    try:
        query = """
            SELECT * FROM blockchain_audits
            WHERE report_id = %(report_id)s
            ORDER BY created_at DESC
            LIMIT 1;
        """
        with pool.connection(timeout=3.0) as conn:
            with conn.cursor() as cur:
                cur.execute(query, {"report_id": report_id})
                row = cur.fetchone()
        if row:
            return dict(row)
    except Exception as exc:
        logger.debug("PostgreSQL get audit fallback: %s", exc)

    return _MEM_STORE.blockchain_audits.get(report_id)


def update_blockchain_audit_status(
    report_id: str,
    verification_status: str,
    verified_at: datetime | None = None,
) -> bool:
    """Update verification status for an existing audit."""
    now_iso = verified_at or datetime.now(timezone.utc)
    if report_id in _MEM_STORE.blockchain_audits:
        _MEM_STORE.blockchain_audits[report_id]["verification_status"] = verification_status
        _MEM_STORE.blockchain_audits[report_id]["verified_at"] = now_iso
        _MEM_STORE.blockchain_audits[report_id]["updated_at"] = now_iso

    pool = get_pool()
    if pool is None:
        return report_id in _MEM_STORE.blockchain_audits

    try:
        query = """
            UPDATE blockchain_audits SET
                verification_status = %(verification_status)s,
                verified_at = %(verified_at)s,
                updated_at = NOW()
            WHERE report_id = %(report_id)s;
        """
        with pool.connection(timeout=3.0) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    {
                        "report_id": report_id,
                        "verification_status": verification_status,
                        "verified_at": now_iso,
                    },
                )
                affected = cur.rowcount
            conn.commit()
        return affected > 0
    except Exception as exc:
        logger.warning("PostgreSQL update audit status error: %s", exc)
        return report_id in _MEM_STORE.blockchain_audits


def list_recent_blockchain_audits(limit: int = 15) -> list[dict[str, Any]]:
    """Return recent blockchain audits for UI / dashboard."""
    pool = get_pool()
    if pool is None:
        audits = list(_MEM_STORE.blockchain_audits.values())
        return sorted(audits, key=lambda x: str(x.get("created_at", "")), reverse=True)[:limit]

    try:
        query = """
            SELECT audit_id, report_id, report_hash, blockchain_network, chain_id,
                   contract_address, transaction_hash, block_number, verification_status,
                   audited_by, report_metadata, recorded_at, verified_at, created_at
            FROM blockchain_audits
            ORDER BY created_at DESC
            LIMIT %(limit)s;
        """
        with pool.connection(timeout=3.0) as conn:
            with conn.cursor() as cur:
                cur.execute(query, {"limit": limit})
                rows = cur.fetchall()
        if rows:
            return [dict(r) for r in rows]
    except Exception as exc:
        logger.warning("PostgreSQL list audits fallback: %s", exc)

    audits = list(_MEM_STORE.blockchain_audits.values())
    return sorted(audits, key=lambda x: str(x.get("created_at", "")), reverse=True)[:limit]


