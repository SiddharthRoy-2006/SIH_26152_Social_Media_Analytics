"""
backend/database/connection.py

Database connection manager and connection pool for Supabase PostgreSQL.
Handles secure connection initialization, migration execution, and health monitoring.
Never exposes plaintext credentials in logs or error messages.
"""

from __future__ import annotations

import logging
from pathlib import Path
import re
import time
from typing import Any
from urllib.parse import urlparse

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from backend.core.config import settings

logger = logging.getLogger(__name__)

_POOL: ConnectionPool | None = None
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def mask_db_url(url: str | None) -> str:
    """Mask password from a PostgreSQL connection string."""
    if not url:
        return ""
    return re.sub(r":([^:@]+)@", r":***@", url)


def is_database_configured() -> bool:
    """Check if database credentials or URL are configured."""
    return bool(settings.get_database_url())


def get_connection_url() -> str:
    """Get the sanitized/configured database URL."""
    return settings.get_database_url()


def get_pool() -> ConnectionPool | None:
    """
    Get or create the global thread-safe connection pool.
    Returns None if database is not configured.
    """
    global _POOL
    url = get_connection_url()
    if not url:
        return None

    if _POOL is None:
        try:
            logger.info("Initializing PostgreSQL connection pool to %s", mask_db_url(url))
            _POOL = ConnectionPool(
                conninfo=url,
                min_size=1,
                max_size=10,
                timeout=15.0,
                max_idle=120.0,
                max_lifetime=1800.0,
                check=ConnectionPool.check_connection,
                kwargs={"row_factory": dict_row},
                open=True,
            )
        except Exception as exc:
            logger.error("Failed to initialize database connection pool: %s", exc)
            return None

    return _POOL


def close_pool() -> None:
    """Close the connection pool cleanly."""
    global _POOL
    if _POOL is not None:
        try:
            _POOL.close()
        except Exception as exc:
            logger.warning("Error closing connection pool: %s", exc)
        finally:
            _POOL = None


_HEALTH_CACHE: tuple[float, dict[str, Any]] | None = None


def check_connection(cached: bool = True, ttl: float = 180.0) -> dict[str, Any]:
    """
    Probe the database and return health metrics.
    Returns safe summary without sensitive information.
    Uses 180s TTL cache by default to keep health-check responses instant (<1ms).
    """
    global _HEALTH_CACHE
    now = time.monotonic()
    if cached and _HEALTH_CACHE is not None:
        cache_time, cached_result = _HEALTH_CACHE
        if now - cache_time < ttl:
            return dict(cached_result)

    url = get_connection_url()
    if not url:
        result = {
            "status": "not_configured",
            "connected": False,
            "message": "Supabase database URL is not configured. Set SUPABASE_DB_URL in environment.",
            "endpoint": None,
        }
        _HEALTH_CACHE = (now, result)
        return dict(result)

    start_time = time.monotonic()
    try:
        pool = get_pool()
        if pool is None:
            result = {
                "status": "error",
                "connected": False,
                "message": "Connection pool could not be initialized.",
                "endpoint": mask_db_url(url),
            }
            _HEALTH_CACHE = (now, result)
            return dict(result)

        with pool.connection(timeout=3.0) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS ping, current_database() AS db_name;")
                row = cur.fetchone()
                latency_ms = round((time.monotonic() - start_time) * 1000, 2)

                result = {
                    "status": "connected",
                    "connected": True,
                    "database": row.get("db_name") if row else "postgres",
                    "latency_ms": latency_ms,
                    "endpoint": mask_db_url(url),
                    "soft_limit_mb": settings.storage_soft_limit_mb,
                    "critical_limit_mb": settings.storage_critical_limit_mb,
                }
                _HEALTH_CACHE = (now, result)
                return dict(result)
    except Exception as exc:
        logger.error("Database health check failed: %s", exc)
        result = {
            "status": "error",
            "connected": False,
            "message": str(exc),
            "endpoint": mask_db_url(url),
        }
        _HEALTH_CACHE = (now, result)
        return dict(result)


def run_migrations() -> list[str]:
    """
    Execute all SQL migration files in sequence idempotently.
    Returns list of applied migration names.
    """
    pool = get_pool()
    if pool is None:
        logger.warning("Skipping migrations: database not configured.")
        return []

    applied: list[str] = []
    with pool.connection(timeout=5.0) as conn:
        with conn.cursor() as cur:
            # Migration tracking table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    migration_name TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)

            migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
            for mfile in migration_files:
                mname = mfile.name
                cur.execute("SELECT 1 FROM schema_migrations WHERE migration_name = %s;", (mname,))
                if cur.fetchone():
                    continue

                logger.info("Applying migration %s...", mname)
                sql_content = mfile.read_text(encoding="utf-8")
                cur.execute(sql_content)
                cur.execute(
                    "INSERT INTO schema_migrations (migration_name) VALUES (%s);",
                    (mname,),
                )
                applied.append(mname)
        conn.commit()

    if applied:
        logger.info("Applied %d migration(s): %s", len(applied), ", ".join(applied))
    return applied
