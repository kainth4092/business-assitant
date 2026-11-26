# Fixdesk — Real Current State Report

**Inspection Timestamp:** 2026-11-26  
**Workspace:** `.`  
**Constraint:** Read-only inspection; no features added and no application code modified during this audit.

---

## 1. Full Stack Startup From Scratch

| Component | Command Tested | Result | Evidence / Blocker |
| :--- | :--- | :--- | :--- |
| **Docker Services (Postgres + pgvector, Backend, Frontend)** | `docker compose -f infra/docker-compose.yml up -d` | **Failed** | `Cannot connect to the Docker daemon at unix:///var/run/docker.sock`. `docker.service` is `inactive (dead)` and `sudo` requires a password. PostgreSQL container (`port 5434`) is not running (`Connection refused`). *(Local system PostgreSQL 16 runs on port `5432`, not `5434`.)* |
| **Setup Script (`scripts/setup.sh`)** | Inspected `scripts/setup.sh` | **Blocked on DB** | Requires PostgreSQL at `DATABASE_URL` (`localhost:5434`) to apply `infra/init.sql` & `infra/support_schema.sql` and run pipelines. |
| **PySpark ETL Pipeline** | `.venv/bin/python3 -c "from pipelines.clean_sales import run_sales_pipeline"` | **Imports OK; full DB run not executed** | Imports cleanly, and `data/` already holds output from a prior run (`reviews.csv`, `cleaned_sales.parquet/`, `data_quality_report.json`, `schema_metadata.json`). Full run requires PostgreSQL on `5434`. |
| **Document Ingestion Pipeline** | `.venv/bin/python3 -c "from pipelines.ingest_docs import ingest_all_docs"` | **Imports OK; full DB run not executed** | Imports cleanly. `docs/` contains only `README.md`, `CHANNELS_SETUP.md`, and `TEAMS_SETUP.md` (all excluded by `is_user_policy_doc`), and DB `5434` is down. |
| **MCP Server** | `.venv/bin/python3 -c "import mcp_server.server as s; print(s.app.name, ...)"` | **Imports OK; live DB calls blocked** | Loads `MCPServer("fixdesk-mcp")` with `tool_query_sales`, `tool_search_docs`, `tool_get_data_quality_report`. Live SQL/RAG calls fail without PostgreSQL on `5434`. |
| **FastAPI Backend** | `.venv/bin/python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8001` | **Starts & Serves (Degraded)** | `GET /status` returns HTTP `200` with `"status": "degraded"` (PostgreSQL `5434` connection refused), `"llm_live_mode": true`, `"tools_count": 7`. `GET /support/channels` returns HTTP `200` with `['email', 'slack', 'teams']`. |
| **Next.js Frontend** | `cd frontend && npm run lint && npm run build && npm run start -- -p 3100 -H 127.0.0.1` | **Works** | ESLint `0` errors/warnings; Next.js `16.4.6` (Turbopack) production build succeeds; `next start` serves HTTP `200` and passes Playwright tests. |

---

## 2. Feature & Redesign Inventory

1. **Chat with Routing (`Auto / Data / Docs / Both`)**:
   - **Backend (`backend/agent/graph.py`, `backend/agent/nodes.py`, `backend/main.py`)**: `POST /chat` executes `router_node -> agent_node -> answer_node -> check_node` (max 2 retries). `tests/test_router.py` (`4/4`) and `tests/test_retry_cap.py` (`6/6`) and `tests/test_api.py::test_chat_endpoint_*` (`3/3`) passed offline. Live DB-backed SQL + RAG chat was **not verified** because PostgreSQL on `5434` is down.
   - **Frontend (`Composer.jsx`, `SegmentedControl.jsx`, `WorkbenchApp.jsx`)**: Offers `Auto / Data / Docs / Both` tab index. **Gap found:** `ChatRequest` in `backend/main.py` only accepts `{ query, thread_id }` (no `route` field), and `WorkbenchApp.jsx` does not transmit `selectedRoute` to `POST /chat`. The route selector affects the UI loading timeline hint, while backend routing is always decided by `router_node`.
