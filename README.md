# Fixdesk (Chat with your Data + Documents)

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20%2B%20pgvector-336791.svg)](https://github.com/pgvector/pgvector)
[![PySpark](https://img.shields.io/badge/Apache%20Spark-3.5%2B-orange.svg)](https://spark.apache.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agentic%20Loops-purple.svg)](https://github.com/langchain-ai/langgraph)
[![Next.js](https://img.shields.io/badge/Next.js-App%20Router-black.svg)](https://nextjs.org/)
[![Tests](https://img.shields.io/badge/Tests-47%20Passed-emerald.svg)](https://docs.pytest.org/)

An enterprise-grade autonomous conversational AI system that allows users to ask questions in plain English. The agent intelligently decides whether to query structured **sales data** (via read-only SQL on PostgreSQL), retrieve unstructured **company policy documents** (via pgvector semantic search), or synthesize **both**, presenting complete execution traces and source citations in a modern Next.js interface.

---

## Architecture at a Glance

```
User Query ──► FastAPI (/chat) ──► LangGraph Agent
                                       │
            ┌──────────────────────────┴──────────────────────────┐
            ▼                                                     ▼
    [Router Node]                                         [Router Node]
      (SQL Route)                                          (RAG Route)
            │                                                     │
    query_sales tool                                      search_docs tool
(Read-Only SQL on Postgres)                           (Cosine pgvector Search)
            │                                                     │
            └──────────────────────────┬──────────────────────────┘
                                       ▼
                                 [Answer Node]
                            (Synthesis & Citations)
                                       ▼
                                 [Check Node]
                           (Groundedness Evaluator)
                            (Max 2 Refinement Loops)
                                       ▼
                          Response + Execution Trace
```

---

## Tech Stack (100% Free & Open-Source)

- **PySpark**: Data cleaning, window imputation, label standardization, quality auditing, Parquet export, and JDBC loading.
- **PostgreSQL 16 + pgvector**: Unified relational store for cleaned BigMart sales records and 768-dimensional document vector embeddings.
- **Model Context Protocol (MCP)**: Audited tool execution server (`query_sales`, `search_docs`, `get_data_quality_report`).
- **LangChain & LangGraph**: Autonomous state machine with Router, Agent, Answer, and Check nodes, stateful checkpointer memory, and a 2-retry cap.
- **LLM & Embeddings**: Google Gemini (`gemini-1.5-flash`, `text-embedding-004`) with deterministic offline mock fallback for local testing.
- **FastAPI**: Asynchronous Python backend exposing `/health`, `/chat`, `/data-quality`, and `/sources`.
- **Next.js (App Router) & Tailwind CSS**: Modern JavaScript React UI with interactive "How I Answered" trace drawer and PySpark quality dashboard.

---

## Step-by-Step Setup & Run Instructions

### Step 1: Navigate to Project & Configure Environment
```bash
cd .

# Copy example environment configuration
cp .env.example .env

# (Optional) Edit .env to add your Google Gemini API key:
# GOOGLE_API_KEY=your_actual_gemini_api_key_here
```
> **Note**: The system includes a deterministic offline fallback mode. All unit tests, data pipelines, and UI queries run immediately even before adding an API key!

### Step 2: Start PostgreSQL with pgvector (via Docker Compose)
```bash
docker compose -f infra/docker-compose.yml up -d postgres
```
*Maps container port 5432 to host port **5434** to prevent port collisions with any existing local PostgreSQL instances.*

### Step 3: Run the PySpark Sales Cleaning & ETL Pipeline
```bash
# Create virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# Run PySpark pipeline
python pipelines/clean_sales.py
```
*Cleans 1,530 raw records, standardizes messy labels, imputes missing values, exports `data/cleaned_sales.parquet`, creates `data/data_quality_report.json`, and loads 1,500 records into PostgreSQL via JDBC.*

### Step 4: Ingest Company Policy Documents into pgvector
```bash
python pipelines/ingest_docs.py
```
*Parses 5 company policy documents in `/docs`, generates 21 chunks with 768-dimensional embeddings, and saves them into the `document_embeddings` table.*

### Step 5: Start the FastAPI Backend Server
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
*Verifiable at `http://localhost:8000/health` and interactive Swagger docs at `http://localhost:8000/docs`.*

### Step 6: Start the Next.js Frontend
In a new terminal window:
```bash
cd frontend
npm install
npm run dev
```
*Open [http://localhost:3000](http://localhost:3000) in your browser.*

---

## 5 Demo Questions to Test

| # | Question Type | Sample Prompt | Expected Route & Tools |
| :--- | :--- | :--- | :--- |
| **1** | **Data-Only** | *"What are the top 5 item types by total outlet sales?"* | **Route**: `data` <br>**Tool**: `query_sales` (aggregates sales by `item_type`) |
| **2** | **Data-Only** | *"Which outlet has the highest average item sales?"* | **Route**: `data` <br>**Tool**: `query_sales` (groups by `outlet_identifier`, computes `avg`) |
| **3** | **Docs-Only** | *"What is the return policy for perishable dairy and meat items?"* | **Route**: `docs` <br>**Tool**: `search_docs` (retrieves `return_policy.md`, cites 7-day window) |
| **4** | **Docs-Only** | *"What are the cold chain and refrigeration guidelines for outlets?"* | **Route**: `docs` <br>**Tool**: `search_docs` (retrieves `outlet_guidelines.md`, cites 1°C - 4°C rule) |
| **5** | **Both (Data + Docs)** | *"Which outlet type sells the most Dairy items, and what promotion or return policies apply to them?"* | **Route**: `both` <br>**Tools**: `query_sales` + `search_docs` (synthesizes sales numbers with `promotion_policy.md` and `return_policy.md`) |

---

## Autonomous Support Desk & Safe Remediation (New Feature)

The platform includes an enterprise **Support Desk** capable of receiving problem statements in plain English from Webhooks, Slack, or Microsoft Teams, diagnosing the root cause, and preparing fixes with Human-in-the-Loop verification:

1. **Autonomous Classification**: Categorizes incoming issues into `data_issue`, `code_bug`, `question`, or `feature_request` with a calibrated confidence score.
2. **Safe Isolated Previews**: Fixes are dry-run exclusively on a clone table (`sales_sandbox`) or validated against test suites (`tests/test_demo_target.py`). Production tables are untouched during investigation.
3. **Human-in-the-Loop Approval Gate**: The LangGraph state pauses before deployment via `interrupt_before=["apply_fix"]`. The `apply_fix` tool requires a cryptographically verified `approval_token`.
4. **Immutable Audit Trail**: Every preview, approval, rejection, and application is recorded in PostgreSQL `audit_log` with operator identity and timestamp.
5. **Interactive Workbench Tab**: A dedicated "Support Desk" tab with an incident simulator, status filter pills, step-by-step timeline, unified diff/SQL viewer, before/after counts, and authorization modal.

### Support Desk API Endpoints
- `POST /support/messages`: Receives client message via Webhook, Slack, or Teams.
- `GET /support/tickets`: Lists tickets with filterable status (`fix_ready`, `done`, `rejected`).
- `GET /support/tickets/{ticket_id}`: Retrieves complete ticket trace, diagnostics, and sandbox diff.
- `POST /support/tickets/{ticket_id}/approve`: Validates approval token, applies fix to production, logs to `audit_log`, and notifies client.
- `POST /support/tickets/{ticket_id}/reject`: Declines proposed remediation with operator reasoning.

### Simulating Client Problem Messages
Run the automated multi-channel simulator:
```bash
python scripts/simulate_messages.py
```
This dispatches three realistic client issues:
1. **[Slack] Data Issue**: Inconsistent `Item_Fat_Content` labels (`LF` and `Low Fat`).
2. **[Teams] Code Bug**: Inverted discount calculation in `demo_target/discount_calculator.py`.
3. **[Webhook] Question**: Perishable return policy inquiry.

---

### Project Init (Secret-Safe Codebase RAG)

Index registered repositories in `projects.yaml` into the isolated PostgreSQL `code_rag` schema (`pgvector` HNSW + full-text metadata) to ask architecture and implementation questions with exact `file:line` citations while excluding secrets:

```bash
# Index or incrementally re-index a registered project
./.venv/bin/project-init index fixdesk
./.venv/bin/project-init reindex fixdesk
./.venv/bin/project-init index fixdesk --watch

# Ask a question from the CLI
./.venv/bin/project-init ask fixdesk "Where are MCP tools registered?"
```

- **MCP Tools (`mcp_server/server.py`)**: `list_projects`, `search_code`, `get_file_outline`, `find_symbol` (all read-only with strict project-root path confinement and `[REDACTED]` scrubbing).
- **API Endpoints**: `GET /projects`, `GET /projects/{name}/index-status`, `GET /projects/{name}/skipped`, `POST /projects/{name}/index`, `POST /projects/{name}/ask`.
- **Workbench Screen**: Open the **`05 Projects`** tab in the web app (`Ctrl+K` or press `5`).

---

## Running Automated Tests

Run the comprehensive pytest suite (47 unit and integration tests):
```bash
.venv/bin/pytest tests/ -v
```

Tests cover:
- **Support Desk & Safe Remediation**: Classifier routing, sandbox isolation, approval gate token checks, SQL safety, retry cap, and immutable audit logging.
- **Buggy Demo Module**: `tests/test_demo_target.py` failing before fix and passing after patch.
- **SQL Injection Prevention**: Blocks comments (`--`, `/* */`), multiple statements (`;`), mutation keywords (`DROP`, `DELETE`, `UPDATE`, `ALTER`, `TRUNCATE`), and enforces `LIMIT 100`.
- **Intent Router**: Accurate categorization into `data`, `docs`, and `both`.
- **Retry Cap**: Verifies LangGraph conditional edges terminate strictly at 2 retries.
- **RAG & Vector Retrieval**: Embedding unit-norm validation, sliding-window chunking, and live cosine similarity search.
- **FastAPI Endpoints**: `/health`, `/data-quality`, `/sources`, `/chat`, and `/support/*`.

---

## Hybrid Google Cloud Architecture

Fixdesk runs all application compute on your laptop (Next.js, FastAPI, LangGraph, MCP server, local PySpark) while optionally connecting to **Google Cloud Storage**, **BigQuery**, **BigQuery Vector Search**, and **Vertex AI Gemini**:
- [Hybrid GCP Migration Plan](GCP_MIGRATION_PLAN.md)
- [GCP Setup & Least-Privilege IAM Guide](scripts/gcp_setup.md)
- [Cost Safety Notes](COST_NOTES.md) & [Cleanup Guide](CLEANUP.md)
