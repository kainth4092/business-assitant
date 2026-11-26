# Rename Audit Report (`RENAME_AUDIT.md`)

Comprehensive pre-rename scan (including hidden files; excluding `.git`, `node_modules`, `.next`, `.venv`, caches, and build artifacts).

## Summary Counts by Risk Level

- **Total Findings**: 203
- **HIGH** (database names, test DB names, container volumes, persistent paths/identifiers): 44
- **MEDIUM** (package names, logger/MCP IDs, container/network names, LLM system prompts, CLI/YAML config slugs): 25
- **LOW** (UI titles, labels, comments, SVG stamp text, test descriptions, Markdown documentation): 134

## Detailed Findings

| Risk | File | Line | Old Text | Proposed New Text |
| :--- | :--- | ---: | :--- | :--- |
| LOW | `.env` | 2 | `# Environment Configuration for Business Assistant` | `# Environment Configuration for Fixdesk` |
| HIGH | `.env` | 24 | `POSTGRES_DB=business_assistant` | `POSTGRES_DB=fixdesk` |
| HIGH | `.env` | 29 | `DATABASE_URL=postgresql://postgres:postgres_password@localhost:5434/business_assistant` | `DATABASE_URL=postgresql://postgres:postgres_password@localhost:5434/fixdesk` |
| HIGH | `.env` | 32 | `READONLY_DATABASE_URL=postgresql://sales_readonly:readonly_password@localhost:5434/business_ass` | `READONLY_DATABASE_URL=postgresql://sales_readonly:readonly_password@localhost:5434/fixdesk` |
| LOW | `.env.example` | 2 | `# Environment Configuration for Business Assistant` | `# Environment Configuration for Fixdesk` |
| HIGH | `.env.example` | 24 | `POSTGRES_DB=business_assistant` | `POSTGRES_DB=fixdesk` |
| HIGH | `.env.example` | 29 | `DATABASE_URL=postgresql://postgres:postgres_password@localhost:5434/business_assistant` | `DATABASE_URL=postgresql://postgres:postgres_password@localhost:5434/fixdesk` |
| HIGH | `.env.example` | 32 | `READONLY_DATABASE_URL=postgresql://sales_readonly:readonly_password@localhost:5434/business_ass` | `READONLY_DATABASE_URL=postgresql://sales_readonly:readonly_password@localhost:5434/fixdesk` |
| LOW | `ARCHITECTURE.md` | 3 | `This document details the complete end-to-end architecture of the **Business Assistant** platfo` | `This document details the complete end-to-end architecture of the **Fixdesk** platform.` |
| LOW | `ARCHITECTURE.md` | 276 | `See [PHASE1_DESIGN.md](file:///home/kanish/Documents/business-assistant/PHASE1_DESIGN.md) for t` | `See [PHASE1_DESIGN.md](file:///home/kanish/Documents/fixdesk/PHASE1_DESIGN.md) for the complete` |
| LOW | `BLOCKED.md` | 5 | `- **PostgreSQL + pgvector (`business_assistant`)**, **FastAPI Backend (`:8000`)**, **Next.js Fr` | `- **PostgreSQL + pgvector (`fixdesk`)**, **FastAPI Backend (`:8000`)**, **Next.js Frontend (`:3` |
| HIGH | `BLOCKED.md` | 12 | `- **What is blocked**: The Docker daemon (`docker.service` / `/var/run/docker.sock`) is current` | `- **What is blocked**: The Docker daemon (`docker.service` / `/var/run/docker.sock`) is current` |
| LOW | `BLOCKED.md` | 18 | `./.venv/bin/project-init index business-assistant` | `./.venv/bin/project-init index fixdesk` |
| LOW | `BLOCKED.md` | 27 | `\| **Email (IMAP/SMTP)** \| `Not configured` \| Set `IMAP_HOST`, `IMAP_USER`, `IMAP_APP_PASSWOR` | `\| **Email (IMAP/SMTP)** \| `Not configured` \| Set `IMAP_HOST`, `IMAP_USER`, `IMAP_APP_PASSWOR` |
| LOW | `BLOCKED.md` | 28 | `\| **Slack (Socket Mode)** \| `Not configured` \| Set `SLACK_BOT_TOKEN` (`xoxb-...`), `SLACK_AP` | `\| **Slack (Socket Mode)** \| `Not configured` \| Set `SLACK_BOT_TOKEN` (`xoxb-...`), `SLACK_AP` |
| LOW | `BLOCKED.md` | 29 | `\| **Microsoft Teams** \| `Not configured` (Stub) \| Requires Microsoft 365 / Azure tenant admi` | `\| **Microsoft Teams** \| `Not configured` (Stub) \| Requires Microsoft 365 / Azure tenant admi` |
| LOW | `DECISIONS.md` | 3 | `This log records all technical, architectural, and design decisions made for the "Business Assi` | `This log records all technical, architectural, and design decisions made for the "Fixdesk" proj` |
| LOW | `DECISIONS.md` | 77 | `### Decision 9: Project Directory Organization (`/home/kanish/Documents/business-assistant`)` | `### Decision 9: Project Directory Organization (`/home/kanish/Documents/fixdesk`)` |
| LOW | `DECISIONS.md` | 79 | `- **Decision**: Move all project files, pipelines, backend, frontend, infra, tests, virtual env` | `- **Decision**: Move all project files, pipelines, backend, frontend, infra, tests, virtual env` |
| LOW | `DECISIONS.md` | 170 | `- **Consequences**: Business Assistant can ingest and analyze any tabular dataset out of the bo` | `- **Consequences**: Fixdesk can ingest and analyze any tabular dataset out of the box with zero` |
| HIGH | `DECISIONS.md` | 219 | `- Created `business_assistant_test` database for all unit, integration, and guardrail tests.` | `- Created `fixdesk_test` database for all unit, integration, and guardrail tests.` |
| LOW | `DECISIONS.md` | 220 | `- Implemented a strict safety guard in `tests/conftest.py` that raises a `RuntimeError` if any ` | `- Implemented a strict safety guard in `tests/conftest.py` that raises a `RuntimeError` if any ` |
| LOW | `DECISIONS.md` | 225 | `- Verified exactly 0 rows across all tables in `business_assistant`.` | `- Verified exactly 0 rows across all tables in `fixdesk`.` |
| LOW | `DEMO_SCRIPT.md` | 3 | `Follow this step-by-step presentation script to demonstrate the **Business Assistant** to your ` | `Follow this step-by-step presentation script to demonstrate the **Fixdesk** to your manager and` |
| LOW | `DEMO_SCRIPT.md` | 8 | `1. Terminal 1: Run `docker ps` &rarr; verify `business_assistant_postgres` is running on port 5` | `1. Terminal 1: Run `docker ps` &rarr; verify `fixdesk_postgres` is running on port 5434.` |
| LOW | `DEMO_SCRIPT.md` | 19 | `- **What to say**: *"Today I am demonstrating the Business Assistant, an autonomous analytics e` | `- **What to say**: *"Today I am demonstrating the Fixdesk, an autonomous analytics engine that ` |
| LOW | `DESIGN_NOTES.md` | 1 | `# Design System & Architecture Notes: Business Assistant` | `# Design System & Architecture Notes: Fixdesk` |
| LOW | `DESIGN_NOTES.md` | 5 | `Business Assistant is a dense, keyboard-first AI operations control room designed for data anal` | `Fixdesk is a dense, keyboard-first AI operations control room designed for data analysts, engin` |
| LOW | `DESIGN_NOTES.md` | 21 | `Defined in [globals.css](file:///home/kanish/Documents/business-assistant/frontend/app/globals.` | `Defined in [globals.css](file:///home/kanish/Documents/fixdesk/frontend/app/globals.css) and ma` |
| LOW | `DESIGN_NOTES.md` | 45 | `Loaded locally via `next/font/google` in [layout.jsx](file:///home/kanish/Documents/business-as` | `Loaded locally via `next/font/google` in [layout.jsx](file:///home/kanish/Documents/fixdesk/fro` |
| LOW | `EXPLAIN.md` | 1 | `# Business Assistant — Plain-English Architecture Guide (`EXPLAIN.md`)` | `# Fixdesk — Plain-English Architecture Guide (`EXPLAIN.md`)` |
| LOW | `EXPLAIN.md` | 3 | `## 1. What Business Assistant Does` | `## 1. What Fixdesk Does` |
| LOW | `EXPLAIN.md` | 5 | `**Business Assistant** is an internal AI operations control room with three core capabilities b` | `**Fixdesk** is an internal AI operations control room with three core capabilities backed by Po` |
| HIGH | `INTERVIEW_QA.md` | 41 | ``tests/conftest.py` enforces `business_assistant_test` and clears `GOOGLE_API_KEY`. `tests/test` | ``tests/conftest.py` enforces `fixdesk_test` and clears `GOOGLE_API_KEY`. `tests/test_project_in` |
| LOW | `Makefile` | 16 | `@.venv/bin/python3 -m project_init index $(or $(PROJECT),business-assistant)` | `@.venv/bin/python3 -m project_init index $(or $(PROJECT),fixdesk)` |
| LOW | `Makefile` | 19 | `@.venv/bin/python3 -m project_init reindex $(or $(PROJECT),business-assistant)` | `@.venv/bin/python3 -m project_init reindex $(or $(PROJECT),fixdesk)` |
| LOW | `PHASE1_DESIGN.md` | 15 | `- name: business-assistant` | `- name: fixdesk` |
| LOW | `README.md` | 1 | `# Business Assistant (Chat with your Data + Documents)` | `# Fixdesk (Chat with your Data + Documents)` |
| LOW | `README.md` | 57 | `cd /home/kanish/Documents/business-assistant` | `cd /home/kanish/Documents/fixdesk` |
| LOW | `README.md` | 157 | `./.venv/bin/project-init index business-assistant` | `./.venv/bin/project-init index fixdesk` |
| LOW | `README.md` | 158 | `./.venv/bin/project-init reindex business-assistant` | `./.venv/bin/project-init reindex fixdesk` |
| LOW | `README.md` | 159 | `./.venv/bin/project-init index business-assistant --watch` | `./.venv/bin/project-init index fixdesk --watch` |
| LOW | `README.md` | 162 | `./.venv/bin/project-init ask business-assistant "Where are MCP tools registered?"` | `./.venv/bin/project-init ask fixdesk "Where are MCP tools registered?"` |
| LOW | `REVIEW.md` | 1 | `# Senior Code & Security Review: Business Assistant Redesign` | `# Senior Code & Security Review: Fixdesk Redesign` |
| HIGH | `REVIEW.md` | 57 | `- Python `tests/conftest.py` enforces `business_assistant_test` and raises `RuntimeError` if `D` | `- Python `tests/conftest.py` enforces `fixdesk_test` and raises `RuntimeError` if `DATABASE_URL` |
| LOW | `STATE_REPORT.md` | 1 | `# Business Assistant — Real Current State Report` | `# Fixdesk — Real Current State Report` |
| LOW | `STATE_REPORT.md` | 4 | `**Workspace:** `/home/kanish/Documents/business-assistant`` | `**Workspace:** `/home/kanish/Documents/fixdesk`` |
| LOW | `STATE_REPORT.md` | 17 | `\| **MCP Server** \| `.venv/bin/python3 -c "import mcp_server.server as s; print(s.app.name, ..` | `\| **MCP Server** \| `.venv/bin/python3 -c "import mcp_server.server as s; print(s.app.name, ..` |
| HIGH | `STATE_REPORT.md` | 77 | `- **Separate test database**: **Yes.** `tests/conftest.py` sets `TEST_DB_NAME = os.environ.get(` | `- **Separate test database**: **Yes.** `tests/conftest.py` sets `TEST_DB_NAME = os.environ.get(` |
| HIGH | `STATE_REPORT.md` | 78 | `- **Safety guard**: `pytest_configure` in `tests/conftest.py` raises `RuntimeError` if `DATABAS` | `- **Safety guard**: `pytest_configure` in `tests/conftest.py` raises `RuntimeError` if `DATABAS` |
| LOW | `STATE_REPORT.md` | 80 | `1. `tests/test_zero_mock_guardrails.py::test_zero_rows_in_production_db_after_reset` intentiona` | `1. `tests/test_zero_mock_guardrails.py::test_zero_rows_in_production_db_after_reset` intentiona` |
| LOW | `STATE_REPORT.md` | 165 | `\| MCP server (`mcp_server/server.py`) \| Yes \| Partial (imports only) \| Registers 3 tools (`` | `\| MCP server (`mcp_server/server.py`) \| Yes \| Partial (imports only) \| Registers 3 tools (`` |
| LOW | `TASKS.md` | 1 | `# Project Tasks Tracker: Business Assistant` | `# Project Tasks Tracker: Fixdesk` |
| LOW | `TASKS.md` | 168 | `- [x] Restrict all operations strictly inside `/home/kanish/Documents/business-assistant`` | `- [x] Restrict all operations strictly inside `/home/kanish/Documents/fixdesk`` |
| HIGH | `TASKS.md` | 173 | `- [x] Create dedicated test database `business_assistant_test`` | `- [x] Create dedicated test database `fixdesk_test`` |
| LOW | `TASKS.md` | 174 | `- [x] Update `tests/conftest.py` with strict safety guard preventing test pollution of `busines` | `- [x] Update `tests/conftest.py` with strict safety guard preventing test pollution of `fixdesk` |
| LOW | `TASKS.md` | 180 | `- [x] Verify exactly 0 rows across all tables in application database `business_assistant`` | `- [x] Verify exactly 0 rows across all tables in application database `fixdesk`` |
| LOW | `TASKS.md` | 197 | `- [x] Verify zero rows in `business_assistant` database after reset` | `- [x] Verify zero rows in `fixdesk` database after reset` |
| LOW | `USAGE.md` | 1 | `# Business Assistant — Complete User & Operator Guide (USAGE.md)` | `# Fixdesk — Complete User & Operator Guide (USAGE.md)` |
| LOW | `USAGE.md` | 3 | `The **Business Assistant** is an enterprise-grade autonomous analyst workbench powered by FastA` | `The **Fixdesk** is an enterprise-grade autonomous analyst workbench powered by FastAPI, LangGra` |
| LOW | `USAGE.md` | 120 | `\| **Microsoft Teams** \| Stub (Admin setup required) \| See [TEAMS_SETUP.md](file:///home/kani` | `\| **Microsoft Teams** \| Stub (Admin setup required) \| See [TEAMS_SETUP.md](file:///home/kani` |
| LOW | `USAGE.md` | 131 | `- See [CHANNELS_SETUP.md](file:///home/kanish/Documents/business-assistant/docs/CHANNELS_SETUP.` | `- See [CHANNELS_SETUP.md](file:///home/kanish/Documents/fixdesk/docs/CHANNELS_SETUP.md) for beg` |
| LOW | `USAGE.md` | 141 | `./.venv/bin/project-init index business-assistant` | `./.venv/bin/project-init index fixdesk` |
| LOW | `USAGE.md` | 142 | `./.venv/bin/project-init reindex business-assistant` | `./.venv/bin/project-init reindex fixdesk` |
| LOW | `USAGE.md` | 143 | `./.venv/bin/project-init index business-assistant --watch` | `./.venv/bin/project-init index fixdesk --watch` |
| HIGH | `USAGE.md` | 153 | `- Tests run against an isolated test database: `business_assistant_test`.` | `- Tests run against an isolated test database: `fixdesk_test`.` |
| LOW | `USAGE.md` | 154 | `- Safety guards in `tests/conftest.py` ensure tests fail immediately if pointed to `business_as` | `- Safety guards in `tests/conftest.py` ensure tests fail immediately if pointed to `fixdesk`.` |
| LOW | `projects.yaml` | 5 | `- name: business-assistant` | `- name: fixdesk` |
| LOW | `backend/__init__.py` | 2 | `Business Assistant Backend Package` | `Fixdesk Backend Package` |
| MEDIUM | `backend/main.py` | 2 | `FastAPI Application Entrypoint for Business Assistant` | `FastAPI Application Entrypoint for Fixdesk` |
| MEDIUM | `backend/main.py` | 55 | `title="Business Assistant API",` | `title="Fixdesk API",` |
| LOW | `backend/requirements.txt` | 1 | `# Backend & Agent Dependencies for Business Assistant` | `# Backend & Agent Dependencies for Fixdesk` |
| LOW | `backend/agent/__init__.py` | 2 | `Autonomous Agent package for Business Assistant (LangChain + LangGraph)` | `Autonomous Agent package for Fixdesk (LangChain + LangGraph)` |
| LOW | `backend/agent/graph.py` | 2 | `LangGraph Workflow Graph Definition for Business Assistant` | `LangGraph Workflow Graph Definition for Fixdesk` |
| LOW | `backend/agent/nodes.py` | 2 | `LangGraph Nodes for Business Assistant` | `LangGraph Nodes for Fixdesk` |
| MEDIUM | `backend/agent/prompts.py` | 2 | `Prompt Templates for Business Assistant Agent` | `Prompt Templates for Fixdesk Agent` |
| MEDIUM | `backend/agent/prompts.py` | 5 | `ROUTER_SYSTEM_PROMPT = """You are an expert intent router for an enterprise Business Assistant.` | `ROUTER_SYSTEM_PROMPT = """You are an expert intent router for an enterprise Fixdesk.` |
| MEDIUM | `backend/agent/prompts.py` | 24 | `return f"""You are an autonomous AI business assistant with access to company tools.` | `return f"""You are an autonomous AI Fixdesk with access to company tools.` |
| LOW | `backend/agent/state.py` | 2 | `LangGraph State Definition for Business Assistant` | `LangGraph State Definition for Fixdesk` |
| LOW | `backend/agent/tools.py` | 2 | `LangChain Tool Bindings for Business Assistant` | `LangChain Tool Bindings for Fixdesk` |
| LOW | `backend/rag/__init__.py` | 2 | `RAG (Retrieval-Augmented Generation) package for Business Assistant` | `RAG (Retrieval-Augmented Generation) package for Fixdesk` |
| LOW | `backend/rag/embeddings.py` | 2 | `Embedding Utilities for Business Assistant RAG` | `Embedding Utilities for Fixdesk RAG` |
| HIGH | `backend/rag/retrieval.py` | 26 | `"postgresql://sales_readonly:readonly_password@localhost:5434/business_assistant"` | `"postgresql://sales_readonly:readonly_password@localhost:5434/fixdesk"` |
| HIGH | `backend/rag/retrieval.py` | 31 | `"postgresql://postgres:postgres_password@localhost:5434/business_assistant"` | `"postgresql://postgres:postgres_password@localhost:5434/fixdesk"` |
| LOW | `backend/support/channels/__init__.py` | 2 | `Channel Adapter Package for Business Assistant Support Desk` | `Channel Adapter Package for Fixdesk Support Desk` |
| LOW | `docs/CHANNELS_SETUP.md` | 3 | `This guide walks step-by-step through connecting **Email (IMAP/SMTP)**, **Slack (Socket Mode)**` | `This guide walks step-by-step through connecting **Email (IMAP/SMTP)**, **Slack (Socket Mode)**` |
| LOW | `docs/CHANNELS_SETUP.md` | 28 | `3. Enter app name `Business Assistant` -> click **Create**.` | `3. Enter app name `Fixdesk` -> click **Create**.` |
| LOW | `docs/CHANNELS_SETUP.md` | 52 | `2. Name it `Business Assistant Support`, pick your workspace, and click **Create App**.` | `2. Name it `Fixdesk Support`, pick your workspace, and click **Create App**.` |
| LOW | `docs/CHANNELS_SETUP.md` | 80 | `/invite @Business Assistant Support` | `/invite @Fixdesk Support` |
| LOW | `docs/CHANNELS_SETUP.md` | 96 | `Microsoft Teams is provided as a stub and does **not** run automatically in local mode because ` | `Microsoft Teams is provided as a stub and does **not** run automatically in local mode because ` |
| LOW | `docs/TEAMS_SETUP.md` | 3 | `Microsoft Teams is intentionally implemented as a **stub (`TeamsAdapterStub`)** in [teams.py](f` | `Microsoft Teams is intentionally implemented as a **stub (`TeamsAdapterStub`)** in [teams.py](f` |
| MEDIUM | `frontend/package-lock.json` | 2 | `"name": "business-assistant-frontend",` | `"name": "fixdesk-frontend",` |
| MEDIUM | `frontend/package-lock.json` | 8 | `"name": "business-assistant-frontend",` | `"name": "fixdesk-frontend",` |
| MEDIUM | `frontend/package.json` | 2 | `"name": "business-assistant-frontend",` | `"name": "fixdesk-frontend",` |
| LOW | `frontend/app/icon.svg` | 4 | `<text x="16" y="20" text-anchor="middle" fill="#C8372D" font-family="monospace" font-size="11" ` | `<text x="16" y="20" text-anchor="middle" fill="#C8372D" font-family="monospace" font-size="11" ` |
| LOW | `frontend/app/layout.jsx` | 30 | `title: "Business Assistant · Operations Control Log",` | `title: "Fixdesk · Operations Control Log",` |
| LOW | `frontend/components/Spine.jsx` | 99 | `BA` | `FD` |
| LOW | `frontend/components/WorkbenchApp.jsx` | 643 | `Business Assistant` | `Fixdesk` |
| LOW | `frontend/tests/workbench.spec.mjs` | 166 | `name: "business-assistant",` | `name: "fixdesk",` |
| LOW | `frontend/tests/workbench.spec.mjs` | 167 | `local_path: "/repo/business-assistant",` | `local_path: "/repo/fixdesk",` |
| LOW | `frontend/tests/workbench.spec.mjs` | 180 | `if (p === "/projects/business-assistant/index-status") {` | `if (p === "/projects/fixdesk/index-status") {` |
| LOW | `frontend/tests/workbench.spec.mjs` | 187 | `name: "business-assistant",` | `name: "fixdesk",` |
| LOW | `frontend/tests/workbench.spec.mjs` | 188 | `local_path: "/repo/business-assistant",` | `local_path: "/repo/fixdesk",` |
| LOW | `frontend/tests/workbench.spec.mjs` | 199 | `if (p === "/projects/business-assistant/skipped") {` | `if (p === "/projects/fixdesk/skipped") {` |
| LOW | `frontend/tests/workbench.spec.mjs` | 203 | `body: JSON.stringify({ status: "SUCCESS", project: "business-assistant", skipped_files: [] }),` | `body: JSON.stringify({ status: "SUCCESS", project: "fixdesk", skipped_files: [] }),` |
| LOW | `frontend/tests/workbench.spec.mjs` | 687 | `name: "business-assistant",` | `name: "fixdesk",` |
| LOW | `frontend/tests/workbench.spec.mjs` | 688 | `local_path: "/repo/business-assistant",` | `local_path: "/repo/fixdesk",` |
| LOW | `frontend/tests/workbench.spec.mjs` | 702 | `if (p === "/projects/business-assistant/index-status") {` | `if (p === "/projects/fixdesk/index-status") {` |
| LOW | `frontend/tests/workbench.spec.mjs` | 709 | `name: "business-assistant",` | `name: "fixdesk",` |
| LOW | `frontend/tests/workbench.spec.mjs` | 710 | `local_path: "/repo/business-assistant",` | `local_path: "/repo/fixdesk",` |
| LOW | `frontend/tests/workbench.spec.mjs` | 732 | `if (p === "/projects/business-assistant/skipped") {` | `if (p === "/projects/fixdesk/skipped") {` |
| LOW | `frontend/tests/workbench.spec.mjs` | 738 | `project: "business-assistant",` | `project: "fixdesk",` |
| LOW | `frontend/tests/workbench.spec.mjs` | 757 | `if (p === "/projects/business-assistant/index" && route.request().method() === "POST") {` | `if (p === "/projects/fixdesk/index" && route.request().method() === "POST") {` |
| LOW | `frontend/tests/workbench.spec.mjs` | 763 | `project: "business-assistant",` | `project: "fixdesk",` |
| LOW | `frontend/tests/workbench.spec.mjs` | 777 | `if (p === "/projects/business-assistant/ask" && route.request().method() === "POST") {` | `if (p === "/projects/fixdesk/ask" && route.request().method() === "POST") {` |
| LOW | `frontend/tests/workbench.spec.mjs` | 783 | `project: "business-assistant",` | `project: "fixdesk",` |
| MEDIUM | `frontend/tests/workbench.spec.mjs` | 819 | `test.describe("Business Assistant Workbench Redesign", () => {` | `test.describe("Fixdesk Workbench Redesign", () => {` |
| LOW | `frontend/tests/workbench.spec.mjs` | 1122 | `.getByLabel(/Ask a question about business-assistant/i)` | `.getByLabel(/Ask a question about fixdesk/i)` |
| LOW | `infra/DEPLOY_AWS.md` | 3 | `This guide provides complete, production-ready specifications for deploying the **Business Assi` | `This guide provides complete, production-ready specifications for deploying the **Fixdesk** sys` |
| LOW | `infra/DEPLOY_AWS.md` | 32 | `aws s3 mb s3://business-assistant-datalake-$ACCOUNT_ID --region $AWS_REGION` | `aws s3 mb s3://fixdesk-datalake-$ACCOUNT_ID --region $AWS_REGION` |
| LOW | `infra/DEPLOY_AWS.md` | 33 | `aws s3 mb s3://business-assistant-docs-$ACCOUNT_ID --region $AWS_REGION` | `aws s3 mb s3://fixdesk-docs-$ACCOUNT_ID --region $AWS_REGION` |
| LOW | `infra/DEPLOY_AWS.md` | 36 | `aws ecr create-repository --repository-name business-assistant-backend --region $AWS_REGION` | `aws ecr create-repository --repository-name fixdesk-backend --region $AWS_REGION` |
| LOW | `infra/DEPLOY_AWS.md` | 37 | `aws ecr create-repository --repository-name business-assistant-frontend --region $AWS_REGION` | `aws ecr create-repository --repository-name fixdesk-frontend --region $AWS_REGION` |
| LOW | `infra/DEPLOY_AWS.md` | 44 | `--db-instance-identifier business-assistant-postgres \` | `--db-instance-identifier fixdesk-postgres \` |
| HIGH | `infra/DEPLOY_AWS.md` | 51 | `--db-name business_assistant \` | `--db-name fixdesk \` |
| LOW | `infra/DEPLOY_AWS.md` | 62 | `aws s3 cp pipelines/clean_sales.py s3://business-assistant-datalake-$ACCOUNT_ID/scripts/clean_s` | `aws s3 cp pipelines/clean_sales.py s3://fixdesk-datalake-$ACCOUNT_ID/scripts/clean_sales.py` |
| LOW | `infra/DEPLOY_AWS.md` | 63 | `aws s3 cp data/BigMart_Sales.csv s3://business-assistant-datalake-$ACCOUNT_ID/raw/BigMart_Sales` | `aws s3 cp data/BigMart_Sales.csv s3://fixdesk-datalake-$ACCOUNT_ID/raw/BigMart_Sales.csv` |
| LOW | `infra/DEPLOY_AWS.md` | 64 | `aws s3 cp pipelines/jars/postgresql-42.7.3.jar s3://business-assistant-datalake-$ACCOUNT_ID/jar` | `aws s3 cp pipelines/jars/postgresql-42.7.3.jar s3://fixdesk-datalake-$ACCOUNT_ID/jars/postgresq` |
| LOW | `infra/DEPLOY_AWS.md` | 68 | `--name "business-assistant-sales-cleaning" \` | `--name "fixdesk-sales-cleaning" \` |
| LOW | `infra/DEPLOY_AWS.md` | 70 | `--command '{"Name":"glueetl","ScriptLocation":"s3://business-assistant-datalake-'$ACCOUNT_ID'/s` | `--command '{"Name":"glueetl","ScriptLocation":"s3://fixdesk-datalake-'$ACCOUNT_ID'/scripts/clea` |
| LOW | `infra/DEPLOY_AWS.md` | 71 | `--default-arguments '{"--extra-jars":"s3://business-assistant-datalake-'$ACCOUNT_ID'/jars/postg` | `--default-arguments '{"--extra-jars":"s3://fixdesk-datalake-'$ACCOUNT_ID'/jars/postgresql-42.7.` |
| LOW | `infra/DEPLOY_AWS.md` | 83 | `docker build -t $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/business-assistant-backend:latest` | `docker build -t $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/fixdesk-backend:latest -f infra/D` |
| LOW | `infra/DEPLOY_AWS.md` | 84 | `docker push $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/business-assistant-backend:latest` | `docker push $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/fixdesk-backend:latest` |
| LOW | `infra/DEPLOY_AWS.md` | 87 | `docker build -t $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/business-assistant-frontend:lates` | `docker build -t $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/fixdesk-frontend:latest -f infra/` |
| LOW | `infra/DEPLOY_AWS.md` | 88 | `docker push $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/business-assistant-frontend:latest` | `docker push $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/fixdesk-frontend:latest` |
| LOW | `infra/DEPLOY_AWS.md` | 91 | `aws ecs create-cluster --cluster-name business-assistant-cluster --region $AWS_REGION` | `aws ecs create-cluster --cluster-name fixdesk-cluster --region $AWS_REGION` |
| LOW | `infra/DEPLOY_GCP.md` | 3 | `This guide provides complete, production-ready specifications for deploying the **Business Assi` | `This guide provides complete, production-ready specifications for deploying the **Fixdesk** sys` |
| LOW | `infra/DEPLOY_GCP.md` | 45 | `gcloud sql instances create business-assistant-db \` | `gcloud sql instances create fixdesk-db \` |
| HIGH | `infra/DEPLOY_GCP.md` | 54 | `gcloud sql databases create business_assistant --instance=business-assistant-db` | `gcloud sql databases create fixdesk --instance=fixdesk-db` |
| LOW | `infra/DEPLOY_GCP.md` | 57 | `gcloud sql users set-password postgres --instance=business-assistant-db --password="STRONG_ADMI` | `gcloud sql users set-password postgres --instance=fixdesk-db --password="STRONG_ADMIN_PASSWORD"` |
| LOW | `infra/DEPLOY_GCP.md` | 65 | `gsutil cp data/BigMart_Sales.csv gs://business-assistant-data/raw/BigMart_Sales.csv` | `gsutil cp data/BigMart_Sales.csv gs://fixdesk-data/raw/BigMart_Sales.csv` |
| LOW | `infra/DEPLOY_GCP.md` | 66 | `gsutil cp pipelines/clean_sales.py gs://business-assistant-data/scripts/clean_sales.py` | `gsutil cp pipelines/clean_sales.py gs://fixdesk-data/scripts/clean_sales.py` |
| LOW | `infra/DEPLOY_GCP.md` | 69 | `gcloud dataproc batches submit pyspark gs://business-assistant-data/scripts/clean_sales.py \` | `gcloud dataproc batches submit pyspark gs://fixdesk-data/scripts/clean_sales.py \` |
| LOW | `infra/DEPLOY_GCP.md` | 71 | `--deps-bucket=gs://business-assistant-data/deps \` | `--deps-bucket=gs://fixdesk-data/deps \` |
| LOW | `infra/DEPLOY_GCP.md` | 72 | `--jars=gs://business-assistant-data/jars/postgresql-42.7.3.jar \` | `--jars=gs://fixdesk-data/jars/postgresql-42.7.3.jar \` |
| LOW | `infra/DEPLOY_GCP.md` | 79 | `gcloud artifacts repositories create business-assistant-repo \` | `gcloud artifacts repositories create fixdesk-repo \` |
| LOW | `infra/DEPLOY_GCP.md` | 84 | `gcloud builds submit --tag $REGION-docker.pkg.dev/YOUR_GCP_PROJECT_ID/business-assistant-repo/b` | `gcloud builds submit --tag $REGION-docker.pkg.dev/YOUR_GCP_PROJECT_ID/fixdesk-repo/backend:late` |
| LOW | `infra/DEPLOY_GCP.md` | 88 | `gcloud run deploy business-assistant-backend \` | `gcloud run deploy fixdesk-backend \` |
| LOW | `infra/DEPLOY_GCP.md` | 89 | `--image=$REGION-docker.pkg.dev/YOUR_GCP_PROJECT_ID/business-assistant-repo/backend:latest \` | `--image=$REGION-docker.pkg.dev/YOUR_GCP_PROJECT_ID/fixdesk-repo/backend:latest \` |
| LOW | `infra/DEPLOY_GCP.md` | 95 | `--add-cloudsql-instances=YOUR_GCP_PROJECT_ID:$REGION:business-assistant-db` | `--add-cloudsql-instances=YOUR_GCP_PROJECT_ID:$REGION:fixdesk-db` |
| LOW | `infra/DEPLOY_GCP.md` | 98 | `gcloud builds submit --tag $REGION-docker.pkg.dev/YOUR_GCP_PROJECT_ID/business-assistant-repo/f` | `gcloud builds submit --tag $REGION-docker.pkg.dev/YOUR_GCP_PROJECT_ID/fixdesk-repo/frontend:lat` |
| LOW | `infra/DEPLOY_GCP.md` | 102 | `gcloud run deploy business-assistant-frontend \` | `gcloud run deploy fixdesk-frontend \` |
| LOW | `infra/DEPLOY_GCP.md` | 103 | `--image=$REGION-docker.pkg.dev/YOUR_GCP_PROJECT_ID/business-assistant-repo/frontend:latest \` | `--image=$REGION-docker.pkg.dev/YOUR_GCP_PROJECT_ID/fixdesk-repo/frontend:latest \` |
| LOW | `infra/DEPLOY_GCP.md` | 107 | `--set-env-vars="NEXT_PUBLIC_API_URL=https://business-assistant-backend-XYZ-uc.a.run.app"` | `--set-env-vars="NEXT_PUBLIC_API_URL=https://fixdesk-backend-XYZ-uc.a.run.app"` |
| LOW | `infra/Dockerfile.backend` | 2 | `# Production Dockerfile for Business Assistant FastAPI Backend` | `# Production Dockerfile for Fixdesk FastAPI Backend` |
| HIGH | `infra/docker-compose.yml` | 9 | `container_name: business_assistant_postgres` | `container_name: fixdesk_postgres` |
| HIGH | `infra/docker-compose.yml` | 12 | `POSTGRES_DB: ${POSTGRES_DB:-business_assistant}` | `POSTGRES_DB: ${POSTGRES_DB:-fixdesk}` |
| HIGH | `infra/docker-compose.yml` | 22 | `test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-postgres} -d ${POSTGRES_DB:-business_assist` | `test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-postgres} -d ${POSTGRES_DB:-fixdesk}"]` |
| MEDIUM | `infra/docker-compose.yml` | 27 | `- business_network` | `- fixdesk_network` |
| MEDIUM | `infra/docker-compose.yml` | 36 | `container_name: business_assistant_backend` | `container_name: fixdesk_backend` |
| HIGH | `infra/docker-compose.yml` | 42 | `- DATABASE_URL=postgresql://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD:-postgres_password}@` | `- DATABASE_URL=postgresql://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD:-postgres_password}@` |
| HIGH | `infra/docker-compose.yml` | 43 | `- READONLY_DATABASE_URL=postgresql://sales_readonly:readonly_password@postgres:5432/${POSTGRES_` | `- READONLY_DATABASE_URL=postgresql://sales_readonly:readonly_password@postgres:5432/${POSTGRES_` |
| MEDIUM | `infra/docker-compose.yml` | 52 | `- business_network` | `- fixdesk_network` |
| MEDIUM | `infra/docker-compose.yml` | 61 | `container_name: business_assistant_frontend` | `container_name: fixdesk_frontend` |
| MEDIUM | `infra/docker-compose.yml` | 70 | `- business_network` | `- fixdesk_network` |
| HIGH | `infra/docker-compose.yml` | 74 | `name: business_assistant_pgdata` | `name: fixdesk_pgdata` |
| MEDIUM | `infra/docker-compose.yml` | 77 | `business_network:` | `fixdesk_network:` |
| MEDIUM | `infra/docker-compose.yml` | 78 | `name: business_assistant_network` | `name: fixdesk_network` |
| LOW | `infra/init.sql` | 2 | `-- Database Initialization Script for Business Assistant` | `-- Database Initialization Script for Fixdesk` |
| HIGH | `infra/init.sql` | 168 | `GRANT CONNECT ON DATABASE business_assistant TO sales_readonly;` | `GRANT CONNECT ON DATABASE fixdesk TO sales_readonly;` |
| LOW | `mcp_server/__init__.py` | 2 | `Model Context Protocol (MCP) Server for Business Assistant` | `Model Context Protocol (MCP) Server for Fixdesk` |
| MEDIUM | `mcp_server/server.py` | 2 | `MCP Server Entrypoint for Business Assistant` | `MCP Server Entrypoint for Fixdesk` |
| MEDIUM | `mcp_server/server.py` | 33 | `app = MCPServer("business-assistant-mcp")` | `app = MCPServer("fixdesk-mcp")` |
| MEDIUM | `mcp_server/server.py` | 105 | `logger.info("Starting Business Assistant MCP Server on stdio...")` | `logger.info("Starting Fixdesk MCP Server on stdio...")` |
| HIGH | `mcp_server/support_tools.py` | 29 | `"postgresql://sales_readonly:readonly_password@localhost:5434/business_assistant"` | `"postgresql://sales_readonly:readonly_password@localhost:5434/fixdesk"` |
| HIGH | `mcp_server/support_tools.py` | 34 | `"postgresql://postgres:postgres_password@localhost:5434/business_assistant"` | `"postgresql://postgres:postgres_password@localhost:5434/fixdesk"` |
| LOW | `mcp_server/tools.py` | 2 | `MCP Tools Implementation for Business Assistant` | `MCP Tools Implementation for Fixdesk` |
| HIGH | `mcp_server/tools.py` | 108 | `"postgresql://sales_readonly:readonly_password@localhost:5434/business_assistant"` | `"postgresql://sales_readonly:readonly_password@localhost:5434/fixdesk"` |
| HIGH | `mcp_server/tools.py` | 195 | `"postgresql://sales_readonly:readonly_password@localhost:5434/business_assistant"` | `"postgresql://sales_readonly:readonly_password@localhost:5434/fixdesk"` |
| HIGH | `mcp_server/tools.py` | 264 | `"postgresql://sales_readonly:readonly_password@localhost:5434/business_assistant"` | `"postgresql://sales_readonly:readonly_password@localhost:5434/fixdesk"` |
| MEDIUM | `pipelines/clean_sales.py` | 315 | `pg_db = os.environ.get("POSTGRES_DB", "business_assistant")` | `pg_db = os.environ.get("POSTGRES_DB", "fixdesk")` |
| LOW | `pipelines/ingest_docs.py` | 2 | `RAG Ingestion Pipeline for Business Assistant` | `RAG Ingestion Pipeline for Fixdesk` |
| HIGH | `pipelines/ingest_docs.py` | 210 | `"postgresql://postgres:postgres_password@localhost:5434/business_assistant"` | `"postgresql://postgres:postgres_password@localhost:5434/fixdesk"` |
| HIGH | `project_init/store.py` | 33 | `"postgresql://postgres:postgres_password@localhost:5434/business_assistant",` | `"postgresql://postgres:postgres_password@localhost:5434/fixdesk",` |
| HIGH | `project_init/store.py` | 37 | `"postgresql://sales_readonly:readonly_password@localhost:5434/business_assistant",` | `"postgresql://sales_readonly:readonly_password@localhost:5434/fixdesk",` |
| MEDIUM | `scripts/setup.sh` | 3 | `# Business Assistant - Automated Environment & Pipeline Setup Script` | `# Fixdesk - Automated Environment & Pipeline Setup Script` |
| MEDIUM | `scripts/setup.sh` | 16 | `echo "          Starting Business Assistant Automated Setup                   "` | `echo "          Starting Fixdesk Automated Setup                   "` |
| HIGH | `scripts/setup.sh` | 67 | `db_url = os.environ.get('DATABASE_URL', 'postgresql://business_admin:admin_password@localhost:5` | `db_url = os.environ.get('DATABASE_URL', 'postgresql://fixdesk_admin:admin_password@localhost:54` |
| HIGH | `scripts/setup.sh` | 86 | `db_url = os.environ.get('DATABASE_URL', 'postgresql://business_admin:admin_password@localhost:5` | `db_url = os.environ.get('DATABASE_URL', 'postgresql://fixdesk_admin:admin_password@localhost:54` |
| MEDIUM | `scripts/setup.sh` | 113 | `echo " Business Assistant setup complete! Real data is loaded and ready.     "` | `echo " Fixdesk setup complete! Real data is loaded and ready.     "` |
| LOW | `tests/conftest.py` | 2 | `Pytest configuration for Business Assistant` | `Pytest configuration for Fixdesk` |
| HIGH | `tests/conftest.py` | 3 | `Configures a dedicated test database (business_assistant_test) and enforces strict safety guard` | `Configures a dedicated test database (fixdesk_test) and enforces strict safety guards` |
| HIGH | `tests/conftest.py` | 18 | `TEST_DB_NAME = os.environ.get("TEST_POSTGRES_DB", "business_assistant_test")` | `TEST_DB_NAME = os.environ.get("TEST_POSTGRES_DB", "fixdesk_test")` |
| HIGH | `tests/conftest.py` | 46 | `if "business_assistant" in current_url and not "business_assistant_test" in current_url:` | `if "fixdesk" in current_url and not "fixdesk_test" in current_url:` |
| MEDIUM | `tests/conftest.py` | 52 | `if current_db == "business_assistant":` | `if current_db == "fixdesk":` |
| LOW | `tests/qa_suite.py` | 2 | `Senior QA End-to-End Test Suite for Business Assistant` | `Senior QA End-to-End Test Suite for Fixdesk` |
| HIGH | `tests/qa_suite.py` | 64 | `db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres_password@localhost:5434` | `db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres_password@localhost:5434` |
| HIGH | `tests/qa_suite.py` | 65 | `readonly_url = os.environ.get("READONLY_DATABASE_URL", "postgresql://sales_readonly:readonly_pa` | `readonly_url = os.environ.get("READONLY_DATABASE_URL", "postgresql://sales_readonly:readonly_pa` |
| HIGH | `tests/test_project_init.py` | 736 | ``business_assistant_test.code_rag` and verify HNSW table contains zero secret strings.` | ``fixdesk_test.code_rag` and verify HNSW table contains zero secret strings.` |
| MEDIUM | `tests/test_project_init.py` | 843 | `assert any(item["name"] == "business-assistant" for item in listed)` | `assert any(item["name"] == "fixdesk" for item in listed)` |
| HIGH | `tests/test_rag.py` | 47 | `test_db = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres_password@localhost:543` | `test_db = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres_password@localhost:543` |
| HIGH | `tests/test_sql_safety.py` | 60 | `test_db = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres_password@localhost:543` | `test_db = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres_password@localhost:543` |
| HIGH | `tests/test_zero_mock_guardrails.py` | 266 | `prod_url = os.environ.get("PRODUCTION_DATABASE_URL", "postgresql://postgres:postgres_password@l` | `prod_url = os.environ.get("PRODUCTION_DATABASE_URL", "postgresql://postgres:postgres_password@l` |
