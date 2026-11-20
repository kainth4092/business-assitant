# Audit Report: Business Assistant Hardcoded & Mock Data Audit

This audit document identifies all static, hardcoded, mock, dummy, and fallback data across the entire repository (`frontend`, `backend`, `mcp_server`, `pipelines`, and `infra`). It defines the exact real data sources that replace each finding.

---

## 1. Frontend Audit Findings

### 1.1 `frontend/app/page.jsx`
- **Line 358**: `#RUN-8842` hardcoded run identifier in the header telemetry breadcrumb.
  - *Current*: `<span className="...">#RUN-8842</span>`
  - *Real Data Source*: Dynamic run/session identifier generated from `thread_id` or backend `/status` system telemetry.
- **Lines 144-150**: `pendingTicketsCount` only fetched once on initial mount and tab change.
  - *Current*: Polled only on manual clicks; default count 0.
  - *Real Data Source*: Real count from `GET /support/tickets` and `GET /status`.
- **Lines 275-284**: Session log history only tracks in-memory component state and gets wiped on refresh.
  - *Current*: `messages.filter(m => m.role === 'user')` stored in React `useState`.
  - *Real Data Source*: PostgreSQL `conversations` and `messages` tables via `GET /conversations` and `GET /conversations/{id}`.

### 1.2 `frontend/components/EmptyState.jsx`
- **Lines 8-44**: `STARTERS` array with 5 completely hardcoded questions and descriptions.
  - *Current*: Static list of questions ("What are the top 5 item types by total outlet sales?", "Which outlet has the highest average item sales?", etc.).
  - *Real Data Source*: Dynamic endpoint `GET /sample-questions` that queries PostgreSQL `sales` for top categories/outlets and `document_embeddings` for ingested document titles.
- **Line 47**: `const salesCount = systemHealth?.sales_records ?? 1500;`
  - *Current*: Hardcoded fallback `1500`.
  - *Real Data Source*: Live count from `GET /status` (`sales_records`). If loading/error, show loading skeleton or error state; never fallback to `1500`.
- **Line 48**: `const chunksCount = systemHealth?.indexed_chunks ?? 21;`
  - *Current*: Hardcoded fallback `21`.
  - *Real Data Source*: Live count from `GET /status` (`indexed_chunks`). If loading/error, show loading skeleton or error state; never fallback to `21`.
- **Line 92**: `value={3}`, `label="MCP Tools Suite"`
  - *Current*: Hardcoded number `3`.
  - *Real Data Source*: Real count of registered tools from `GET /status` (`tools_count` or `tools.length`).

### 1.3 `frontend/components/DataQualityView.jsx`
- **Line 48**: `const rawRows = profile.raw_total_rows || 1530;`
  - *Current*: Hardcoded fallback `1530`.
  - *Real Data Source*: `report.records_profile.raw_total_rows` fetched live from `GET /data-quality` (from database table `quality_reports`).
- **Line 49**: `const cleanedRows = profile.cleaned_total_rows || 1500;`
  - *Current*: Hardcoded fallback `1500`.
  - *Real Data Source*: `report.records_profile.cleaned_total_rows` from `GET /data-quality`.
- **Line 50**: `const dupsRemoved = profile.duplicate_rows_removed || 30;`
  - *Current*: Hardcoded fallback `30`.
  - *Real Data Source*: `report.records_profile.duplicate_rows_removed` from `GET /data-quality`.
- **Line 52**: `const weightNullBefore = nulls.Item_Weight_nulls_before ?? 245;`
  - *Current*: Hardcoded fallback `245`.
  - *Real Data Source*: `report.null_imputation_summary.Item_Weight_nulls_before` from `GET /data-quality`.
- **Line 54**: `const sizeNullBefore = nulls.Outlet_Size_nulls_before ?? 410;`
  - *Current*: Hardcoded fallback `410`.
  - *Real Data Source*: `report.null_imputation_summary.Outlet_Size_nulls_before` from `GET /data-quality`.
- **Line 90-93**: `rule: "Vector Normalization & 1536-Dim Invariant", scope: "21 chunks indexed"`
  - *Current*: Hardcoded string `"21 chunks indexed"` and `"1536-Dim"`.
  - *Real Data Source*: Live chunk count from `GET /status` (`indexed_chunks`) and embedding dimension (`768-Dim`).
- **Line 154**: `METRIC-SET #402`
  - *Current*: Hardcoded string `METRIC-SET #402`.
  - *Real Data Source*: Report execution ID / timestamp from `GET /data-quality` (`report_id` or `timestamp`).
- **Line 188**: `96%` hardcoded radial integrity metric.
  - *Current*: Static `96%`.
  - *Real Data Source*: Computed score based on `(cleaned_rows / raw_rows) * 100` and pass rate of checks in `report`.
