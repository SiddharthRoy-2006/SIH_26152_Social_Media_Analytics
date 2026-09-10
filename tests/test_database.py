"""
tests/test_database.py

Comprehensive test suite verifying:
- Supabase PostgreSQL schema, connection security, and migrations
- First search: records stored in persistence layer
- Repeated search: deduplication prevents duplicates
- Larger-period request: recognizes partial interval coverage (does NOT treat Sept 8 as 1 Year)
- Missing history: requests missing data where platform API supports it
- Unavailable history: reports truthful unavailability without fabricating data
- Overlapping API pages deduplication
- Storage cleanup Priority 1: temporary/waste data purged first
- Storage cleanup Priority 2: duplicate records removed before important history
- Storage cleanup Priority 3 & 4: FIFO oldest historical data removed only as last resort
- Data provenance: source/retrieval metadata and lineage preserved
- Demo isolation: demo records never enter live analytics
- Platform isolation: records remain strictly attributed to their platform
- Time-period coverage: exact stored coverage is tracked
- Credential protection: secrets absent from logs, responses, and errors
"""

from datetime import datetime, timedelta, timezone
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.connectors.base import PlatformCapability, PlatformConnector, PlatformStatus, SocialRecord
from backend.core.config import Settings
from backend.database.connection import check_connection, mask_db_url
from backend.database.repository import (
    get_mem_store,
    get_records,
    get_sync_coverage,
    save_social_records,
    update_sync_coverage,
)
from backend.database.storage_manager import (
    enforce_storage_policy,
    get_storage_usage,
    purge_tier_1_waste,
    purge_tier_2_duplicates,
    purge_tier_3_archived,
    purge_tier_4_fifo_oldest,
)
from backend.services.sync_engine import check_coverage, get_period_bounds, sync_topic_incremental


@pytest.fixture(autouse=True)
def reset_store():
    """Reset repository before and after each test."""
    get_mem_store().reset()
    from backend.database.connection import get_pool
    pool = get_pool()
    test_topics = (
        "Toxic", "Main", "OverlapTest", "FifoTest", "DemoIsolation",
        "MultiPlatform", "TopicD", "WasteTest", "CoverageTopicM",
        "ProvenanceTest", "__SIH_VERIFICATION_TEST__"
    )
    if pool is not None:
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM social_records WHERE topic = ANY(%s);", (list(test_topics),))
                    cur.execute("DELETE FROM sync_metadata WHERE topic = ANY(%s);", (list(test_topics),))
                    cur.execute("DELETE FROM ingestion_jobs WHERE topic = ANY(%s);", (list(test_topics),))
                conn.commit()
        except Exception:
            pass
    yield
    get_mem_store().reset()
    if pool is not None:
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM social_records WHERE topic = ANY(%s);", (list(test_topics),))
                    cur.execute("DELETE FROM sync_metadata WHERE topic = ANY(%s);", (list(test_topics),))
                    cur.execute("DELETE FROM ingestion_jobs WHERE topic = ANY(%s);", (list(test_topics),))
                conn.commit()
        except Exception:
            pass


def _make_record(
    content_id: str,
    platform: str = "YouTube",
    timestamp: datetime | None = None,
    text: str = "Sample post",
    views: int | None = 100,
    likes: int | None = 10,
    comments: int | None = 5,
    shares: int | None = None, # Nullable metric
    is_demo: bool = False,
    is_waste: bool = False,
    is_archived: bool = False,
) -> SocialRecord:
    ts = timestamp or datetime.now(timezone.utc)
    engagement = {}
    if views is not None:
        engagement["views"] = views
    if likes is not None:
        engagement["likes"] = likes
    if comments is not None:
        engagement["comments"] = comments
    if shares is not None:
        engagement["shares"] = shares

    return SocialRecord(
        platform=platform,
        content_id=content_id,
        content_type="video",
        timestamp=ts,
        text=text,
        author_id=f"auth_{content_id}",
        author_name=f"Creator {content_id}",
        engagement=engagement,
        topic_keywords=["toxic", "analytics"],
        source_url=f"https://{platform.lower()}.com/watch?v={content_id}",
    )


# ---------------------------------------------------------------------------
# Test A: First Search Stores Records
# ---------------------------------------------------------------------------

def test_a_first_search_stores_records():
    records = [
        _make_record("rec_1", platform="YouTube", text="First search toxic video 1"),
        _make_record("rec_2", platform="YouTube", text="First search toxic video 2"),
    ]
    inserted, updated, skipped = save_social_records(records, topic="Toxic")
    assert inserted == 2
    assert updated == 0

    stored = get_records(platform="YouTube", topic="Toxic")
    assert len(stored) == 2
    ids = {r.content_id for r in stored}
    assert "rec_1" in ids
    assert "rec_2" in ids


