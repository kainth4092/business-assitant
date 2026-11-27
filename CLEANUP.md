# GCP Resource Cleanup & Teardown Guide (`CLEANUP.md`)

Use these **explicit manual commands** to inspect or tear down GCP resources created for Fixdesk. Fixdesk scripts never auto-delete cloud resources.

---

## 1. Read-Only Inventory Check (Safe)

Before deleting anything, inspect what currently exists using the read-only inventory script:

```bash
.venv/bin/python scripts/gcp_inventory.py
```

---

## 2. Delete BigQuery Datasets (`fixdesk`, `fixdesk_sandbox`, `fixdesk_vectors`)

```bash
export GCP_PROJECT_ID="your-gcp-project-id"

bq rm -r -f -d "${GCP_PROJECT_ID}:fixdesk"
bq rm -r -f -d "${GCP_PROJECT_ID}:fixdesk_sandbox"
bq rm -r -f -d "${GCP_PROJECT_ID}:fixdesk_vectors"
```

---

## 3. Delete Cloud Storage Bucket (`GCS_BUCKET`)

```bash
export GCS_BUCKET="your-fixdesk-bucket"

gcloud storage rm --recursive "gs://${GCS_BUCKET}"
```

*(Or delete individual prefixes only: `gcloud storage rm --recursive "gs://${GCS_BUCKET}/raw"`, `/clean`, `/docs`.)*

---

## 4. Revoke Local ADC Credentials & Clean Local State

```bash
# Revoke local Application Default Credentials if no longer needed
gcloud auth application-default revoke

# Reset local AI budget state & GCS download cache
rm -f data/.budget_state.json
rm -rf /tmp/fixdesk_gcs_cache
```

---

## 5. Switch `.env` Back to Pure Local Mode

```env
STORAGE_BACKEND=local
VECTOR_BACKEND=local
FILE_STORE_BACKEND=local
LLM_BACKEND=auto
EMBEDDING_BACKEND=auto
```
