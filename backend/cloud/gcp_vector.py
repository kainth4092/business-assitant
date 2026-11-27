"""
BigQuery Vector Search Store (`VECTOR_BACKEND=gcp`) for Policy Documents & Opt-In Codebase RAG.
Uses `ARRAY<FLOAT64>` (768 dimensions), `CREATE VECTOR INDEX ... OPTIONS(index_type = 'IVF', distance_type = 'COSINE')`,
and `VECTOR_SEARCH(TABLE ..., 'embedding', (SELECT @query_vec AS embedding), top_k => ..., distance_type => 'COSINE')`.
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from backend.cloud.auth import load_adc_credentials
from backend.cloud.config import (
    get_bq_max_bytes_billed,
    get_bq_vector_dataset,
    get_document_rag_backend,
    get_gcp_multi_region,
    get_gcp_project_id,
    get_gcp_region,
)
from backend.cloud.interfaces import VectorStore
from project_init.security import redact_secrets

logger = logging.getLogger("FixdeskBQVector")

VECTOR_DIMENSION = 768


class BigQueryVectorStore(VectorStore):
    """BigQuery Vector Search store for `document_embeddings`."""

    backend_name = "gcp"

    def __init__(
        self,
        project_id: Optional[str] = None,
        dataset: Optional[str] = None,
        max_bytes_billed: Optional[int] = None,
        client: Optional[Any] = None,
    ):
        self.project_id = (project_id or get_gcp_project_id()).strip()
        self.dataset = (dataset or get_bq_vector_dataset()).strip()
        self.max_bytes_billed = (
            max_bytes_billed if max_bytes_billed is not None else get_bq_max_bytes_billed()
        )
        self._client = client

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
            raise ValueError("GCP_PROJECT_ID must be configured for BigQuery Vector Search.")
        return self.project_id

    def _table_id(self) -> str:
        return f"{self._resolve_project()}.{self.dataset}.document_embeddings"

    def ensure_schema(self, try_vector_index: bool = True) -> None:
        from google.cloud import bigquery

        client = self._get_client()
        project = self._resolve_project()
        ds = bigquery.Dataset(f"{project}.{self.dataset}")
        ds.location = get_gcp_multi_region()
        client.create_dataset(ds, exists_ok=True)

        table_id = self._table_id()
        schema = [
            bigquery.SchemaField("chunk_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("source_file", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("title", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("content", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("chunk_index", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("total_chunks", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("embedding", "FLOAT64", mode="REPEATED"),
            bigquery.SchemaField("updated_at", "TIMESTAMP", mode="REQUIRED"),
        ]
        client.create_table(bigquery.Table(table_id, schema=schema), exists_ok=True)

        if try_vector_index:
            self._maybe_create_vector_index(table_id, "idx_document_embeddings_ivf")

    def _maybe_create_vector_index(self, table_id: str, index_name: str) -> None:
        """
        Issue `CREATE VECTOR INDEX IF NOT EXISTS ...` using IVF + COSINE.
        BigQuery IVF indexes require a minimum row threshold in production; small tables still
        work seamlessly via VECTOR_SEARCH brute-force scan if index creation is deferred.
        """
        from google.cloud import bigquery

        client = self._get_client()
        ddl = (
            f"CREATE VECTOR INDEX IF NOT EXISTS `{index_name}` "
            f"ON `{table_id}`(embedding) "
            f"OPTIONS(index_type = 'IVF', distance_type = 'COSINE', ivf_options = '{{\"num_lists\": 100}}')"
        )
        try:
            cfg = bigquery.QueryJobConfig(maximum_bytes_billed=self.max_bytes_billed)
            client.query(ddl, job_config=cfg).result()
        except Exception as exc:
            logger.info(f"BigQuery VECTOR INDEX deferred (VECTOR_SEARCH remains active): {exc}")

    def upsert_document_chunks(
        self, chunks: List[Dict[str, Any]], embeddings: List[List[float]]
    ) -> int:
        from google.cloud import bigquery

        self.ensure_schema(try_vector_index=False)
        client = self._get_client()
        table_id = self._table_id()

        # Replace existing chunks cleanly for fresh ingestion
        client.query(
            f"TRUNCATE TABLE `{table_id}`",
            job_config=bigquery.QueryJobConfig(maximum_bytes_billed=self.max_bytes_billed),
        ).result()

        now_iso = datetime.now(timezone.utc).isoformat()
        rows = []
        for chunk, emb in zip(chunks, embeddings):
            rows.append(
                {
                    "chunk_id": chunk["chunk_id"],
                    "source_file": chunk["source_file"],
                    "title": chunk["title"],
                    "content": chunk["content"],
                    "chunk_index": int(chunk["chunk_index"]),
                    "total_chunks": int(chunk["total_chunks"]),
                    "embedding": [float(x) for x in emb],
                    "updated_at": now_iso,
                }
            )

        if rows:
            load_cfg = bigquery.LoadJobConfig(
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            )
            client.load_table_from_json(rows, table_id, job_config=load_cfg).result()
            self._maybe_create_vector_index(table_id, "idx_document_embeddings_ivf")
        return len(rows)

    def search_documents(
        self, query_vector: List[float], top_k: int = 3, query_text: str = ""
    ) -> List[Dict[str, Any]]:
        if get_document_rag_backend() == "vertex_rag_engine" and query_text:
            rag_results = self._search_vertex_rag_engine(query_text=query_text, top_k=top_k)
            if rag_results is not None:
                return rag_results

        from google.cloud import bigquery

        client = self._get_client()
        table_id = self._table_id()
        safe_k = max(1, min(int(top_k), 20))
        sql = f"""
            SELECT
                base.chunk_id AS chunk_id,
                base.source_file AS source_file,
                base.title AS title,
                base.content AS content,
                base.chunk_index AS chunk_index,
                ROUND(1.0 - distance, 4) AS similarity
            FROM VECTOR_SEARCH(
                TABLE `{table_id}`,
                'embedding',
                (SELECT @query_vec AS embedding),
                top_k => @top_k,
                distance_type => 'COSINE'
            )
            ORDER BY distance ASC
        """
        cfg = bigquery.QueryJobConfig(
            maximum_bytes_billed=self.max_bytes_billed,
            query_parameters=[
                bigquery.ArrayQueryParameter("query_vec", "FLOAT64", [float(x) for x in query_vector]),
                bigquery.ScalarQueryParameter("top_k", "INT64", safe_k),
            ],
        )
        try:
            rows = client.query(sql, job_config=cfg).result()
            return [
                {
                    "chunk_id": r["chunk_id"],
                    "source_file": r["source_file"],
                    "title": r["title"] or r["source_file"],
                    "content": r["content"],
                    "similarity": float(r["similarity"]),
                    "chunk_index": int(r["chunk_index"]),
                }
                for r in rows
            ]
        except Exception as e:
            logger.error(f"Error during BigQuery VECTOR_SEARCH: {e}")
            return []

    def _search_vertex_rag_engine(self, query_text: str, top_k: int) -> Optional[List[Dict[str, Any]]]:
        """Optional DOCUMENT_RAG_BACKEND=vertex_rag_engine hook (disabled by default)."""
        corpus_name = os.environ.get("VERTEX_RAG_CORPUS", "").strip()
        if not corpus_name:
            logger.info("DOCUMENT_RAG_BACKEND=vertex_rag_engine set without VERTEX_RAG_CORPUS; falling back to BigQuery Vector Search.")
            return None
        try:
            from google import genai

            creds, project = load_adc_credentials(require_project=True)
            _client = genai.Client(
                vertexai=True,
                project=self.project_id or project,
                location=get_gcp_region(),
                credentials=creds,
            )
            logger.info(f"Vertex RAG Engine corpus '{corpus_name}' hook invoked for top_k={top_k}.")
            return None
        except Exception as exc:
            logger.warning(f"Vertex RAG Engine hook unavailable ({exc}); using BigQuery Vector Search.")
            return None

    def list_indexed_sources(self) -> List[Dict[str, Any]]:
        from google.cloud import bigquery

        client = self._get_client()
        table_id = self._table_id()
        sql = f"""
            SELECT
                source_file,
                COUNT(*) AS total_chunks,
                ARRAY_AGG(STRUCT(title, content) ORDER BY chunk_index ASC LIMIT 1)[OFFSET(0)] AS first_chunk
            FROM `{table_id}`
            GROUP BY source_file
            ORDER BY source_file ASC
        """
        try:
            rows = client.query(
                sql,
                job_config=bigquery.QueryJobConfig(maximum_bytes_billed=self.max_bytes_billed),
            ).result()
            result = []
            for r in rows:
                first_chunk = r.get("first_chunk") or {}
                content = first_chunk.get("content") or ""
                lines = [l.strip() for l in content.split("\n") if l.strip()]
                summary_lines = [l for l in lines if not l.startswith("#")]
                summary_text = " ".join(summary_lines) if summary_lines else content
                snippet = summary_text[:180].strip()
                if len(summary_text) > 180:
                    snippet += "..."
                result.append(
                    {
                        "source_file": r["source_file"],
                        "total_chunks": int(r["total_chunks"]),
                        "sample_title": first_chunk.get("title") or r["source_file"],
                        "sample_summary": snippet or "No text summary available.",
                    }
                )
            return result
        except Exception as e:
            logger.error(f"Error listing BigQuery indexed sources: {e}")
            return []

    def get_document_chunks(self, source_file: str) -> List[Dict[str, Any]]:
        from google.cloud import bigquery

        client = self._get_client()
        table_id = self._table_id()
        sql = f"""
            SELECT chunk_id, source_file, title, content, chunk_index, total_chunks
            FROM `{table_id}`
            WHERE source_file = @exact OR source_file LIKE @pattern
            ORDER BY chunk_index ASC
        """
        cfg = bigquery.QueryJobConfig(
            maximum_bytes_billed=self.max_bytes_billed,
            query_parameters=[
                bigquery.ScalarQueryParameter("exact", "STRING", source_file),
                bigquery.ScalarQueryParameter("pattern", "STRING", f"%{source_file}%"),
            ],
        )
        try:
            return [dict(r) for r in client.query(sql, job_config=cfg).result()]
        except Exception as e:
            logger.error(f"Error fetching BigQuery document chunks: {e}")
            return []

    def count_chunks(self) -> int:
        from google.cloud import bigquery

        try:
            client = self._get_client()
            sql = f"SELECT COUNT(*) AS cnt FROM `{self._table_id()}`"
            rows = list(
                client.query(
                    sql,
                    job_config=bigquery.QueryJobConfig(maximum_bytes_billed=self.max_bytes_billed),
                ).result()
            )
            return int(rows[0]["cnt"]) if rows else 0
        except Exception:
            return 0

    def health_check(self) -> Dict[str, Any]:
        try:
            project = self._resolve_project()
            count = self.count_chunks()
            return {
                "backend": "gcp",
                "pgvector_ready": True,
                "vector_backend": "bigquery",
                "project_id": project,
                "dataset": self.dataset,
                "indexed_chunks": count,
            }
        except Exception as e:
            return {
                "backend": "gcp",
                "pgvector_ready": False,
                "vector_backend": "bigquery",
                "indexed_chunks": 0,
                "error": str(e),
            }


# ==============================================================================
# Opt-In BigQuery Codebase RAG Store (Strictly Guarded by cloud_index_allowed)
# ==============================================================================
class BigQueryCodeVectorStore:
    """
    BigQuery Vector Search store for `code_rag` tables.
    Only instantiated when `VECTOR_BACKEND=gcp` AND the target project has
    `cloud_index_allowed: true` in `projects.yaml`.
    """

    backend_name = "gcp"

    def __init__(
        self,
        project_id: Optional[str] = None,
        dataset: Optional[str] = None,
        max_bytes_billed: Optional[int] = None,
        client: Optional[Any] = None,
    ):
        self.project_id = (project_id or get_gcp_project_id()).strip()
        self.dataset = (dataset or get_bq_vector_dataset()).strip()
        self.max_bytes_billed = (
            max_bytes_billed if max_bytes_billed is not None else get_bq_max_bytes_billed()
        )
        self._client = client

    def _get_client(self):
        if self._client is not None:
            return self._client
        from google.cloud import bigquery

        creds, resolved = load_adc_credentials(require_project=True)
        if not self.project_id:
            self.project_id = resolved
        self._client = bigquery.Client(project=self.project_id, credentials=creds)
        return self._client

    def _resolve_project(self) -> str:
        if self.project_id:
            return self.project_id
        client = self._get_client()
        self.project_id = getattr(client, "project", "") or get_gcp_project_id()
        return self.project_id

    def _tbl(self, name: str) -> str:
        return f"{self._resolve_project()}.{self.dataset}.{name}"

    def _query(self, sql: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        from google.cloud import bigquery

        client = self._get_client()
        cfg = bigquery.QueryJobConfig(
            maximum_bytes_billed=self.max_bytes_billed,
            query_parameters=params or [],
        )
        return [dict(r) for r in client.query(sql, job_config=cfg).result()]

    def ensure_schema(self) -> None:
        from google.cloud import bigquery

        client = self._get_client()
        project = self._resolve_project()
        ds = bigquery.Dataset(f"{project}.{self.dataset}")
        ds.location = get_gcp_multi_region()
        client.create_dataset(ds, exists_ok=True)

        tables = {
            "code_projects": [
                bigquery.SchemaField("name", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("local_path", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("default_branch", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("last_commit_hash", "STRING"),
                bigquery.SchemaField("last_indexed_at", "TIMESTAMP"),
                bigquery.SchemaField("file_count", "INT64"),
                bigquery.SchemaField("chunk_count", "INT64"),
                bigquery.SchemaField("skipped_count", "INT64"),
                bigquery.SchemaField("status", "STRING"),
                bigquery.SchemaField("last_error", "STRING"),
            ],
            "code_file_metadata": [
                bigquery.SchemaField("project", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("file_path", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("language", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("commit_hash", "STRING"),
                bigquery.SchemaField("content_hash", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("line_count", "INT64"),
                bigquery.SchemaField("chunk_count", "INT64"),
                bigquery.SchemaField("imports", "STRING"),
                bigquery.SchemaField("symbols", "STRING"),
                bigquery.SchemaField("updated_at", "TIMESTAMP"),
            ],
            "code_chunks": [
                bigquery.SchemaField("chunk_uid", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("project", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("file_path", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("language", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("symbol_name", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("chunk_kind", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("start_line", "INT64", mode="REQUIRED"),
                bigquery.SchemaField("end_line", "INT64", mode="REQUIRED"),
                bigquery.SchemaField("commit_hash", "STRING"),
                bigquery.SchemaField("content_hash", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("summary", "STRING"),
                bigquery.SchemaField("content", "STRING"),
                bigquery.SchemaField("embedding", "FLOAT64", mode="REPEATED"),
            ],
            "code_summary_cache": [
                bigquery.SchemaField("content_hash", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("summary", "STRING", mode="REQUIRED"),
            ],
            "code_skipped_files": [
                bigquery.SchemaField("project", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("file_path", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("reason", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("rule", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("scanned_at", "TIMESTAMP"),
            ],
        }
        for name, schema in tables.items():
            client.create_table(bigquery.Table(self._tbl(name), schema=schema), exists_ok=True)

    def upsert_project(
        self,
        name: str,
        local_path: str,
        default_branch: str,
        status: str = "ready",
        last_commit_hash: Optional[str] = None,
        file_count: Optional[int] = None,
        chunk_count: Optional[int] = None,
        skipped_count: Optional[int] = None,
        last_error: Optional[str] = None,
    ) -> None:
        from google.cloud import bigquery

        tbl = self._tbl("code_projects")
        now_iso = datetime.now(timezone.utc).isoformat()
        self._query(
            f"DELETE FROM `{tbl}` WHERE name = @name",
            [bigquery.ScalarQueryParameter("name", "STRING", name)],
        )
        self._get_client().insert_rows_json(
            tbl,
            [
                {
                    "name": name,
                    "local_path": local_path,
                    "default_branch": default_branch,
                    "last_commit_hash": last_commit_hash,
                    "last_indexed_at": now_iso,
                    "file_count": int(file_count or 0),
                    "chunk_count": int(chunk_count or 0),
                    "skipped_count": int(skipped_count or 0),
                    "status": status,
                    "last_error": last_error,
                }
            ],
        )

    def get_file_hashes(self, project: str) -> Dict[str, str]:
        from google.cloud import bigquery

        rows = self._query(
            f"SELECT file_path, content_hash FROM `{self._tbl('code_file_metadata')}` WHERE project = @p",
            [bigquery.ScalarQueryParameter("p", "STRING", project)],
        )
        return {r["file_path"]: r["content_hash"] for r in rows}

    def get_cached_summaries(self, content_hashes: Sequence[str]) -> Dict[str, str]:
        from google.cloud import bigquery

        hashes = [h for h in set(content_hashes) if h]
        if not hashes:
            return {}
        rows = self._query(
            f"SELECT content_hash, summary FROM `{self._tbl('code_summary_cache')}` WHERE content_hash IN UNNEST(@hashes)",
            [bigquery.ArrayQueryParameter("hashes", "STRING", hashes)],
        )
        return {r["content_hash"]: r["summary"] for r in rows}

    def save_cached_summaries(self, summaries: Dict[str, str]) -> None:
        if not summaries:
            return
        tbl = self._tbl("code_summary_cache")
        rows = [
            {"content_hash": k, "summary": redact_secrets(v)}
            for k, v in summaries.items()
        ]
        self._get_client().insert_rows_json(tbl, rows)

    def replace_file_chunks(
        self,
        project: str,
        file_path: str,
        language: str,
        commit_hash: str,
        content_hash: str,
        line_count: int,
        imports: List[str],
        symbols: List[Dict[str, Any]],
        chunks: List[Any],
        embeddings: List[List[float]],
    ) -> None:
        from google.cloud import bigquery

        self.delete_file(project, file_path)
        chunk_rows = []
        for chunk, vec in zip(chunks, embeddings):
            chunk_rows.append(
                {
                    "chunk_uid": chunk.chunk_uid,
                    "project": project,
                    "file_path": chunk.file_path,
                    "language": chunk.language,
                    "symbol_name": chunk.symbol_name,
                    "chunk_kind": chunk.chunk_kind,
                    "start_line": int(chunk.start_line),
                    "end_line": int(chunk.end_line),
                    "commit_hash": chunk.commit_hash,
                    "content_hash": chunk.content_hash,
                    "summary": redact_secrets(chunk.summary),
                    "content": redact_secrets(chunk.content),
                    "embedding": [float(x) for x in vec],
                }
            )
        if chunk_rows:
            self._get_client().load_table_from_json(
                chunk_rows,
                self._tbl("code_chunks"),
                job_config=bigquery.LoadJobConfig(
                    write_disposition=bigquery.WriteDisposition.WRITE_APPEND
                ),
            ).result()

        self._get_client().insert_rows_json(
            self._tbl("code_file_metadata"),
            [
                {
                    "project": project,
                    "file_path": file_path,
                    "language": language,
                    "commit_hash": commit_hash,
                    "content_hash": content_hash,
                    "line_count": int(line_count),
                    "chunk_count": len(chunks),
                    "imports": json.dumps(imports),
                    "symbols": json.dumps(symbols),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            ],
        )

    def delete_file(self, project: str, file_path: str) -> None:
        from google.cloud import bigquery

        params = [
            bigquery.ScalarQueryParameter("p", "STRING", project),
            bigquery.ScalarQueryParameter("fp", "STRING", file_path),
        ]
        self._query(
            f"DELETE FROM `{self._tbl('code_chunks')}` WHERE project = @p AND file_path = @fp",
            params,
        )
        self._query(
            f"DELETE FROM `{self._tbl('code_file_metadata')}` WHERE project = @p AND file_path = @fp",
            params,
        )

    def replace_skipped_files(self, project: str, skipped: List[Dict[str, str]]) -> None:
        from google.cloud import bigquery

        tbl = self._tbl("code_skipped_files")
        self._query(
            f"DELETE FROM `{tbl}` WHERE project = @p",
            [bigquery.ScalarQueryParameter("p", "STRING", project)],
        )
        if skipped:
            now_iso = datetime.now(timezone.utc).isoformat()
            rows = [
                {
                    "project": project,
                    "file_path": item["file_path"],
                    "reason": item["reason"],
                    "rule": item.get("rule", "policy"),
                    "scanned_at": now_iso,
                }
                for item in skipped
            ]
            self._get_client().insert_rows_json(tbl, rows)

    def refresh_project_counts(self, project: str, commit_hash: str) -> Dict[str, int]:
        from google.cloud import bigquery

        p_param = [bigquery.ScalarQueryParameter("p", "STRING", project)]
        fc = int(self._query(f"SELECT COUNT(*) AS c FROM `{self._tbl('code_file_metadata')}` WHERE project = @p", p_param)[0]["c"])
        cc = int(self._query(f"SELECT COUNT(*) AS c FROM `{self._tbl('code_chunks')}` WHERE project = @p", p_param)[0]["c"])
        sc = int(self._query(f"SELECT COUNT(*) AS c FROM `{self._tbl('code_skipped_files')}` WHERE project = @p", p_param)[0]["c"])
        self._query(
            f"""
            UPDATE `{self._tbl('code_projects')}`
            SET file_count = @fc, chunk_count = @cc, skipped_count = @sc,
                last_commit_hash = @ch, last_indexed_at = CURRENT_TIMESTAMP(),
                status = 'indexed', last_error = NULL
            WHERE name = @p
            """,
            [
                bigquery.ScalarQueryParameter("fc", "INT64", fc),
                bigquery.ScalarQueryParameter("cc", "INT64", cc),
                bigquery.ScalarQueryParameter("sc", "INT64", sc),
                bigquery.ScalarQueryParameter("ch", "STRING", commit_hash),
                bigquery.ScalarQueryParameter("p", "STRING", project),
            ],
        )
        return {"file_count": fc, "chunk_count": cc, "skipped_count": sc}

    def list_projects(self) -> List[Dict[str, Any]]:
        return self._query(
            f"""
            SELECT name, local_path, default_branch, last_commit_hash,
                   last_indexed_at, file_count, chunk_count, skipped_count,
                   status, last_error
            FROM `{self._tbl('code_projects')}`
            ORDER BY name ASC
            """
        )

    def get_project_status(self, project: str) -> Optional[Dict[str, Any]]:
        from google.cloud import bigquery

        rows = self._query(
            f"""
            SELECT name, local_path, default_branch, last_commit_hash,
                   last_indexed_at, file_count, chunk_count, skipped_count,
                   status, last_error
            FROM `{self._tbl('code_projects')}`
            WHERE name = @p
            """,
            [bigquery.ScalarQueryParameter("p", "STRING", project)],
        )
        if not rows:
            return None
        info = dict(rows[0])
        info["languages"] = self._query(
            f"""
            SELECT language, COUNT(*) AS files
            FROM `{self._tbl('code_file_metadata')}`
            WHERE project = @p
            GROUP BY language
            ORDER BY files DESC
            """,
            [bigquery.ScalarQueryParameter("p", "STRING", project)],
        )
        return info

    def get_skipped_files(self, project: str) -> List[Dict[str, Any]]:
        from google.cloud import bigquery

        return self._query(
            f"""
            SELECT file_path, reason, rule, scanned_at
            FROM `{self._tbl('code_skipped_files')}`
            WHERE project = @p
            ORDER BY file_path ASC
            """,
            [bigquery.ScalarQueryParameter("p", "STRING", project)],
        )

    def get_file_outline(self, project: str, file_path: str) -> Optional[Dict[str, Any]]:
        from google.cloud import bigquery

        rows = self._query(
            f"""
            SELECT file_path, language, commit_hash, line_count, chunk_count, imports, symbols
            FROM `{self._tbl('code_file_metadata')}`
            WHERE project = @p AND file_path = @fp
            """,
            [
                bigquery.ScalarQueryParameter("p", "STRING", project),
                bigquery.ScalarQueryParameter("fp", "STRING", file_path),
            ],
        )
        if not rows:
            return None
        row = dict(rows[0])
        for field in ("imports", "symbols"):
            if isinstance(row.get(field), str):
                row[field] = json.loads(row[field])
        return row

    def list_file_tree(self, project: str, limit: int = 200) -> List[Dict[str, Any]]:
        from google.cloud import bigquery

        rows = self._query(
            f"""
            SELECT file_path, language, line_count, chunk_count, imports
            FROM `{self._tbl('code_file_metadata')}`
            WHERE project = @p
            ORDER BY file_path ASC
            LIMIT @lim
            """,
            [
                bigquery.ScalarQueryParameter("p", "STRING", project),
                bigquery.ScalarQueryParameter("lim", "INT64", int(limit)),
            ],
        )
        for row in rows:
            if isinstance(row.get("imports"), str):
                row["imports"] = json.loads(row["imports"])
        return rows

    def find_files_importing(self, project: str, module_query: str) -> List[Dict[str, Any]]:
        from google.cloud import bigquery

        q = module_query.strip().lower()
        if not q:
            return []
        rows = self._query(
            f"""
            SELECT file_path, language, imports
            FROM `{self._tbl('code_file_metadata')}`
            WHERE project = @p AND LOWER(imports) LIKE @pat
            ORDER BY file_path ASC
            """,
            [
                bigquery.ScalarQueryParameter("p", "STRING", project),
                bigquery.ScalarQueryParameter("pat", "STRING", f"%{q}%"),
            ],
        )
        for row in rows:
            if isinstance(row.get("imports"), str):
                row["imports"] = json.loads(row["imports"])
        return rows

    def find_symbol(self, project: str, symbol_query: str, limit: int = 20) -> List[Dict[str, Any]]:
        from google.cloud import bigquery

        q = symbol_query.strip()
        if not q:
            return []
        rows = self._query(
            f"""
            SELECT file_path, language, symbol_name, chunk_kind,
                   start_line, end_line, commit_hash, summary, content
            FROM `{self._tbl('code_chunks')}`
            WHERE project = @p AND LOWER(symbol_name) LIKE LOWER(@pat)
            ORDER BY file_path ASC, start_line ASC
            LIMIT @lim
            """,
            [
                bigquery.ScalarQueryParameter("p", "STRING", project),
                bigquery.ScalarQueryParameter("pat", "STRING", f"%{q}%"),
                bigquery.ScalarQueryParameter("lim", "INT64", int(limit)),
            ],
        )
        for r in rows:
            r["summary"] = redact_secrets(r.get("summary", ""))
            r["content"] = redact_secrets(r.get("content", ""))
        return rows

    def search_hybrid(
        self,
        project: str,
        query: str,
        query_embedding: List[float],
        limit: int = 12,
    ) -> List[Dict[str, Any]]:
        from google.cloud import bigquery

        table_id = self._tbl("code_chunks")
        safe_limit = max(1, min(int(limit), 30))
        tokens = [t.lower() for t in re.findall(r"[A-Za-z0-9_]{2,}", query)]
        sql = f"""
            SELECT
                base.file_path AS file_path,
                base.language AS language,
                base.symbol_name AS symbol_name,
                base.chunk_kind AS chunk_kind,
                base.start_line AS start_line,
                base.end_line AS end_line,
                base.commit_hash AS commit_hash,
                base.summary AS summary,
                base.content AS content,
                GREATEST(0.0, 1.0 - distance) AS vec_score
            FROM VECTOR_SEARCH(
                (SELECT * FROM `{table_id}` WHERE project = @p AND ARRAY_LENGTH(embedding) > 0),
                'embedding',
                (SELECT @query_vec AS embedding),
                top_k => @lim,
                distance_type => 'COSINE'
            )
            ORDER BY distance ASC
        """
        rows = self._query(
            sql,
            [
                bigquery.ScalarQueryParameter("p", "STRING", project),
                bigquery.ArrayQueryParameter("query_vec", "FLOAT64", [float(x) for x in query_embedding]),
                bigquery.ScalarQueryParameter("lim", "INT64", safe_limit),
            ],
        )
        for r in rows:
            r["summary"] = redact_secrets(r.get("summary", ""))
            r["content"] = redact_secrets(r.get("content", ""))
            haystack = f"{r['file_path']} {r['symbol_name']} {r['summary']} {r['content']}".lower()
            hits = sum(1 for tok in tokens if tok in haystack)
            r["kw_score"] = (hits / len(tokens)) if tokens else 0.0
        return rows
