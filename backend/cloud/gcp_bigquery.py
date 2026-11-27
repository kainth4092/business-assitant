"""
BigQuery SalesStore Implementation (`STORAGE_BACKEND=gcp`).
Provides cost-guarded read-only analytics (`query_sales`), Parquet load jobs,
quality report & schema metadata tables, and isolated Support Desk sandbox previews
in `BQ_SANDBOX_DATASET`.
"""

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.cloud.auth import load_adc_credentials
from backend.cloud.config import (
    get_bq_dataset,
    get_bq_max_bytes_billed,
    get_bq_sandbox_dataset,
    get_gcp_multi_region,
    get_gcp_project_id,
)
from backend.cloud.interfaces import SalesStore
from backend.cloud.sql_guard import adapt_dml_for_bigquery, rewrite_sql_for_bigquery

logger = logging.getLogger("FixdeskBigQuery")


def _json_safe_value(val: Any) -> Any:
    if isinstance(val, Decimal) or type(val).__name__ == "Decimal":
        return float(val)
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return val


def _json_safe_row(row: Any) -> Dict[str, Any]:
    return {k: _json_safe_value(v) for k, v in dict(row).items()}


def _bq_type_is_numeric(field_type: str) -> bool:
    return field_type.upper() in ("INT64", "INTEGER", "FLOAT64", "FLOAT", "NUMERIC", "BIGNUMERIC")


def _bq_type_is_categorical(field_type: str) -> bool:
    return field_type.upper() in ("STRING",)