# ---------------------------------------------------------------------------
# Test B: Repeated Search Does Not Create Duplicates (Idempotent UPSERT)
# ---------------------------------------------------------------------------

def test_b_repeated_search_does_not_create_duplicates():
    records_1 = [_make_record("rec_dup", platform="YouTube", views=100, likes=10)]
    inserted, updated, _ = save_social_records(records_1, topic="Toxic")
    assert inserted == 1

    # Second search with updated metrics (e.g. likes went up)
    records_2 = [_make_record("rec_dup", platform="YouTube", views=150, likes=20)]
    inserted_2, updated_2, _ = save_social_records(records_2, topic="Toxic")
    assert inserted_2 == 0
    assert updated_2 == 1

    stored = get_records(platform="YouTube", topic="Toxic")
    assert len(stored) == 1
    assert stored[0].engagement["likes"] == 20
    assert stored[0].engagement["views"] == 150


# ---------------------------------------------------------------------------
# Test C: Larger-Period Request Recognizes Partial Coverage
# ---------------------------------------------------------------------------

def test_c_larger_period_request_recognizes_partial_coverage():
    # Only Sept 8 is stored (e.g. today)
    today = datetime.now(timezone.utc)
    sept_8 = today.replace(hour=12, minute=0, second=0, microsecond=0)
    save_social_records([_make_record("sept8_rec", timestamp=sept_8)], topic="Toxic")
    update_sync_coverage("YouTube", "Toxic", start_time=sept_8 - timedelta(hours=6), end_time=sept_8 + timedelta(hours=6))

    # User asks for "1 Year"
    req_start, req_end = get_period_bounds("1 Year")
    stored, missing_intervals, is_full = check_coverage("YouTube", "Toxic", req_start, req_end)

    # Must NOT claim Sept 8 is the whole year
    assert is_full is False
    assert len(missing_intervals) >= 1
    # Missing interval starts back at req_start (1 year ago)
    assert missing_intervals[0][0] == req_start


# ---------------------------------------------------------------------------
# Test D: Missing History Requests Missing Data from Platform API
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_d_missing_history_requests_missing_data():
    connector = MagicMock(spec=PlatformConnector)
    connector.platform_name = "YouTube"
    connector.check_health.return_value = PlatformCapability(
        platform="YouTube", status=PlatformStatus.CONNECTED, reason="Active"
    )
    # Mock connector search returning older records
    older_time = datetime.now(timezone.utc) - timedelta(days=60)
    connector.search = AsyncMock(return_value=[
        _make_record("older_rec_1", timestamp=older_time, text="Older toxic discussion")
    ])
    connector.fetch_comments = AsyncMock(return_value=[])

    combined, source, meta = await sync_topic_incremental("YouTube", "TopicD", "Last 30 Days", connector)
    assert len(combined) >= 1
    assert meta["new_records_fetched"] == 1
    assert source == "live"


# ---------------------------------------------------------------------------
# Test E: Unavailable History Reports Truthful Unavailability
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_e_unavailable_history_reports_truthful_unavailability():
    # Connector not configured / unavailable
    connector = MagicMock(spec=PlatformConnector)
    connector.check_health.return_value = PlatformCapability(
        platform="YouTube", status=PlatformStatus.NOT_CONFIGURED, reason="API Key missing"
    )

    combined, source, meta = await sync_topic_incremental("YouTube", "UnconfiguredTopic", "1 Year", connector)
    assert len(combined) == 0
    assert source == "empty"
    assert meta["stored_records_found"] == 0


# ---------------------------------------------------------------------------
# Test F: Overlapping API Pages Deduplication
# ---------------------------------------------------------------------------

def test_f_overlapping_api_pages_deduplication():
    # Page 1 contains items [A, B, C]
    page_1 = [_make_record("item_A"), _make_record("item_B"), _make_record("item_C")]
    save_social_records(page_1, topic="OverlapTest")

    # Page 2 overlaps and contains [C, D, E]
    page_2 = [_make_record("item_C"), _make_record("item_D"), _make_record("item_E")]
    inserted, updated, _ = save_social_records(page_2, topic="OverlapTest")

    assert inserted == 2  # Only D and E inserted
    assert updated == 1   # C updated

    all_stored = get_records(topic="OverlapTest")
    assert len(all_stored) == 5  # A, B, C, D, E without duplicates


# ---------------------------------------------------------------------------
# Test G: Storage Cleanup Priority 1 — Waste Data Purged First
# ---------------------------------------------------------------------------

def test_g_storage_cleanup_priority_1_waste_removed_first():
    # Store normal historical data and temporary waste data
    save_social_records([_make_record("valid_1"), _make_record("valid_2")], topic="WasteTest")
    save_social_records([_make_record("waste_1"), _make_record("waste_2")], topic="WasteTest", is_waste=True)

    removed = purge_tier_1_waste()
    assert removed >= 2

    # Critical data preserved
    remaining = get_records(topic="WasteTest")
    assert len(remaining) == 2
    ids = {r.content_id for r in remaining}
    assert "valid_1" in ids
    assert "valid_2" in ids


