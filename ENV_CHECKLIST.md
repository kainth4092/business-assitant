# Fixdesk Environment Configuration Checklist (`ENV_CHECKLIST.md`)

This audit compares [.env.example](.env.example), your local `.env`, and every environment variable read in the Fixdesk codebase. **No secret values are shown anywhere in this file.**

---

## 1. Security & Database Match Check

- **Git Protection**: `.env` is matched by `.gitignore` (`*.env`) and is **not tracked by Git** (`git ls-files .env` = `0`).
- **Docker Compose Match**: [infra/docker-compose.yml](infra/docker-compose.yml) exposes PostgreSQL on `localhost:5434` (`${POSTGRES_PORT:-5434}:5432`). Your `.env` uses `POSTGRES_HOST=localhost` and `POSTGRES_PORT=5434`, which **matches**.
- **Database Name Note**: Your `.env` has `POSTGRES_DB`, `DATABASE_URL`, and `READONLY_DATABASE_URL` pointing to `business_assistant` (the pre-rename database), while [infra/docker-compose.yml](infra/docker-compose.yml) defaults to `fixdesk`. Both databases exist on port `5434`, so `business_assistant` works if intentional, or you can switch those three lines to `fixdesk`.
- **Gemini Key Format**: `GOOGLE_API_KEY` is `SET` (53 characters, starts with `AQ.`, no surrounding quotes). Google AI Studio transitioned newly created keys from `AIza...` to `AQ....`, so this **format looks valid**.

---

## 2. What I Must Do First (Ordered by Importance)

1. **Create a GCS bucket & set `GCS_BUCKET` + `FILE_STORE_BACKEND=gcp` (if you want GCS uploads + BigQuery Parquet loading)**: Your `.env` already has `STORAGE_BACKEND=gcp` and `GCP_PROJECT_ID`, so adding `GCS_BUCKET` lets PySpark write Parquet to Cloud Storage (`gs://<bucket>/clean/`) and load BigQuery directly.
2. **Add explicit BigQuery & AI safety-cap variables to `.env`**: Add `BQ_DATASET`, `BQ_SANDBOX_DATASET`, `BQ_MAX_BYTES_BILLED`, `GCP_MULTI_REGION`, `GCP_REGION`, `AI_DAILY_REQUEST_LIMIT`, `AI_DAILY_TOKEN_LIMIT`, and `AI_BUDGET_WARN_RATIO` (they fall back to defaults right now, but setting them in `.env` makes limits explicit).
3. **Decide whether `.env` should point to `fixdesk` instead of `business_assistant`**: Even with `STORAGE_BACKEND=gcp`, Support Desk tickets, audit logs, and chat history stay in local PostgreSQL (`DATABASE_URL`).
4. **Add Project Init & Rate-Limit defaults (`PROJECTS_CONFIG_PATH`, `CODE_RAG_*`, `SUPPORT_RATE_LIMIT_PER_HOUR`)**: Optional right now because defaults work automatically, but cleaner to keep in `.env`.
5. **Skip Email, Slack, Teams, Telegram, and GitHub for now unless you want those integrations**: Email and Slack are optional support channels; Teams is a stub only; **Telegram and `GITHUB_TOKEN` are not implemented in Fixdesk's code**.

---

## 3. Complete Environment Variable Audit

### A. Core (Gemini & Local PostgreSQL)

