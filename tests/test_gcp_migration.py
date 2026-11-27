"""
Comprehensive Contract, Security, Cost-Guard, Auth, Budget & Privacy Tests
for Fixdesk Hybrid GCP Migration (`tests/test_gcp_migration.py`).
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from backend.cloud.auth import (
    GcpAuthError,
    ServiceAccountKeyBlockedError,
    check_adc_status,
    load_adc_credentials,
)
from backend.cloud.budget import (
    BudgetExceededError,
    check_budget_available,
    get_budget_status,
    record_ai_usage,
    reset_budget_state,
)
from backend.cloud.factories import (
    get_code_store,
    get_embedding_client,
    get_file_store,
    get_llm_client,
    get_sales_store,
    get_vector_store,
)
from backend.cloud.gcp_bigquery import BigQuerySalesStore
from backend.cloud.gcp_storage import GcsFileStore
from backend.cloud.gcp_vector import BigQueryCodeVectorStore, BigQueryVectorStore
from backend.cloud.interfaces import CloudPrivacyError
from backend.cloud.local_impl import LocalFileStore, PgVectorStore, PostgresSalesStore
from backend.cloud.sql_guard import (
    build_ctas_from_update,
    is_bigquery_sandbox_dml_error,
    rewrite_sql_for_bigquery,
)
from backend.main import app
from project_init.chunker import CodeChunk
from project_init.config import get_project_config
from project_init.indexer import index_project
from project_init.retriever import ask_codebase
from project_init.summarizer import generate_chunk_summary


# ------------------------------------------------------------------------------
# Lightweight In-Memory Fake GCS & BigQuery Clients for Offline Contract Tests
# ------------------------------------------------------------------------------
class _FakeBlob:
    def __init__(self, bucket_store: Dict[str, bytes], name: str):
        self._store = bucket_store
        self.name = name

    def upload_from_string(self, data: bytes) -> None:
        self._store[self.name] = bytes(data)

    def upload_from_filename(self, filename: str) -> None:
        self._store[self.name] = Path(filename).read_bytes()

    def download_as_bytes(self) -> bytes:
        if self.name not in self._store:
            raise FileNotFoundError(self.name)
        return self._store[self.name]

    def download_to_filename(self, filename: str) -> None:
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        Path(filename).write_bytes(self.download_as_bytes())

    def exists(self) -> bool:
        return self.name in self._store


class _FakeBucket:
    def __init__(self, name: str):
        self.name = name
        self.location = "US"
        self.blobs: Dict[str, bytes] = {}

    def blob(self, blob_name: str) -> _FakeBlob:
        return _FakeBlob(self.blobs, blob_name)


class _FakeStorageClient:
    def __init__(self):
        self.buckets: Dict[str, _FakeBucket] = {}

    def bucket(self, name: str) -> _FakeBucket:
        if name not in self.buckets:
            self.buckets[name] = _FakeBucket(name)
        return self.buckets[name]

    def lookup_bucket(self, name: str):
        return self.buckets.get(name)

    def list_blobs(self, bucket_name: str, prefix: str = ""):
        b = self.bucket(bucket_name)
        return [
            _FakeBlob(b.blobs, k)
            for k in sorted(b.blobs.keys())
            if k.startswith(prefix)
        ]


class _FakeBQJob:
    def __init__(self, rows=None, total_bytes_processed=1024, total_bytes_billed=1024, dml_rows=0):
        self._rows = rows or []
        self.total_bytes_processed = total_bytes_processed
        self.total_bytes_billed = total_bytes_billed
        self.num_dml_affected_rows = dml_rows

    def result(self):
        return self._rows


class _FakeBigQueryClient:
    def __init__(self, project: str = "test-gcp-proj", dry_run_bytes: int = 2048):
        self.project = project
        self.dry_run_bytes = dry_run_bytes
        self.queries: List[Dict[str, Any]] = []
        self.load_uri_calls: List[Dict[str, Any]] = []
        self.load_json_calls: List[Dict[str, Any]] = []
        self.copy_calls: List[Dict[str, Any]] = []
        self.insert_json_calls: List[Dict[str, Any]] = []
        self.created_datasets: List[str] = []
        self.created_tables: List[str] = []
        self.query_rows: List[Dict[str, Any]] = [{"item_type": "Dairy", "total_sales": 1200.5}]

    def create_dataset(self, ds_ref, exists_ok=True):
        self.created_datasets.append(str(ds_ref.dataset_id))

    def create_table(self, tbl, exists_ok=True):
        self.created_tables.append(str(tbl.table_id))

    def get_table(self, table_id: str):
        return SimpleNamespace(
            table_id=table_id,
            num_rows=10,
            schema=[
                SimpleNamespace(name="item_type", field_type="STRING"),
                SimpleNamespace(name="item_outlet_sales", field_type="FLOAT64"),
            ],
        )

    def copy_table(self, src, dst, job_config=None):
        self.copy_calls.append({"src": src, "dst": dst})
        return _FakeBQJob()

    def load_table_from_uri(self, source_uri, destination, job_config=None):
        self.load_uri_calls.append({"source_uri": source_uri, "destination": destination, "job_config": job_config})
        return _FakeBQJob()

    def load_table_from_json(self, rows, destination, job_config=None):
        self.load_json_calls.append({"rows": rows, "destination": destination})
        return _FakeBQJob()

    def insert_rows_json(self, table, rows):
        self.insert_json_calls.append({"table": table, "rows": rows})
        return []

    def query(self, sql: str, job_config=None):
        is_dry = bool(getattr(job_config, "dry_run", False))
        self.queries.append({"sql": sql, "dry_run": is_dry, "job_config": job_config})
        if is_dry:
            return _FakeBQJob(total_bytes_processed=self.dry_run_bytes)
        if "COUNT(*) AS total" in sql or "COUNT(*) AS total_rows" in sql:
            return _FakeBQJob(rows=[{"total": 5, "total_rows": 5}])
        if "COUNT(*) AS cnt" in sql:
            return _FakeBQJob(rows=[{"cnt": 5}])
        if sql.strip().upper().startswith("UPDATE"):
            return _FakeBQJob(dml_rows=3)
        return _FakeBQJob(rows=self.query_rows)


# ------------------------------------------------------------------------------
# 1. Factory Selection & Interface Contracts
# ------------------------------------------------------------------------------
def test_factory_selection_switches_cleanly(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("VECTOR_BACKEND", "local")
    monkeypatch.setenv("FILE_STORE_BACKEND", "local")
    assert isinstance(get_sales_store(), PostgresSalesStore)
    assert isinstance(get_vector_store(), PgVectorStore)
    assert isinstance(get_file_store(), LocalFileStore)

    monkeypatch.setenv("STORAGE_BACKEND", "gcp")
    monkeypatch.setenv("VECTOR_BACKEND", "gcp")
    monkeypatch.setenv("FILE_STORE_BACKEND", "gcp")
    monkeypatch.setenv("GCS_BUCKET", "test-fixdesk-bucket")
    monkeypatch.setenv("GCP_PROJECT_ID", "test-proj")

    assert isinstance(get_sales_store(), BigQuerySalesStore)
    assert isinstance(get_vector_store(), BigQueryVectorStore)
    assert isinstance(get_file_store(), GcsFileStore)


# ------------------------------------------------------------------------------
# 2. FileStore Contract Tests (LocalFileStore vs GcsFileStore)
# ------------------------------------------------------------------------------
def test_file_store_contract_local_and_gcs(tmp_path, monkeypatch):
    local_root = tmp_path / "local_fs"
    local_store = LocalFileStore(base_dir=str(local_root))
    fake_gcs_client = _FakeStorageClient()
    gcs_store = GcsFileStore(bucket_name="unit-bucket", project_id="test-proj", client=fake_gcs_client)

    for store in (local_store, gcs_store):
        uri = store.save_bytes("raw", "orders.csv", b"id,amount\n1,42.5\n")
        assert store.exists(uri)
        assert store.read_bytes(uri) == b"id,amount\n1,42.5\n"
        listed = store.list_files("raw", extensions=(".csv",))
        assert any("orders.csv" in item for item in listed)

        local_copy = store.ensure_local_copy(uri, cache_dir=str(tmp_path / "cache"))
        assert Path(local_copy).read_bytes() == b"id,amount\n1,42.5\n"

    # Parquet folder upload skips Spark _SUCCESS marker on GCS
    pq_dir = tmp_path / "cleaned_sales.parquet"
    pq_dir.mkdir()
    (pq_dir / "_SUCCESS").write_text("", encoding="utf-8")
    (pq_dir / "part-00000.parquet").write_bytes(b"PAR1")

    gcs_pq_uri = gcs_store.upload_from_local(str(pq_dir), "clean", remote_name="cleaned_sales.parquet")
    assert gcs_pq_uri == "gs://unit-bucket/clean/cleaned_sales.parquet"
    clean_objs = gcs_store.list_files("clean")
    assert clean_objs == ["gs://unit-bucket/clean/cleaned_sales.parquet/part-00000.parquet"]


# ------------------------------------------------------------------------------
# 3. ADC-Only Auth Security Tests
# ------------------------------------------------------------------------------
def test_auth_blocks_service_account_key_files(tmp_path, monkeypatch):
    sa_file = tmp_path / "sa-key.json"
    sa_file.write_text(
        json.dumps({"type": "service_account", "project_id": "p", "private_key": "-----BEGIN PRIVATE KEY-----"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(sa_file))
    with pytest.raises(ServiceAccountKeyBlockedError):
        load_adc_credentials()

    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.setenv("GCP_PROJECT_ID", "demo-proj")

    class _MockSACreds:
        pass

    _MockSACreds.__module__ = "google.oauth2.service_account"
    monkeypatch.setattr("google.auth.default", lambda **kwargs: (_MockSACreds(), "demo-proj"))
    with pytest.raises(ServiceAccountKeyBlockedError):
        load_adc_credentials()


def test_auth_missing_adc_error_and_valid_adc(monkeypatch):
    from google.auth.exceptions import DefaultCredentialsError

    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.setenv("GCP_PROJECT_ID", "demo-proj")
    monkeypatch.setattr("google.auth.default", lambda **kwargs: (_ for _ in ()).throw(DefaultCredentialsError("missing")))
    with pytest.raises(GcpAuthError, match="gcloud auth application-default login"):
        load_adc_credentials()

    status_err = check_adc_status()
    assert status_err["adc_ready"] is False

    fake_creds = SimpleNamespace(quota_project_id="demo-proj")
    monkeypatch.setattr("google.auth.default", lambda **kwargs: (fake_creds, "demo-proj"))
    creds, proj = load_adc_credentials()
    assert proj == "demo-proj"
    assert creds is fake_creds
    assert check_adc_status()["adc_ready"] is True


# ------------------------------------------------------------------------------
# 4. BigQuery SalesStore Cost Safety, SQL Guard & Support Sandbox Tests
# ------------------------------------------------------------------------------
def test_bigquery_sql_guard_and_cost_limits():
    bq_sql = rewrite_sql_for_bigquery(
        'SELECT "item_type", round(sum("item_outlet_sales")::numeric, 2) FROM sales GROUP BY "item_type" LIMIT 500',
        project_id="my-proj",
        dataset="fixdesk",
    )
    assert "`my-proj.fixdesk.sales`" in bq_sql
    assert "`item_type`" in bq_sql
    assert "CAST(" in bq_sql
    assert "LIMIT 100" in bq_sql

    with pytest.raises(ValueError, match="must target dataset"):
        rewrite_sql_for_bigquery("SELECT * FROM other_proj.secret_ds.users", "my-proj", "fixdesk")

    with pytest.raises(ValueError, match="INFORMATION_SCHEMA"):
        rewrite_sql_for_bigquery("SELECT * FROM INFORMATION_SCHEMA.TABLES", "my-proj", "fixdesk")

    # Dry-run exceeds BQ_MAX_BYTES_BILLED -> rejected before running
    expensive_client = _FakeBigQueryClient(project="my-proj", dry_run_bytes=500_000_000)
    bq_store = BigQuerySalesStore(
        project_id="my-proj",
        dataset="fixdesk",
        sandbox_dataset="fixdesk_sandbox",
        max_bytes_billed=104_857_600,
        client=expensive_client,
    )
    blocked = bq_store.query_sales("SELECT item_type FROM sales")
    assert blocked["status"] == "ERROR"
    assert "BQ_MAX_BYTES_BILLED" in blocked["error"]
    assert len(expensive_client.queries) == 1  # dry-run only; real query never ran

    # Safe query passes dry-run and executes with maximum_bytes_billed
    ok_client = _FakeBigQueryClient(project="my-proj", dry_run_bytes=4096)
    ok_store = BigQuerySalesStore(
        project_id="my-proj",
        dataset="fixdesk",
        sandbox_dataset="fixdesk_sandbox",
        max_bytes_billed=104_857_600,
        client=ok_client,
    )
    res = ok_store.query_sales("SELECT item_type FROM sales")
    assert res["status"] == "SUCCESS"
    assert res["backend"] == "gcp"
    assert len(ok_client.queries) == 2
    assert ok_client.queries[0]["dry_run"] is True
    assert ok_client.queries[1]["dry_run"] is False
    assert ok_client.queries[1]["job_config"].maximum_bytes_billed == 104_857_600


def test_bigquery_load_parquet_and_sandbox_isolation():
    fake_bq = _FakeBigQueryClient(project="my-proj")
    store = BigQuerySalesStore(
        project_id="my-proj",
        dataset="fixdesk",
        sandbox_dataset="fixdesk_sandbox",
        client=fake_bq,
    )
    load_res = store.load_sales_from_parquet(
        parquet_uri_or_path="gs://my-bucket/clean/cleaned_sales.parquet",
        schema_metadata={"dataset_name": "sales.csv", "row_count": 5, "columns": [{"name": "item_type", "type": "TEXT"}]},
        quality_report={"records_profile": {"raw_total_rows": 6, "cleaned_total_rows": 5, "duplicate_rows_removed": 1}},
    )
    assert load_res["status"] == "SUCCESS"
    assert fake_bq.load_uri_calls[0]["source_uri"] == "gs://my-bucket/clean/cleaned_sales.parquet/*.parquet"
    assert fake_bq.copy_calls[0]["dst"] == "my-proj.fixdesk_sandbox.sales_sandbox"
    # quality_reports & schema_metadata must use batch load jobs (not streaming insert_rows_json)
    assert len(fake_bq.insert_json_calls) == 0
    assert len(fake_bq.load_json_calls) == 2

    # Preview runs strictly on fixdesk_sandbox, never production fixdesk
    preview = store.preview_data_fix(
        sql_patch='UPDATE sales SET "item_type" = TRIM(UPPER("item_type")) WHERE "item_type" IS NOT NULL',
        ticket_id="tkt_1",
    )
    assert preview["status"] == "SUCCESS"
    assert preview["target_table"] == "fixdesk_sandbox.sales_sandbox"
    assert "`my-proj.fixdesk_sandbox.sales_sandbox`" in preview["sql_applied_to_sandbox"]
    assert "`my-proj.fixdesk.sales`" not in preview["sql_applied_to_sandbox"]


def test_bigquery_sandbox_dml_fallback_to_ctas():
    assert is_bigquery_sandbox_dml_error(
        RuntimeError("403 Billing has not been enabled for this project. DML queries are not allowed in the free tier.")
    )
    assert is_bigquery_sandbox_dml_error(
        RuntimeError("Streaming insert is not allowed in the free tier")
    )
    assert not is_bigquery_sandbox_dml_error(RuntimeError("Syntax error at line 1"))

    count_sql, ctas_sql = build_ctas_from_update(
        sql_patch='UPDATE sales SET "item_type" = TRIM(UPPER("item_type")) WHERE "item_type" IS NOT NULL',
        table_columns=["item_type", "item_outlet_sales"],
        source_fq_table="my-proj.fixdesk.sales",
        target_fq_table="my-proj.fixdesk_sandbox.sales_sandbox",
    )
    assert "SELECT COUNT(*) AS affected FROM `my-proj.fixdesk.sales` WHERE `item_type` IS NOT NULL" == count_sql
    assert ctas_sql.startswith("CREATE OR REPLACE TABLE `my-proj.fixdesk_sandbox.sales_sandbox` AS SELECT ")
    assert "CASE WHEN (`item_type` IS NOT NULL) THEN (TRIM(UPPER(`item_type`))) ELSE `item_type` END AS `item_type`" in ctas_sql
    assert "`item_outlet_sales`" in ctas_sql

    class _SandboxFakeBQ(_FakeBigQueryClient):
        def query(self, sql: str, job_config=None):
            is_dry = bool(getattr(job_config, "dry_run", False))
            self.queries.append({"sql": sql, "dry_run": is_dry, "job_config": job_config})
            if not is_dry and sql.strip().upper().startswith("UPDATE"):
                raise RuntimeError(
                    "403 Billing has not been enabled for this project. DML queries are not allowed in the free tier."
                )
            if not is_dry and "SELECT COUNT(*) AS affected" in sql:
                return _FakeBQJob(rows=[{"affected": 4}])
            if is_dry:
                return _FakeBQJob(total_bytes_processed=1024)
            if "COUNT(*) AS total" in sql:
                return _FakeBQJob(rows=[{"total": 10}])
            return _FakeBQJob(rows=self.query_rows)

    sandbox_bq = _SandboxFakeBQ(project="my-proj")
    store = BigQuerySalesStore(
        project_id="my-proj",
        dataset="fixdesk",
        sandbox_dataset="fixdesk_sandbox",
        client=sandbox_bq,
    )

    preview = store.preview_data_fix(
        sql_patch='UPDATE sales SET "item_type" = TRIM(UPPER("item_type")) WHERE "item_type" IS NOT NULL',
        ticket_id="tkt_sandbox",
    )
    assert preview["status"] == "SUCCESS"
    assert preview["sandbox_mode_fallback"] is True
    assert preview["execution_mode"] == "ctas_sandbox_fallback"
    assert preview["rows_affected"] == 4
    assert "CREATE OR REPLACE TABLE `my-proj.fixdesk_sandbox.sales_sandbox` AS SELECT" in preview["sql_applied_to_sandbox"]
    assert "BigQuery Sandbox mode" in preview["fallback_note"]

    applied = store.apply_data_fix(
        sql_patch='UPDATE sales SET "item_type" = TRIM(UPPER("item_type")) WHERE "item_type" IS NOT NULL'
    )
    assert applied["sandbox_mode_fallback"] is True
    assert applied["execution_mode"] == "ctas_sandbox_fallback"
    assert applied["rows_affected"] == 4
    assert "BigQuery Sandbox mode" in applied["fallback_note"]
    assert any(
        "CREATE OR REPLACE TABLE `my-proj.fixdesk.sales` AS SELECT" in q["sql"]
        for q in sandbox_bq.queries
    )


def test_bigquery_code_vector_store_uses_load_jobs_and_ctas_fallback():
    class _SandboxCodeBQ(_FakeBigQueryClient):
        def query(self, sql: str, job_config=None):
            self.queries.append({"sql": sql, "dry_run": False, "job_config": job_config})
            upper = sql.strip().upper()
            if upper.startswith("DELETE") or upper.startswith("UPDATE"):
                raise RuntimeError("DML queries are not allowed in the free tier.")
            if "SELECT COUNT(*) AS C" in upper:
                return _FakeBQJob(rows=[{"c": 2}])
            return _FakeBQJob(rows=[])

    sb_bq = _SandboxCodeBQ(project="my-proj")
    code_store = BigQueryCodeVectorStore(project_id="my-proj", dataset="fixdesk_vectors", client=sb_bq)
    code_store.upsert_project("demo", "/tmp/demo", "main")
    code_store.save_cached_summaries({"h1": "summary 1"})
    code_store.replace_skipped_files("demo", [{"file_path": ".env", "reason": "secret", "rule": "env"}])
    counts = code_store.refresh_project_counts("demo", "abc123")

    assert counts == {"file_count": 2, "chunk_count": 2, "skipped_count": 2}
    # Zero streaming inserts anywhere
    assert len(sb_bq.insert_json_calls) == 0
    assert len(sb_bq.load_json_calls) == 3  # code_projects, code_summary_cache, code_skipped_files
    assert any("CREATE OR REPLACE TABLE `my-proj.fixdesk_vectors.code_projects` AS" in q["sql"] for q in sb_bq.queries)


# ------------------------------------------------------------------------------
# 5. BigQuery VectorStore Contract Tests
# ------------------------------------------------------------------------------
def test_bigquery_vector_store_contract():
    fake_bq = _FakeBigQueryClient(project="my-proj")
    fake_bq.query_rows = [
        {
            "chunk_id": "policy.md_0",
            "source_file": "policy.md",
            "title": "Return Policy",
            "content": "Dairy items may be returned within 7 days.",
            "chunk_index": 0,
            "similarity": 0.9123,
        }
    ]
    vec_store = BigQueryVectorStore(project_id="my-proj", dataset="fixdesk_vectors", client=fake_bq)
    chunks = [
        {
            "chunk_id": "policy.md_0",
            "source_file": "policy.md",
            "title": "Return Policy",
            "content": "Dairy items may be returned within 7 days.",
            "chunk_index": 0,
            "total_chunks": 1,
        }
    ]
    embeddings = [[0.1] * 768]
    count = vec_store.upsert_document_chunks(chunks, embeddings)
    assert count == 1
    assert not any("TRUNCATE TABLE" in q["sql"] for q in fake_bq.queries)
    assert any("CREATE VECTOR INDEX IF NOT EXISTS" in q["sql"] for q in fake_bq.queries)
    assert len(fake_bq.load_json_calls[0]["rows"][0]["embedding"]) == 768

    hits = vec_store.search_documents([0.1] * 768, top_k=3)
    assert len(hits) == 1
    assert hits[0]["source_file"] == "policy.md"
    assert any("VECTOR_SEARCH(" in q["sql"] for q in fake_bq.queries)


# ------------------------------------------------------------------------------
# 6. Daily AI Budget Guard & /status Telemetry Tests
# ------------------------------------------------------------------------------
def test_daily_ai_budget_warning_and_block(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_BUDGET_STATE_PATH", str(tmp_path / "budget.json"))
    monkeypatch.setenv("AI_DAILY_REQUEST_LIMIT", "10")
    monkeypatch.setenv("AI_DAILY_TOKEN_LIMIT", "1000")
    monkeypatch.setenv("AI_BUDGET_WARN_RATIO", "0.8")
    reset_budget_state()

    record_ai_usage(requests=8, tokens=400)
    st = get_budget_status()
    assert st["warning_active"] is True
    assert st["limit_reached"] is False

    record_ai_usage(requests=2, tokens=100)
    with pytest.raises(BudgetExceededError):
        check_budget_available()

    client = TestClient(app)
    resp = client.get("/status")
    assert resp.status_code == 200
    payload = resp.json()
    assert "ai_budget" in payload
    assert payload["ai_budget"]["limit_reached"] is True
    assert "storage_backend" in payload
    assert "adc_status" in payload


# ------------------------------------------------------------------------------
# 7. Codebase Privacy Guard (`cloud_index_allowed: false`)
# ------------------------------------------------------------------------------
def test_codebase_privacy_guard_blocks_cloud_when_disabled(tmp_path, monkeypatch):
    # Real fixdesk repo must default to cloud_index_allowed: false
    fixdesk_cfg = get_project_config("fixdesk")
    assert fixdesk_cfg.cloud_index_allowed is False

    monkeypatch.setenv("VECTOR_BACKEND", "gcp")
    monkeypatch.setenv("LLM_BACKEND", "vertexai")
    monkeypatch.setenv("EMBEDDING_BACKEND", "vertexai")
    monkeypatch.setenv("GCP_PROJECT_ID", "my-proj")

    # Local PostgresCodeStore is forced when cloud_index_allowed is False
    code_store = get_code_store("fixdesk")
    assert not isinstance(code_store, BigQueryCodeVectorStore)

    with pytest.raises(CloudPrivacyError):
        get_code_store("fixdesk", require_cloud_if_gcp=True)

    with pytest.raises(CloudPrivacyError):
        get_llm_client(cloud_allowed=False)

    with pytest.raises(CloudPrivacyError):
        get_embedding_client(cloud_allowed=False)

    # Summarizer must never invoke LLM when cloud_allowed=False
    ch = CodeChunk(
        project="fixdesk",
        file_path="app.py",
        language="python",
        symbol_name="hello",
        chunk_kind="function",
        start_line=1,
        end_line=2,
        commit_hash="abc",
        content="def hello():\n    return 1\n",
    )
    summary = generate_chunk_summary(ch, use_llm=True, cloud_allowed=False)
    assert "[python] hello" in summary

    # Create a temporary private repo with cloud_index_allowed: false + fake secret file
    repo = tmp_path / "priv_repo"
    repo.mkdir()
    (repo / ".env").write_text("SECRET_KEY=super_secret_token_999\n", encoding="utf-8")
    (repo / "service.py").write_text("def calc(x):\n    return x + 1\n", encoding="utf-8")

    cfg_path = tmp_path / "projects.yaml"
    cfg_path.write_text(
        f"projects:\n  - name: priv\n    local_path: {repo}\n    cloud_index_allowed: false\n",
        encoding="utf-8",
    )

    # Even if global backends are set to GCP/Vertex, indexing & asking must stay local and never touch cloud
    class _InMemStore:
        def ensure_schema(self): pass
        def get_project_status(self, p): return None
        def upsert_project(self, **kw): pass
        def get_file_hashes(self, p): return {}
        def get_cached_summaries(self, h): return {}
        def save_cached_summaries(self, s): pass
        def delete_file(self, p, f): pass
        def replace_file_chunks(self, **kw): self.saved = kw
        def replace_skipped_files(self, p, s): self.skipped = s
        def refresh_project_counts(self, p, c): return {}
        def find_files_importing(self, p, m): return []
        def search_hybrid(self, p, q, vec, limit=12):
            return [{
                "file_path": "service.py",
                "language": "python",
                "symbol_name": "calc",
                "chunk_kind": "function",
                "start_line": 1,
                "end_line": 2,
                "commit_hash": "working-tree",
                "summary": "calc",
                "content": "def calc(x):\n    return x + 1",
                "vec_score": 0.9,
                "kw_score": 0.9,
            }]

    mem = _InMemStore()
    stats = index_project("priv", config_path=str(cfg_path), store=mem)
    assert stats.indexed_files == 1
    assert any(s["file_path"] == ".env" for s in stats.skipped_files)

    ans = ask_codebase("priv", "where is calc implemented?", config_path=str(cfg_path), store=mem)
    assert ans["found"] is True
    assert "super_secret_token_999" not in json.dumps(ans)


# ------------------------------------------------------------------------------
# 8. Print-Only Scripts Smoke Tests
# ------------------------------------------------------------------------------
def test_print_only_gcp_setup_and_inventory_scripts():
    setup_proc = subprocess.run(
        [sys.executable, "scripts/gcp_setup.py", "--project-id", "demo-proj", "--bucket", "demo-bkt"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "gcloud auth application-default login" in setup_proc.stdout
    assert 'GCP_PROJECT_ID="demo-proj"' in setup_proc.stdout
    assert 'GCS_BUCKET="demo-bkt"' in setup_proc.stdout
    assert 'gs://${GCS_BUCKET}' in setup_proc.stdout

    inv_proc = subprocess.run(
        [sys.executable, "scripts/gcp_inventory.py"],
        capture_output=True,
        text=True,
        check=True,
    )
    inv_data = json.loads(inv_proc.stdout)
    assert "backends" in inv_data
    assert "ai_budget" in inv_data
