# System Readiness & User Action Items (`BLOCKED.md`)

## Core Platform Status: Operational & Verified

- **PostgreSQL + pgvector (`fixdesk`)**, **FastAPI Backend (`:8000`)**, **Next.js Frontend (`:3000`)**, **PySpark Universal Pipeline**, **Gemini 3.5 Flash Lite + Gemini Embedding 2 (768-D)**, and **Support Desk Channels Architecture** are implemented and tested (offline/fake payloads in pytest).

---

## Blocked / Pending User Action Items

### 1. Docker Daemon / PostgreSQL (`localhost:5434`) Inactive in Current Environment
- **What is blocked**: The Docker daemon (`docker.service` / `/var/run/docker.sock`) is currently stopped on this Linux host and starting it requires `sudo`. As a result, live `postgresql://postgres:postgres_password@localhost:5434/fixdesk` (`pgvector`) is offline here.
- **What still works & is verified**: All schema DDL (`infra/code_rag_schema.sql`, `infra/init.sql`), `PostgresCodeStore` parameterized queries, CLI (`project-init`), MCP tools, FastAPI `/projects*` endpoints, secret exclusion/redaction, AST chunking, frontend build, Playwright E2E, and automated pytest suites are implemented and verified offline.
- **Exact command for user to unblock live database & run Project Init against pgvector**:
  ```bash
  sudo systemctl start docker
  docker compose -f infra/docker-compose.yml up -d postgres
  ./.venv/bin/project-init index fixdesk
  ```

### 2. Live External Support Channels (Unconfigured `.env` Credentials)

Real channel listeners are implemented and ready to start automatically with the backend (or via `make channels`), **but cannot connect to live external services yet because credentials are not configured in `.env`**:

| Channel | Current UI Status | Missing `.env` Credentials / Action Needed | Setup Guide |
| :--- | :--- | :--- | :--- |
| **Email (IMAP/SMTP)** | `Not configured` | Set `IMAP_HOST`, `IMAP_USER`, `IMAP_APP_PASSWORD` (Gmail App Password), `SMTP_HOST`, `SMTP_PORT`, and `EMAIL_ALLOWED_SENDERS` in `.env` | [docs/CHANNELS_SETUP.md](docs/CHANNELS_SETUP.md) |
| **Slack (Socket Mode)** | `Not configured` | Set `SLACK_BOT_TOKEN` (`xoxb-...`), `SLACK_APP_TOKEN` (`xapp-...`), and `SLACK_ALLOWED_CHANNELS` in `.env` | [docs/CHANNELS_SETUP.md](docs/CHANNELS_SETUP.md) |
| **Microsoft Teams** | `Not configured` (Stub) | Requires Microsoft 365 / Azure tenant admin to register an Azure Bot, approve Entra ID permissions, and provide a public HTTPS messaging endpoint | [docs/TEAMS_SETUP.md](docs/TEAMS_SETUP.md) |

---

## Optional Gemini API Key Note

- `.env` already contains an active `GOOGLE_API_KEY` configured with `LLM_MODEL=gemini-3.5-flash-lite` and `EMBEDDING_MODEL=gemini-embedding-2`.
- Keep `.env` strictly untracked (ignored by `.gitignore`) so credentials are never committed to Git.

---

### 3. Live GCP Verification (ADC, `GCP_PROJECT_ID`, `GCS_BUCKET`, and Billing Not Configured)
- **What is blocked**: Neither `gcloud` CLI nor `~/.config/gcloud/application_default_credentials.json` is present in this environment, and `GCP_PROJECT_ID` / `GCS_BUCKET` are unset in `.env`. As a result, live calls to Cloud Storage, BigQuery, BigQuery Vector Search, and Vertex AI Gemini could not be executed here.
- **What still works & is verified**: All GCP adapters (`backend/cloud/auth.py`, `backend/cloud/budget.py`, `backend/cloud/gcp_storage.py`, `backend/cloud/gcp_bigquery.py`, `backend/cloud/gcp_ai.py`, `backend/cloud/gcp_vector.py`), `google-cloud-bigquery==3.47.0`, `google-cloud-storage==3.17.2`, `google-genai==3.6.1`, `langchain-google-genai==4.5.1`, `google-auth==2.62.2`, contract tests, SQL/cost safety tests, privacy guard tests, and print-only setup/inventory scripts are implemented and verified offline.
- **Exact commands for user to unblock live GCP mode**:
  ```bash
  # 1. Authenticate via ADC (never download service-account JSON key files)
  gcloud auth login
  gcloud config set project YOUR_GCP_PROJECT_ID
  gcloud auth application-default login
  gcloud auth application-default set-quota-project YOUR_GCP_PROJECT_ID

  # 2. Generate & run provisioning commands (reviews APIs, US bucket, and BigQuery datasets)
  .venv/bin/python scripts/gcp_setup.py --project-id YOUR_GCP_PROJECT_ID --bucket YOUR_UNIQUE_BUCKET

  # 3. Set GCP_PROJECT_ID, GCS_BUCKET, and *_BACKEND=gcp in .env, then verify read-only inventory
  .venv/bin/python scripts/gcp_inventory.py
  ```
  See [scripts/gcp_setup.md](scripts/gcp_setup.md), [COST_NOTES.md](COST_NOTES.md), and [CLEANUP.md](CLEANUP.md).
