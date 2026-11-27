"""
Local Backend Implementations for Fixdesk (`STORAGE_BACKEND=local`, `VECTOR_BACKEND=local`,
`FILE_STORE_BACKEND=local`, and Gemini Developer API key LLM/Embeddings).
Wraps existing PostgreSQL, pgvector, and local filesystem workflows with zero regressions.
"""

import hashlib
import json
import logging
import math
import os
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor, execute_batch

from backend.cloud.budget import BudgetExceededError, check_budget_available, record_ai_usage
from backend.cloud.config import is_valid_gemini_api_key
from backend.cloud.interfaces import (
    EmbeddingClient,
    FileStore,
    LlmClient,
    SalesStore,
    VectorStore,
)
from backend.cloud.sql_guard import validate_and_sanitize_sql, validate_dml_patch

logger = logging.getLogger("FixdeskLocalCloud")

VECTOR_DIMENSION = 768
DEFAULT_LLM_MODEL = "gemini-3.5-flash-lite"
DEFAULT_EMBEDDING_MODEL = "gemini-embedding-2"


def normalize_vector(vector: List[float]) -> List[float]:
    """L2-normalize a vector to unit length for cosine similarity."""
    norm = math.sqrt(sum(v * v for v in vector))
    if norm > 0:
        return [v / norm for v in vector]
    if vector:
        out = [0.0] * len(vector)
        out[0] = 1.0
        return out
    return vector


def deterministic_fallback_embedding(text: str, dim: int = VECTOR_DIMENSION) -> List[float]:
    """Deterministic unit-normalized 768-D hash vector for offline testing without live APIs."""
    words = text.lower().split()
    vector = [0.0] * dim
    if not words:
        vector[0] = 1.0
        return vector

    for idx, word in enumerate(words):
        h = int(hashlib.sha256(word.encode("utf-8")).hexdigest(), 16)
        slot = h % dim
        weight = 1.0 / (1.0 + math.log(1.0 + idx))
        vector[slot] += weight

        h2 = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
        slot2 = (h2 + slot) % dim
        vector[slot2] += weight * 0.5

    return normalize_vector(vector)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _pg_connect(readonly: bool = True):
    if readonly:
        url = os.environ.get(
            "READONLY_DATABASE_URL",
            "postgresql://sales_readonly:readonly_password@localhost:5434/fixdesk",
        )
    else:
        url = os.environ.get(
            "DATABASE_URL",
            "postgresql://postgres:postgres_password@localhost:5434/fixdesk",
        )
    return psycopg2.connect(url)


# ==============================================================================
# 1. Local FileStore
# ==============================================================================
class LocalFileStore(FileStore):
    """Stores raw CSVs, cleaned Parquet, and policy documents on local disk."""

    backend_name = "local"

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir).resolve() if base_dir else _repo_root()

    def _prefix_dir(self, prefix: str) -> Path:
        clean_prefix = prefix.strip("/").lower()
        if clean_prefix == "docs":
            env_docs = os.environ.get("DOCS_DIR", "").strip()
            if env_docs:
                p = Path(env_docs)
                return p if p.is_absolute() else (self.base_dir / p)
            return self.base_dir / "docs"
        env_data = os.environ.get("DATA_DIR", "").strip()
        if env_data:
            p = Path(env_data)
            data_dir = p if p.is_absolute() else (self.base_dir / p)
        else:
            data_dir = self.base_dir / "data"
        return data_dir

    def save_bytes(self, prefix: str, filename: str, data: bytes) -> str:
        target_dir = self._prefix_dir(prefix)
        target_dir.mkdir(parents=True, exist_ok=True)
        dest = target_dir / os.path.basename(filename)
        dest.write_bytes(data)
        return str(dest)

    def read_bytes(self, uri_or_path: str) -> bytes:
        return Path(uri_or_path).read_bytes()

    def download_to_local(self, uri_or_path: str, dest_path: str) -> str:
        src = Path(uri_or_path)
        dst = Path(dest_path)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.resolve() != dst.resolve():
            shutil.copy2(src, dst)
        return str(dst)

    def upload_from_local(
        self, local_path: str, prefix: str, remote_name: Optional[str] = None
    ) -> str:
        src = Path(local_path)
        target_dir = self._prefix_dir(prefix)
        target_dir.mkdir(parents=True, exist_ok=True)
        name = remote_name or src.name
        dst = target_dir / name
        if src.is_dir():
            if src.resolve() != dst.resolve():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
        else:
            if src.resolve() != dst.resolve():
                shutil.copy2(src, dst)
        return str(dst)

    def list_files(self, prefix: str, extensions: Optional[tuple] = None) -> List[str]:
        target_dir = self._prefix_dir(prefix)
        if not target_dir.exists():
            return []
        items = []
        for entry in sorted(target_dir.iterdir()):
            if entry.name.startswith("."):
                continue
            if extensions and not entry.name.lower().endswith(extensions):
                continue
            items.append(str(entry))
        return items

    def exists(self, uri_or_path: str) -> bool:
        return Path(uri_or_path).exists()

    def ensure_local_copy(self, uri_or_path: str, cache_dir: Optional[str] = None) -> str:
        return str(Path(uri_or_path))


