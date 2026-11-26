# Fixdesk — Complete User & Operator Guide (USAGE.md)

The **Fixdesk** is an enterprise-grade autonomous analyst workbench powered by FastAPI, LangGraph, Model Context Protocol (MCP), PySpark, and PostgreSQL 16 with `pgvector`, paired with a Next.js App Router frontend.

The platform is completely **data-agnostic**: you can provide **ANY CSV** dataset and any policy or procedure documents (`.md`, `.txt`, `.pdf`). The assistant will automatically discover the schema, clean the dataset with PySpark, build semantic vector indexes, and allow you to ask natural language questions across structured data, policy documents, or both.

---

## 1. Quick Start: Uploading New Data & Running the Project

You can upload your data and documents through the **Web UI** or directly via the **Command Line**.

### Option A: Upload & Ingest via the Web UI (Recommended)
1. Open the workbench in your browser at **[http://localhost:3000](http://localhost:3000)**.
2. In the First-Run Onboarding screen (or by clicking the **"Add Data"** button in the top navigation bar):
   - **Upload CSV**: Click or drag your `.csv` dataset file into the Dataset box and click **"Upload CSV"**.
   - **Upload Docs**: Click or drag your `.md`, `.txt`, or `.pdf` policy files into the Documents box and click **"Upload Docs"**.
3. Click **"Run PySpark Pipeline & Ingestion"**.
   - The PySpark pipeline will automatically profile the columns, clean nulls/duplicates, create the PostgreSQL table, and index vector embeddings.
4. The workbench will transition immediately to the active analysis screen with dynamic starter investigation questions.

---

### Option B: Upload & Ingest via Command Line
1. **Stage your CSV**: Place your CSV file in the `data/` directory:
   ```bash
   cp /path/to/your_dataset.csv data/
   ```
2. **Stage your Documents**: Place your policy or guidelines documents (`.md`, `.txt`, or `.pdf`) in the `docs/` directory:
   ```bash
   cp /path/to/your_policies/*.md docs/
   ```
3. **Execute the Universal Pipelines**:
   ```bash
   # 1. Run the PySpark Universal Data Cleaning Pipeline
   .venv/bin/python pipelines/clean_sales.py

   # 2. Run the Multi-Format Document Ingestion Pipeline
   .venv/bin/python pipelines/ingest_docs.py
   ```

---

## 2. Resetting the Project to a Clean Slate

To wipe all data, reset all database tables, and start fresh with zero records:

```bash
# 1. Stop and remove Docker containers and volumes
docker compose -f infra/docker-compose.yml down -v

# 2. Wipe temporary pipeline outputs and caches
rm -rf data/*.parquet data/*.json .pytest_cache frontend/.next

# 3. Bring up a fresh PostgreSQL container
docker compose -f infra/docker-compose.yml up -d

# 4. Remove staged files in data/ and docs/ (keeping README.md files)
find data/ -type f ! -name "README.md" -delete
find docs/ -type f ! -name "README.md" -delete
```

All 9 database tables (`sales`, `document_embeddings`, `quality_reports`, `conversations`, `messages`, `support_tickets`, `audit_log`, `sales_sandbox`, `schema_metadata`) will start with exactly **0 rows**.

---

## 3. Starting the Services

**Terminal 1 — Backend (FastAPI)**:
```bash
.venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
*(Verify by checking `http://localhost:8000/status`)*

**Terminal 2 — Frontend (Next.js)**:
```bash
cd frontend
npm run dev
```
*(Open [http://localhost:3000](http://localhost:3000))*

---

## 4. Testing the Three Kinds of Questions

Once your CSV and documents are ingested, you can ask queries through the chat composer or by clicking the generated starters:

### 1. Data-Only Query (SQL)
- **What it does**: Translates your natural language into read-only SQL, executes it against the PostgreSQL table matching your discovered schema, and presents the tabular metrics.
- **Example**: *"What are the total and average values for [Your Metric Column] grouped by [Your Category Column]?"*
- **What to look for**:
  - Route badge displays **`DATA (SQL)`**.
  - Evidence Panel shows the generated sanitized `SELECT` statement and the returned rows table.

### 2. Docs-Only Query (Vector RAG)
- **What it does**: Performs cosine similarity search over your vectorized documents in `pgvector` and produces a grounded response with verifiable citations.
- **Example**: *"What standard procedures or policies apply to [Topic from your documents]?"*
- **What to look for**:
  - Route badge displays **`DOCS (RAG)`**.
  - Citations (e.g., `[policy_name.md#...]`) appear in the text and can be inspected in the Evidence Panel.

### 3. Hybrid Query (Data + Docs)
- **What it does**: Queries the SQL database for real quantitative figures and simultaneously retrieves relevant policy sections, synthesizing both into a unified answer.
- **Example**: *"What were our total metrics for [Top Category], and what operational guidelines apply to it?"*
- **What to look for**:
  - Route badge displays **`BOTH`**.
  - Output combines exact SQL numbers with policy rules from documentation.
  - Evidence Panel displays both SQL trace and vector sources.

---

## 5. Support Desk Live Communication Channels (Email, Slack, Teams)

The Support Desk accepts incident messages not only from the **`+ Simulate Client`** modal, but also automatically from live communication channels configured in `.env`:

| Channel | Transport | Required `.env` Variables |
| :--- | :--- | :--- |
| **Email** | IMAP Polling (30s) + SMTP Reply | `IMAP_HOST`, `IMAP_USER`, `IMAP_APP_PASSWORD`, `SMTP_HOST`, `SMTP_PORT`, `EMAIL_ALLOWED_SENDERS` |
| **Slack** | Socket Mode (no public URL) | `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `SLACK_ALLOWED_CHANNELS` |
| **Microsoft Teams** | Stub (Admin setup required) | See [TEAMS_SETUP.md](docs/TEAMS_SETUP.md) |

- **Automatic Startup**: Running the FastAPI backend (`uvicorn backend.main:app --host 0.0.0.0 --port 8000` or `make start-backend`) automatically starts workers for configured channels and logs `"skipped"` for unconfigured ones.
- **Standalone Channels Worker Command**: You can also start the background listeners independently with:
  ```bash
  make channels
  ```
- **UI Controls & Safety**:
  - Open **Support** in [http://localhost:3000](http://localhost:3000) to inspect each channel's live status (`Connected`, `Not configured`, `Paused`, `Error`), last received message timestamp, and toggle listeners On/Off.
  - All inbound messages pass strict `.env` allowlists, deduplication, hourly per-sender rate limits (`SUPPORT_RATE_LIMIT_PER_HOUR=10`), and untrusted prompt-injection scanning.
  - **Human approval is mandatory**: approvals/rejections can only be executed by a logged-in operator in the Web UI, never via a chat message.
  - See [CHANNELS_SETUP.md](docs/CHANNELS_SETUP.md) for beginner step-by-step setup instructions.

---

## 6. Project Init (Codebase RAG) Operations

1. Register repositories in `projects.yaml` (`name`, `local_path`, `default_branch`, `include`, `exclude`).
2. Index or watch from the CLI:
   ```bash
   ./.venv/bin/project-init list
   ./.venv/bin/project-init index fixdesk
   ./.venv/bin/project-init reindex fixdesk
   ./.venv/bin/project-init index fixdesk --watch
   ```
3. Or open the **`05 Projects`** tab (shortcut `5`) in [http://localhost:3000](http://localhost:3000) to inspect file/chunk counts, commit hash, the **Skipped Files** security audit report, click **Re-Index Incremental**, and ask plain-English codebase questions with clickable `file:line` citations.

---

## 7. Running Tests & Guardrails

The project includes strict test isolation preventing any test from modifying production data:

- Tests run against an isolated test database: `fixdesk_test`.
- Safety guards in `tests/conftest.py` ensure tests fail immediately if pointed to `fixdesk`.

```bash
# Run the complete automated test suite (53 tests)
.venv/bin/python -m pytest tests/

# Run frontend linting & production build
cd frontend && npm run lint && npm run build
```
Expected output: **100% PASS** with zero warnings and zero mock data.