- **Line 208**: `<span className="...">100% resolved</span>`
  - *Current*: Hardcoded string.
  - *Real Data Source*: Computed resolution rate `((null_before - null_after) / null_before) * 100`.
- **Line 212**: `<span className="...">0 FAULT</span>`
  - *Current*: Hardcoded string.
  - *Real Data Source*: Actual count of check violations.
- **Line 222**: `<span className="...">99.98% PASS</span>`
  - *Current*: Hardcoded string.
  - *Real Data Source*: Live database vector integrity check status.
- **Line 261**: `<span className="...">5 Classes &rarr; 2 Canonical</span>`
  - *Current*: Hardcoded string.
  - *Real Data Source*: `report.categorical_cleanup_summary.Item_Fat_Content_classes_before` and `classes_after`.
- **Line 274**: `<span className="...">SPARK 3.5</span>`
  - *Current*: Hardcoded string.
  - *Real Data Source*: Engine metadata from `GET /status` or `GET /data-quality`.
- **Lines 294-296**: `21 HNSW vectors`
  - *Current*: Hardcoded `21`.
  - *Real Data Source*: Live count from `GET /status` (`indexed_chunks`).

### 1.4 `frontend/components/DocumentsView.jsx`
- **Lines 37-75**: `getDocDescription` and `getSampleQuestion` with hardcoded switch cases for 5 file names.
  - *Current*: Switch case checking `return_policy`, `promotions`, `outlet_guidelines`, etc.
  - *Real Data Source*: Dynamic first heading / summary and sample prompt extracted from real markdown content stored in PostgreSQL `document_embeddings`.
- **Line 111**: `value={documents?.length || 5}`
  - *Current*: Hardcoded fallback `5`.
  - *Real Data Source*: `documents.length` from `GET /documents`.
- **Line 118**: `value={totalChunks || 21}`
  - *Current*: Hardcoded fallback `21`.
  - *Real Data Source*: Computed sum of `total_chunks` across documents from `GET /documents`.
- **Line 135**: `badge="1536-D"`
  - *Current*: Hardcoded `1536-D`.
  - *Real Data Source*: Dynamic embedding dimension from `GET /status` (`embedding_dimension`, e.g. `768-D`).

### 1.5 `frontend/components/Sidebar.jsx`
- **Line 50**: `count: systemHealth?.indexed_chunks ? `${systemHealth.indexed_chunks}` : "21"`
  - *Current*: Fallback `"21"`.
  - *Real Data Source*: Live count from `GET /status`.
- **Lines 275-309**: `Session Log` only reading from current session memory.
  - *Current*: Ephemeral in-memory questions.
  - *Real Data Source*: `GET /conversations` from PostgreSQL.

### 1.6 `frontend/components/EvidencePanel.jsx`
- **Line 201**: `<SqlBlock sql={...} executionTime="14.2ms" />`
  - *Current*: Hardcoded execution time `14.2ms`.
  - *Real Data Source*: Real query latency recorded in `trace.execution_time_ms` or `trace.latency`.
- **Line 235**: `const score = doc.score || doc.similarity || 0.89;`
  - *Current*: Hardcoded fallback similarity score `0.89`.
  - *Real Data Source*: Actual cosine similarity returned by pgvector (`doc.similarity`).
- **Line 253**: `doc.content || ... || "Relevant operational text excerpt..."`
  - *Current*: Fallback placeholder string.
  - *Real Data Source*: Actual content chunk from PostgreSQL.

### 1.7 `frontend/components/SupportDeskView.jsx`
- **Lines 34-59**: `PRESET_CLIENT_MESSAGES` contains static messages and names ("Alex Chen", "David Miller", "Elena Rostova").
  - *Current*: Hardcoded client personas and messages.
  - *Real Data Source*: Real client problems generated from current database diagnostics (e.g., detected inconsistent fat labels in `sales` or real pricing rules in `docs`).
- **Line 237**: `#SUP-8921`
  - *Current*: Hardcoded string.
  - *Real Data Source*: Real selected ticket ID or queue sequence.
- **Line 293-294**: `Autonomous Fix Rate 91.4%` and `+4.2%`
  - *Current*: Hardcoded `91.4%` and `+4.2%`.
  - *Real Data Source*: Computed rate from `tickets.filter(t => t.status === 'done').length / tickets.length`.
- **Line 306**: `Sandbox Latency 1.8s`
  - *Current*: Hardcoded `1.8s`.
  - *Real Data Source*: Real sandbox dry run execution time from `ticket.sandbox_diff.execution_time` or average of audit log timestamps.

### 1.8 `frontend/components/TicketDetail.jsx`
- **Line 103**: `Confidence: {Math.round((ticket.confidence || 0.98) * 100)}%`
  - *Current*: Fallback `0.98`.
  - *Real Data Source*: Real classifier confidence score from `support_graph` classifier node (`ticket.confidence`).