class BigQuerySalesStore(SalesStore):
    """BigQuery implementation for analytics `sales`, `quality_reports`, `schema_metadata`, and sandbox."""

    backend_name = "gcp"

    def __init__(
        self,
        project_id: Optional[str] = None,
        dataset: Optional[str] = None,
        sandbox_dataset: Optional[str] = None,
        max_bytes_billed: Optional[int] = None,
        client: Optional[Any] = None,
    ):
        self.project_id = (project_id or get_gcp_project_id()).strip()
        self.dataset = (dataset or get_bq_dataset()).strip()
        self.sandbox_dataset = (sandbox_dataset or get_bq_sandbox_dataset()).strip()
        self.max_bytes_billed = (
            max_bytes_billed if max_bytes_billed is not None else get_bq_max_bytes_billed()
        )
        self._client = client

    def sql_dialect(self) -> str:
        return "bigquery"

    def _get_client(self):
        if self._client is not None:
            return self._client
        from google.cloud import bigquery

        creds, resolved_project = load_adc_credentials(require_project=True)
        if not self.project_id:
            self.project_id = resolved_project
        self._client = bigquery.Client(project=self.project_id, credentials=creds)
        return self._client

    def _resolve_project(self) -> str:
        if self.project_id:
            return self.project_id
        client = self._get_client()
        self.project_id = getattr(client, "project", "") or get_gcp_project_id()
        if not self.project_id:
            raise ValueError("GCP_PROJECT_ID must be configured for BigQuery operations.")
        return self.project_id

    def _ensure_dataset(self, dataset_id: str) -> None:
        from google.cloud import bigquery

        client = self._get_client()
        project = self._resolve_project()
        ds_ref = bigquery.Dataset(f"{project}.{dataset_id}")
        ds_ref.location = get_gcp_multi_region()
        client.create_dataset(ds_ref, exists_ok=True)

    def _run_cost_guarded_query(
        self,
        sql: str,
        dataset_id: str,
        query_parameters: Optional[List[Any]] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        from google.cloud import bigquery

        client = self._get_client()
        project = self._resolve_project()
        default_ds = f"{project}.{dataset_id}"

        dry_cfg = bigquery.QueryJobConfig(
            dry_run=True,
            use_query_cache=False,
            default_dataset=default_ds,
            query_parameters=query_parameters or [],
        )
        dry_job = client.query(sql, job_config=dry_cfg)
        bytes_est = int(getattr(dry_job, "total_bytes_processed", 0) or 0)
        if bytes_est > self.max_bytes_billed:
            raise ValueError(
                f"Security/cost violation: BigQuery dry-run estimated {bytes_est} bytes, "
                f"which exceeds BQ_MAX_BYTES_BILLED ({self.max_bytes_billed} bytes)."
            )

        run_cfg = bigquery.QueryJobConfig(
            maximum_bytes_billed=self.max_bytes_billed,
            use_query_cache=use_cache,
            default_dataset=default_ds,
            query_parameters=query_parameters or [],
        )
        job = client.query(sql, job_config=run_cfg)
        rows = [_json_safe_row(r) for r in job.result()]
        return {
            "rows": rows,
            "dry_run_bytes": bytes_est,
            "bytes_billed": int(getattr(job, "total_bytes_billed", bytes_est) or 0),
        }

    def query_sales(self, sql_query: str) -> Dict[str, Any]:
        try:
            project = self._resolve_project()
            bq_sql = rewrite_sql_for_bigquery(sql_query, project_id=project, dataset=self.dataset)
        except Exception as ve:
            return {"status": "ERROR", "error": str(ve), "data": [], "row_count": 0}

        try:
            res = self._run_cost_guarded_query(bq_sql, dataset_id=self.dataset, use_cache=True)
            rows = res["rows"]
            return {
                "status": "SUCCESS",
                "query_executed": bq_sql,
                "row_count": len(rows),
                "data": rows,
                "dry_run_bytes": res["dry_run_bytes"],
                "bytes_billed": res["bytes_billed"],
                "backend": "gcp",
            }
        except Exception as e:
            logger.error(f"Error executing BigQuery sales query: {e}")
            return {
                "status": "ERROR",
                "error": f"BigQuery error: {str(e)}",
                "query_attempted": bq_sql,
                "data": [],
                "row_count": 0,
            }

    def get_data_quality_report(self) -> Dict[str, Any]:
        try:
            project = self._resolve_project()
            sql = (
                f"SELECT report_id, raw_rows, cleaned_rows, duplicates_removed, report_data, created_at "
                f"FROM `{project}.{self.dataset}.quality_reports` "
                f"ORDER BY created_at DESC LIMIT 1"
            )
            res = self._run_cost_guarded_query(sql, dataset_id=self.dataset, use_cache=True)
            rows = res["rows"]
            if rows and rows[0].get("report_data"):
                row = rows[0]
                report = row["report_data"]
                if isinstance(report, str):
                    report = json.loads(report)
                return {
                    "status": "SUCCESS",
                    "report": report,
                    "report_id": row.get("report_id"),
                    "created_at": str(row.get("created_at")),
                }
        except Exception as bq_err:
            logger.warning(f"Could not read quality report from BigQuery: {bq_err}")

        report_file = os.environ.get("DATA_QUALITY_REPORT", "data/data_quality_report.json")
        if os.path.exists(report_file):
            try:
                with open(report_file, "r", encoding="utf-8") as f:
                    return {"status": "SUCCESS", "report": json.load(f)}
            except Exception as exc:
                return {"status": "ERROR", "error": str(exc)}
        return {
            "status": "ERROR",
            "error": "Data quality report not found in BigQuery or local cache. Run PySpark pipeline first.",
        }

    def get_schema_metadata(self) -> Dict[str, Any]:
        try:
            project = self._resolve_project()
            sql = (
                f"SELECT dataset_name, table_name, row_count, column_count, columns_info "
                f"FROM `{project}.{self.dataset}.schema_metadata` "
                f"ORDER BY created_at DESC LIMIT 1"
            )
            res = self._run_cost_guarded_query(sql, dataset_id=self.dataset, use_cache=True)
            rows = res["rows"]
            if rows and rows[0].get("columns_info"):
                sm_row = rows[0]
                cols = sm_row["columns_info"]
                if isinstance(cols, str):
                    cols = json.loads(cols)
                return {
                    "dataset_name": sm_row.get("dataset_name"),
                    "table_name": sm_row.get("table_name", "sales"),
                    "row_count": int(sm_row.get("row_count", 0) or 0),
                    "columns": cols,
                    "numeric_columns": [c["name"] for c in cols if c.get("is_numeric")],
                    "categorical_columns": [c["name"] for c in cols if c.get("is_categorical")],
                }
        except Exception as err:
            logger.warning(f"Could not read schema_metadata table from BigQuery: {err}")

        try:
            client = self._get_client()
            project = self._resolve_project()
            table = client.get_table(f"{project}.{self.dataset}.sales")
            columns = [
                {
                    "name": f.name,
                    "type": f.field_type,
                    "is_numeric": _bq_type_is_numeric(f.field_type),
                    "is_categorical": _bq_type_is_categorical(f.field_type),
                }
                for f in table.schema
            ]
            return {
                "table_name": "sales",
                "row_count": int(getattr(table, "num_rows", 0) or 0),
                "columns": columns,
                "numeric_columns": [c["name"] for c in columns if c["is_numeric"]],
                "categorical_columns": [c["name"] for c in columns if c["is_categorical"]],
            }
        except Exception as err:
            logger.warning(f"Could not inspect BigQuery sales schema: {err}")

        meta_path = Path(__file__).resolve().parents[2] / "data" / "schema_metadata.json"
        if meta_path.exists():
            try:
                return json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"table_name": "sales", "columns": [], "numeric_columns": [], "categorical_columns": []}

    def get_sales_count(self) -> int:
        try:
            project = self._resolve_project()
            sql = f"SELECT COUNT(*) AS cnt FROM `{project}.{self.dataset}.sales`"
            res = self._run_cost_guarded_query(sql, dataset_id=self.dataset, use_cache=True)
            if res["rows"]:
                return int(res["rows"][0]["cnt"])
        except Exception:
            pass
        return 0

    def get_top_categorical_values(self, column: str, limit: int = 2) -> List[str]:
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", column):
            return []
        try:
            from google.cloud import bigquery

            project = self._resolve_project()
            safe_limit = max(1, min(int(limit), 10))
            sql = (
                f"SELECT `{column}` AS val, COUNT(*) AS cnt "
                f"FROM `{project}.{self.dataset}.sales` "
                f"WHERE `{column}` IS NOT NULL AND `{column}` != 'Unknown' "
                f"GROUP BY `{column}` ORDER BY cnt DESC LIMIT @lim"
            )
            res = self._run_cost_guarded_query(
                sql,
                dataset_id=self.dataset,
                query_parameters=[bigquery.ScalarQueryParameter("lim", "INT64", safe_limit)],
            )
            return [str(r["val"]) for r in res["rows"]]
        except Exception:
            return []

    def run_data_quality_checks(self, table_name: str = "sales") -> Dict[str, Any]:
        is_sandbox = "sandbox" in table_name
        target_ds = self.sandbox_dataset if is_sandbox else self.dataset
        target_tbl = "sales_sandbox" if is_sandbox else "sales"
        try:
            client = self._get_client()
            project = self._resolve_project()
            fq_table = f"{project}.{target_ds}.{target_tbl}"
            table = client.get_table(fq_table)
            cols = {f.name: f.field_type for f in table.schema}

            cnt_res = self._run_cost_guarded_query(
                f"SELECT COUNT(*) AS total_rows FROM `{fq_table}`", dataset_id=target_ds
            )
            total_rows = int(cnt_res["rows"][0]["total_rows"]) if cnt_res["rows"] else 0

            cat_cols = [
                c
                for c, dt in cols.items()
                if _bq_type_is_categorical(dt)
                and c not in ("created_at", "id", "review_id", "review_text")
            ]
            primary_cat = cat_cols[0] if cat_cols else None

            cat_distribution = {}
            inconsistent_labels = []
            if primary_cat:
                dist_res = self._run_cost_guarded_query(
                    f"SELECT `{primary_cat}` AS label, COUNT(*) AS count "
                    f"FROM `{fq_table}` WHERE `{primary_cat}` IS NOT NULL "
                    f"GROUP BY `{primary_cat}` ORDER BY count DESC LIMIT 10",
                    dataset_id=target_ds,
                )
                cat_distribution = {str(r["label"]): int(r["count"]) for r in dist_res["rows"]}
                inconsistent_labels = [
                    k
                    for k in cat_distribution.keys()
                    if k != k.strip()
                    or (
                        k != k.upper()
                        and k in ("lf", "low fat", "reg", "ps5", "xbox", "playstation-5")
                    )
                ]

            null_metrics = {}
            for c in list(cols.keys())[:5]:
                n_res = self._run_cost_guarded_query(
                    f"SELECT COUNT(*) AS null_cnt FROM `{fq_table}` WHERE `{c}` IS NULL",
                    dataset_id=target_ds,
                )
                null_metrics[c] = int(n_res["rows"][0]["null_cnt"]) if n_res["rows"] else 0

            num_cols = [c for c, dt in cols.items() if _bq_type_is_numeric(dt)]
            outliers_found = 0
            if num_cols:
                primary_num = num_cols[0]
                o_res = self._run_cost_guarded_query(
                    f"SELECT COUNT(*) AS cnt FROM `{fq_table}` WHERE `{primary_num}` <= 0",
                    dataset_id=target_ds,
                )
                outliers_found = int(o_res["rows"][0]["cnt"]) if o_res["rows"] else 0

            findings = {
                "table_audited": f"{target_ds}.{target_tbl}",
                "total_records": total_rows,
                "inconsistent_fat_labels": {
                    "detected": len(inconsistent_labels) > 0,
                    "problematic_labels": inconsistent_labels,
                    "full_distribution": cat_distribution,
                },
                "inconsistent_labels": {
                    "detected": len(inconsistent_labels) > 0,
                    "target_column": primary_cat,
                    "problematic_labels": inconsistent_labels,
                    "full_distribution": cat_distribution,
                },
                "null_values": null_metrics,
                "duplicate_records_found": 0,
                "outliers_found": outliers_found,
                "root_cause": f"Detected {len(inconsistent_labels)} inconsistent label formats in column '{primary_cat or 'category'}'.",
                "recommendation": f"Standardize casing and trim whitespace in column '{primary_cat or 'category'}'.",
            }
            return {"status": "SUCCESS", "findings": findings}
        except Exception as e:
            logger.error(f"BigQuery data quality checks failed: {e}")
            return {"status": "ERROR", "error": str(e)}

    def preview_data_fix(self, sql_patch: str, ticket_id: str) -> Dict[str, Any]:
        from google.cloud import bigquery

        try:
            client = self._get_client()
            project = self._resolve_project()
            self._ensure_dataset(self.sandbox_dataset)

            prod_table = f"{project}.{self.dataset}.sales"
            sandbox_table = f"{project}.{self.sandbox_dataset}.sales_sandbox"

            copy_cfg = bigquery.CopyJobConfig(
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE
            )
            client.copy_table(prod_table, sandbox_table, job_config=copy_cfg).result()

            before_res = self._run_cost_guarded_query(
                f"SELECT COUNT(*) AS total FROM `{sandbox_table}`",
                dataset_id=self.sandbox_dataset,
                use_cache=False,
            )
            before_counts = {"total_rows": int(before_res["rows"][0]["total"])}

            rows_affected = 0
            applied_sql = ""
            if (sql_patch or "").strip():
                applied_sql = adapt_dml_for_bigquery(
                    sql_patch,
                    project_id=project,
                    dataset=self.sandbox_dataset,
                    table_name="sales_sandbox",
                )
                dml_cfg = bigquery.QueryJobConfig(
                    maximum_bytes_billed=self.max_bytes_billed,
                    default_dataset=f"{project}.{self.sandbox_dataset}",
                )
                dml_job = client.query(applied_sql, job_config=dml_cfg)
                dml_job.result()
                rows_affected = int(getattr(dml_job, "num_dml_affected_rows", 0) or 0)

            after_res = self._run_cost_guarded_query(
                f"SELECT COUNT(*) AS total FROM `{sandbox_table}`",
                dataset_id=self.sandbox_dataset,
                use_cache=False,
            )
            after_counts = {"total_rows": int(after_res["rows"][0]["total"])}

            sample_res = self._run_cost_guarded_query(
                f"SELECT * FROM `{sandbox_table}` LIMIT 5",
                dataset_id=self.sandbox_dataset,
                use_cache=False,
            )

            return {
                "status": "SUCCESS",
                "fix_type": "data_issue",
                "target_table": f"{self.sandbox_dataset}.sales_sandbox",
                "rows_affected": rows_affected,
                "before_counts": before_counts,
                "after_counts": after_counts,
                "sample_diff": sample_res["rows"],
                "sql_applied_to_sandbox": applied_sql,
            }
        except Exception as e:
            logger.error(f"Error previewing BigQuery data fix in sandbox: {e}")
            return {"status": "ERROR", "error": str(e)}

    def apply_data_fix(self, sql_patch: str) -> Dict[str, Any]:
        from google.cloud import bigquery

        client = self._get_client()
        project = self._resolve_project()
        prod_table = f"{project}.{self.dataset}.sales"

        before_res = self._run_cost_guarded_query(
            f"SELECT COUNT(*) AS total FROM `{prod_table}`",
            dataset_id=self.dataset,
            use_cache=False,
        )
        before_counts = {"total_rows": int(before_res["rows"][0]["total"])}

        applied_sql = adapt_dml_for_bigquery(
            sql_patch,
            project_id=project,
            dataset=self.dataset,
            table_name="sales",
        )
        dml_cfg = bigquery.QueryJobConfig(
            maximum_bytes_billed=self.max_bytes_billed,
            default_dataset=f"{project}.{self.dataset}",
        )
        dml_job = client.query(applied_sql, job_config=dml_cfg)
        dml_job.result()
        rows_affected = int(getattr(dml_job, "num_dml_affected_rows", 0) or 0)

        after_res = self._run_cost_guarded_query(
            f"SELECT COUNT(*) AS total FROM `{prod_table}`",
            dataset_id=self.dataset,
            use_cache=False,
        )
        after_counts = {"total_rows": int(after_res["rows"][0]["total"])}
        return {
            "before_counts": before_counts,
            "after_counts": after_counts,
            "rows_affected": rows_affected,
            "target_table": f"{self.dataset}.sales",
        }

    def load_sales_from_parquet(
        self,
        parquet_uri_or_path: str,
        schema_metadata: Dict[str, Any],
        quality_report: Dict[str, Any],
        df: Any = None,
    ) -> Dict[str, Any]:
        from google.cloud import bigquery

        client = self._get_client()
        project = self._resolve_project()
        self._ensure_dataset(self.dataset)
        self._ensure_dataset(self.sandbox_dataset)

        prod_table = f"{project}.{self.dataset}.sales"
        sandbox_table = f"{project}.{self.sandbox_dataset}.sales_sandbox"

        load_cfg = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.PARQUET,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            autodetect=True,
        )

        if parquet_uri_or_path.startswith("gs://"):
            source_uri = parquet_uri_or_path
            leaf = source_uri.rstrip("/").rsplit("/", 1)[-1]
            if not source_uri.endswith("*") and (not source_uri.endswith(".parquet") or leaf == "cleaned_sales.parquet"):
                source_uri = f"{source_uri.rstrip('/')}/*.parquet"
            load_job = client.load_table_from_uri(source_uri, prod_table, job_config=load_cfg)
            load_job.result()
        else:
            local_path = Path(parquet_uri_or_path)
            parquet_files = (
                sorted(local_path.glob("*.parquet"))
                if local_path.is_dir()
                else [local_path]
            )
            if not parquet_files:
                raise FileNotFoundError(f"No .parquet files found at '{parquet_uri_or_path}'.")
            for idx, pq_file in enumerate(parquet_files):
                part_cfg = bigquery.LoadJobConfig(
                    source_format=bigquery.SourceFormat.PARQUET,
                    write_disposition=(
                        bigquery.WriteDisposition.WRITE_TRUNCATE
                        if idx == 0
                        else bigquery.WriteDisposition.WRITE_APPEND
                    ),
                    autodetect=True,
                )
                with open(pq_file, "rb") as fh:
                    client.load_table_from_file(fh, prod_table, job_config=part_cfg).result()

        # Mirror production sales to BQ_SANDBOX_DATASET
        copy_cfg = bigquery.CopyJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE
        )
        client.copy_table(prod_table, sandbox_table, job_config=copy_cfg).result()

        # Ensure quality_reports & schema_metadata tables exist and insert latest record
        qr_table_id = f"{project}.{self.dataset}.quality_reports"
        qr_schema = [
            bigquery.SchemaField("report_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("raw_rows", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("cleaned_rows", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("duplicates_removed", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("report_data", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
        ]
        client.create_table(bigquery.Table(qr_table_id, schema=qr_schema), exists_ok=True)

        rec_prof = quality_report.get("records_profile", {})
        now_iso = datetime.now(timezone.utc).isoformat()
        qr_row = {
            "report_id": f"qr_{uuid.uuid4().hex[:12]}",
            "raw_rows": int(rec_prof.get("raw_total_rows", 0)),
            "cleaned_rows": int(rec_prof.get("cleaned_total_rows", 0)),
            "duplicates_removed": int(rec_prof.get("duplicate_rows_removed", 0)),
            "report_data": json.dumps(quality_report),
            "created_at": now_iso,
        }
        client.insert_rows_json(qr_table_id, [qr_row])

        sm_table_id = f"{project}.{self.dataset}.schema_metadata"
        sm_schema = [
            bigquery.SchemaField("dataset_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("table_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("row_count", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("column_count", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("columns_info", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
        ]
        client.create_table(bigquery.Table(sm_table_id, schema=sm_schema), exists_ok=True)

        cols = schema_metadata.get("columns", [])
        sm_row = {
            "dataset_name": schema_metadata.get("dataset_name", "dataset.csv"),
            "table_name": "sales",
            "row_count": int(schema_metadata.get("row_count", 0)),
            "column_count": len(cols),
            "columns_info": json.dumps(cols),
            "created_at": now_iso,
        }
        client.insert_rows_json(sm_table_id, [sm_row])

        return {
            "status": "SUCCESS",
            "rows_loaded": int(schema_metadata.get("row_count", 0)),
            "backend": "gcp",
            "table": prod_table,
            "sandbox_table": sandbox_table,
        }

    def health_check(self) -> Dict[str, Any]:
        try:
            project = self._resolve_project()
            count = self.get_sales_count()
            return {
                "backend": "gcp",
                "database": "connected",
                "project_id": project,
                "dataset": self.dataset,
                "sandbox_dataset": self.sandbox_dataset,
                "sales_records": count,
            }
        except Exception as e:
            return {
                "backend": "gcp",
                "database": f"error: {str(e)}",
                "sales_records": 0,
            }
