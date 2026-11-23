# Business Assistant — Complete User & Operator Guide

The **Business Assistant** is an enterprise-grade autonomous analyst workbench powered by FastAPI, LangGraph, Model Context Protocol (MCP), PySpark, and PostgreSQL with `pgvector`, paired with a Next.js App Router frontend.

The system is completely **schema-agnostic**: you can drop **ANY CSV** into `/data` and any SOP or policy documents into `/docs`, and the assistant will automatically discover the schema, clean the dataset with PySpark, build semantic vector indexes, and allow you to ask natural language questions across structured data, policy documents, or both.

---

## 1. Quick Start: Uploading New Data & Running the Project

Follow these beginner-friendly steps to upload your data, reset the system, run the pipelines, and start the application.

### Step 1: Upload Your Data and Documents
1. **Upload your CSV**: Place your CSV file in the `data/` directory.
   ```bash
   cp /path/to/your_file.csv data/
   ```
   *(The pipeline automatically detects any `.csv` inside `/data` and discovers its columns, types, and labels).*
2. **Upload your Documents**: Place your policy or guidelines documents (`.md` or `.txt`) in the `docs/` directory.
   ```bash
   cp /path/to/your_policy.md docs/
   ```

### Step 2: Reset the Project State (Fresh Clean Slate)
To wipe all old databases, Docker volumes, cached vector embeddings, and temporary artifacts:
```bash
# 1. Stop and remove existing Docker containers and volumes
docker compose -f infra/docker-compose.yml down -v

# 2. Clean temporary parquet files and caches
rm -rf data/*.parquet data/*.json .pytest_cache frontend/.next
```

### Step 3: Start Database and Run the Universal Pipelines
```bash
# 1. Start clean PostgreSQL 16 container with pgvector
docker compose -f infra/docker-compose.yml up -d

# 2. Wait 3 seconds for PostgreSQL to be ready, then run the PySpark Universal Cleaning Pipeline
.venv/bin/python pipelines/clean_sales.py

# 3. Run the Document Vector Ingestion Pipeline
.venv/bin/python pipelines/ingest_docs.py
```
What happens automatically:
- PySpark inspects your CSV schema, standardizes column names, removes duplicates, normalizes inconsistent labels, and imputes nulls.
- It dynamically generates the PostgreSQL table `sales` matching your columns and loads the clean data.
- It writes `data/schema_metadata.json` and records data quality metrics into `data/data_quality_report.json` and PostgreSQL.
- `ingest_docs.py` parses all documents in `docs/`, cleans stale chunks, and indexes them into `document_embeddings` with pgvector.

### Step 4: Start Backend and Frontend

**Terminal 1 — Backend (FastAPI)**:
```bash
.venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
*(Verify health by opening `http://localhost:8000/health` in your browser)*

**Terminal 2 — Frontend (Next.js)**:
```bash
cd frontend
npm run dev
```
*(Open [http://localhost:3000](http://localhost:3000) in your browser)*

---

## 2. Testing the Three Kinds of Questions

The Business Assistant autonomously classifies your question intent and executes the optimal retrieval path:

### Type A: Data-Only Query (SQL)
- **What it does**: Translates your plain English into read-only SQL, runs it against the PostgreSQL `sales` table, and presents the tabular metrics and calculation summary.
- **Example Question**:
  > *"What are the total sales and transaction count for Frozen Foods?"*
- **What to look for**:
  - The router badge highlights **`DATA (SQL)`**.
  - The right Evidence Panel displays the generated `SELECT` query and the exact database results table.

### Type B: Docs-Only Query (Vector RAG)
- **What it does**: Performs semantic similarity search across your uploaded documents in `docs/` and produces a grounded answer with verifiable citations.
- **Example Question**:
  > *"What is our company policy on returning opened perishable items?"*
- **What to look for**:
  - The router badge highlights **`DOCS (RAG)`**.
  - Inline citation badges (e.g., `[return_policy.md#...]`) appear in the text.
  - The Evidence Panel shows the retrieved source document chunks and similarity scores.

### Type C: Hybrid Query (Data + Docs)
- **What it does**: Simultaneously queries the SQL database and searches policy documents, merging quantitative sales metrics with operational business rules.
- **Example Question**:
  > *"What are our total sales for Dairy items, and what special handling or return rules apply to Dairy?"*
- **What to look for**:
  - The router badge highlights **`BOTH`**.
  - The output provides both numerical figures from your dataset and policy requirements from your documentation.
  - The Evidence Panel contains both SQL execution details and policy citations.

---

## 3. Environment Configuration (`.env`)

Ensure a `.env` file exists in the project root:

```bash
# Database Configuration (PostgreSQL 16 + pgvector)
POSTGRES_HOST=localhost
POSTGRES_PORT=5434
POSTGRES_DB=business_assistant
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres_password

# Read-only user used for safe SQL query execution by the agent
POSTGRES_READONLY_USER=sales_readonly
POSTGRES_READONLY_PASSWORD=readonly_password

# Artificial Intelligence & LLM Settings
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash
EMBEDDING_MODEL=text-embedding-004

# Backend & Frontend
API_HOST=0.0.0.0
API_PORT=8000
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 4. Frontend Workbench Features

- **Header Telemetry**: Displays real-time counts of Cleaned Records in PostgreSQL, Vector Chunks in pgvector, and Active MCP Tools.
- **Theme Switcher**: High-contrast Dark and Light modes toggled from the left utility rail.
- **Tabs**:
  1. **Analysis (`Analysis`)**: Live natural language query chat with interactive suggested starters, route chips, and split-screen Evidence Panel.
  2. **Data Quality (`Quality`)**: Real-time PySpark data quality report showing duplicate removal counts, column profiles, and null imputation deltas.
  3. **Documentation (`Docs`)**: Live inventory of vectorized files in `docs/` with chunk inspectors.
  4. **Support Desk (`Support`)**: Plain-English incident ticketing workbench with isolated sandbox execution and Human-in-the-Loop approval gates.

---

## 5. Running the Test Suites

To verify zero regressions and complete pipeline integrity:

```bash
# Run unit, integration, safety, and zero-mock tests (54 tests)
.venv/bin/python -m pytest

# Run the Senior QA Comprehensive End-to-End Audit (62 tests)
.venv/bin/python tests/qa_suite.py

# Run frontend lint and production build
cd frontend && npm run lint && npm run build
```
Expected output: **100% PASS** on all suites.
