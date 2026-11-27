# Google Cloud Data, AI & Vector Migration Plan (`GCP_MIGRATION_PLAN.md`)

**Architecture Mode**: Hybrid — **Laptop runtime** (Next.js frontend, FastAPI backend, LangGraph agents, MCP server, local PySpark ETL, pytest/Playwright) paired with **GCP cloud data, file, AI, and vector services** (BigQuery, Cloud Storage, Vertex AI Gemini, BigQuery Vector Search). Zero cloud app hosting, Cloud Run, GCE VMs, Cloud SQL, GPUs, or Dataproc clusters.

---

## 1. Current Verified Package & SDK Matrix

Verified against PyPI and official documentation on 2026-11-27:

| Package                  | Version                | Role & Current Pattern                                                                                                                                                                                                                                             |
| :----------------------- | :--------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `google-genai`           | `3.6.1` (installed)    | Unified Gemini SDK; supports `genai.Client(vertexai=True, project=..., location=...)` with Application Default Credentials (`ADC`) and `client.models.generate_content` / `embed_content`. Replaces legacy `vertexai.generative_models`.                           |
| `langchain-google-genai` | `4.5.1` (installed)    | Supports both Developer API and Vertex AI natively via `ChatGoogleGenerativeAI(..., vertexai=True, project=..., location=...)` and `GoogleGenerativeAIEmbeddings(..., vertexai=True, project=..., location=...)`. Replaces deprecated `langchain-google-vertexai`. |
| `google-cloud-bigquery`  | `3.47.0` (PyPI latest) | BigQuery Client (`QueryJobConfig(dry_run=True, use_query_cache=False)`, `maximum_bytes_billed`, parameterized `ScalarQueryParameter`, `load_table_from_uri` for GCS Parquet).                                                                                      |
| `google-cloud-storage`   | `3.17.2` (PyPI latest) | Google Cloud Storage `storage.Client(project=...)` using ADC for `raw/` and `clean/` uploads/downloads.                                                                                                                                                            |
| `google-auth`            | `2.62.2` (installed)   | `google.auth.default()` ADC credential detection & quota project validation without service account key files.                                                                                                                                                     |

**BigQuery Vector Search Pattern (Verified Docs)**:

- Embedding columns stored as `ARRAY<FLOAT64>` (uniform `768` dimensions).
- Accelerated with `CREATE VECTOR INDEX ... ON dataset.table(embedding) OPTIONS(index_type = 'IVF', distance_type = 'COSINE', ivf_options = '{"num_lists": ...}')`.
- Queried with `VECTOR_SEARCH(TABLE ..., 'embedding', (SELECT @query_vec AS embedding), top_k => ..., distance_type => 'COSINE')`.

---

## 2. Inventory of Existing Touchpoints & Target GCP Services

### A. Structured Data & Support Sandbox (PostgreSQL → BigQuery + Local Fallback)

| Current File & Lines                                                                                                                     | Current Dependency                                                                                                         | Target Service (`local` / `gcp`)                                          | What Changes                                                                                                                                                                                                                                                                                                                                                                           |
| :--------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------ | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [mcp_server/tools.py](mcp_server/tools.py) (`query_sales`, `get_data_quality_report`, `get_schema_metadata`)                             | `psycopg2` against `sales`, `quality_reports`, `schema_metadata`                                                           | `SalesStore` (`PostgresSalesStore` / `BigQuerySalesStore`)                | Delegate SQL read-only queries, quality report lookup, and schema metadata inspection to `SalesStore` selected by `STORAGE_BACKEND`. BigQuery enforces dry-run byte estimate, `maximum_bytes_billed`, single `SELECT` validation, `LIMIT 100`, and fixed `BQ_DATASET`.                                                                                                                 |
| [mcp_server/support_tools.py](mcp_server/support_tools.py) (`run_data_quality_checks`, `preview_fix`, `apply_fix`, `get_ticket_context`) | `psycopg2` against `sales`, `sales_sandbox`, `support_tickets`, `audit_log`                                                | `SalesStore` + BigQuery `BQ_SANDBOX_DATASET`                              | Support data previews copy target table into `BQ_SANDBOX_DATASET` when `STORAGE_BACKEND=gcp`; `apply_fix` updates production `BQ_DATASET` table ONLY after human `approval_token` validation. `support_tickets` & `audit_log` remain on local operational Postgres/store (decision recorded in `DECISIONS.md` to guarantee transactional HITL locking & zero-cost local audit trails). |
| [pipelines/clean_sales.py](pipelines/clean_sales.py)                                                                                     | Local CSV read, local Parquet write, Postgres JDBC/psycopg2 `sales`, `quality_reports`, `sales_sandbox`, `schema_metadata` | Local PySpark + `FileStore` (`GCS` `raw/` & `clean/`) + BigQuery Load Job | PySpark stays on laptop (`master="local[*]"`). Reads CSV via `FileStore` (`data/` or `gs://<bucket>/raw/`), writes cleaned Parquet via `FileStore` (`gs://<bucket>/clean/`), loads BigQuery `<dataset>.sales` via `load_table_from_uri` (`SourceFormat.PARQUET`) + mirrors to `BQ_SANDBOX_DATASET`, and writes `quality_reports` + `schema_metadata` rows in BigQuery.                 |
| [backend/main.py](backend/main.py) (`/status`, `/data-quality`, `/sample-questions`, `/upload/csv`)                                      | Direct `psycopg2` queries & `data/` writes                                                                                 | `SalesStore` + `FileStore`                                                | Route telemetry, quality reports, schema inspection, and CSV uploads through active stores; include daily LLM/embedding budget status in `/status`.                                                                                                                                                                                                                                    |
| [backend/agent/nodes.py](backend/agent/nodes.py) (`execute_sql_for_query`)                                                               | Uses PostgreSQL SQL casts (`::numeric`, `\"col\"`)                                                                         | Dialect-aware helper via `STORAGE_BACKEND`                                | Generate Standard SQL compatible with BigQuery (`ROUND(CAST(... AS NUMERIC), 2)` + backticks `` `col` ``) when `STORAGE_BACKEND=gcp`.                                                                                                                                                                                                                                                  |

