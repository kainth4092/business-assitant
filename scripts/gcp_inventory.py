"""
Read-Only GCP Resource Inventory & Print-Only Cost Guard Helper (`scripts/gcp_inventory.py`).
Safely inspects active Fixdesk backend flags, ADC readiness, AI daily budget,
and (if ADC + GCP_PROJECT_ID exist) reads GCS bucket & BigQuery dataset inventories.
Never creates, modifies, or deletes any cloud resources.
"""

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv()

from backend.cloud.auth import check_adc_status, load_adc_credentials
from backend.cloud.budget import get_budget_status
from backend.cloud.config import (
    get_bq_dataset,
    get_bq_max_bytes_billed,
    get_bq_sandbox_dataset,
    get_bq_vector_dataset,
    get_embedding_backend,
    get_file_store_backend,
    get_gcp_multi_region,
    get_gcp_project_id,
    get_gcp_region,
    get_gcs_bucket,
    get_llm_backend,
    get_storage_backend,
    get_vector_backend,
)


def collect_inventory() -> dict:
    adc = check_adc_status()
    budget = get_budget_status()
    project_id = get_gcp_project_id() or adc.get("project_id") or ""
    bucket_name = get_gcs_bucket()

    report = {
        "backends": {
            "STORAGE_BACKEND": get_storage_backend(),
            "VECTOR_BACKEND": get_vector_backend(),
            "FILE_STORE_BACKEND": get_file_store_backend(),
            "LLM_BACKEND": get_llm_backend(),
            "EMBEDDING_BACKEND": get_embedding_backend(),
        },
        "gcp_config": {
            "GCP_PROJECT_ID": project_id or None,
            "GCP_REGION": get_gcp_region(),
            "GCP_MULTI_REGION": get_gcp_multi_region(),
            "GCS_BUCKET": bucket_name or None,
            "BQ_DATASET": get_bq_dataset(),
            "BQ_SANDBOX_DATASET": get_bq_sandbox_dataset(),
            "BQ_VECTOR_DATASET": get_bq_vector_dataset(),
            "BQ_MAX_BYTES_BILLED": get_bq_max_bytes_billed(),
        },
        "adc": adc,
        "ai_budget": budget,
        "gcs": {"checked": False, "objects_by_prefix": {}},
        "bigquery": {"checked": False, "datasets": {}},
    }

    if not adc.get("adc_ready") or not project_id:
        report["note"] = "ADC or GCP_PROJECT_ID missing; skipped live cloud read-only inspection."
        return report

    creds, _ = load_adc_credentials(require_project=True)

    # Read-only GCS inspection
    if bucket_name:
        try:
            from google.cloud import storage

            sc = storage.Client(project=project_id, credentials=creds)
            bucket = sc.lookup_bucket(bucket_name)
            if bucket is None:
                report["gcs"] = {"checked": True, "bucket_exists": False, "bucket": bucket_name}
            else:
                counts = {}
                for prefix in ("raw/", "clean/", "docs/"):
                    counts[prefix] = sum(1 for _ in sc.list_blobs(bucket_name, prefix=prefix))
                report["gcs"] = {
                    "checked": True,
                    "bucket_exists": True,
                    "bucket": bucket_name,
                    "location": getattr(bucket, "location", None),
                    "objects_by_prefix": counts,
                }
        except Exception as exc:
            report["gcs"] = {"checked": True, "error": str(exc)}

    # Read-only BigQuery dataset/table inspection
    try:
        from google.cloud import bigquery

        bq = bigquery.Client(project=project_id, credentials=creds)
        ds_info = {}
        for ds_name in (get_bq_dataset(), get_bq_sandbox_dataset(), get_bq_vector_dataset()):
            ds_ref = f"{project_id}.{ds_name}"
            try:
                ds_obj = bq.get_dataset(ds_ref)
                tables = []
                for t in bq.list_tables(ds_ref):
                    tbl = bq.get_table(t.reference)
                    tables.append(
                        {
                            "table": t.table_id,
                            "num_rows": int(getattr(tbl, "num_rows", 0) or 0),
                            "num_bytes": int(getattr(tbl, "num_bytes", 0) or 0),
                        }
                    )
                ds_info[ds_name] = {
                    "exists": True,
                    "location": ds_obj.location,
                    "tables": tables,
                }
            except Exception:
                ds_info[ds_name] = {"exists": False, "tables": []}
        report["bigquery"] = {"checked": True, "datasets": ds_info}
    except Exception as exc:
        report["bigquery"] = {"checked": True, "error": str(exc)}

    return report


def main() -> None:
    report = collect_inventory()
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