2. **Evidence Panel (`Margin.jsx`)**:
   - Exists with vertical `Timeline` (`Route`, `Query`, `Retrieve`, `Answer`, `Check`), `SqlBlock`, `DataTable`, document relevance bars, citation `[n]` highlighting, groundedness `Stamp`, and mobile bottom sheet. Verified in Playwright with mocked API routes; live DB-backed traces **not verified**.
3. **Data Quality**:
   - Exists (`GET /data-quality`, `pipelines/clean_sales.py`, `DataQualityView.jsx`, `QualityBars.jsx`). Verified in Playwright with mocked data + error/retry flow. `test_api.py::test_data_quality_endpoint_when_empty` returned `200` or `404` and passed. Live PostgreSQL `quality_reports` table read **not verified** (and note `mcp_server/tools.py` falls back to `data/data_quality_report.json` on disk when DB fails).
4. **Documents**:
   - Exists (`GET /documents`, `GET /documents/{id}/chunks`, `GET /sources`, `POST /upload/documents`, `POST /pipeline/ingest-docs`, `DocumentsView.jsx`, `IndexCard.jsx`). Verified in Playwright with mocked API; `test_rag.py` offline unit tests (`4/4`) passed; live DB RAG tests (`test_live_search_documents`, `test_list_indexed_sources`) **failed** due to PostgreSQL `5434` connection refused.
5. **Support Desk (Sandbox + Approval Gate + `audit_log`)**:
   - Exists (`infra/support_schema.sql`, `backend/agent/support_graph.py`, `backend/support/service.py`, `mcp_server/support_tools.py`, `SupportDeskView.jsx`, `StripBoard.jsx`, `Strip.jsx`, `TicketDetail.jsx`, `Stamp.jsx`).
   - UI flight-strip board, XSS escaping, diff/before-after table, and deliberate two-step approval + `APPROVED` seal drop-in verified in Playwright with mocked API.
   - Backend DB tests (`tests/test_support_desk.py`, `4/4`) **failed** because PostgreSQL `5434` is down, so live `sales_sandbox` isolation, token verification, and `audit_log` persistence were **not verified**.
6. **Channel Adapters**:
   - **Telegram**: **Does not exist** (intentionally removed in Stage 17; `backend/support/channels/telegram.py` deleted; only a stale `backend/support/channels/__pycache__/telegram.cpython-312.pyc` artifact remains).
   - **Slack (`backend/support/channels/slack.py`)**: Exists (Socket Mode via `slack_sdk`). Offline unit tests pass; live Slack connection **not verified**.
   - **Email (`backend/support/channels/email.py`)**: Exists (IMAP polling + SMTP threaded reply). Offline unit tests pass; live IMAP/SMTP connection **not verified**.
   - **Microsoft Teams (`backend/support/channels/teams.py`)**: Exists strictly as a non-configured webhook stub (`is_configured() -> False`, pointing to `docs/TEAMS_SETUP.md`).
7. **New Frontend Redesign**:
   - Exists (`Next.js 16.4.6`, `React 19.3.1`, `Tailwind CSS 4.3.5`, `motion 14.14.0`, `lucide-react 1.81.0`). Verified via `npm run lint` (`0` errors), `npm run build`, and Playwright + `@axe-core/playwright` (`3/3` tests passing across `1440px` and `390px`, light and dark themes).

---

## 3. Test Suite & Build Results

### Backend (`pytest`)
Command: `.venv/bin/pytest tests/ -v --tb=short`  
Result: **49 passed, 14 failed** out of **63 collected** (2.35s). *(Note: `tests/qa_suite.py` is a standalone script and is not collected by pytest naming convention.)*

- **Passing Suites (49 tests)**:
  - `tests/test_router.py`: `4/4` passed
  - `tests/test_retry_cap.py`: `6/6` passed
  - `tests/test_demo_target.py`: `2/2` passed
  - `tests/test_sql_safety.py`: `11/12` passed (`test_live_query_sales_execution` failed on DB `5434`)
  - `tests/test_rag.py`: `4/6` passed (`test_live_search_documents`, `test_list_indexed_sources` failed on DB `5434`)
  - `tests/test_api.py`: `5/6` passed (`test_health_endpoint` failed because `database != "connected"`)
  - `tests/test_zero_mock_guardrails.py`: `5/6` passed (`test_zero_rows_in_production_db_after_reset` failed on DB `5434`)
  - `tests/test_support_channels.py`: `12/17` passed (`5` DB-backed deduplication, rate-limit, routing, injection, and approval tests failed on DB `5434`)
