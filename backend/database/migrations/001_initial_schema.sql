-- ===========================================================================
-- SocialIQ Analytics — Migration 001: Initial Supabase PostgreSQL Schema
-- Tables: social_records, sync_metadata, ingestion_jobs, analytics_snapshots, retention_events
-- Adheres to Supabase Postgres Best Practices:
--   - Lowercase identifiers
--   - bigint generated always as identity primary keys
--   - timestamptz for all timestamps
--   - text for unbounded strings
--   - Appropriate constraints and deduplication indexes
-- ===========================================================================

-- 1. Social Records: Normalized social-media content persistence
CREATE TABLE IF NOT EXISTS social_records (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    platform TEXT NOT NULL,                          -- 'YouTube', 'Telegram', 'Reddit', 'Twitter / X', 'Instagram', 'Facebook'
    platform_record_id TEXT NOT NULL,                -- Platform's unique ID
    content_type TEXT NOT NULL DEFAULT 'post',       -- 'video', 'comment', 'post', 'message', 'reply'
    topic TEXT NOT NULL DEFAULT '',                  -- Topic or query under which this was collected
    author_id TEXT,                                  -- Author/channel identifier
    author_name TEXT,                                -- Author display name
    text TEXT NOT NULL DEFAULT '',                   -- Caption / post / video description
    published_at TIMESTAMPTZ NOT NULL,               -- Original publish time from platform
    retrieved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), -- When SocialIQ fetched it
    updated_at TIMESTAMPTZ,                          -- Last modified timestamp
    views BIGINT,                                    -- Nullable: preserves distinction between unavailable vs 0
    likes BIGINT,                                    -- Nullable: preserves distinction between unavailable vs 0
    comments BIGINT,                                 -- Nullable: preserves distinction between unavailable vs 0
    shares BIGINT,                                   -- Nullable: preserves distinction between unavailable vs 0
    followers BIGINT,                                -- Author follower/subscriber count if available
    topic_keywords TEXT[] DEFAULT '{}',              -- Extracted or platform hashtags/keywords
    source_url TEXT,                                 -- Direct link to the post/video
    raw_metadata JSONB DEFAULT '{}'::jsonb,          -- Platform-specific attributes
    provenance JSONB DEFAULT '{}'::jsonb,            -- Data lineage (source API, job ID, query)
    is_demo BOOLEAN NOT NULL DEFAULT FALSE,          -- Isolation flag: demo data never enters live analytics
    is_waste BOOLEAN NOT NULL DEFAULT FALSE,         -- Priority 1 cleanup candidate
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,      -- Priority 3 cleanup candidate
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_social_records_platform_id UNIQUE (platform, platform_record_id)
);

-- Indexes for fast query patterns (query-composite-indexes, query-partial-indexes)
CREATE INDEX IF NOT EXISTS idx_social_records_platform_topic_pub 
    ON social_records (platform, topic, published_at DESC) 
    WHERE is_demo = FALSE;

CREATE INDEX IF NOT EXISTS idx_social_records_topic_pub 
    ON social_records (topic, published_at DESC) 
    WHERE is_demo = FALSE;

CREATE INDEX IF NOT EXISTS idx_social_records_published_at 
    ON social_records (published_at DESC);

CREATE INDEX IF NOT EXISTS idx_social_records_retrieved_at 
    ON social_records (retrieved_at DESC);

CREATE INDEX IF NOT EXISTS idx_social_records_waste 
    ON social_records (is_waste) 
    WHERE is_waste = TRUE;

CREATE INDEX IF NOT EXISTS idx_social_records_archived 
    ON social_records (is_archived) 
    WHERE is_archived = TRUE;


-- 2. Sync Metadata: Tracks exact time interval and coverage of collected data
CREATE TABLE IF NOT EXISTS sync_metadata (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    platform TEXT NOT NULL,
    topic TEXT NOT NULL,
    available_start TIMESTAMPTZ NOT NULL,            -- Earliest timestamp covered
    available_end TIMESTAMPTZ NOT NULL,              -- Latest timestamp covered
    last_successful_sync TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_attempt TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sync_status TEXT NOT NULL DEFAULT 'complete',    -- 'complete', 'partial', 'in_progress', 'failed'
    coverage_complete BOOLEAN NOT NULL DEFAULT FALSE,-- True if complete platform history is fetched
    record_count BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_sync_metadata_platform_topic UNIQUE (platform, topic)
);

CREATE INDEX IF NOT EXISTS idx_sync_metadata_platform_topic 
    ON sync_metadata (platform, topic);


-- 3. Ingestion Jobs: Auditable lineage and tracking for API fetch operations
CREATE TABLE IF NOT EXISTS ingestion_jobs (
    job_id TEXT PRIMARY KEY,                         -- Unique UUID or deterministic job key
    platform TEXT NOT NULL,
    topic TEXT NOT NULL DEFAULT '',
    requested_period TEXT NOT NULL,                  -- 'Today', 'Last 7 Days', 'Last 30 Days', '1 Year'
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running',          -- 'running', 'completed', 'failed', 'partial'
    records_seen INT NOT NULL DEFAULT 0,
    records_inserted INT NOT NULL DEFAULT 0,
    records_updated INT NOT NULL DEFAULT 0,
    duplicates_skipped INT NOT NULL DEFAULT 0,
    error_summary TEXT,                              -- Masked error description (never exposes credentials)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_platform_started 
    ON ingestion_jobs (platform, started_at DESC);


-- 4. Analytics Snapshots: Derived analytics summaries for fast historical recall
CREATE TABLE IF NOT EXISTS analytics_snapshots (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    snapshot_key TEXT NOT NULL UNIQUE,               -- Hash/Key: e.g. 'YouTube:AI:Last 30 Days:Monthly'
    platform TEXT NOT NULL,
    topic TEXT NOT NULL DEFAULT '',
    period TEXT NOT NULL,
    chart_period TEXT NOT NULL,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    sentiment JSONB NOT NULL DEFAULT '{}'::jsonb,
    insights JSONB NOT NULL DEFAULT '{}'::jsonb,
    record_count INT NOT NULL DEFAULT 0,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ                           -- Cache invalidation boundary
);

CREATE INDEX IF NOT EXISTS idx_analytics_snapshots_key 
    ON analytics_snapshots (snapshot_key);


-- 5. Retention Events: Auditable log of storage management cleanup actions
CREATE TABLE IF NOT EXISTS retention_events (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cleanup_tier INT NOT NULL,                       -- 1: waste, 2: duplicates, 3: archive, 4: FIFO oldest
    tier_name TEXT NOT NULL,                         -- 'waste', 'duplicates', 'archive', 'fifo_history'
    records_removed INT NOT NULL DEFAULT 0,
    bytes_reclaimed BIGINT NOT NULL DEFAULT 0,
    db_size_before_mb NUMERIC(10, 2),
    db_size_after_mb NUMERIC(10, 2),
    reason TEXT NOT NULL
);
