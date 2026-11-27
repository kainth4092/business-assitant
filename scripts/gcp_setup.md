# Google Cloud Hybrid Setup Guide (`scripts/gcp_setup.md`)

Fixdesk runs **all application compute locally on your laptop** (Next.js, FastAPI, LangGraph, MCP server, local PySpark ETL) while delegating storage, analytics tables, AI inference, and vector search to **GCP serverless data/AI services** (`GCS`, `BigQuery`, `Vertex AI Gemini`, `BigQuery Vector Search`).

---

## 1. Security Rule: ADC Only (Zero Service Account Key Files)

Fixdesk **explicitly blocks static service-account JSON key files** (`GOOGLE_APPLICATION_CREDENTIALS` pointing to `"type": "service_account"`).

Always authenticate via **Application Default Credentials (ADC)**:

```bash
gcloud auth login
gcloud config set project YOUR_GCP_PROJECT_ID
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR_GCP_PROJECT_ID
```

---

## 2. Least-Privilege IAM Roles

Grant only the data/AI roles required for your developer identity (avoid `roles/owner` or `roles/editor` on shared projects):

| Role | Purpose |
| :--- | :--- |
| `roles/storage.objectAdmin` (scoped to `GCS_BUCKET`) | Read/write `raw/`, `clean/`, `docs/` objects |
| `roles/bigquery.dataEditor` (scoped to `fixdesk`, `fixdesk_sandbox`, `fixdesk_vectors` datasets) | Load Parquet, manage tables & vector indexes, preview sandbox fixes |
| `roles/bigquery.jobUser` | Execute dry-run & cost-capped BigQuery queries |
| `roles/aiplatform.user` | Call Vertex AI Gemini (`generate_content`, `embed_content`) |

---

## 3. Print-Only Provisioning Command Generator

To generate exact `gcloud` and `bq` commands for your project without executing anything automatically:

```bash
.venv/bin/python scripts/gcp_setup.py --project-id YOUR_GCP_PROJECT_ID --bucket YOUR_UNIQUE_BUCKET
```

---

## 4. Manual Provisioning Steps (US Multi-Region / `us-central1`)

```bash
export GCP_PROJECT_ID="your-gcp-project-id"
export GCS_BUCKET="${GCP_PROJECT_ID}-fixdesk-data"
export GCP_REGION="us-central1"
export GCP_MULTI_REGION="US"

# 1. Enable required APIs only (no Cloud Run, Compute Engine, Cloud SQL, or Dataproc)
gcloud services enable \
  bigquery.googleapis.com \
  storage.googleapis.com \
  aiplatform.googleapis.com \
  --project="${GCP_PROJECT_ID}"

# 2. Create US multi-region GCS bucket with uniform bucket-level access
gcloud storage buckets create "gs://${GCS_BUCKET}" \
  --project="${GCP_PROJECT_ID}" \
  --location="${GCP_MULTI_REGION}" \
  --uniform-bucket-level-access

# 3. Create US multi-region BigQuery datasets
bq --project_id="${GCP_PROJECT_ID}" mk --dataset --location="${GCP_MULTI_REGION}" "${GCP_PROJECT_ID}:fixdesk"
bq --project_id="${GCP_PROJECT_ID}" mk --dataset --location="${GCP_MULTI_REGION}" "${GCP_PROJECT_ID}:fixdesk_sandbox"
bq --project_id="${GCP_PROJECT_ID}" mk --dataset --location="${GCP_MULTI_REGION}" "${GCP_PROJECT_ID}:fixdesk_vectors"
```

---

## 5. Enable Hybrid GCP Mode in `.env`

```env
GCP_PROJECT_ID=your-gcp-project-id
GCP_REGION=us-central1
GCP_MULTI_REGION=US
GCS_BUCKET=your-gcp-project-id-fixdesk-data

STORAGE_BACKEND=gcp
VECTOR_BACKEND=gcp
FILE_STORE_BACKEND=gcp
LLM_BACKEND=vertexai
EMBEDDING_BACKEND=vertexai
DOCUMENT_RAG_BACKEND=default

BQ_DATASET=fixdesk
BQ_SANDBOX_DATASET=fixdesk_sandbox
BQ_VECTOR_DATASET=fixdesk_vectors
BQ_MAX_BYTES_BILLED=104857600
AI_DAILY_REQUEST_LIMIT=500
AI_DAILY_TOKEN_LIMIT=500000
AI_BUDGET_WARN_RATIO=0.8
```

Verify configuration safely with:

```bash
.venv/bin/python scripts/gcp_inventory.py
```