- **Failing Suites (14 tests total — all caused by PostgreSQL `localhost:5434` refusing connections)**:
  - `tests/test_support_desk.py`: `0/4` passed
  - Plus the DB-dependent cases noted above in `test_api.py`, `test_rag.py`, `test_sql_safety.py`, `test_support_channels.py`, and `test_zero_mock_guardrails.py`.

### Frontend (`eslint`, `next build`, `playwright`)
- `cd frontend && npm run lint`: **Passed** (`0` errors, `0` warnings).
- `cd frontend && npm run build`: **Passed** (Next.js `16.4.6` Turbopack).
- `cd frontend && npm audit --omit=dev`: **Passed** (`0` vulnerabilities).
- `cd frontend && npm run test:e2e`: **3/3 passed** (Playwright `1.65.1` + `@axe-core/playwright 4.14.1` against `next start`, using `page.route` HTTP mocks for `http://localhost:8000/**`).

---

## 4. Database Isolation in Tests

- **Separate test database**: **Yes.** `tests/conftest.py` sets `TEST_DB_NAME = os.environ.get("TEST_POSTGRES_DB", "fixdesk_test")` and overrides `POSTGRES_DB`, `DATABASE_URL`, and `READONLY_DATABASE_URL` before test modules load.
- **Safety guard**: `pytest_configure` in `tests/conftest.py` raises `RuntimeError` if `DATABASE_URL` contains `fixdesk` without `fixdesk_test`, or if `POSTGRES_DB == "fixdesk"`.
- **Exceptions**:
  1. `tests/test_zero_mock_guardrails.py::test_zero_rows_in_production_db_after_reset` intentionally connects read-only (`SELECT count(*)`) to `PRODUCTION_DATABASE_URL` (`fixdesk`) to assert 0 rows remain.
  2. `tests/test_zero_mock_guardrails.py::test_upload_endpoints_validation_and_flow` writes temporary files (`data/test_upload_dataset.csv`, `docs/test_upload_policy.md`) and deletes them in `finally:`.

---

## 5. Hardcoded, Seeded, or Mock Data Audit

- **Frontend (`frontend/app/`, `frontend/components/`)**: Zero hardcoded sample data, mock arrays, or placeholder metrics (`tests/test_zero_mock_guardrails.py::test_no_forbidden_patterns_in_production_code` passes). *(Playwright mocks exist only inside `frontend/tests/workbench.spec.mjs`.)*
- **Data directory artifacts on disk (`data/`)**: Even though PostgreSQL `5434` is down, `data/` currently contains leftover files from a prior pipeline run:
  - `data/reviews.csv` (`24.5 MB`)
  - `data/cleaned_sales.parquet/`
  - `data/data_quality_report.json` (`79,360` raw rows, `78,299` cleaned rows)
  - `data/schema_metadata.json` (`sales` schema for `reviews.csv`)
  - **Runtime impact**: `mcp_server/tools.py::get_data_quality_report()` falls back to `data/data_quality_report.json` when PostgreSQL fails, and `get_schema_metadata()` reads `data/schema_metadata.json` first if present.
- **Intentional demo target & offline fallbacks**:
  - `demo_target/discount_calculator.py`: Intentional buggy pricing target for Support Desk code-fix remediation demos.
  - `backend/agent/nodes.py` (`heuristic_route`, `execute_sql_for_query` fallbacks) and `backend/agent/support_nodes.py` (deterministic keyword classification and patch templates): Used when offline or without live LLM calls.

---

## 6. `.env` Hygiene & Secret Scan