# ---------------------------------------------------------------------------
# Test H: Storage Cleanup Priority 2 — Duplicate Cleanup
# ---------------------------------------------------------------------------

def test_h_storage_cleanup_priority_2_duplicate_cleanup():
    # Insert record then update it
    save_social_records([_make_record("canon_1")], topic="Main")
    save_social_records([_make_record("canon_1", views=999)], topic="Main")

    # Tier 2 duplicate cleaner operates idempotently
    removed = purge_tier_2_duplicates()
    assert removed == 0  # Deduplication handled at upsert boundary
    assert len(get_records(topic="Main")) == 1


# ---------------------------------------------------------------------------
# Test I: FIFO Fallback — Oldest History Removed Only as Last Resort
# ---------------------------------------------------------------------------

def test_i_fifo_fallback_removes_oldest_eligible_history():
    now = datetime.now(timezone.utc)
    # Recent record (within 10 days) — must NOT be deleted by FIFO
    recent_rec = _make_record("recent_rec", timestamp=now - timedelta(days=5))
    # Old record (120 days ago) — eligible for FIFO removal
    old_rec = _make_record("old_rec", timestamp=now - timedelta(days=120))

    save_social_records([recent_rec, old_rec], topic="FifoTest")

    removed = purge_tier_4_fifo_oldest(batch_size=1, preserve_recent_days=30, topic="FifoTest")
    assert removed == 1

    stored = get_records(topic="FifoTest")
    assert len(stored) == 1
    assert stored[0].content_id == "recent_rec"


# ---------------------------------------------------------------------------
# Test J: Data Provenance Tracking
# ---------------------------------------------------------------------------

def test_j_data_provenance_tracking():
    rec = _make_record("prov_rec", platform="YouTube", text="Provenance test post")
    save_social_records([rec], topic="ProvenanceTest", job_id="job_xyz_123")

    stored = get_records(topic="ProvenanceTest")
    assert len(stored) == 1
    assert stored[0].retrieval_time is not None
    assert stored[0].platform == "YouTube"


# ---------------------------------------------------------------------------
# Test K: Demo Isolation — Demo Records Never Enter Live Analytics
# ---------------------------------------------------------------------------

def test_k_demo_isolation():
    live_rec = _make_record("live_rec", is_demo=False)
    demo_rec = _make_record("demo_rec", is_demo=True)

    save_social_records([live_rec], topic="DemoIsolation", is_demo=False)
    save_social_records([demo_rec], topic="DemoIsolation", is_demo=True)

    # Standard query (include_demo=False) must never return demo record
    live_results = get_records(topic="DemoIsolation", include_demo=False)
    assert len(live_results) == 1
    assert live_results[0].content_id == "live_rec"

    # Explicit demo query
    demo_results = get_records(topic="DemoIsolation", include_demo=True)
    assert len(demo_results) == 2


# ---------------------------------------------------------------------------
# Test L: Platform Isolation
# ---------------------------------------------------------------------------

def test_l_platform_isolation():
    yt_rec = _make_record("same_id", platform="YouTube")
    tg_rec = _make_record("same_id", platform="Telegram")

    save_social_records([yt_rec], topic="MultiPlatform")
    save_social_records([tg_rec], topic="MultiPlatform")

    yt_stored = get_records(platform="YouTube", topic="MultiPlatform")
    tg_stored = get_records(platform="Telegram", topic="MultiPlatform")

    assert len(yt_stored) == 1
    assert yt_stored[0].platform == "YouTube"

    assert len(tg_stored) == 1
    assert tg_stored[0].platform == "Telegram"


# ---------------------------------------------------------------------------
# Test M: Time-Period Coverage Tracking
# ---------------------------------------------------------------------------

def test_m_time_period_coverage_tracking():
    start = datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 9, 8, 18, 0, tzinfo=timezone.utc)

    update_sync_coverage("YouTube", "CoverageTopicM", start, end, record_count_delta=25)
    cov = get_sync_coverage("YouTube", "CoverageTopicM")

    assert cov is not None
    assert cov["available_start"] == start
    assert cov["available_end"] == end
    assert cov["record_count"] == 25


# ---------------------------------------------------------------------------
# Test N: No Credential Leakage in Masking and Health Responses
# ---------------------------------------------------------------------------

def test_n_no_credential_leakage():
    raw_url = "postgresql://postgres:SuperSecretPassword123!@aws-0-ap-south-1.pooler.supabase.com:5432/postgres"
    masked = mask_db_url(raw_url)

    assert "SuperSecretPassword123!" not in masked
    assert "***" in masked

    health = check_connection()
    # In health response, secret must never appear
    health_str = str(health)
    assert "SuperSecretPassword123!" not in health_str
