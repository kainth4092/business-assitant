# GCP Cost Safety & Quota Guardrails (`COST_NOTES.md`)

Fixdesk uses a **Hybrid Laptop + Cloud Data/AI/Vector** topology to keep cloud spend near zero during development and demos.

---

## 1. Zero Cloud Compute / Always-On Hosting Costs

Fixdesk intentionally **does NOT deploy**:
- Cloud Run services or Cloud Functions
- Google Compute Engine (GCE) VMs or GKE clusters
- Cloud SQL instances (transactional `support_tickets`, `audit_log`, `conversations`, `messages` remain in local PostgreSQL)
- Cloud Dataproc clusters (PySpark runs locally on the laptop via `master="local[*]"`)
- Dedicated GPU endpoints or Vertex AI Vector Search managed index nodes (uses serverless BigQuery Vector Search instead)

---

## 2. Built-In Spend & Quota Protections

### A. BigQuery Query Cost Guards (`backend/cloud/gcp_bigquery.py`, `backend/cloud/sql_guard.py`)
1. **Dry-Run Byte Gate**: Every `query_sales` call first runs `QueryJobConfig(dry_run=True, use_query_cache=False)` to obtain `total_bytes_processed` at **$0 cost**. If the estimate exceeds `BQ_MAX_BYTES_BILLED` (default `104857600` = 100 MiB), the query is rejected before execution.
2. **Hard Billing Cap**: Every BigQuery execution sets `maximum_bytes_billed=BQ_MAX_BYTES_BILLED`, ensuring BigQuery aborts any unexpected scan before billing beyond 100 MiB.
3. **Single-SELECT & Row Cap**: Queries must be a single `SELECT`/`WITH` targeting `BQ_DATASET` tables only (`sales`, `quality_reports`, `schema_metadata`), with `LIMIT <= 100`.
4. **Free Tier & US Multi-Region**: Both `GCS_BUCKET` and BigQuery datasets (`fixdesk`, `fixdesk_sandbox`, `fixdesk_vectors`) default to `US` multi-region, maximizing BigQuery sandbox/free-tier query allowance (1 TiB/month) and GCS free-tier storage.

### B. BigQuery Vector Search vs. Managed Vector Endpoints
- `BigQueryVectorStore` stores 768-D embeddings as `ARRAY<FLOAT64>` and queries via `VECTOR_SEARCH(..., distance_type => 'COSINE')`.
- IVF vector indexes (`CREATE VECTOR INDEX ... OPTIONS(index_type='IVF', distance_type='COSINE')`) require at least 5,000 rows in BigQuery before index build activates; smaller tables run exact cosine scans at negligible byte cost with **zero hourly index-hosting fees**.

### C. Daily Vertex AI / Gemini Request & Token Cap (`backend/cloud/budget.py`)
- Persists daily usage locally in `data/.budget_state.json` (resets automatically at midnight).
- Defaults:
  - `AI_DAILY_REQUEST_LIMIT=500`
  - `AI_DAILY_TOKEN_LIMIT=500000`
  - `AI_BUDGET_WARN_RATIO=0.8` (80% warning surfaced in `GET /status` and rendered as an amber/seal banner in `WorkbenchApp.jsx`)
- Once 100% is reached, `BudgetExceededError` blocks further cloud LLM/embedding calls until the next day.

### D. Codebase Privacy Guard (`projects.yaml`)
- `cloud_index_allowed: false` by default prevents automatic bulk embedding/upload of private source repositories to Vertex AI or BigQuery.

---

## 3. Recommended GCP Billing Budget Alerts

Set a low monthly budget alert (e.g. \$5 / \$10) in **Google Cloud Console → Billing → Budgets & alerts** with notifications at 50%, 90%, and 100% before enabling live GCP backends.