- **`.gitignore` check**: `.env`, `*.env`, and `*.env.local` are listed in `.gitignore`.
- **Git tracking & history check**: `git ls-files .env` and `git log --all --stat -- .env` produced empty output — `.env` is untracked and was never committed.
- **Note on local `.env`**: `.env` exists locally on disk and has `GOOGLE_API_KEY` set (length `53`), plus local Docker PostgreSQL defaults. Value was not printed.
- **Secret scan**: `gitleaks` / `trufflehog` / `detect-secrets` were not installed; ran a Python regex scan across all **109** tracked files in the working tree and every commit patch in `git log --all -p` for Google API keys (`AIza...`), Slack tokens (`xoxb-`, `xapp-`), AWS keys (`AKIA...`), GitHub tokens (`ghp_...`), and private key headers:
  - **Tracked working tree hits**: `0`
  - **Git history hits**: `0`
  - *(Note: Non-secret local dev default passwords `postgres_password` and `readonly_password` appear in `.env.example`, `infra/docker-compose.yml`, `infra/init.sql`, and fallback connection strings.)*

---

## 7. Environment Variables Read vs. `.env.example`

| Environment Variable | Where Read | Documented in `.env.example`? |
| :--- | :--- | :--- |
| `GOOGLE_API_KEY` | `backend/main.py`, `backend/agent/nodes.py`, `backend/rag/embeddings.py`, `tests/conftest.py` | Yes |
| `LLM_MODEL` | `backend/main.py`, `backend/agent/nodes.py` | Yes |
| `EMBEDDING_MODEL` | `backend/main.py`, `backend/rag/embeddings.py` | Yes |
| `POSTGRES_HOST` | `pipelines/clean_sales.py` | Yes |
| `POSTGRES_PORT` | `pipelines/clean_sales.py`, `infra/docker-compose.yml` | Yes |
| `POSTGRES_DB` | `pipelines/clean_sales.py`, `infra/docker-compose.yml`, `tests/conftest.py` | Yes |
| `POSTGRES_USER` | `pipelines/clean_sales.py`, `infra/docker-compose.yml` | Yes |
| `POSTGRES_PASSWORD` | `pipelines/clean_sales.py`, `infra/docker-compose.yml` | Yes |
| `DATABASE_URL` | `backend/rag/retrieval.py`, `mcp_server/support_tools.py`, `pipelines/ingest_docs.py`, `scripts/setup.sh`, `tests/conftest.py` | Yes |
| `READONLY_DATABASE_URL` | `backend/rag/retrieval.py`, `mcp_server/tools.py`, `mcp_server/support_tools.py`, `tests/conftest.py` | Yes |
| `BACKEND_HOST` | `backend/main.py` | Yes |
| `BACKEND_PORT` | `backend/main.py` | Yes |
| `ALLOWED_ORIGINS` | `backend/main.py` | Yes |
| `NEXT_PUBLIC_API_URL` | `frontend/components/*`, `frontend/app/api/chat/stream/route.js` | Yes |
| `SUPPORT_RATE_LIMIT_PER_HOUR` | `backend/support/service.py` | Yes |
| `IMAP_HOST` | `backend/support/channels/email.py` | Yes |
| `IMAP_USER` | `backend/support/channels/email.py` | Yes |
| `IMAP_APP_PASSWORD` | `backend/support/channels/email.py` | Yes |
| `IMAP_FOLDER` | `backend/support/channels/email.py` | Yes |
| `SMTP_HOST` | `backend/support/channels/email.py` | Yes |
| `SMTP_PORT` | `backend/support/channels/email.py` | Yes |
| `EMAIL_ALLOWED_SENDERS` | `backend/support/channels/email.py` (via `parse_allowlist`) | Yes |
| `SLACK_BOT_TOKEN` | `backend/support/channels/slack.py` | Yes |
| `SLACK_APP_TOKEN` | `backend/support/channels/slack.py` | Yes |
| `SLACK_ALLOWED_CHANNELS` | `backend/support/channels/slack.py` (via `parse_allowlist`) | Yes |
| `DATA_DIR` | Declared in `.env.example` (unused in code; code uses `PROJECT_ROOT/data`) | Yes |
| `DOCS_DIR` | Declared in `.env.example` (unused in code; code uses `PROJECT_ROOT/docs`) | Yes |
| `ENABLE_LLM_CHECKER` | `backend/agent/nodes.py` | **No** |
| `DATA_QUALITY_REPORT` | `mcp_server/tools.py` | **No** |
| `JAVA_HOME` | `pipelines/clean_sales.py`, `scripts/setup.sh` | **No** |
| `BACKEND_URL` | `frontend/app/api/chat/stream/route.js` | **No** |
| `STANDALONE` | `frontend/next.config.js` | **No** |
| `API_URL` | `scripts/simulate_messages.py` | **No** |
| `PYTEST_CURRENT_TEST` | `backend/main.py` (set by pytest) | **No** |
| `TEST_POSTGRES_DB` | `tests/conftest.py` | **No** |
| `TEST_DATABASE_URL` | `tests/conftest.py` | **No** |
| `TEST_READONLY_DATABASE_URL` | `tests/conftest.py` | **No** |
| `RUN_LIVE_GEMINI_TESTS` | `tests/conftest.py` | **No** |
| `PRODUCTION_DATABASE_URL` | `tests/test_zero_mock_guardrails.py` | **No** |

