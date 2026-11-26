-- =============================================================================
-- Project Init (Codebase RAG) Dedicated Schema
-- Separate from 'public' sales tables; stores AST code chunks, 768-dim
-- embeddings with HNSW index, file tree & imports metadata, summary cache,
-- and skipped-files audit records (strictly without secret values).
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS code_rag;

CREATE TABLE IF NOT EXISTS code_rag.projects (
    name VARCHAR(128) PRIMARY KEY,
    local_path TEXT NOT NULL,
    default_branch VARCHAR(128) DEFAULT 'main',
    last_commit_hash VARCHAR(64),
    last_indexed_at TIMESTAMP WITH TIME ZONE,
    file_count INT NOT NULL DEFAULT 0,
    chunk_count INT NOT NULL DEFAULT 0,
    skipped_count INT NOT NULL DEFAULT 0,
    status VARCHAR(32) NOT NULL DEFAULT 'never_indexed',
    last_error TEXT
);

CREATE TABLE IF NOT EXISTS code_rag.file_metadata (
    id SERIAL PRIMARY KEY,
    project VARCHAR(128) NOT NULL REFERENCES code_rag.projects(name) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    language VARCHAR(32) NOT NULL,
    commit_hash VARCHAR(64),
    content_hash VARCHAR(64) NOT NULL,
    line_count INT NOT NULL DEFAULT 0,
    chunk_count INT NOT NULL DEFAULT 0,
    imports JSONB NOT NULL DEFAULT '[]'::jsonb,
    symbols JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project, file_path)
);
CREATE INDEX IF NOT EXISTS idx_code_file_metadata_project ON code_rag.file_metadata(project);
CREATE INDEX IF NOT EXISTS idx_code_file_metadata_imports ON code_rag.file_metadata USING gin(imports);

CREATE TABLE IF NOT EXISTS code_rag.code_chunks (
    id SERIAL PRIMARY KEY,
    chunk_uid VARCHAR(128) UNIQUE NOT NULL,
    project VARCHAR(128) NOT NULL REFERENCES code_rag.projects(name) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    language VARCHAR(32) NOT NULL,
    symbol_name VARCHAR(255) NOT NULL DEFAULT '',
    chunk_kind VARCHAR(32) NOT NULL DEFAULT 'block',
    start_line INT NOT NULL,
    end_line INT NOT NULL,
    commit_hash VARCHAR(64),
    content_hash VARCHAR(64) NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    search_tsv TSVECTOR GENERATED ALWAYS AS (
        to_tsvector(
            'simple',
            coalesce(file_path, '') || ' ' ||
            coalesce(symbol_name, '') || ' ' ||
            coalesce(summary, '') || ' ' ||
            coalesce(content, '')
        )
    ) STORED,
    embedding VECTOR(768),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_code_chunks_project_file ON code_rag.code_chunks(project, file_path);
CREATE INDEX IF NOT EXISTS idx_code_chunks_symbol ON code_rag.code_chunks(project, symbol_name);
CREATE INDEX IF NOT EXISTS idx_code_chunks_tsv ON code_rag.code_chunks USING gin(search_tsv);
CREATE INDEX IF NOT EXISTS idx_code_chunks_embedding_hnsw
    ON code_rag.code_chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS code_rag.summary_cache (
    content_hash VARCHAR(64) PRIMARY KEY,
    summary TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS code_rag.skipped_files (
    id SERIAL PRIMARY KEY,
    project VARCHAR(128) NOT NULL REFERENCES code_rag.projects(name) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    reason TEXT NOT NULL,
    rule VARCHAR(128) NOT NULL,
    scanned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project, file_path, rule)
);
CREATE INDEX IF NOT EXISTS idx_code_skipped_project ON code_rag.skipped_files(project);

-- Grant read-only SELECT access if sales_readonly role exists
DO
$do$
BEGIN
   IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'sales_readonly') THEN
      GRANT USAGE ON SCHEMA code_rag TO sales_readonly;
      GRANT SELECT ON ALL TABLES IN SCHEMA code_rag TO sales_readonly;
      ALTER DEFAULT PRIVILEGES IN SCHEMA code_rag GRANT SELECT ON TABLES TO sales_readonly;
   END IF;
END
$do$;
