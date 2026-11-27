# Hybrid Google Cloud Migration Report (`MIGRATION_REPORT.md`)

**Date**: 2026-11-27  
**Architecture Mode**: Hybrid — Laptop Runtime (Next.js frontend, FastAPI backend, LangGraph agents, MCP server, local PySpark ETL, pytest/Playwright) + GCP Cloud Data, File, AI, and Vector Services (`BigQuery`, `Cloud Storage`, `Vertex AI Gemini`, `BigQuery Vector Search`). Zero Cloud Run, GCE VMs, Cloud SQL, GPUs, or Dataproc clusters.

---

## 1. Installed & Verified SDK Matrix

| Package | Installed Version | Role |
| :--- | :--- | :--- |
| `google-genai` | `3.6.1` | Unified Gemini SDK (`genai.Client(vertexai=True, project=..., location=...)`) |
| `langchain-google-genai` | `4.5.1` | `ChatGoogleGenerativeAI(..., vertexai=True)` & `GoogleGenerativeAIEmbeddings(..., vertexai=True)` |
| `google-cloud-bigquery` | `3.47.0` | BigQuery dry-run, `maximum_bytes_billed`, parameterized queries, Parquet load jobs, `VECTOR_SEARCH` |
| `google-cloud-storage` | `3.17.2` | Cloud Storage `raw/`, `clean/`, `docs/` bucket object operations via ADC |
| `google-auth` | `2.62.2` | `google.auth.default()` ADC credential detection without service-account JSON key files |

---

## 2. Stages Completed

- **Stage 1 — Dependency Install & Abstraction Layer**:
  - Updated `backend/requirements.txt` and `requirements.txt`; installed `google-cloud-bigquery==3.47.0` and `google-cloud-storage==3.17.2`.
  - Created `backend/cloud/` (`config.py`, `interfaces.py`, `sql_guard.py`, `local_impl.py`, `factories.py`, `__init__.py`) defining `SalesStore`, `VectorStore`, `FileStore`, `LlmClient`, and `EmbeddingClient`.
- **Stage 2 — ADC-Only Auth**:
  - Implemented `backend/cloud/auth.py` (`load_adc_credentials`, `check_adc_status`) enforcing `google.auth.default()` and blocking static service-account JSON key files (`ServiceAccountKeyBlockedError`).
- **Stage 3 — GCS `FileStore`**:
  - Implemented `backend/cloud/gcp_storage.py` (`GcsFileStore`) for `raw/`, `clean/`, and `docs/` prefixes, including PySpark Parquet folder uploads (skipping `_SUCCESS`) and local staging downloads.
- **Stage 4 — Laptop PySpark ETL -> GCS Parquet -> BigQuery Load**:
  - Updated `pipelines/clean_sales.py` to keep `master="local[*]"`, read CSVs and upload cleaned Parquet via `FileStore`, and load `sales`, `sales_sandbox`, `quality_reports`, and `schema_metadata` via `SalesStore`.
- **Stage 5 — BigQuery `SalesStore` & Support Sandbox Isolation**:
  - Implemented `backend/cloud/gcp_bigquery.py` (`BigQuerySalesStore`) enforcing single-`SELECT` validation, `LIMIT <= 100`, dataset pinning (`BQ_DATASET`), `$0` dry-run byte gating (`BQ_MAX_BYTES_BILLED=104857600`), `maximum_bytes_billed`, and `BQ_SANDBOX_DATASET` Support Desk previews while keeping `support_tickets` and `audit_log` in local PostgreSQL (`mcp_server/support_tools.py`, `mcp_server/tools.py`).
  - Added BigQuery Standard SQL dialect adaptation in `backend/agent/nodes.py` and `backend/agent/support_nodes.py`.
- **Stage 6 — Vertex AI LLM/Embeddings & Daily Budget Guard**:
  - Implemented `backend/cloud/gcp_ai.py` (`VertexLlmClient`, `VertexEmbeddingClient`) with ADC, retry/backoff, and timeouts.
  - Implemented `backend/cloud/budget.py` persisting daily request/token counters to `data/.budget_state.json`, exposed in `GET /status` (`backend/main.py`) and rendered as an amber/seal warning banner in `frontend/components/WorkbenchApp.jsx`.