### B. Vector Embeddings & RAG (pgvector → BigQuery Vector Search + Optional Vertex RAG Flag)

| Current File & Lines                                                                                                     | Current Dependency                                                 | Target Service                                                                          | What Changes                                                                                                                                                                                                                                               |
| :----------------------------------------------------------------------------------------------------------------------- | :----------------------------------------------------------------- | :-------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| [pipelines/ingest_docs.py](pipelines/ingest_docs.py) & [backend/main.py](backend/main.py) (`/upload/documents`)          | `TRUNCATE/INSERT document_embeddings` (`pgvector`) & local `docs/` | `FileStore` + `VectorStore` (`PgVectorStore` / `BigQueryVectorStore`)                   | Upload source docs via `FileStore` (`docs/` or `gs://<bucket>/docs/`), index chunks into `document_embeddings` table (pgvector locally or BigQuery `ARRAY<FLOAT64>` + `VECTOR INDEX` on GCP). Add `DOCUMENT_RAG_BACKEND=default                            | vertex_rag_engine` optional hook (off by default). |
| [backend/rag/retrieval.py](backend/rag/retrieval.py) (`search_documents`, `list_indexed_sources`, `get_document_chunks`) | Raw SQL `<=>` cosine distance on `document_embeddings`             | `VectorStore`                                                                           | Delegate search, source listing, and chunk inspection to active `VectorStore`.                                                                                                                                                                             |
| [project_init/store.py](project_init/store.py) & [project_init/retriever.py](project_init/retriever.py)                  | `PostgresCodeStore` (`code_rag` schema)                            | Local `PostgresCodeStore` or `BigQueryCodeVectorStore` guarded by `cloud_index_allowed` | Keep AST chunking, secret filter, incremental hash/git diff unchanged on laptop. Only route chunks/embeddings to BigQuery + Vertex AI if `cloud_index_allowed: true` in `projects.yaml` (default `false` → stays local Postgres + local/API key fallback). |

### C. LLM & Embeddings (Gemini API Key → Vertex AI via ADC + Daily Budget Guard)

| Current File & Lines                                                                                                | Current Dependency                                 | Target Service                                                   | What Changes                                                                          |
| :------------------------------------------------------------------------------------------------------------------ | :------------------------------------------------- | :--------------------------------------------------------------- | :------------------------------------------------------------------------------------ | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [backend/agent/nodes.py](backend/agent/nodes.py) & [backend/agent/support_nodes.py](backend/agent/support_nodes.py) | `ChatGoogleGenerativeAI(google_api_key=...)`       | `LlmClient` (`vertexai` via ADC or `gemini_api_key`)             | Switch via `LLM_BACKEND=vertexai                                                      | gemini_api | auto`, using `ChatGoogleGenerativeAI(vertexai=True, project=..., location=...)`, exponential backoff retries, timeouts, and daily call/token budget tracking. |
| [backend/rag/embeddings.py](backend/rag/embeddings.py)                                                              | `GoogleGenerativeAIEmbeddings(google_api_key=...)` | `EmbeddingClient` (`vertexai` via ADC or `gemini_api_key`)       | Switch via `EMBEDDING_BACKEND=vertexai                                                | gemini_api | auto`, enforcing `768` dimensions, retry/backoff, and budget accounting.                                                                                      |
| [project_init/summarizer.py](project_init/summarizer.py) & [project_init/retriever.py](project_init/retriever.py)   | `get_llm()` & `get_text_embedding()`               | `LlmClient` / `EmbeddingClient` respecting `cloud_index_allowed` | Refuse Vertex AI / cloud embedding calls if project has `cloud_index_allowed: false`. |

