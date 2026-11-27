"""
Print-Only GCP Setup Command Generator (`scripts/gcp_setup.py`).
Prints exact, copy-pasteable `gcloud` and `bq` commands for Fixdesk Hybrid GCP setup.
NEVER executes cloud mutations or creates billable resources on its own.
"""

import argparse
import os
from dotenv import load_dotenv

load_dotenv()


def render_setup_commands(
    project_id: str,
    bucket_name: str,
    region: str = "us-central1",
    multi_region: str = "US",
    bq_dataset: str = "fixdesk",
    bq_sandbox_dataset: str = "fixdesk_sandbox",
    bq_vector_dataset: str = "fixdesk_vectors",
) -> str:
    lines = [
        "# =============================================================================",
        "# Fixdesk Hybrid GCP Setup Commands (PRINT-ONLY — review before running)",
        "# =============================================================================",
        f'export GCP_PROJECT_ID="{project_id}"',
        f'export GCS_BUCKET="{bucket_name}"',
        f'export GCP_REGION="{region}"',
        f'export GCP_MULTI_REGION="{multi_region}"',
        "",
        "# 1. Authenticate via Application Default Credentials (NO service account keys)",
        "gcloud auth login",
        'gcloud config set project "${GCP_PROJECT_ID}"',
        "gcloud auth application-default login",
        'gcloud auth application-default set-quota-project "${GCP_PROJECT_ID}"',
        "",
        "# 2. Enable only required APIs (BigQuery, GCS, Vertex AI)",
        "gcloud services enable \\",
        "  bigquery.googleapis.com \\",
        "  storage.googleapis.com \\",
        "  aiplatform.googleapis.com \\",
        '  --project="${GCP_PROJECT_ID}"',
        "",
        "# 3. Create US multi-region Cloud Storage bucket (uniform access)",
        'gcloud storage buckets create "gs://${GCS_BUCKET}" \\',
        '  --project="${GCP_PROJECT_ID}" \\',
        '  --location="${GCP_MULTI_REGION}" \\',
        "  --uniform-bucket-level-access",
        "",
        "# 4. Create BigQuery datasets in US multi-region",
        f'bq --project_id="${{GCP_PROJECT_ID}}" mk --dataset --location="${{GCP_MULTI_REGION}}" "${{GCP_PROJECT_ID}}:{bq_dataset}"',
        f'bq --project_id="${{GCP_PROJECT_ID}}" mk --dataset --location="${{GCP_MULTI_REGION}}" "${{GCP_PROJECT_ID}}:{bq_sandbox_dataset}"',
        f'bq --project_id="${{GCP_PROJECT_ID}}" mk --dataset --location="${{GCP_MULTI_REGION}}" "${{GCP_PROJECT_ID}}:{bq_vector_dataset}"',
        "",
        "# 5. Verify ADC & resource inventory (read-only)",
        ".venv/bin/python scripts/gcp_inventory.py",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Print-only GCP setup command generator for Fixdesk.")
    parser.add_argument(
        "--project-id",
        default=os.environ.get("GCP_PROJECT_ID", "YOUR_GCP_PROJECT_ID") or "YOUR_GCP_PROJECT_ID",
    )
    parser.add_argument(
        "--bucket",
        default=os.environ.get("GCS_BUCKET", "YOUR_FIXDESK_BUCKET") or "YOUR_FIXDESK_BUCKET",
    )
    parser.add_argument("--region", default=os.environ.get("GCP_REGION", "us-central1") or "us-central1")
    parser.add_argument("--multi-region", default=os.environ.get("GCP_MULTI_REGION", "US") or "US")
    args = parser.parse_args()

    print(
        render_setup_commands(
            project_id=args.project_id,
            bucket_name=args.bucket,
            region=args.region,
            multi_region=args.multi_region,
        )
    )


if __name__ == "__main__":
    main()
