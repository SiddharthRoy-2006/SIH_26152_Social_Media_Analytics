-- ===========================================================================
-- SocialIQ Analytics — Migration 002: Blockchain Report Audits & Integrity Records
-- Tables: blockchain_audits
-- Adheres to Supabase Postgres Best Practices:
--   - Lowercase identifiers
--   - bigint generated always as identity primary keys
--   - timestamptz for all timestamps
--   - text for unbounded strings / hashes
--   - Appropriate indexes for report_id and transaction_hash lookups
-- ===========================================================================

CREATE TABLE IF NOT EXISTS blockchain_audits (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    audit_id TEXT NOT NULL UNIQUE,                    -- e.g. "audit-inst-20260910-a4f2"
    report_id TEXT NOT NULL,                          -- Identifies the SocialIQ report
    report_hash TEXT NOT NULL,                        -- 64-character SHA-256 hexadecimal string
    blockchain_network TEXT NOT NULL,                 -- e.g. "Local EVM (Hardhat Node)", "Anvil", "Ethereum Sepolia"
    chain_id BIGINT NOT NULL,                         -- e.g. 31337
    contract_address TEXT NOT NULL,                   -- 0x... contract address
    transaction_hash TEXT,                            -- 0x... transaction receipt hash
    block_number BIGINT,                              -- Block number where mined
    verification_status TEXT NOT NULL DEFAULT 'RECORDED', -- 'PENDING', 'RECORDED', 'VERIFIED', 'MODIFIED', 'FAILED'
    audited_by TEXT,                                  -- Wallet address that submitted the transaction
    report_metadata JSONB DEFAULT '{}'::jsonb,        -- Context: platform, topic, period, chart_period, summary
    report_payload JSONB DEFAULT '{}'::jsonb,         -- Off-chain canonical copy for later verification
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Fast lookup indexes
CREATE INDEX IF NOT EXISTS idx_blockchain_audits_report_id 
    ON blockchain_audits (report_id);

CREATE INDEX IF NOT EXISTS idx_blockchain_audits_tx_hash 
    ON blockchain_audits (transaction_hash) 
    WHERE transaction_hash IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_blockchain_audits_report_hash 
    ON blockchain_audits (report_hash);

CREATE INDEX IF NOT EXISTS idx_blockchain_audits_status 
    ON blockchain_audits (verification_status);