- **Lines 128-163**: Static step subtitle badges (`100% Match`, `Schema isolated`, `Diff generated`, `Tests pass`).
  - *Current*: Hardcoded static step descriptions regardless of ticket status.
  - *Real Data Source*: Dynamic status indicators based on `ticket.status` and `ticket.audit_trail`.
- **Line 329**: `Audit Token: #SEC-9842`
  - *Current*: Hardcoded token `#SEC-9842`.
  - *Real Data Source*: Real `ticket.approval_token`.

---

## 2. Backend & MCP Server Audit Findings

### 2.1 `backend/main.py`
- Missing `GET /status`: Currently only has `/health`. Need full `/status` returning PostgreSQL connection, sales row count, document chunk count, available MCP tools list, model name, and embedding dimension.
- Missing `GET /documents`: Ingestion document list currently only on `/sources`. Need `/documents` and `/documents/{id}/chunks` to retrieve all chunks for any document.
- Missing `GET /conversations` and `GET /conversations/{id}`: Chat history is not persisted into PostgreSQL; only kept in ephemeral memory.
- Missing `GET /sample-questions`: Starter questions are hardcoded in `EmptyState.jsx`. Need dynamic generation based on real database records and vectorized document titles.
- `GET /data-quality`: Only reads from a local JSON file `data/data_quality_report.json`. Needs to read from a persistent PostgreSQL `quality_reports` table populated by the PySpark pipeline.

### 2.2 `backend/rag/embeddings.py`
- **Lines 4, 60, 89**: References to "mock mode" and fallback embedding generation.
  - *Current*: Deterministic pseudo-embedding generator when API key is missing.
  - *Real Data Source*: Real Gemini API `text-embedding-004` embeddings. Cleanly fail or raise if key is absent during ingestion rather than silently generating pseudo-vectors.

### 2.3 `backend/agent/nodes.py`
- **Line 33**: `not key.startswith("mock_")`
  - *Action*: Ensure all agent reasoning and routing execute through real Gemini API or transparently report error state if offline.

### 2.4 `infra/init.sql` & `infra/support_schema.sql`
- Need `quality_reports` table to store real before/after PySpark audit reports in PostgreSQL.
- Need `conversations` and `messages` tables to persist chat history, traces, SQL queries, and sources.
- In `infra/support_schema.sql`: Contains seeded demo rows with hardcoded IDs (`FDA15_MESSY`, `DRC01_MESSY`, etc.). These should be cleanly integrated into the initial BigMart Sales data or generated via the pipeline with realistic messy attributes, rather than ad-hoc SQL script injections.

### 2.5 `pipelines/clean_sales.py`
- Does not persist the quality report into PostgreSQL `quality_reports` table; only writes to `data/data_quality_report.json`.
  - *Action*: Insert the full report JSON into PostgreSQL table `quality_reports` upon ETL completion.

### 2.6 `pipelines/ingest_docs.py`
- **Lines 28-34**: `COMPANY_DOCS` list is hardcoded to 5 specific filenames.
  - *Action*: Dynamically scan `docs/*.md` and `docs/*.txt` so any files added to `/docs` are automatically chunked and ingested.

---

## 3. Real Data Architecture Plan

| Feature / UI Component | Real Data Source | Endpoint / Storage |
|---|---|---|
| Sales Row Count | `SELECT count(*) FROM sales` | `GET /status` |
| Vector Chunks Count | `SELECT count(*) FROM document_embeddings` | `GET /status`, `GET /documents` |
| Available MCP Tools | Introspected from MCP server instance | `GET /status` |
| LLM & Embedding Models | Configured environment variables | `GET /status` |
| Starter Questions | `SELECT DISTINCT item_type FROM sales`, `SELECT DISTINCT outlet_type FROM sales`, `SELECT DISTINCT title FROM document_embeddings` | `GET /sample-questions` |
| Document Catalog & Chunks | `document_embeddings` table grouped by `source_file` | `GET /documents`, `GET /documents/{id}/chunks` |
| Data Quality Report | PySpark audit metrics persisted to PostgreSQL | `GET /data-quality` (table `quality_reports`) |
| Invariant Verification Table | Dynamic evaluations of nulls, duplicates, label domain, and bounds | `GET /data-quality` |
| Chat History & Session Log | PostgreSQL `conversations` & `messages` tables | `GET /conversations`, `GET /conversations/{id}` |
| Evidence & Traces | Recorded in `messages.trace` column | `GET /conversations/{id}` & `/chat` response |
| Support Desk Backlog | PostgreSQL `support_tickets` table | `GET /support/tickets` |
| Support Desk Detail & Audit | PostgreSQL `support_tickets` & `audit_log` tables | `GET /support/tickets/{id}` |
| Single Setup Script | `scripts/setup.sh` / `Makefile` | Automates DB init, PySpark ETL, doc ingestion, and table population |
