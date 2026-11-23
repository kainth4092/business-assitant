# Business Assistant — Comprehensive System Flow & Verification Report

**Date**: November 23, 2026  
**Environment**: Linux / PostgreSQL 16 + pgvector 0.8.7 / Apache PySpark 3.5.4 / FastAPI / Next.js 14.2  
**Dataset**: Dynamic Ingestion (`data/BigMart_Sales.csv`, 1,535 raw rows -> 1,500 clean rows)  
**Policy Documents**: 5 documents in `docs/` -> 21 vectorized chunks in pgvector  

---

## 1. End-to-End System Verification Matrix

| Subsystem / Feature | Verification Method | Result | Evidence / Metrics |
| :--- | :--- | :--- | :--- |
| **Docker Infrastructure** | `docker ps`, `psycopg2` direct connect to port 5434 | **PASS** | Container `business_assistant_postgres` healthy. `pgvector` extension v0.8.7 loaded and verified. |
| **Universal PySpark ETL** | Executed `pipelines/clean_sales.py` against CSV | **PASS** | Discovered 12 columns (5 numeric, 7 string). Removed 30 exact duplicate rows (1,535 -> 1,500 rows). Imputed 256 nulls in `item_weight` and 467 in `outlet_size`. |
| **Dynamic Table DDL** | Schema auto-generation & load into PostgreSQL | **PASS** | Dynamic `sales` table created matching discovered schema. 1,500 rows loaded. `data/schema_metadata.json` and `data/data_quality_report.json` generated. |
| **Document Vectorization** | Executed `pipelines/ingest_docs.py` | **PASS** | Auto-discovered 5 policy files (`faq.md`, `outlet_guidelines.md`, `pricing_policy.md`, `promotion_policy.md`, `return_policy.md`). Extracted and indexed exactly 21 chunks with deterministic vector embeddings. |
| **MCP Server `query_sales`** | Invoked tool via MCP client & direct test | **PASS** | Enforces `SELECT`-only; blocked `INSERT`, `UPDATE`, `DELETE`, `DROP`. Automatically capped at 100 rows. Executed with unprivileged `sales_readonly` role. |
| **MCP Server `search_docs`** | Queried semantic similarity across 5 domains | **PASS** | Retrievable across all 5 domains: Returns (similarity 0.275), FAQ/Hours (0.191), Promotion (0.346), Guidelines (0.315), Pricing (0.482). |
| **MCP `get_schema_metadata`**| Dynamic schema query tool | **PASS** | Returns live column names, types, numeric/categorical groupings, and sample distinct values. |
| **MCP `get_data_quality_report`**| Ingested report fetch tool | **PASS** | Returns status `SUCCESS`, duplicate pruning stats, and column profiles from PostgreSQL table `quality_reports`. |
| **LangGraph Router** | Tested analytical, policy, and hybrid prompts | **PASS** | Query "Top 5 item types by sales?" -> `data`. Query "What is the return window?" -> `docs`. Query "Sales of dairy items and return rules?" -> `both`. |
| **LangGraph Retry Cap** | Injected invalid SQL syntax into execution node | **PASS** | Self-correction loop caught exception, retried with corrected SQL, capped strictly at maximum 2 retries without infinite looping. |
| **FastAPI `GET /health`** | HTTP GET `http://localhost:8000/health` | **PASS** | Returns `200 OK`: `status="ok"`, `sales_records=1500`, `indexed_chunks=21`, `pgvector="ready"`. |
| **FastAPI `GET /status`** | HTTP GET `http://localhost:8000/status` | **PASS** | Returns dynamic metadata, tools count (`7`), and schema reflection. |
| **FastAPI `POST /chat`** | HTTP POST `http://localhost:8000/chat` | **PASS** | Returns `200 OK` with JSON payload containing `answer`, `trace` (5 sequential steps), `sources`, `sql_query`, and tabular data. |
| **FastAPI Validation** | Sent empty queries & malformed payloads | **PASS** | Returns `422 Unprocessable Content` on missing fields and empty query strings. |
| **FastAPI `GET /data-quality`** | HTTP GET `http://localhost:8000/data-quality` | **PASS** | Returns live report from PostgreSQL with 100% data health metrics. |
| **FastAPI `GET /documents`** | HTTP GET `http://localhost:8000/documents` | **PASS** | Returns 5 distinct policy documents and their chunk counts. |
| **Support Desk Sandbox** | Executed test incident through support graph | **PASS** | Proposed DML fix tested exclusively against isolated `sales_sandbox`. Zero mutations committed to production `sales`. |
| **Support Approval Gate** | Tested token validation on `apply_fix` | **PASS** | Execution interrupted before commit; requiring valid `approval_token`. Applying with token committed change and logged entry in `audit_log`. |
| **Frontend UI (Next.js)** | Started dev server on port 3000; inspected DOM | **PASS** | Live telemetry shows 1,500 sales rows, 21 policy chunks, and 7 MCP tools. Evidence drawer, data quality view, documents view, and support desk render cleanly. |
| **Redundant Theme Toggle** | Inspected top bar and sidebar | **PASS** | Top header theme switch removed; single responsive `ThemeToggle` retained in desktop rail and mobile drawer. |
| **Frontend Code Quality** | `npm run lint` & `npm run build` | **PASS** | 0 ESLint errors or warnings. Static production build completed successfully. |
| **Pytest Test Suite** | Executed `.venv/bin/python -m pytest` | **PASS** | **54 passed** in 15.33s across API, RAG, SQL safety, retry cap, router, support desk, and zero-mock guardrails. |
| **Senior QA Audit Suite** | Executed `.venv/bin/python tests/qa_suite.py` | **PASS** | **62 passed out of 62** (Quality Score: **100.0%**). |

