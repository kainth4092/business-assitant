-- =============================================================================
-- Support Desk Schema & Demo Problem Seeding
-- =============================================================================

-- 1. Support Tickets Table
CREATE TABLE IF NOT EXISTS support_tickets (
    id VARCHAR(64) PRIMARY KEY,
    client_name VARCHAR(128) NOT NULL DEFAULT 'Client User',
    client_email VARCHAR(128) NOT NULL DEFAULT 'client@example.com',
    channel VARCHAR(64) NOT NULL DEFAULT 'webhook',
    message TEXT NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'new', -- 'new', 'investigating', 'fix_ready', 'approved', 'done', 'rejected'
    classification VARCHAR(32), -- 'data_issue', 'code_bug', 'question', 'feature_request'
    confidence NUMERIC(4, 3) DEFAULT 0.000,
    investigation JSONB DEFAULT '{}'::jsonb,
    proposed_fix JSONB DEFAULT '{}'::jsonb,
    sandbox_diff JSONB DEFAULT '{}'::jsonb,
    test_results JSONB DEFAULT '{}'::jsonb,
    approval_token VARCHAR(128),
    reply_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_support_tickets_status ON support_tickets(status);
CREATE INDEX IF NOT EXISTS idx_support_tickets_classification ON support_tickets(classification);

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

-- Populate sandbox if empty
INSERT INTO sales_sandbox
SELECT * FROM sales
WHERE NOT EXISTS (SELECT 1 FROM sales_sandbox LIMIT 1);

-- 4. Seed intentional messy data in sales table to be diagnosed
INSERT INTO sales (item_identifier, item_weight, item_fat_content, item_visibility, item_type, item_mrp, outlet_identifier, outlet_establishment_year, outlet_size, outlet_location_type, outlet_type, item_outlet_sales)
SELECT 'FDA15_MESSY', NULL, 'LF', 0.016, 'Dairy', 249.8, 'OUT049', 1999, 'Medium', 'Tier 1', 'Supermarket Type1', 3735.1
WHERE NOT EXISTS (SELECT 1 FROM sales WHERE item_identifier = 'FDA15_MESSY');

INSERT INTO sales (item_identifier, item_weight, item_fat_content, item_visibility, item_type, item_mrp, outlet_identifier, outlet_establishment_year, outlet_size, outlet_location_type, outlet_type, item_outlet_sales)
SELECT 'DRC01_MESSY', 5.92, 'low fat', 0.019, 'Soft Drinks', 48.3, 'OUT018', 2009, 'Medium', 'Tier 3', 'Supermarket Type2', 443.4
WHERE NOT EXISTS (SELECT 1 FROM sales WHERE item_identifier = 'DRC01_MESSY');

INSERT INTO sales (item_identifier, item_weight, item_fat_content, item_visibility, item_type, item_mrp, outlet_identifier, outlet_establishment_year, outlet_size, outlet_location_type, outlet_type, item_outlet_sales)
SELECT 'FDN15_MESSY', NULL, 'reg', 0.072, 'Meat', 117.7, 'OUT010', 1998, NULL, 'Tier 3', 'Grocery Store', 140.2
WHERE NOT EXISTS (SELECT 1 FROM sales WHERE item_identifier = 'FDN15_MESSY');

INSERT INTO sales (item_identifier, item_weight, item_fat_content, item_visibility, item_type, item_mrp, outlet_identifier, outlet_establishment_year, outlet_size, outlet_location_type, outlet_type, item_outlet_sales)
SELECT 'FDX07_MESSY', 19.2, 'Low Fat', 0.021, 'Canned', 182.1, 'OUT013', 1987, 'High', 'Tier 3', 'Supermarket Type1', 2148.7
WHERE NOT EXISTS (SELECT 1 FROM sales WHERE item_identifier = 'FDX07_MESSY');

INSERT INTO sales (item_identifier, item_weight, item_fat_content, item_visibility, item_type, item_mrp, outlet_identifier, outlet_establishment_year, outlet_size, outlet_location_type, outlet_type, item_outlet_sales)
SELECT 'FDP10_MESSY', NULL, 'LF', 0.045, 'Snack Foods', 104.9, 'OUT027', 1985, 'Medium', 'Tier 3', 'Supermarket Type3', 2764.4
WHERE NOT EXISTS (SELECT 1 FROM sales WHERE item_identifier = 'FDP10_MESSY');

-- Also sync messy rows into sales_sandbox so tests have identical initial baseline
TRUNCATE TABLE sales_sandbox;
INSERT INTO sales_sandbox SELECT * FROM sales;

-- Grant permissions to sales_readonly where needed
GRANT SELECT ON support_tickets TO sales_readonly;
GRANT SELECT ON audit_log TO sales_readonly;
GRANT SELECT ON sales_sandbox TO sales_readonly;
