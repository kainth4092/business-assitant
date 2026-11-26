-- =============================================================================
-- Database Initialization Script for Business Assistant
-- Initializes schema for sales data, pgvector document embeddings,
-- and configures the dedicated read-only role 'sales_readonly'.
-- =============================================================================

-- Enable required PostgreSQL extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- -----------------------------------------------------------------------------
-- 1. Sales Table (stores cleaned BigMart sales dataset from PySpark pipeline)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sales (
    id SERIAL PRIMARY KEY,
    item_identifier VARCHAR(50) NOT NULL,
    item_weight NUMERIC(10, 4),
    item_fat_content VARCHAR(50) NOT NULL,
    item_visibility NUMERIC(10, 6),
    item_type VARCHAR(100) NOT NULL,
    item_mrp NUMERIC(10, 4) NOT NULL,
    outlet_identifier VARCHAR(50) NOT NULL,
    outlet_establishment_year INT NOT NULL,
    outlet_size VARCHAR(50),
    outlet_location_type VARCHAR(50) NOT NULL,
    outlet_type VARCHAR(100) NOT NULL,
    item_outlet_sales NUMERIC(12, 4) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for high-frequency queries
CREATE INDEX IF NOT EXISTS idx_sales_item_identifier ON sales(item_identifier);
CREATE INDEX IF NOT EXISTS idx_sales_outlet_identifier ON sales(outlet_identifier);
CREATE INDEX IF NOT EXISTS idx_sales_item_type ON sales(item_type);
CREATE INDEX IF NOT EXISTS idx_sales_outlet_type ON sales(outlet_type);
CREATE INDEX IF NOT EXISTS idx_sales_fat_content ON sales(item_fat_content);

-- -----------------------------------------------------------------------------
-- 2. Document Embeddings Table (stores RAG chunks + 768-dim vector embeddings)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS document_embeddings (
    id SERIAL PRIMARY KEY,
    chunk_id VARCHAR(100) UNIQUE NOT NULL,
    source_file VARCHAR(255) NOT NULL,
    title VARCHAR(255),
    content TEXT NOT NULL,
    chunk_index INT NOT NULL,
    total_chunks INT NOT NULL,
    embedding vector(768),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Metadata and vector index for cosine distance search (<=>)
CREATE INDEX IF NOT EXISTS idx_doc_embed_source_file ON document_embeddings(source_file);

-- -----------------------------------------------------------------------------
-- 3. Data Quality Reports Table (stores PySpark ETL audit summaries)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS quality_reports (
    id SERIAL PRIMARY KEY,
    report_id VARCHAR(64) UNIQUE NOT NULL,
    raw_rows INT NOT NULL,
    cleaned_rows INT NOT NULL,
    duplicates_removed INT NOT NULL,
    report_data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_quality_reports_created ON quality_reports(created_at DESC);

-- -----------------------------------------------------------------------------
-- 4. Conversation History & Message Persistence
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS conversations (
    id VARCHAR(64) PRIMARY KEY,
    title VARCHAR(255) NOT NULL DEFAULT 'New Conversation',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id VARCHAR(64) PRIMARY KEY,
    conversation_id VARCHAR(64) REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(32) NOT NULL, -- 'user', 'assistant'
    content TEXT NOT NULL,
    tools_used JSONB DEFAULT '[]'::jsonb,
    sources JSONB DEFAULT '[]'::jsonb,
    trace JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);

-- -----------------------------------------------------------------------------
-- 5. Support Tickets & Audit Log
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS support_tickets (
    id VARCHAR(64) PRIMARY KEY,
    client_name VARCHAR(128) NOT NULL DEFAULT 'Client User',
    client_email VARCHAR(128) NOT NULL DEFAULT 'client@example.com',
    sender_id VARCHAR(128),
    channel VARCHAR(64) NOT NULL DEFAULT 'webhook',
    message TEXT NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'new',
    classification VARCHAR(32),
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
CREATE UNIQUE INDEX IF NOT EXISTS idx_support_tickets_channel_ext_id ON support_tickets(channel, external_message_id) WHERE external_message_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_support_tickets_sender_rate ON support_tickets(channel, sender_id, created_at);

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

CREATE TABLE IF NOT EXISTS sales_sandbox (LIKE sales INCLUDING ALL);

-- -----------------------------------------------------------------------------
-- 6. Schema Metadata Table (stores dynamic schema & data dictionary)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_metadata (
    id SERIAL PRIMARY KEY,
    dataset_name VARCHAR(255) NOT NULL,
    table_name VARCHAR(255) NOT NULL DEFAULT 'sales',
    row_count INT NOT NULL DEFAULT 0,
    column_count INT NOT NULL DEFAULT 0,
    columns_info JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_schema_metadata_dataset ON schema_metadata(dataset_name);

-- -----------------------------------------------------------------------------
-- 7. Dedicated Read-Only Security Role ('sales_readonly')
-- -----------------------------------------------------------------------------
-- Create the role safely if it does not already exist
DO
$do$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles
      WHERE  rolname = 'sales_readonly') THEN
      CREATE ROLE sales_readonly WITH LOGIN PASSWORD 'readonly_password';
   END IF;
END
$do$;

-- Connection & schema permissions
GRANT CONNECT ON DATABASE business_assistant TO sales_readonly;
GRANT USAGE ON SCHEMA public TO sales_readonly;

-- Grant SELECT on tables to sales_readonly
GRANT SELECT ON TABLE sales TO sales_readonly;
GRANT SELECT ON TABLE sales_sandbox TO sales_readonly;
GRANT SELECT ON TABLE document_embeddings TO sales_readonly;
GRANT SELECT ON TABLE quality_reports TO sales_readonly;
GRANT SELECT ON TABLE conversations TO sales_readonly;
GRANT SELECT ON TABLE messages TO sales_readonly;
GRANT SELECT ON TABLE support_tickets TO sales_readonly;
GRANT SELECT ON TABLE audit_log TO sales_readonly;
GRANT SELECT ON TABLE schema_metadata TO sales_readonly;

-- Explicitly ensure no mutation permissions exist
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON ALL TABLES IN SCHEMA public FROM sales_readonly;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM sales_readonly;

-- Ensure future tables in public schema only grant SELECT to sales_readonly
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO sales_readonly;
