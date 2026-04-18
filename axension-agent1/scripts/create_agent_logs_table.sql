-- ═══════════════════════════════════════════════════════════
-- Axension AI — Create agent_logs table for Agent 1
-- Run this in Supabase SQL Editor BEFORE first task execution
-- ═══════════════════════════════════════════════════════════

-- Create schema if not exists (factory_001 should already exist from PO sync)
CREATE SCHEMA IF NOT EXISTS factory_001;

-- Create agent_logs table
CREATE TABLE IF NOT EXISTS factory_001.agent_logs (
    id              BIGSERIAL PRIMARY KEY,
    agent_id        VARCHAR(50)     NOT NULL,
    factory_id      VARCHAR(50)     NOT NULL,
    po_number       VARCHAR(50),
    supplier_phone  VARCHAR(50),
    message_type    VARCHAR(50)     NOT NULL,
    message_preview TEXT,
    sent_at         TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    status          VARCHAR(20)     NOT NULL DEFAULT 'pending',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Index for quick lookups
CREATE INDEX IF NOT EXISTS idx_agent_logs_factory
    ON factory_001.agent_logs (factory_id, sent_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_logs_agent
    ON factory_001.agent_logs (agent_id, sent_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_logs_po
    ON factory_001.agent_logs (po_number);

-- Verify
SELECT 'agent_logs table created successfully' AS result;
