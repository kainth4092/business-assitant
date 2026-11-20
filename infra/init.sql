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
-- 5. Dedicated Read-Only Security Role ('sales_readonly')
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
GRANT SELECT ON TABLE document_embeddings TO sales_readonly;
GRANT SELECT ON TABLE quality_reports TO sales_readonly;
GRANT SELECT ON TABLE conversations TO sales_readonly;
GRANT SELECT ON TABLE messages TO sales_readonly;

-- Explicitly ensure no mutation permissions exist
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON ALL TABLES IN SCHEMA public FROM sales_readonly;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM sales_readonly;

-- Ensure future tables in public schema only grant SELECT to sales_readonly
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO sales_readonly;