### D. Environment Configuration (`.env.example` Additions)

- `GCP_PROJECT_ID`, `GCP_REGION` (default `us-central1`), `GCP_MULTI_REGION` (`US`)
- `STORAGE_BACKEND=local|gcp`
- `VECTOR_BACKEND=local|gcp`
- `FILE_STORE_BACKEND=local|gcp`
- `LLM_BACKEND=auto|vertexai|gemini_api`
- `EMBEDDING_BACKEND=auto|vertexai|gemini_api`
- `DOCUMENT_RAG_BACKEND=default|vertex_rag_engine`
- `GCS_BUCKET`, `BQ_DATASET=fixdesk`, `BQ_SANDBOX_DATASET=fixdesk_sandbox`, `BQ_VECTOR_DATASET=fixdesk_vectors`
- `BQ_MAX_BYTES_BILLED=104857600` (100 MB safety cap per query)
- `AI_DAILY_REQUEST_LIMIT=500`, `AI_DAILY_TOKEN_LIMIT=500000`, `AI_BUDGET_WARN_RATIO=0.8`

---

## 3. Core Architecture & Interfaces (`backend/cloud/`)

1. **`backend/cloud/interfaces.py`**: Clean ABCs / Protocols for `SalesStore`, `VectorStore`, `FileStore`, `LlmClient`, `EmbeddingClient`.
2. **`backend/cloud/auth.py`**: ADC loader (`google.auth.default()`), explicit error remediation when ADC, `GCP_PROJECT_ID`, or billing is missing; blocks service account key file usage cleanly.
3. **`backend/cloud/budget.py`**: Thread-safe daily request & estimated token counter (persisted lightly in local JSON state under `data/.budget_state.json`), warning thresholds surfaced in `GET /status` and rendered as a subtle amber/seal banner in `WorkbenchApp.jsx`.
4. **`backend/cloud/local_impl.py` & `backend/cloud/gcp_*.py`**: Drop-in local & GCP adapters for every interface + factory selectors (`get_sales_store()`, `get_vector_store()`, `get_file_store()`, `get_llm_client()`, `get_embedding_client()`).

---

## 4. Implementation Stages Checklist

1. **Stage 1**: Dependency verification & install (`google-cloud-bigquery`, `google-cloud-storage`), `backend/cloud/` interfaces & factories (`local` adapters wrapping existing behavior with zero regressions).
2. **Stage 2**: ADC-only GCP auth module + least-privilege IAM documentation.
3. **Stage 3**: GCS `FileStore` (`raw/`, `clean/`, `docs/` prefixes in US bucket) + local `FileStore`.
4. **Stage 4**: PySpark ETL updated cleanly for local/GCS CSV input, GCS Parquet output, BigQuery load job + metadata/quality tables (no Dataproc).
5. **Stage 5**: BigQuery `SalesStore` (dry run, `maximum_bytes_billed`, single `SELECT`, `LIMIT 100`) + `BQ_SANDBOX_DATASET` Support Desk sandbox isolation + human approval gate.
6. **Stage 6**: Vertex AI `LlmClient` & `EmbeddingClient` via ADC + retry/backoff/timeouts + daily budget tracker + UI warning badge/banner.
7. **Stage 7**: BigQuery `VectorStore` (`ARRAY<FLOAT64>` + `VECTOR INDEX` + `VECTOR_SEARCH`) for docs RAG & code RAG + optional `DOCUMENT_RAG_BACKEND` flag.
8. **Stage 8**: `projects.yaml` `cloud_index_allowed: false` privacy guard + secret-never-reaches-cloud tests.
9. **Stage 9**: Print-only cost safety guards, `CLEANUP.md`, `scripts/gcp_inventory.py`, `COST_NOTES.md`.
10. **Stage 10**: `scripts/gcp_setup.md` + print-only setup generator, update `.env.example`, `USAGE.md`, `ARCHITECTURE.md`, `EXPLAIN.md`, `INTERVIEW_QA.md` (10 GCP Q&As).
11. **Stage 11**: Contract tests (same suite run against local & GCP implementations/fakes), SQL/cost safety tests, privacy tests, full pytest + frontend build + Playwright suite.
12. **Stage 12**: Live GCP verification if ADC & billing exist; otherwise record honest blocked instructions in `BLOCKED.md` and `MIGRATION_REPORT.md`.
