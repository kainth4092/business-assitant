-- =============================================================================
-- Support Desk Schema & Demo Problem Seeding
-- =============================================================================

-- 1. Support Tickets Table
CREATE TABLE IF NOT EXISTS support_tickets (
    id VARCHAR(64) PRIMARY KEY,
    client_name VARCHAR(128) NOT NULL DEFAULT 'Client User',
    client_email VARCHAR(128) NOT NULL DEFAULT 'client@example.com',
    sender_id VARCHAR(128),
    channel VARCHAR(64) NOT NULL DEFAULT 'webhook',
    message TEXT NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'new', -- 'new', 'investigating', 'fix_ready', 'approved', 'done', 'rejected', 'flagged'
    classification VARCHAR(32), -- 'data_issue', 'code_bug', 'question', 'feature_request', 'security_flagged'
    confidence NUMERIC(4, 3) DEFAULT 0.000,
    investigation JSONB DEFAULT '{}'::jsonb,
    proposed_fix JSONB DEFAULT '{}'::jsonb,
    sandbox_diff JSONB DEFAULT '{}'::jsonb,
    test_results JSONB DEFAULT '{}'::jsonb,
    approval_token VARCHAR(128),
    reply_message TEXT,
    external_message_id VARCHAR(255),
    thread_id VARCHAR(255),
    thread_url TEXT,
    channel_metadata JSONB DEFAULT '{}'::jsonb,
    is_flagged BOOLEAN NOT NULL DEFAULT FALSE,
    flag_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_support_tickets_status ON support_tickets(status);
CREATE INDEX IF NOT EXISTS idx_support_tickets_classification ON support_tickets(classification);
CREATE UNIQUE INDEX IF NOT EXISTS idx_support_tickets_channel_ext_id ON support_tickets(channel, external_message_id) WHERE external_message_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_support_tickets_sender_rate ON support_tickets(channel, sender_id, created_at);

-- 2. Audit Log Table (Tracking all AI & human actions)
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    ticket_id VARCHAR(64) NOT NULL,
    action VARCHAR(64) NOT NULL,
    performed_by VARCHAR(128) NOT NULL DEFAULT 'system_agent',
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    before_counts JSONB DEFAULT '{}'::jsonb,
    after_counts JSONB DEFAULT '{}'::jsonb,
    details JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_audit_log_ticket_id ON audit_log(ticket_id);

-- 3. Sales Sandbox Table (Clone of sales table for isolated previewing)
CREATE TABLE IF NOT EXISTS sales_sandbox (LIKE sales INCLUDING ALL);

-- Grant permissions to sales_readonly where needed
GRANT SELECT ON support_tickets TO sales_readonly;
GRANT SELECT ON audit_log TO sales_readonly;
GRANT SELECT ON sales_sandbox TO sales_readonly;