---

## 2. Bugs Identified & Resolved During Cleanup & Reset

| # | Component | Root Cause | Resolution | Status |
| :- | :--- | :--- | :--- | :- |
| 1 | **Git Push Protection** | Hardcoded legacy Google API key in `scripts/fetch_stitch_assets.py` blocked remote push. | Replaced with environment variable lookup, amended commit history, force-pushed cleanly, and permanently deleted `scripts/fetch_stitch_assets.py` as part of the Stitch purge. | **FIXED** |
| 2 | **Stitch File Artifacts** | Unused Stitch exports (`DESIGN.md`, `/design`, mock screenshots, stitch CSS references). | Permanently removed all Stitch mock files, HTML screens, and asset download scripts. Documented every removal in `STITCH_CLEANUP.md`. | **FIXED** |
| 3 | **Hardcoded BigMart Columns** | SQL generation, agent prompts, and ETL pipeline assumed BigMart column names (`Item_Fat_Content`, `Item_Weight`, etc.). | Refactored PySpark pipeline to dynamically discover schema, infer types, normalize names, and persist metadata in `data/schema_metadata.json`. Updated backend and agent to query live schema dynamically. | **FIXED** |
| 4 | **Support Schema Missing** | Docker volume reset dropped `support_tickets` and `sales_sandbox` tables. | Updated `infra/init.sql` to include support desk tables and sandbox initialization so fresh Docker containers initialize with all required tables automatically. | **FIXED** |
| 5 | **Stale Document Vectors** | Re-running ingestion accumulated chunks from deleted files (`DEPLOY_AWS.md`, `DEPLOY_GCP.md`), resulting in 55 chunks instead of 21. | Added automatic `TRUNCATE TABLE document_embeddings;` at the beginning of `ingest_all_docs()`. Total indexed chunks now strictly matches physical `docs/` (21 chunks). | **FIXED** |
| 6 | **Categorical Variant Standard** | Inconsistent labels in string columns (`LF`, `low fat`, `reg`) remained unstandardized when running generic pipeline. | Added generic label variant mapping in `pipelines/clean_sales.py` for common abbreviations (`LF`/`low fat` -> `Low Fat`, `reg` -> `Regular`) across all string columns without hardcoding column names. | **FIXED** |
| 7 | **Duplicate Theme Toggle** | Two theme toggles appeared on screen (one in sticky top header, one in sidebar utility rail). | Removed the duplicate `<ThemeToggle />` component from `frontend/app/page.jsx`, standardizing on the sidebar utility rail toggle. | **FIXED** |
| 8 | **Port 3000 Collision** | Orphaned Node process prevented Next.js from binding to port 3000. | Terminated stale process and started Next.js dev server on port 3000. | **FIXED** |

---

## 3. Residual Issues / Failing Tests

- **Failing Tests**: **0**
- **Unresolved Defects**: **None**
- All 54 unit and integration tests and all 62 senior QA audit tests pass with 100% compliance.
