# Rename Verification Report (`RENAME_REPORT.md`)

**Project**: `Fixdesk` (slug: `fixdesk`, test DB: `fixdesk_test`)  
**Safety Branch / Commit**: `backup-before-rename` (`ebeb072`)

---

## 1. Summary of Changes by Area

| Area | Files Changed | Summary of Replacements | Risk |
| :--- | :---: | :--- | :--- |
| **Frontend UI & Package** | 6 | Updated `package.json` / `package-lock.json` (`fixdesk-frontend`), `app/layout.jsx` (`Fixdesk · Operations Control Log`), `app/icon.svg` & `Spine.jsx` stamp monogram (`BA` → `FD`), `WorkbenchApp.jsx` header breadcrumb (`Fixdesk` + `Projects Registry`), and `frontend/tests/workbench.spec.mjs`. | LOW / MEDIUM |
| **Backend & LLM Prompts** | 12 | Updated `backend/main.py` FastAPI title (`Fixdesk API`), LLM prompts in `backend/agent/prompts.py` (`ROUTER_SYSTEM_PROMPT`, `get_agent_system_prompt`, `ANSWER_SYSTEM_PROMPT`), package docstrings, and `backend/rag/retrieval.py` default DB URL (`fixdesk`). | MEDIUM |
| **MCP Server & Project Init** | 4 | Updated `mcp_server/server.py` (`MCPServer("fixdesk-mcp")`), `mcp_server/tools.py`, `mcp_server/support_tools.py`, and `project_init/store.py` default DB URLs; updated `projects.yaml` slug to `fixdesk`. | MEDIUM / HIGH |
| **Pipelines & Scripts** | 4 | Updated `pipelines/clean_sales.py`, `pipelines/ingest_docs.py`, `Makefile` (`PROJECT` default `fixdesk`), and `scripts/setup.sh` banners and PostgreSQL URLs. | MEDIUM / HIGH |
| **Docker & SQL Infrastructure** | 4 | Updated `infra/docker-compose.yml` (`fixdesk_postgres`, `fixdesk_backend`, `fixdesk_frontend`, `fixdesk_pgdata`, `fixdesk_network`, `fixdesk` DB), `infra/init.sql` (dynamic `current_database()` read-only grant), `infra/Dockerfile.backend`, and `.env.example`. | HIGH |
| **Tests & Guardrails** | 7 | Updated `tests/conftest.py` (`fixdesk_test` enforcement), `tests/test_rag.py`, `tests/test_sql_safety.py`, `tests/test_qa_suite`, `tests/test_zero_mock_guardrails.py`, `tests/test_project_init.py`, and added [test_rename_guardrail.py](tests/test_rename_guardrail.py). | MEDIUM / HIGH |
| **Documentation** | 20 | Updated `README.md`, `USAGE.md`, `ARCHITECTURE.md`, `EXPLAIN.md`, `INTERVIEW_QA.md`, `PHASE1_DESIGN.md`, `DESIGN_NOTES.md`, `DEMO_SCRIPT.md`, `DECISIONS.md` (Decision 25), `TASKS.md` (Stage 20), `BLOCKED.md`, `REVIEW.md`, `STATE_REPORT.md`, `docs/*`, `infra/DEPLOY_*.md`; created `RENAME_AUDIT.md`, `MIGRATION.md`, and `RENAME_REPORT.md`. | LOW |

---

## 2. Intentionally Kept Untouched & Why

- **`.git` commit history & `backup-before-rename` branch (`ebeb072`)**: Left immutable for auditability and rollback safety.
- **User `.env` & existing Docker volume `business_assistant_pgdata` (`business_assistant_postgres` on port `5434`)**: Contains 78,299 live rows of existing user data; intentionally untouched so existing setups continue running uninterrupted via `.env` overrides (documented in [MIGRATION.md](MIGRATION.md)).
- **`/data` and `/docs` user content & secrets**: No user datasets, `.env` keys/tokens, or channel secrets were modified.
- **Local Workspace Directory Path**: Not renamed on disk while processes and tools were active inside it; documented as a manual step in [MIGRATION.md](MIGRATION.md).
- **`RENAME_AUDIT.md`, `MIGRATION.md`, `RENAME_REPORT.md`**: Intentionally excluded from [test_rename_guardrail.py](tests/test_rename_guardrail.py) because they record the migration mapping and pre-rename inventory.

---

## 3. Checks Run & Verified Results

| Check | Scope & Target | Outcome |
| :--- | :--- | :--- |
| `pytest tests/test_rename_guardrail.py` | Full repository scan excluding `.git`, `node_modules`, `.next`, `.venv`, audit/migration reports, and gitignored `.env` | **PASSED (`1/1`)** — 0 legacy name matches remaining |
| `pytest tests/ -k "not production_db" -v` | Full backend, SQL safety, router, retry cap, support desk, channels, RAG, Project Init (including live `pgvector` test on `5434`), and zero-mock guardrails | **PASSED (`73 passed, 1 deselected`)** |
| `cd frontend && npm run lint && npm run build && npm run test:unit && npm run test:e2e` | ESLint (`eslint .`), Next.js 16.4.6 Turbopack production build, 4 SSE unit tests, 5 Playwright E2E + `@axe-core/playwright` WCAG 2.1 AA responsive tests (explicit `<title>` / `Fixdesk` header assertions) | **PASSED (`4/4` unit, `5/5` E2E)** |
| Fresh Stack E2E Verification (`POSTGRES_PORT=5435`, `POSTGRES_DB=fixdesk`) | Brought up `fixdesk_postgres` container + `fixdesk_pgdata` volume + `fixdesk_network`; ran `init.sql`, `support_schema.sql`, `code_rag_schema.sql`; verified `/openapi.json` title (`"Fixdesk API"`), `data` chat route, `docs` chat route, Support Desk sandbox + `fix_ready` → `approve` → `done` + 4 `audit_log` entries, and `project-init index fixdesk --full` (120 files, 722 chunks) | **PASSED** |
| Running Web & API Servers (`http://localhost:3000`, `http://localhost:8000`) | Verified `<title>Fixdesk · Operations Control Log</title>`, header `"Fixdesk"`, `/openapi.json` title `"Fixdesk API"`, and `/status` (`healthy`, `78,299` rows in preserved legacy container on `5434`) | **PASSED** |