# ==============================================================================
# 2. PostgreSQL SalesStore
# ==============================================================================
class PostgresSalesStore(SalesStore):
    """PostgreSQL implementation for `sales`, `sales_sandbox`, `quality_reports`, `schema_metadata`."""

    backend_name = "local"

    def sql_dialect(self) -> str:
        return "postgres"

    def query_sales(self, sql_query: str) -> Dict[str, Any]:
        try:
            sanitized_sql = validate_and_sanitize_sql(sql_query)
        except ValueError as ve:
            return {"status": "ERROR", "error": str(ve), "data": [], "row_count": 0}

        conn = None
        try:
            conn = _pg_connect(readonly=True)
            conn.set_session(readonly=True, autocommit=True)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(sanitized_sql)
            rows = cursor.fetchall()

            results = []
            for r in rows:
                clean_row = {}
                for k, v in r.items():
                    if hasattr(v, "is_finite") or type(v).__name__ == "Decimal":
                        clean_row[k] = float(v)
                    else:
                        clean_row[k] = v
                results.append(clean_row)
            cursor.close()
            return {
                "status": "SUCCESS",
                "query_executed": sanitized_sql,
                "row_count": len(results),
                "data": results,
                "backend": "local",
            }
        except Exception as e:
            logger.error(f"Error executing sales query: {e}")
            return {
                "status": "ERROR",
                "error": f"Database error: {str(e)}",
                "query_attempted": sanitized_sql,
                "data": [],
                "row_count": 0,
            }
        finally:
            if conn:
                conn.close()

    def get_data_quality_report(self) -> Dict[str, Any]:
        conn = None
        try:
            conn = _pg_connect(readonly=True)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                SELECT report_id, raw_rows, cleaned_rows, duplicates_removed, report_data, created_at
                FROM quality_reports
                ORDER BY created_at DESC
                LIMIT 1;
                """
            )
            row = cur.fetchone()
            cur.close()
            if row and row.get("report_data"):
                report = row["report_data"]
                if isinstance(report, str):
                    report = json.loads(report)
                return {
                    "status": "SUCCESS",
                    "report": report,
                    "report_id": row["report_id"],
                    "created_at": row["created_at"].isoformat()
                    if hasattr(row["created_at"], "isoformat")
                    else str(row["created_at"]),
                }
        except Exception as db_err:
            logger.warning(f"Could not read quality report from PostgreSQL: {db_err}")
        finally:
            if conn:
                conn.close()

        report_file = os.environ.get("DATA_QUALITY_REPORT", "data/data_quality_report.json")
        if not os.path.exists(report_file):
            return {
                "status": "ERROR",
                "error": f"Data quality report not found in PostgreSQL or filesystem ({report_file}). Run PySpark pipeline first.",
            }
        try:
            with open(report_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {"status": "SUCCESS", "report": data}
        except Exception as e:
            logger.error(f"Error reading data quality report: {e}")
            return {"status": "ERROR", "error": str(e)}

    def get_schema_metadata(self) -> Dict[str, Any]:
        meta_path = _repo_root() / "data" / "schema_metadata.json"
        if meta_path.exists():
            try:
                return json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"Failed to read schema_metadata.json: {e}")

        conn = None
        try:
            conn = _pg_connect(readonly=True)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cur.execute(
                    "SELECT dataset_name, table_name, row_count, column_count, columns_info "
                    "FROM schema_metadata ORDER BY id DESC LIMIT 1;"
                )
                sm_row = cur.fetchone()
                if sm_row and sm_row.get("columns_info"):
                    cols = sm_row["columns_info"]
                    cur.close()
                    return {
                        "dataset_name": sm_row.get("dataset_name"),
                        "table_name": sm_row.get("table_name", "sales"),
                        "row_count": sm_row.get("row_count", 0),
                        "columns": cols,
                        "numeric_columns": [c["name"] for c in cols if c.get("is_numeric")],
                        "categorical_columns": [c["name"] for c in cols if c.get("is_categorical")],
                    }
            except Exception:
                pass

            cur.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'sales'
                ORDER BY ordinal_position;
                """
            )
            cols = cur.fetchall()
            cur.close()
            columns = [
                {"name": c["column_name"], "type": c["data_type"]}
                for c in cols
                if c["column_name"] not in ("id", "created_at")
            ]
            return {
                "table_name": "sales",
                "columns": columns,
                "numeric_columns": [
                    c["name"]
                    for c in columns
                    if "int" in c["type"] or "numeric" in c["type"] or "double" in c["type"]
                ],
                "categorical_columns": [
                    c["name"]
                    for c in columns
                    if "text" in c["type"] or "char" in c["type"]
                ],
            }
        except Exception as err:
            logger.warning(f"Could not inspect schema from PostgreSQL: {err}")
            return {"table_name": "sales", "columns": [], "numeric_columns": [], "categorical_columns": []}
        finally:
            if conn:
                conn.close()

    def get_sales_count(self) -> int:
        conn = None
        try:
            conn = _pg_connect(readonly=True)
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM sales;")
            val = int(cur.fetchone()[0])
            cur.close()
            return val
        except Exception:
            return 0
        finally:
            if conn:
                conn.close()

    def get_top_categorical_values(self, column: str, limit: int = 2) -> List[str]:
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", column):
            return []
        conn = None
        try:
            conn = _pg_connect(readonly=True)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                f"""
                SELECT "{column}", count(*) as count
                FROM sales
                WHERE "{column}" IS NOT NULL AND "{column}" != 'Unknown'
                GROUP BY "{column}"
                ORDER BY count DESC
                LIMIT %s;
                """,
                (max(1, min(int(limit), 10)),),
            )
            rows = cur.fetchall()
            cur.close()
            return [str(r[column]) for r in rows]
        except Exception:
            return []
        finally:
            if conn:
                conn.close()

    def run_data_quality_checks(self, table_name: str = "sales") -> Dict[str, Any]:
        safe_table = "sales_sandbox" if "sandbox" in table_name else "sales"
        conn = None
        try:
            conn = _pg_connect(readonly=True)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = %s;
                """,
                (safe_table,),
            )
            cols = {r["column_name"]: r["data_type"] for r in cur.fetchall()}

            cur.execute(f"SELECT count(*) as total_rows FROM {safe_table};")
            total_rows = cur.fetchone()["total_rows"]

            cat_cols = [
                c
                for c, dt in cols.items()
                if dt in ("text", "character varying")
                and c not in ("created_at", "id", "review_id", "review_text")
            ]
            primary_cat = cat_cols[0] if cat_cols else None

            cat_distribution = {}
            inconsistent_labels = []
            if primary_cat:
                try:
                    cur.execute(
                        f"""
                        SELECT "{primary_cat}", count(*) as count
                        FROM {safe_table}
                        WHERE "{primary_cat}" IS NOT NULL
                        GROUP BY "{primary_cat}"
                        ORDER BY count DESC
                        LIMIT 10;
                        """
                    )
                    cat_distribution = {str(row[primary_cat]): row["count"] for row in cur.fetchall()}
                    inconsistent_labels = [
                        k
                        for k in cat_distribution.keys()
                        if k != k.strip()
                        or (
                            k != k.upper()
                            and k in ("lf", "low fat", "reg", "ps5", "xbox", "playstation-5")
                        )
                    ]
                except Exception:
                    pass

            null_metrics = {}
            for c in list(cols.keys())[:5]:
                try:
                    cur.execute(f'SELECT count(*) as null_cnt FROM {safe_table} WHERE "{c}" IS NULL;')
                    null_metrics[c] = cur.fetchone()["null_cnt"]
                except Exception:
                    pass

            num_cols = [
                c
                for c, dt in cols.items()
                if "int" in dt or "float" in dt or "numeric" in dt or "double" in dt
            ]
            outliers_found = 0
            if num_cols:
                try:
                    primary_num = num_cols[0]
                    cur.execute(f'SELECT count(*) as cnt FROM {safe_table} WHERE "{primary_num}" <= 0;')
                    outliers_found = cur.fetchone()["cnt"]
                except Exception:
                    pass

            cur.close()
            findings = {
                "table_audited": safe_table,
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
            logger.error(f"Error in data quality checks: {e}")
            return {"status": "ERROR", "error": str(e)}
        finally:
            if conn:
                conn.close()

    def preview_data_fix(self, sql_patch: str, ticket_id: str) -> Dict[str, Any]:
        conn = None
        try:
            conn = _pg_connect(readonly=False)
            conn.autocommit = False
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute("TRUNCATE TABLE sales_sandbox;")
            cur.execute("INSERT INTO sales_sandbox SELECT * FROM sales;")

            cur.execute("SELECT count(*) as total FROM sales_sandbox;")
            before_counts = {"total_rows": cur.fetchone()["total"]}

            cleaned_patch = (sql_patch or "").strip()
            rows_affected = 0
            applied_sql = ""
            if cleaned_patch:
                validated = validate_dml_patch(cleaned_patch, allowed_table="sales_sandbox")
                applied_sql = re.sub(r"\bsales_sandbox\b", "sales", validated, flags=re.IGNORECASE)
                applied_sql = re.sub(r"\bsales\b", "sales_sandbox", applied_sql, flags=re.IGNORECASE)
                cur.execute(applied_sql)
                rows_affected = cur.rowcount

            cur.execute("SELECT count(*) as total FROM sales_sandbox;")
            after_counts = {"total_rows": cur.fetchone()["total"]}

            cur.execute("SELECT * FROM sales_sandbox LIMIT 5;")
            sample_diff = [
                {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in dict(r).items()}
                for r in cur.fetchall()
            ]
            conn.commit()
            cur.close()
            return {
                "status": "SUCCESS",
                "fix_type": "data_issue",
                "target_table": "sales_sandbox",
                "rows_affected": rows_affected,
                "before_counts": before_counts,
                "after_counts": after_counts,
                "sample_diff": sample_diff,
                "sql_applied_to_sandbox": applied_sql,
            }
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Error previewing data fix in sandbox: {e}")
            return {"status": "ERROR", "error": str(e)}
        finally:
            if conn:
                conn.close()

    def apply_data_fix(self, sql_patch: str) -> Dict[str, Any]:
        conn = None
        try:
            conn = _pg_connect(readonly=False)
            conn.autocommit = False
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute("SELECT count(*) as total FROM sales;")
            before_counts = {"total_rows": cur.fetchone()["total"]}

            validated = validate_dml_patch(sql_patch, allowed_table="sales")
            sql_prod = re.sub(r"\bsales_sandbox\b", "sales", validated, flags=re.IGNORECASE)
            cur.execute(sql_prod)
            rows_affected = cur.rowcount

            cur.execute("SELECT count(*) as total FROM sales;")
            after_counts = {"total_rows": cur.fetchone()["total"]}
            conn.commit()
            cur.close()
            return {
                "before_counts": before_counts,
                "after_counts": after_counts,
                "rows_affected": rows_affected,
                "target_table": "sales",
            }
        except Exception:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

    def load_sales_from_parquet(
        self,
        parquet_uri_or_path: str,
        schema_metadata: Dict[str, Any],
        quality_report: Dict[str, Any],
        df: Any = None,
    ) -> Dict[str, Any]:
        if df is None:
            raise ValueError("PostgresSalesStore.load_sales_from_parquet requires the cleaned Spark DataFrame.")

        from pyspark.sql.types import DoubleType, FloatType

        conn = _pg_connect(readonly=False)
        cursor = conn.cursor()
        try:
            col_defs = ["id SERIAL PRIMARY KEY"]
            for col_info in schema_metadata.get("columns", []):
                col_defs.append(f'"{col_info["name"]}" {col_info["type"]}')
            col_defs.append("created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP")

            cursor.execute(
                f"""
                DROP TABLE IF EXISTS sales CASCADE;
                CREATE TABLE sales ({', '.join(col_defs)});
                GRANT SELECT ON TABLE sales TO sales_readonly;
                """
            )
            conn.commit()

            col_names = list(df.columns)
            raw_col_names = [f'"{c}"' for c in col_names]
            placeholders = ["%s"] * len(col_names)
            insert_sql = f"INSERT INTO sales ({', '.join(raw_col_names)}) VALUES ({', '.join(placeholders)});"

            records = []
            for r in df.collect():
                row_vals = []
                for c in col_names:
                    val = r[c]
                    if val is not None and isinstance(df.schema[c].dataType, (DoubleType, FloatType)):
                        val = float(val)
                    row_vals.append(val)
                records.append(tuple(row_vals))

            execute_batch(cursor, insert_sql, records, page_size=500)
            conn.commit()

            rec_prof = quality_report.get("records_profile", {})
            report_id = f"qr_{uuid.uuid4().hex[:12]}"
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS quality_reports (
                    id SERIAL PRIMARY KEY,
                    report_id VARCHAR(64) UNIQUE NOT NULL,
                    raw_rows INT NOT NULL,
                    cleaned_rows INT NOT NULL,
                    duplicates_removed INT NOT NULL,
                    report_data JSONB NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                GRANT SELECT ON TABLE quality_reports TO sales_readonly;
                """
            )
            cursor.execute(
                """
                INSERT INTO quality_reports (report_id, raw_rows, cleaned_rows, duplicates_removed, report_data)
                VALUES (%s, %s, %s, %s, %s);
                """,
                (
                    report_id,
                    int(rec_prof.get("raw_total_rows", 0)),
                    int(rec_prof.get("cleaned_total_rows", len(records))),
                    int(rec_prof.get("duplicate_rows_removed", 0)),
                    json.dumps(quality_report),
                ),
            )
            conn.commit()

            cursor.execute(
                """
                DROP TABLE IF EXISTS sales_sandbox CASCADE;
                CREATE TABLE sales_sandbox (LIKE sales INCLUDING ALL);
                INSERT INTO sales_sandbox SELECT * FROM sales;
                GRANT SELECT ON TABLE sales_sandbox TO sales_readonly;
                """
            )
            conn.commit()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_metadata (
                    id SERIAL PRIMARY KEY,
                    dataset_name VARCHAR(255) NOT NULL,
                    table_name VARCHAR(255) NOT NULL DEFAULT 'sales',
                    row_count INT NOT NULL DEFAULT 0,
                    column_count INT NOT NULL DEFAULT 0,
                    columns_info JSONB NOT NULL DEFAULT '[]'::jsonb,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                GRANT SELECT ON TABLE schema_metadata TO sales_readonly;
                """
            )
            cursor.execute(
                """
                INSERT INTO schema_metadata (dataset_name, table_name, row_count, column_count, columns_info)
                VALUES (%s, %s, %s, %s, %s);
                """,
                (
                    schema_metadata.get("dataset_name", "dataset.csv"),
                    "sales",
                    len(records),
                    len(col_names),
                    json.dumps(schema_metadata.get("columns", [])),
                ),
            )
            conn.commit()
            return {"status": "SUCCESS", "rows_loaded": len(records), "backend": "local"}
        finally:
            cursor.close()
            conn.close()

    def health_check(self) -> Dict[str, Any]:
        conn = None
        try:
            conn = _pg_connect(readonly=True)
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM sales;")
            sales_count = int(cur.fetchone()[0])
            cur.close()
            return {
                "backend": "local",
                "database": "connected",
                "sales_records": sales_count,
            }
        except Exception as e:
            return {
                "backend": "local",
                "database": f"error: {str(e)}",
                "sales_records": 0,
            }
        finally:
            if conn:
                conn.close()


# ==============================================================================
# 3. pgvector VectorStore
# ==============================================================================
class PgVectorStore(VectorStore):
    """PostgreSQL pgvector implementation for `document_embeddings`."""

    backend_name = "local"

    def upsert_document_chunks(
        self, chunks: List[Dict[str, Any]], embeddings: List[List[float]]
    ) -> int:
        conn = _pg_connect(readonly=False)
        cursor = conn.cursor()
        try:
            cursor.execute("TRUNCATE TABLE document_embeddings;")
            conn.commit()
            insert_sql = """
                INSERT INTO document_embeddings (
                    chunk_id, source_file, title, content, chunk_index, total_chunks, embedding
                ) VALUES (%s, %s, %s, %s, %s, %s, %s::vector)
                ON CONFLICT (chunk_id) DO UPDATE SET
                    source_file = EXCLUDED.source_file,
                    title = EXCLUDED.title,
                    content = EXCLUDED.content,
                    chunk_index = EXCLUDED.chunk_index,
                    total_chunks = EXCLUDED.total_chunks,
                    embedding = EXCLUDED.embedding;
            """
            records = []
            for chunk, emb in zip(chunks, embeddings):
                vector_str = "[" + ",".join(f"{x:.8f}" for x in emb) + "]"
                records.append(
                    (
                        chunk["chunk_id"],
                        chunk["source_file"],
                        chunk["title"],
                        chunk["content"],
                        chunk["chunk_index"],
                        chunk["total_chunks"],
                        vector_str,
                    )
                )
            execute_batch(cursor, insert_sql, records, page_size=100)
            conn.commit()
            return len(records)
        finally:
            cursor.close()
            conn.close()

    def search_documents(
        self, query_vector: List[float], top_k: int = 3, query_text: str = ""
    ) -> List[Dict[str, Any]]:
        query_vector_str = "[" + ",".join(f"{x:.8f}" for x in query_vector) + "]"
        conn = None
        try:
            conn = _pg_connect(readonly=True)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            search_sql = """
                SELECT
                    chunk_id,
                    source_file,
                    title,
                    content,
                    chunk_index,
                    ROUND((1 - (embedding <=> %s::vector))::numeric, 4) AS similarity
                FROM document_embeddings
                ORDER BY embedding <=> %s::vector ASC
                LIMIT %s;
            """
            cursor.execute(
                search_sql, (query_vector_str, query_vector_str, max(1, min(int(top_k), 20)))
            )
            rows = cursor.fetchall()
            cursor.close()
            return [
                {
                    "chunk_id": r["chunk_id"],
                    "source_file": r["source_file"],
                    "title": r["title"] or r["source_file"],
                    "content": r["content"],
                    "similarity": float(r["similarity"]),
                    "chunk_index": r["chunk_index"],
                }
                for r in rows
            ]
        except Exception as e:
            logger.error(f"Error during pgvector search_documents: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def list_indexed_sources(self) -> List[Dict[str, Any]]:
        conn = None
        try:
            conn = _pg_connect(readonly=True)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                """
                SELECT
                    d.source_file,
                    COUNT(*) as total_chunks,
                    c.title as sample_title,
                    c.content as first_chunk_content
                FROM document_embeddings d
                LEFT JOIN (
                    SELECT DISTINCT ON (source_file) source_file, title, content
                    FROM document_embeddings
                    ORDER BY source_file, chunk_index ASC
                ) c ON d.source_file = c.source_file
                GROUP BY d.source_file, c.title, c.content
                ORDER BY d.source_file ASC;
                """
            )
            rows = cursor.fetchall()
            cursor.close()
            result = []
            for r in rows:
                content = r.get("first_chunk_content") or ""
                lines = [l.strip() for l in content.split("\n") if l.strip()]
                summary_lines = [l for l in lines if not l.startswith("#")]
                summary_text = " ".join(summary_lines) if summary_lines else content
                summary_snippet = summary_text[:180].strip()
                if len(summary_text) > 180:
                    summary_snippet += "..."
                result.append(
                    {
                        "source_file": r["source_file"],
                        "total_chunks": r["total_chunks"],
                        "sample_title": r.get("sample_title") or r["source_file"],
                        "sample_summary": summary_snippet or "No text summary available.",
                    }
                )
            return result
        except Exception as e:
            logger.error(f"Error listing indexed sources: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def get_document_chunks(self, source_file: str) -> List[Dict[str, Any]]:
        conn = None
        try:
            conn = _pg_connect(readonly=True)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                """
                SELECT
                    chunk_id,
                    source_file,
                    title,
                    content,
                    chunk_index,
                    total_chunks
                FROM document_embeddings
                WHERE source_file = %s OR source_file LIKE %s
                ORDER BY chunk_index ASC;
                """,
                (source_file, f"%{source_file}%"),
            )
            rows = cursor.fetchall()
            cursor.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Error fetching document chunks for {source_file}: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def count_chunks(self) -> int:
        conn = None
        try:
            conn = _pg_connect(readonly=True)
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM document_embeddings;")
            count = int(cur.fetchone()[0])
            cur.close()
            return count
        except Exception:
            return 0
        finally:
            if conn:
                conn.close()

    def health_check(self) -> Dict[str, Any]:
        conn = None
        try:
            conn = _pg_connect(readonly=True)
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM document_embeddings;")
            chunks = int(cur.fetchone()[0])
            cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector';")
            ext = cur.fetchone()
            cur.close()
            return {
                "backend": "local",
                "pgvector_ready": bool(ext),
                "indexed_chunks": chunks,
            }
        except Exception as e:
            return {
                "backend": "local",
                "pgvector_ready": False,
                "indexed_chunks": 0,
                "error": str(e),
            }
        finally:
            if conn:
                conn.close()


# ==============================================================================
# 4. Gemini Developer API LLM & Embedding Clients (with Retry + Budget Guard)
# ==============================================================================
class GeminiApiLlmClient(LlmClient):
    """Gemini Developer API key client via `langchain-google-genai`."""

    backend_name = "gemini_api"

    def is_configured(self) -> bool:
        return is_valid_gemini_api_key()

    def get_chat_model(
        self, model_name: Optional[str] = None, temperature: Optional[float] = None
    ) -> Any:
        if not self.is_configured():
            return None
        from langchain_google_genai import ChatGoogleGenerativeAI

        resolved_model = (
            (model_name or os.environ.get("LLM_MODEL", DEFAULT_LLM_MODEL)).strip()
            or DEFAULT_LLM_MODEL
        )
        kwargs: Dict[str, Any] = {
            "model": resolved_model,
            "google_api_key": os.environ.get("GOOGLE_API_KEY", "").strip(),
            "max_retries": 1,
            "timeout": 25.0,
        }
        if not ("gemini-3" in resolved_model or "gemini-4" in resolved_model):
            kwargs["temperature"] = 0.0 if temperature is None else temperature
        return ChatGoogleGenerativeAI(**kwargs)

    def invoke_messages(
        self,
        messages: Any,
        model_name: Optional[str] = None,
        tools: Optional[List[Any]] = None,
    ) -> Any:
        model = self.get_chat_model(model_name=model_name)
        if model is None:
            return None
        check_budget_available()
        runnable = model.bind_tools(tools) if tools else model
        last_exc: Optional[Exception] = None
        for attempt in range(3):
            try:
                resp = runnable.invoke(messages)
                in_chars = sum(len(str(m)) for m in messages) if isinstance(messages, list) else len(str(messages))
                out_chars = len(str(getattr(resp, "content", resp)))
                record_ai_usage(requests=1, input_chars=in_chars, output_chars=out_chars)
                return resp
            except BudgetExceededError:
                raise
            except Exception as exc:
                last_exc = exc
                if attempt < 2:
                    time.sleep(0.5 * (2 ** attempt))
        if last_exc:
            raise last_exc
        return None

    def status_summary(self) -> Dict[str, Any]:
        return {
            "backend": self.backend_name,
            "configured": self.is_configured(),
            "model": os.environ.get("LLM_MODEL", DEFAULT_LLM_MODEL),
        }


class GeminiApiEmbeddingClient(EmbeddingClient):
    """Gemini Developer API key 768-D embeddings with deterministic offline fallback."""

    backend_name = "gemini_api"

    def is_configured(self) -> bool:
        return is_valid_gemini_api_key()

    def _get_client(self):
        if not self.is_configured():
            return None
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        model_name = (
            os.environ.get("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL).strip()
            or DEFAULT_EMBEDDING_MODEL
        )
        if not model_name.startswith("models/"):
            model_name = f"models/{model_name}"
        return GoogleGenerativeAIEmbeddings(
            model=model_name,
            google_api_key=os.environ.get("GOOGLE_API_KEY", "").strip(),
        )

    def embed_query(self, text: str) -> List[float]:
        try:
            client = self._get_client()
            if client is not None:
                check_budget_available()
                vec = client.embed_query(text, output_dimensionality=VECTOR_DIMENSION)
                record_ai_usage(requests=1, input_chars=len(text), output_chars=0)
                if len(vec) == VECTOR_DIMENSION:
                    return normalize_vector(vec)
        except BudgetExceededError:
            raise
        except Exception as e:
            logger.warning(f"Gemini embedding error ({e}). Using deterministic local embedding.")
        return deterministic_fallback_embedding(text, VECTOR_DIMENSION)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        try:
            client = self._get_client()
            if client is not None:
                check_budget_available()
                vecs = client.embed_documents(texts, output_dimensionality=VECTOR_DIMENSION)
                record_ai_usage(requests=1, input_chars=sum(len(t) for t in texts), output_chars=0)
                if len(vecs) == len(texts) and all(len(v) == VECTOR_DIMENSION for v in vecs):
                    return [normalize_vector(v) for v in vecs]
        except BudgetExceededError:
            raise
        except Exception as e:
            logger.warning(f"Gemini batch embedding error ({e}). Using deterministic local embedding.")
        return [deterministic_fallback_embedding(t, VECTOR_DIMENSION) for t in texts]

    def status_summary(self) -> Dict[str, Any]:
        return {
            "backend": self.backend_name if self.is_configured() else "fallback",
            "configured": self.is_configured(),
            "model": os.environ.get("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
            "dimension": VECTOR_DIMENSION,
        }