| Variable | Needed for | Status | Required now? | Where to get it |
| :--- | :--- | :--- | :--- | :--- |
| `GOOGLE_API_KEY` | Gemini chat & 768-D embeddings (`gemini_api` / `auto`) | `SET` (format looks valid: `AQ.` key) | yes (unless using `LLM_BACKEND=vertexai`) | [Section 4.1](#41-google_api_key-google-ai-studio) |
| `LLM_MODEL` | Chat / router / groundedness model name | `SET` (format looks valid) | yes | [Section 4.1](#41-google_api_key-google-ai-studio) |
| `EMBEDDING_MODEL` | 768-D RAG embedding model name | `SET` (format looks valid) | yes | [Section 4.1](#41-google_api_key-google-ai-studio) |
| `POSTGRES_HOST` | Local PostgreSQL host (`support_tickets`, `audit_log`, `code_rag`) | `SET` (`localhost`, matches Compose) | yes | [Section 4.2](#42-database_url-and-postgresql-settings) |
| `POSTGRES_PORT` | Local PostgreSQL port (`5434` mapped to container `5432`) | `SET` (`5434`, matches Compose) | yes | [Section 4.2](#42-database_url-and-postgresql-settings) |
| `POSTGRES_DB` | PostgreSQL database name | `SET` (legacy `business_assistant` vs Compose `fixdesk`) | yes | [Section 4.2](#42-database_url-and-postgresql-settings) |
| `POSTGRES_USER` | PostgreSQL admin user | `SET` (format looks valid) | yes | [Section 4.2](#42-database_url-and-postgresql-settings) |
| `POSTGRES_PASSWORD` | PostgreSQL admin password | `SET` (format looks valid) | yes | [Section 4.2](#42-database_url-and-postgresql-settings) |
| `DATABASE_URL` | Read/write Postgres DSN (tickets, audit log, chat history, code RAG) | `SET` (valid URL, points to `business_assistant`) | yes | [Section 4.2](#42-database_url-and-postgresql-settings) |
| `READONLY_DATABASE_URL` | Read-only Postgres DSN (`sales_readonly`) | `SET` (valid URL, points to `business_assistant`) | yes | [Section 4.2](#42-database_url-and-postgresql-settings) |
| `BACKEND_HOST` | FastAPI listen host | `SET` (format looks valid) | yes | Local default `0.0.0.0` |
| `BACKEND_PORT` | FastAPI listen port | `SET` (integer `8000`) | yes | Local default `8000` |
| `ALLOWED_ORIGINS` | FastAPI CORS allowlist | `SET` (valid comma-separated HTTP origins) | yes | Local default `http://localhost:3000,http://127.0.0.1:3000` |
| `NEXT_PUBLIC_API_URL` | Next.js frontend backend URL | `SET` (valid HTTP URL) | yes | Local default `http://localhost:8000` |
| `DATA_DIR` | Local CSV, Parquet & `.budget_state.json` folder | `SET` (format looks valid) | yes | Local default `./data` |
| `DOCS_DIR` | Local policy documents folder | `SET` (format looks valid) | yes | Local default `./docs` |

### B. Google Cloud Platform (BigQuery, GCS, Vertex AI, Budget Caps)

| Variable | Needed for | Status | Required now? | Where to get it |
| :--- | :--- | :--- | :--- | :--- |
| `GCP_PROJECT_ID` | BigQuery, GCS & Vertex AI project target | `SET` (format looks valid) | yes (since `STORAGE_BACKEND=gcp`) | [Section 4.3](#43-gcp_project_id-gcs_bucket-bigquery--adc-login) |
| `STORAGE_BACKEND` | Switches analytics & sandbox (`local` vs `gcp`) | `SET` (`gcp`) | yes | [Section 4.3](#43-gcp_project_id-gcs_bucket-bigquery--adc-login) |
| `BQ_DATASET` | Production BigQuery dataset (`sales`, `quality_reports`, `schema_metadata`) | `MISSING` (defaults to `fixdesk`) | yes (recommended with `STORAGE_BACKEND=gcp`) | [Section 4.3](#43-gcp_project_id-gcs_bucket-bigquery--adc-login) |
| `BQ_SANDBOX_DATASET` | Isolated Support Desk preview dataset | `MISSING` (defaults to `fixdesk_sandbox`) | yes (recommended with `STORAGE_BACKEND=gcp`) | [Section 4.3](#43-gcp_project_id-gcs_bucket-bigquery--adc-login) |
| `BQ_MAX_BYTES_BILLED` | Per-query BigQuery scan byte safety limit | `MISSING` (defaults to `104857600`) | yes (recommended cost guard) | [Section 4.3](#43-gcp_project_id-gcs_bucket-bigquery--adc-login) |
| `GCP_MULTI_REGION` | BigQuery datasets & GCS bucket location | `MISSING` (defaults to `US`) | yes (recommended) | [Section 4.3](#43-gcp_project_id-gcs_bucket-bigquery--adc-login) |
| `GCP_REGION` | Vertex AI regional endpoint | `MISSING` (defaults to `us-central1`) | later (when `LLM_BACKEND=vertexai`) | [Section 4.3](#43-gcp_project_id-gcs_bucket-bigquery--adc-login) |
| `AI_DAILY_REQUEST_LIMIT` | Daily AI call safety cap | `MISSING` (defaults to `500`) | yes (recommended cost guard) | [Section 4.3](#43-gcp_project_id-gcs_bucket-bigquery--adc-login) |
| `AI_DAILY_TOKEN_LIMIT` | Daily estimated/reported AI token cap | `MISSING` (defaults to `500000`) | yes (recommended cost guard) | [Section 4.3](#43-gcp_project_id-gcs_bucket-bigquery--adc-login) |
| `AI_BUDGET_WARN_RATIO` | UI amber warning threshold (`0.8` = 80%) | `MISSING` (defaults to `0.8`) | yes (recommended cost guard) | [Section 4.3](#43-gcp_project_id-gcs_bucket-bigquery--adc-login) |
| `GCS_BUCKET` | Cloud Storage bucket for `raw/`, `clean/`, `docs/` | `NOT NEEDED YET` (needed if `FILE_STORE_BACKEND=gcp`) | later | [Section 4.3](#43-gcp_project_id-gcs_bucket-bigquery--adc-login) |
| `FILE_STORE_BACKEND` | Switches CSV/Parquet/Docs disk (`local` vs `gcp`) | `NOT NEEDED YET` (defaults to `local`) | later | [Section 4.3](#43-gcp_project_id-gcs_bucket-bigquery--adc-login) |
| `VECTOR_BACKEND` | Switches vector search (`local` pgvector vs `gcp` BigQuery) | `NOT NEEDED YET` (defaults to `local`) | later | [Section 4.3](#43-gcp_project_id-gcs_bucket-bigquery--adc-login) |
| `BQ_VECTOR_DATASET` | BigQuery dataset for `document_embeddings` & `code_rag` | `NOT NEEDED YET` (defaults to `fixdesk_vectors`) | later | [Section 4.3](#43-gcp_project_id-gcs_bucket-bigquery--adc-login) |
| `LLM_BACKEND` | Switches LLM (`auto`, `vertexai`, `gemini_api`) | `NOT NEEDED YET` (defaults to `auto`) | later | [Section 4.3](#43-gcp_project_id-gcs_bucket-bigquery--adc-login) |
| `EMBEDDING_BACKEND` | Switches embeddings (`auto`, `vertexai`, `gemini_api`) | `NOT NEEDED YET` (defaults to `auto`) | later | [Section 4.3](#43-gcp_project_id-gcs_bucket-bigquery--adc-login) |
| `DOCUMENT_RAG_BACKEND` | Optional Vertex RAG Engine hook (`default` vs `vertex_rag_engine`) | `NOT NEEDED YET` (defaults to `default`) | optional | [Section 4.3](#43-gcp_project_id-gcs_bucket-bigquery--adc-login) |
| `VERTEX_RAG_CORPUS` | Vertex RAG Engine corpus resource name | `NOT NEEDED YET` | optional | Only if `DOCUMENT_RAG_BACKEND=vertex_rag_engine` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Key-file path (Fixdesk **blocks** SA JSON keys) | `NOT NEEDED YET` (leave unset; use ADC) | optional (do not use SA keys) | [Section 4.3](#43-gcp_project_id-gcs_bucket-bigquery--adc-login) |

### C. Channels (Telegram, Slack, Email, Teams)

| Variable | Needed for | Status | Required now? | Where to get it |
| :--- | :--- | :--- | :--- | :--- |
| `SUPPORT_RATE_LIMIT_PER_HOUR` | Support Desk per-sender hourly ticket limit | `MISSING` (defaults to `10`) | optional | `.env.example` default `10` |
| `IMAP_HOST` | Support Email inbound polling server | `NOT NEEDED YET` | optional | [Section 4.6](#46-email-imap--smtp-with-gmail-app-password) |
| `IMAP_USER` | Support Email login address | `NOT NEEDED YET` | optional | [Section 4.6](#46-email-imap--smtp-with-gmail-app-password) |
| `IMAP_APP_PASSWORD` | 16-char Gmail App Password (not regular password) | `NOT NEEDED YET` | optional | [Section 4.6](#46-email-imap--smtp-with-gmail-app-password) |
| `IMAP_FOLDER` | Mailbox folder/label to poll (`INBOX`) | `NOT NEEDED YET` | optional | [Section 4.6](#46-email-imap--smtp-with-gmail-app-password) |
| `SMTP_HOST` | Outbound email reply server | `NOT NEEDED YET` | optional | [Section 4.6](#46-email-imap--smtp-with-gmail-app-password) |
| `SMTP_PORT` | Outbound SMTP port (`587` STARTTLS) | `NOT NEEDED YET` | optional | [Section 4.6](#46-email-imap--smtp-with-gmail-app-password) |
| `EMAIL_ALLOWED_SENDERS` | Comma-separated allowlisted emails or `@domain.com` | `NOT NEEDED YET` | optional | [Section 4.6](#46-email-imap--smtp-with-gmail-app-password) |
| `SLACK_BOT_TOKEN` | Slack Bot User OAuth Token (`xoxb-...`) | `NOT NEEDED YET` | optional | [Section 4.5](#45-slack-socket-mode-slack_bot_token-slack_app_token-slack_allowed_channels) |
| `SLACK_APP_TOKEN` | Slack App-Level Socket Mode Token (`xapp-...`) | `NOT NEEDED YET` | optional | [Section 4.5](#45-slack-socket-mode-slack_bot_token-slack_app_token-slack_allowed_channels) |
| `SLACK_ALLOWED_CHANNELS` | Allowlisted Slack channel IDs / `dm` | `NOT NEEDED YET` | optional | [Section 4.5](#45-slack-socket-mode-slack_bot_token-slack_app_token-slack_allowed_channels) |
| `TELEGRAM_BOT_TOKEN` | Not implemented in Fixdesk codebase | `NOT NEEDED YET` (not used by code) | optional (not supported) | [Section 4.4](#44-telegram-telegram_bot_token-telegram_allowed_chat_ids--not-used-in-code) |
| `TELEGRAM_ALLOWED_CHAT_IDS` | Not implemented in Fixdesk codebase | `NOT NEEDED YET` (not used by code) | optional (not supported) | [Section 4.4](#44-telegram-telegram_bot_token-telegram_allowed_chat_ids--not-used-in-code) |
| *(Teams env vars)* | Microsoft Teams (`TeamsAdapterStub` reads no env vars) | `NOT NEEDED YET` (stub only) | optional | [Section 4.8](#48-microsoft-teams-optional-admin-setup) |

### D. GitHub (Coding Agent)

| Variable | Needed for | Status | Required now? | Where to get it |
| :--- | :--- | :--- | :--- | :--- |
| `GITHUB_TOKEN` | Not read by Fixdesk code yet (only redacted if leaked in code) | `NOT NEEDED YET` (not used by code) | optional | [Section 4.7](#47-github_token-optional--not-used-in-code-yet) |

### E. Other (Project Init, Runtime & Test Overrides)

| Variable | Needed for | Status | Required now? | Where to get it |
| :--- | :--- | :--- | :--- | :--- |
| `PROJECTS_CONFIG_PATH` | Path to `projects.yaml` for Codebase RAG | `MISSING` (defaults to `./projects.yaml`) | later | Repo root `projects.yaml` |
| `CODE_RAG_MAX_FILE_BYTES` | Max file size indexed by Project Init (`524288`) | `MISSING` (defaults to `524288`) | later | `.env.example` default `524288` |
| `CODE_RAG_ENTROPY_THRESHOLD` | Secret-scanner Shannon entropy cutoff (`3.6`) | `MISSING` (defaults to `3.6`) | later | `.env.example` default `3.6` |
| `CODE_RAG_LLM_SUMMARY` | `1` uses LLM 1-line chunk summaries, `0` uses local AST | `MISSING` (defaults to `0`) | optional | `.env.example` default `0` |
| `AI_BUDGET_STATE_PATH` | Override path for `.budget_state.json` | `NOT NEEDED YET` | optional | Runtime/test override |
| `API_URL` | Override URL for `scripts/simulate_messages.py` | `NOT NEEDED YET` | optional | Defaults to `http://localhost:8000` |
| `BACKEND_URL` | Internal Next.js proxy target (`frontend/app/api/chat/stream`) | `NOT NEEDED YET` | optional | Defaults to `NEXT_PUBLIC_API_URL` |
| `DATA_QUALITY_REPORT` | Fallback JSON report path | `NOT NEEDED YET` | optional | Defaults to `data/data_quality_report.json` |
| `ENABLE_LLM_CHECKER` | Enable LLM groundedness checker (`false` by default) | `NOT NEEDED YET` | optional | Defaults to `false` |
| `FIXDESK_ALLOW_GCE_METADATA` | Set `1` only on GCE VMs (laptop sets `NO_GCE_CHECK=true`) | `NOT NEEDED YET` | optional | Defaults to `0` |
| `JAVA_HOME` | JDK 17/21 path for local PySpark | `NOT NEEDED YET` | optional | Auto-detected in `clean_sales.py` |
| `PRODUCTION_DATABASE_URL` | Override prod DB URL for `test_zero_mock_guardrails.py` | `NOT NEEDED YET` | optional | Test override |
| `PYTEST_CURRENT_TEST` | Set automatically by `pytest` | `NOT NEEDED YET` | optional | Set by pytest |
| `RUN_LIVE_GCP_TESTS` | Set `1` to allow live GCP calls inside `pytest` | `NOT NEEDED YET` | optional | Test override |
| `RUN_LIVE_GEMINI_TESTS` | Set `1` to allow live Gemini API calls inside `pytest` | `NOT NEEDED YET` | optional | Test override |
| `STANDALONE` | Next.js standalone build output toggle | `NOT NEEDED YET` | optional | Used in Docker build |
| `TEST_DATABASE_URL` | Override test DB URL in `tests/conftest.py` | `NOT NEEDED YET` | optional | Defaults to `fixdesk_test` |
| `TEST_POSTGRES_DB` | Override test DB name in `tests/conftest.py` | `NOT NEEDED YET` | optional | Defaults to `fixdesk_test` |
| `TEST_READONLY_DATABASE_URL` | Override readonly test DB URL in `tests/conftest.py` | `NOT NEEDED YET` | optional | Defaults to `fixdesk_test` |

---

## 4. Step-by-Step Setup Instructions

### 4.1 `GOOGLE_API_KEY` (Google AI Studio)
- **What it is**: API key for Gemini chat (`LLM_MODEL`) and 768-D embeddings (`EMBEDDING_MODEL`) when not using Vertex AI.
- **Cost / Billing**: Free tier is available in Google AI Studio without a credit card (rate-limited); paid tier requires Cloud Billing. *(Note: your `.env` already has a `SET` key starting with `AQ.`.)*
- **Steps** *(menu names may change slightly; follow the on-screen wording if updated)*:
  1. Open [https://aistudio.google.com/](https://aistudio.google.com/) and sign in with your Google account.
  2. Click **Get API key** in the left sidebar.
  3. Click **Create API key**, pick or create a project, and copy the generated key (newer keys start with `AQ.`; older ones start with `AIza`).
  4. Paste it into `.env` (no quotes or spaces):
     ```env
     GOOGLE_API_KEY=AQ.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
     LLM_MODEL=gemini-3.5-flash-lite
     EMBEDDING_MODEL=gemini-embedding-2
     ```
- **Safe test (never prints the key)**:
  ```bash
  .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); from backend.cloud.config import is_valid_gemini_api_key; print('Gemini key valid format:', is_valid_gemini_api_key())"
  ```
- **Common mistakes**: Leaving `your_gemini_api_key_here`, wrapping the key in quotes, or hitting free-tier quota (`429 ResourceExhausted`).
- **Safety**: Never paste this key in chat, screenshots, or Git. If leaked, open AI Studio → **Get API key** → delete/revoke it immediately and create a new one.

---

### 4.2 `DATABASE_URL` and PostgreSQL Settings
- **What it is**: Connection strings and credentials for your local PostgreSQL 16 + `pgvector` container (`support_tickets`, `audit_log`, `conversations`, `messages`, `code_rag`, and local `sales`).
- **Cost / Billing**: 100% free (runs locally via Docker).
- **Steps**:
  1. Start PostgreSQL from the repo root:
     ```bash
     docker compose -f infra/docker-compose.yml up -d postgres
     ```
  2. Update `.env` if you want to switch from `business_assistant` to the `fixdesk` database:
     ```env
     POSTGRES_HOST=localhost
     POSTGRES_PORT=5434
     POSTGRES_DB=fixdesk
     POSTGRES_USER=postgres
     POSTGRES_PASSWORD=postgres_password
     DATABASE_URL=postgresql://postgres:postgres_password@localhost:5434/fixdesk
     READONLY_DATABASE_URL=postgresql://sales_readonly:readonly_password@localhost:5434/fixdesk
     ```
- **Safe test (never prints passwords)**:
  ```bash
  .venv/bin/python -c "import os, psycopg2; from dotenv import load_dotenv; load_dotenv(); c=psycopg2.connect(os.environ['DATABASE_URL']); print('Postgres connected, version:', c.server_version); c.close()"
  ```
- **Common mistakes**: Using port `5432` instead of `5434` (collides with system Postgres), forgetting to start Docker (`Connection refused`), or connecting to a DB name that was not created yet (`FATAL: database "..." does not exist`).
- **Safety**: Keep `.env` untracked in Git. If you ever use non-default passwords and leak `.env`, rotate the DB user password with `ALTER USER ... WITH PASSWORD ...;`.

---

### 4.3 `GCP_PROJECT_ID`, `GCS_BUCKET`, BigQuery & ADC Login
- **What it is**: Connects Fixdesk's hybrid cloud layer to BigQuery (`BQ_DATASET`, `BQ_SANDBOX_DATASET`, `BQ_VECTOR_DATASET`), Cloud Storage (`GCS_BUCKET`), and Vertex AI (`GCP_REGION`) using Application Default Credentials (ADC).
- **Cost / Billing**:
  - **BigQuery Sandbox**: Free without a credit card (10 GB active storage + 1 TB queries/month; Fixdesk automatically uses batch load jobs and `CREATE OR REPLACE TABLE ... AS SELECT` fallback when DML is blocked).
  - **Cloud Storage (`GCS_BUCKET`) & Vertex AI**: Typically require a GCP Billing Account attached to your project (check Google Cloud Billing free-tier limits; exact free-tier quotas vary by account/region).
- **Steps**:
  1. Open [https://console.cloud.google.com/](https://console.cloud.google.com/) and note your **Project ID** (yours is already set in `.env` as `GCP_PROJECT_ID`).
  2. Run ADC login in your terminal (never download a service-account JSON key file—Fixdesk blocks key files):
     ```bash
     gcloud auth login
     gcloud config set project YOUR_GCP_PROJECT_ID
     gcloud auth application-default login
     gcloud auth application-default set-quota-project YOUR_GCP_PROJECT_ID
     ```
  3. Enable the required APIs:
     ```bash
     gcloud services enable bigquery.googleapis.com storage.googleapis.com aiplatform.googleapis.com --project=YOUR_GCP_PROJECT_ID
     ```
  4. *(Optional, needed when enabling `FILE_STORE_BACKEND=gcp`)* Create a US multi-region bucket:
     ```bash
     gcloud storage buckets create gs://your-unique-fixdesk-bucket --project=YOUR_GCP_PROJECT_ID --location=US --uniform-bucket-level-access
     ```
  5. Add the missing BigQuery & safety-cap lines to `.env`:
     ```env
     GCP_PROJECT_ID=your-gcp-project-id
     GCP_REGION=us-central1
     GCP_MULTI_REGION=US
     STORAGE_BACKEND=gcp
     BQ_DATASET=fixdesk
     BQ_SANDBOX_DATASET=fixdesk_sandbox
     BQ_MAX_BYTES_BILLED=104857600
     AI_DAILY_REQUEST_LIMIT=500
     AI_DAILY_TOKEN_LIMIT=500000
     AI_BUDGET_WARN_RATIO=0.8
     # Optional (uncomment when enabling GCS / BigQuery Vector / Vertex AI):
     # FILE_STORE_BACKEND=gcp
     # GCS_BUCKET=your-unique-fixdesk-bucket
     # VECTOR_BACKEND=gcp
     # BQ_VECTOR_DATASET=fixdesk_vectors
     # LLM_BACKEND=vertexai
     # EMBEDDING_BACKEND=vertexai
     ```
- **Safe test (read-only, prints no secrets)**:
  ```bash
  .venv/bin/python scripts/gcp_inventory.py
  ```
- **Common mistakes**: Setting `GOOGLE_APPLICATION_CREDENTIALS` to a JSON key file (`ServiceAccountKeyBlockedError`), leaving `GCS_BUCKET` blank while `FILE_STORE_BACKEND=gcp`, or creating a bucket in a region different from `US` multi-region BigQuery datasets.
- **Safety**: Never commit or share `~/.config/gcloud/application_default_credentials.json`. If a laptop is compromised, run `gcloud auth application-default revoke`.

---

### 4.4 Telegram (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_CHAT_IDS`) — *Not Used in Code*
- **What it is**: Telegram bot credentials. **Fixdesk does not implement a Telegram channel adapter** (`tests/test_support_channels.py` explicitly verifies Telegram is absent; only Webhook, Email, Slack, and a Teams stub exist).
- **Cost / Billing**: Free if you ever add a custom Telegram bot later.
- **Steps (only if you build a Telegram adapter in the future)** *(menu prompts may change; follow `@BotFather` replies)*:
  1. Open Telegram, search for **`@BotFather`**, and send `/newbot`.
  2. Follow the prompts for bot name and username; copy the token (`123456789:ABCdef...`).
  3. Message your new bot once, then call `https://api.telegram.org/bot<TOKEN>/getUpdates` locally to read your numeric `chat.id`.
  4. Example `.env` format (not read by Fixdesk today):
     ```env
     TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
     TELEGRAM_ALLOWED_CHAT_IDS=123456789
     ```
- **Safe test**: `not verified` (no Telegram code exists in Fixdesk).
- **Safety**: Never share the BotFather token in chat/screenshots/git; if leaked, send `/revoke` to `@BotFather`.

---

### 4.5 Slack Socket Mode (`SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `SLACK_ALLOWED_CHANNELS`)
- **What it is**: Connects your Slack workspace to Fixdesk Support Desk over an outbound WebSocket (no public webhook URL needed).
- **Cost / Billing**: Free (works on Slack's free workspace plan).
- **Steps** *(Slack dashboard labels can change slightly; follow on-screen wording if updated)*:
  1. Open [https://api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch** → name it `Fixdesk Support` → select your workspace → **Create App**.
  2. Left sidebar → **Settings** → **Socket Mode** → turn **Enable Socket Mode** **ON**.
  3. Left sidebar → **Settings** → **Basic Information** → scroll to **App-Level Tokens** → **Generate Token and Scopes** → name it `socket-token` → add scope `connections:write` → **Generate** → copy the `xapp-...` token (`SLACK_APP_TOKEN`).
  4. Left sidebar → **Features** → **OAuth & Permissions** → **Scopes** → **Bot Token Scopes** → add: `app_mentions:read`, `channels:history`, `groups:history`, `im:history`, `chat:write`, `users:read`.
  5. Left sidebar → **Features** → **Event Subscriptions** → toggle **Enable Events** **ON** → **Subscribe to bot events** → add `app_mention`, `message.channels`, `message.groups`, `message.im` → **Save Changes**.
  6. Go back to **OAuth & Permissions** → click **Install to Workspace** → **Allow** → copy the **Bot User OAuth Token** starting with `xoxb-...` (`SLACK_BOT_TOKEN`).
  7. In Slack, open your support channel, run `/invite @Fixdesk Support`, right-click the channel → **View channel details** → copy the Channel ID at the bottom (e.g. `C0123456789`).
  8. Paste into `.env`:
     ```env
     SLACK_BOT_TOKEN=xoxb-your-bot-token-here
     SLACK_APP_TOKEN=xapp-your-app-token-here
     SLACK_ALLOWED_CHANNELS=C0123456789,dm
     ```
- **Safe test (never prints tokens)**:
  ```bash
  .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); from backend.support.channels.slack import SlackAdapter; print('Slack configured:', SlackAdapter().is_configured())"
  ```
- **Common mistakes**: Swapping `xoxb-` and `xapp-`, forgetting `/invite @Fixdesk Support` in the channel (`not_in_channel`), or leaving `SLACK_ALLOWED_CHANNELS` empty (messages get rejected).
- **Safety**: Never paste `xoxb-` or `xapp-` in chat, screenshots, or Git. If leaked, revoke/regenerate both in Slack App Settings immediately.

---

### 4.6 Email (`IMAP_*`, `SMTP_*`, `EMAIL_ALLOWED_SENDERS` with Gmail App Password)
- **What it is**: Lets Fixdesk poll a Gmail/IMAP inbox every 30 seconds and reply to support tickets via SMTP.
- **Cost / Billing**: Free with a personal Gmail account (requires **2-Step Verification** enabled; Google Workspace accounts may have App Passwords disabled by an admin).
- **Steps** *(Google Account menus occasionally move; if not visible, search `"App passwords"` in the Google Account search bar)*:
  1. Open [https://myaccount.google.com/](https://myaccount.google.com/) → **Security**.
  2. Under **How you sign in to Google**, turn **2-Step Verification** **ON** (if not already on).
  3. Open **2-Step Verification** → scroll to the bottom → click **App passwords** (or search `"App passwords"` at the top of myaccount.google.com).
  4. Enter app name `Fixdesk` → click **Create** / **Generate** → copy the 16-character password.
  5. *(If using Gmail)* Open Gmail → Gear icon → **See all settings** → **Forwarding and POP/IMAP** → ensure IMAP is enabled (some accounts enable it automatically).
  6. Paste into `.env`:
     ```env
     IMAP_HOST=imap.gmail.com
     IMAP_USER=your.support@gmail.com
     IMAP_APP_PASSWORD=abcd_efgh_ijkl_mnop
     IMAP_FOLDER=INBOX
     SMTP_HOST=smtp.gmail.com
     SMTP_PORT=587
     EMAIL_ALLOWED_SENDERS=you@gmail.com,@yourcompany.com
     ```
- **Safe test (never prints password)**:
  ```bash
  .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); from backend.support.channels.email import EmailAdapter; print('Email configured:', EmailAdapter().is_configured())"
  ```
- **Common mistakes**: Using your regular Google password (`AUTHENTICATIONFAILED`), forgetting `EMAIL_ALLOWED_SENDERS` (all senders ignored), or using an organization account where App Passwords are blocked.
- **Safety**: Never share your 16-character App Password. If leaked, delete that App Password immediately inside Google Account → **App passwords**.

---

### 4.7 `GITHUB_TOKEN` *(Optional — Not Used in Code Yet)*
- **What it is**: Fine-grained GitHub Personal Access Token (PAT) if you later add automated PR creation. **Fixdesk does not read `GITHUB_TOKEN` today** (`demo_target` code fixes generate local unified diffs without calling GitHub).
- **Cost / Billing**: Free on any GitHub account.
- **Steps** *(GitHub menu wording may change slightly; follow on-screen labels if updated)*:
  1. Open [https://github.com/settings/tokens](https://github.com/settings/tokens) → **Fine-grained tokens** → **Generate new token**.
  2. Give it a name (e.g. `fixdesk-pr-bot`) and short expiration (e.g. `30 days`).
  3. Under **Repository access**, choose **Only select repositories** → pick **ONE** repository only.
  4. Under **Repository permissions**, set **Contents** = `Read and write` and **Pull requests** = `Read and write` (leave Administration, Merging, and Workflows = `No access`).
  5. Click **Generate token** and copy the `github_pat_...` token.
  6. Only if you add GitHub automation later, place in `.env`:
     ```env
     GITHUB_TOKEN=github_pat_your_token_here
     ```
- **Safe test**: `not verified` (`GITHUB_TOKEN` is not wired into Fixdesk runtime code).
- **Safety**: Never give broad `All repositories` or `Admin` permissions, and never paste `github_pat_` tokens in chat/screenshots/git. If leaked, click **Revoke** in GitHub → Settings → Developer settings → Personal access tokens.

---

### 4.8 Microsoft Teams *(Optional — Admin Setup Only)*
- **What it is**: Microsoft Teams integration is currently a stub (`TeamsAdapterStub` in [teams.py](backend/support/channels/teams.py)) and reads **no `.env` variables**.
- **Cost / Billing**: Requires a Microsoft 365 / Azure tenant administrator (or Microsoft 365 Developer tenant) and a public HTTPS endpoint (Azure Bot + hosting may require an Azure billing subscription).
- **Steps**: See [docs/TEAMS_SETUP.md](docs/TEAMS_SETUP.md) if your company IT admin asks to enable live Teams webhooks. In local/hybrid development, keep Teams disabled.
- **Safe test**:
  ```bash
  .venv/bin/python -c "from backend.support.channels.teams import TeamsAdapterStub; print('Teams configured:', TeamsAdapterStub().is_configured())"
  ```