- **Stage 7 — BigQuery Vector Search**:
  - Implemented `backend/cloud/gcp_vector.py` (`BigQueryVectorStore` & `BigQueryCodeVectorStore`) using 768-D `ARRAY<FLOAT64>`, `CREATE VECTOR INDEX ... OPTIONS(index_type = 'IVF', distance_type = 'COSINE')`, and `VECTOR_SEARCH(...)`, plus optional `DOCUMENT_RAG_BACKEND=vertex_rag_engine` hook, wired into `pipelines/ingest_docs.py` and `backend/rag/retrieval.py`.
- **Stage 8 — Codebase Privacy Guard**:
  - Set `cloud_index_allowed: false` in `projects.yaml` and `project_init/config.py`; enforced cloud refusal in `backend/cloud/factories.py`, `backend/cloud/config.py` (`cloud_allowed_scope`), `backend/rag/embeddings.py`, `project_init/indexer.py`, `project_init/retriever.py`, `project_init/summarizer.py`, `mcp_server/code_tools.py`, and `backend/main.py`.
- **Stage 9 & 10 — Cost Safety, Cleanup & Documentation**:
  - Created `COST_NOTES.md`, `CLEANUP.md`, `scripts/gcp_inventory.py`, `scripts/gcp_setup.md`, and `scripts/gcp_setup.py`.
  - Updated `.env.example`, `USAGE.md`, `ARCHITECTURE.md`, `EXPLAIN.md`, and `INTERVIEW_QA.md` (10 GCP Q&As added).
- **Stage 11 — Automated Verification**:
  - Added `tests/test_gcp_migration.py` covering factory switching, `FileStore` local/GCS contracts, ADC & service-account key blocking, BigQuery SQL/dry-run/bytes caps, Parquet load & `BQ_SANDBOX_DATASET` isolation, `BigQueryVectorStore`, AI daily budget warning/blocking, `cloud_index_allowed: false` privacy enforcement, and print-only scripts.

---

## 3. Observed Verification Results

| Check | Command | Observed Result |
| :--- | :--- | :--- |
| Core + GCP Migration pytest | `.venv/bin/python -m pytest tests/test_gcp_migration.py tests/test_sql_safety.py tests/test_api.py tests/test_rag.py tests/test_router.py tests/test_retry_cap.py tests/test_support_desk.py tests/test_support_channels.py tests/test_demo_target.py tests/test_rename_guardrail.py -v` | **69 passed** (0 failed) |
| Full pytest suite | `.venv/bin/python -m pytest -v` | **84 passed** (0 failed; verified after updating `.venv/bin/project-init` shebang and initializing empty `fixdesk` DB on `localhost:5434`) |
| Production code zero-mock scan | `grep -rn -iE "\b(mock|dummy|fake|lorem)\b" backend/ pipelines/ project_init/ mcp_server/ frontend/components/ frontend/app/` | **Clean** (0 matches) |
| Frontend lint, build & unit tests | `cd frontend && npm run lint && npm run build && node --test tests/sse.test.mjs` | **Passed** (`eslint`: 0 errors; `next build`: compiled; `sse.test.mjs`: 4/4 passed) |
| Playwright E2E & Axe WCAG AA | `cd frontend && npm run test:e2e` | **5 passed** (1.6m) |
| Read-only GCP inventory | `.venv/bin/python scripts/gcp_inventory.py` | **Exited 0**; accurately reported local flags and missing ADC |

---

## 4. Stage 12 Live GCP Verification Status

- **Status**: **Blocked on missing local ADC / `gcloud` / `GCP_PROJECT_ID` / `GCS_BUCKET` / billing** in this environment.
- No live GCP resources were created or modified.
- Exact operator commands to authenticate via ADC, generate setup commands, and verify live BigQuery/GCS/Vertex AI connectivity are documented in [BLOCKED.md](BLOCKED.md) and [scripts/gcp_setup.md](scripts/gcp_setup.md).