---

## 8. Feature Summary Matrix

| Feature | Exists | Works (verified by running) | Notes |
| :--- | :--- | :--- | :--- |
| Docker Compose stack (`infra/docker-compose.yml`) | Yes | No | Docker daemon not running (`/var/run/docker.sock` missing). |
| PySpark ETL (`pipelines/clean_sales.py`) | Yes | Not verified end-to-end | Module imports; `data/` has prior `reviews.csv` artifacts; live DB load blocked by down Postgres `5434`. |
| Document ingestion (`pipelines/ingest_docs.py`) | Yes | Not verified end-to-end | Module imports; `docs/` has 0 user docs; live pgvector write blocked by down Postgres `5434`. |
| MCP server (`mcp_server/server.py`) | Yes | Partial (imports only) | Registers 3 tools (`fixdesk-mcp`); live DB execution blocked by down Postgres `5434`. |
| FastAPI backend (`backend/main.py`) | Yes | Partial (starts degraded) | `uvicorn` starts and serves HTTP `200` on `/status` & `/support/channels`, degraded without Postgres `5434`. |
| Chat with routing (`Auto/Data/Docs/Both`) | Yes | Partial (offline tests + UI mocked) | Offline router/retry/chat tests pass (`13/13`); `POST /chat` does not accept `route` from UI (`selectedRoute` is UI-only); live SQL+RAG not verified. |
| Evidence panel (`Margin.jsx`) | Yes | Partial (UI mocked) | Verified in Playwright with `page.route` mocks; live DB trace not verified. |
| Data Quality (`DataQualityView.jsx`, `/data-quality`) | Yes | Partial (UI mocked + JSON fallback) | Verified in Playwright with mocks; backend falls back to `data/data_quality_report.json` when DB `5434` is down. |
| Documents catalog + chunk viewer (`DocumentsView.jsx`) | Yes | Partial (offline unit + UI mocked) | Offline chunker tests pass (`4/4`); UI chunk inspector verified in Playwright with mocks; live pgvector tests failed (`5434` down). |
| Support Desk (sandbox + approval gate + `audit_log`) | Yes | Partial (UI mocked; DB failed) | UI board, escaped XSS, 2-step approval & seal verified in Playwright with mocks; all 4 `test_support_desk.py` DB tests failed (`5434` down). |
| Channel adapter: Telegram | No | No | Removed in Stage 17 (`telegram.py` deleted; stale `.pyc` remains in `__pycache__`). |
| Channel adapter: Slack | Yes | Partial (offline unit tests) | `slack.py` Socket Mode exists; offline normalization/allowlist pass; live Slack not verified. |
| Channel adapter: Email | Yes | Partial (offline unit tests) | `email.py` IMAP/SMTP exists; offline normalization/allowlist pass; live mail server not verified. |
| Channel adapter: Teams stub | Yes | Partial (stub status) | `teams.py` stub returns `not_configured` in `/support/channels`; intentionally unimplemented. |
| New frontend redesign | Yes | Yes | `npm run lint` (`0` errors), `npm run build`, and `npm run test:e2e` (`3/3` Playwright + axe-core WCAG AA tests) all pass. |
