"""
PostgreSQL (`code_rag` schema) storage layer for Project Init.
Isolated from `public.sales`, storing vectorized chunks (768-D HNSW index),
file tree & import metadata, content-hash cached summaries, and skipped-file reports.
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import psycopg2
from psycopg2.extras import RealDictCursor

from project_init.chunker import CodeChunk
from project_init.config import REPO_ROOT
from project_init.security import redact_secrets

SCHEMA_SQL_PATH = REPO_ROOT / "infra" / "code_rag_schema.sql"


def _vector_literal(vec: Sequence[float]) -> str:
    return "[" + ",".join(f"{float(v):.8f}" for v in vec) + "]"


class PostgresCodeStore:
    """PostgreSQL + pgvector backend for the `code_rag` schema."""

    def __init__(self, database_url: Optional[str] = None, readonly_url: Optional[str] = None):
        self.database_url = database_url or os.environ.get(
            "DATABASE_URL",
            "postgresql://postgres:postgres_password@localhost:5434/business_assistant",
        )
        self.readonly_url = readonly_url or os.environ.get(
            "READONLY_DATABASE_URL",
            "postgresql://sales_readonly:readonly_password@localhost:5434/business_assistant",
        )

    def _connect(self, readonly: bool = False):
        url = self.readonly_url if readonly else self.database_url
        return psycopg2.connect(url)

    def ensure_schema(self) -> None:
        """Create `code_rag` schema, tables, HNSW index, and GIN text index if absent."""
        sql_text = SCHEMA_SQL_PATH.read_text(encoding="utf-8")
        conn = self._connect(readonly=False)
        try:
            with conn.cursor() as cur:
                cur.execute(sql_text)
            conn.commit()
        finally:
            conn.close()

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
        conn = self._connect(readonly=False)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO code_rag.projects (
                        name, local_path, default_branch, last_commit_hash,
                        last_indexed_at, file_count, chunk_count, skipped_count,
                        status, last_error
                    )
                    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, COALESCE(%s, 0), COALESCE(%s, 0), COALESCE(%s, 0), %s, %s)
                    ON CONFLICT (name) DO UPDATE SET
                        local_path = EXCLUDED.local_path,
                        default_branch = EXCLUDED.default_branch,
                        last_commit_hash = COALESCE(EXCLUDED.last_commit_hash, code_rag.projects.last_commit_hash),
                        last_indexed_at = CURRENT_TIMESTAMP,
                        file_count = COALESCE(%s, code_rag.projects.file_count),
                        chunk_count = COALESCE(%s, code_rag.projects.chunk_count),
                        skipped_count = COALESCE(%s, code_rag.projects.skipped_count),
                        status = EXCLUDED.status,
                        last_error = EXCLUDED.last_error;
                    """,
                    (
                        name,
                        local_path,
                        default_branch,
                        last_commit_hash,
                        file_count,
                        chunk_count,
                        skipped_count,
                        status,
                        last_error,
                        file_count,
                        chunk_count,
                        skipped_count,
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def get_file_hashes(self, project: str) -> Dict[str, str]:
        """Return `{file_path: content_hash}` currently stored for `project`."""
        conn = self._connect(readonly=True)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT file_path, content_hash FROM code_rag.file_metadata WHERE project = %s;",
                    (project,),
                )
                return {row[0]: row[1] for row in cur.fetchall()}
        finally:
            conn.close()

    def get_cached_summaries(self, content_hashes: Sequence[str]) -> Dict[str, str]:
        """Bulk fetch cached chunk summaries keyed by SHA-256 content_hash."""
        hashes = [h for h in set(content_hashes) if h]
        if not hashes:
            return {}
        conn = self._connect(readonly=True)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT content_hash, summary FROM code_rag.summary_cache WHERE content_hash = ANY(%s);",
                    (hashes,),
                )
                return {row[0]: row[1] for row in cur.fetchall()}
        finally:
            conn.close()

    def save_cached_summaries(self, summaries: Dict[str, str]) -> None:
        if not summaries:
            return
        conn = self._connect(readonly=False)
        try:
            with conn.cursor() as cur:
                for chash, summ in summaries.items():
                    cur.execute(
                        """
                        INSERT INTO code_rag.summary_cache (content_hash, summary)
                        VALUES (%s, %s)
                        ON CONFLICT (content_hash) DO NOTHING;
                        """,
                        (chash, redact_secrets(summ)),
                    )
            conn.commit()
        finally:
            conn.close()

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
        chunks: List[CodeChunk],
        embeddings: List[List[float]],
    ) -> None:
        """Atomically replace file metadata and vectorized chunks for one file."""
        conn = self._connect(readonly=False)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM code_rag.code_chunks WHERE project = %s AND file_path = %s;",
                    (project, file_path),
                )
                for chunk, vec in zip(chunks, embeddings):
                    cur.execute(
                        """
                        INSERT INTO code_rag.code_chunks (
                            chunk_uid, project, file_path, language, symbol_name,
                            chunk_kind, start_line, end_line, commit_hash,
                            content_hash, summary, content, embedding
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
                        ON CONFLICT (chunk_uid) DO UPDATE SET
                            language = EXCLUDED.language,
                            chunk_kind = EXCLUDED.chunk_kind,
                            commit_hash = EXCLUDED.commit_hash,
                            content_hash = EXCLUDED.content_hash,
                            summary = EXCLUDED.summary,
                            content = EXCLUDED.content,
                            embedding = EXCLUDED.embedding;
                        """,
                        (
                            chunk.chunk_uid,
                            project,
                            chunk.file_path,
                            chunk.language,
                            chunk.symbol_name,
                            chunk.chunk_kind,
                            int(chunk.start_line),
                            int(chunk.end_line),
                            chunk.commit_hash,
                            chunk.content_hash,
                            redact_secrets(chunk.summary),
                            redact_secrets(chunk.content),
                            _vector_literal(vec),
                        ),
                    )

                cur.execute(
                    """
                    INSERT INTO code_rag.file_metadata (
                        project, file_path, language, commit_hash, content_hash,
                        line_count, chunk_count, imports, symbols, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, CURRENT_TIMESTAMP)
                    ON CONFLICT (project, file_path) DO UPDATE SET
                        language = EXCLUDED.language,
                        commit_hash = EXCLUDED.commit_hash,
                        content_hash = EXCLUDED.content_hash,
                        line_count = EXCLUDED.line_count,
                        chunk_count = EXCLUDED.chunk_count,
                        imports = EXCLUDED.imports,
                        symbols = EXCLUDED.symbols,
                        updated_at = CURRENT_TIMESTAMP;
                    """,
                    (
                        project,
                        file_path,
                        language,
                        commit_hash,
                        content_hash,
                        int(line_count),
                        len(chunks),
                        json.dumps(imports),
                        json.dumps(symbols),
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def delete_file(self, project: str, file_path: str) -> None:
        conn = self._connect(readonly=False)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM code_rag.code_chunks WHERE project = %s AND file_path = %s;",
                    (project, file_path),
                )
                cur.execute(
                    "DELETE FROM code_rag.file_metadata WHERE project = %s AND file_path = %s;",
                    (project, file_path),
                )
            conn.commit()
        finally:
            conn.close()

    def replace_skipped_files(self, project: str, skipped: List[Dict[str, str]]) -> None:
        """Replace skipped-file audit entries for `project` (names + reasons only)."""
        conn = self._connect(readonly=False)
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM code_rag.skipped_files WHERE project = %s;", (project,))
                for item in skipped:
                    cur.execute(
                        """
                        INSERT INTO code_rag.skipped_files (project, file_path, reason, rule)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (project, file_path, rule) DO UPDATE SET
                            reason = EXCLUDED.reason,
                            scanned_at = CURRENT_TIMESTAMP;
                        """,
                        (
                            project,
                            item["file_path"],
                            item["reason"],
                            item.get("rule", "policy"),
                        ),
                    )
            conn.commit()
        finally:
            conn.close()

    def refresh_project_counts(self, project: str, commit_hash: str) -> Dict[str, int]:
        conn = self._connect(readonly=False)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM code_rag.file_metadata WHERE project = %s;", (project,))
                file_count = int(cur.fetchone()[0])
                cur.execute("SELECT count(*) FROM code_rag.code_chunks WHERE project = %s;", (project,))
                chunk_count = int(cur.fetchone()[0])
                cur.execute("SELECT count(*) FROM code_rag.skipped_files WHERE project = %s;", (project,))
                skipped_count = int(cur.fetchone()[0])
                cur.execute(
                    """
                    UPDATE code_rag.projects
                    SET file_count = %s,
                        chunk_count = %s,
                        skipped_count = %s,
                        last_commit_hash = %s,
                        last_indexed_at = CURRENT_TIMESTAMP,
                        status = 'indexed',
                        last_error = NULL
                    WHERE name = %s;
                    """,
                    (file_count, chunk_count, skipped_count, commit_hash, project),
                )
            conn.commit()
            return {"file_count": file_count, "chunk_count": chunk_count, "skipped_count": skipped_count}
        finally:
            conn.close()

    def list_projects(self) -> List[Dict[str, Any]]:
        conn = self._connect(readonly=True)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT name, local_path, default_branch, last_commit_hash,
                           last_indexed_at, file_count, chunk_count, skipped_count,
                           status, last_error
                    FROM code_rag.projects
                    ORDER BY name ASC;
                    """
                )
                return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def get_project_status(self, project: str) -> Optional[Dict[str, Any]]:
        conn = self._connect(readonly=True)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT name, local_path, default_branch, last_commit_hash,
                           last_indexed_at, file_count, chunk_count, skipped_count,
                           status, last_error
                    FROM code_rag.projects
                    WHERE name = %s;
                    """,
                    (project,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                info = dict(row)
                cur.execute(
                    """
                    SELECT language, count(*) AS files
                    FROM code_rag.file_metadata
                    WHERE project = %s
                    GROUP BY language
                    ORDER BY files DESC;
                    """,
                    (project,),
                )
                info["languages"] = [dict(r) for r in cur.fetchall()]
                return info
        finally:
            conn.close()

    def get_skipped_files(self, project: str) -> List[Dict[str, Any]]:
        conn = self._connect(readonly=True)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT file_path, reason, rule, scanned_at
                    FROM code_rag.skipped_files
                    WHERE project = %s
                    ORDER BY file_path ASC;
                    """,
                    (project,),
                )
                return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def get_file_outline(self, project: str, file_path: str) -> Optional[Dict[str, Any]]:
        conn = self._connect(readonly=True)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT file_path, language, commit_hash, line_count, chunk_count, imports, symbols
                    FROM code_rag.file_metadata
                    WHERE project = %s AND file_path = %s;
                    """,
                    (project, file_path),
                )
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

    def list_file_tree(self, project: str, limit: int = 200) -> List[Dict[str, Any]]:
        conn = self._connect(readonly=True)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT file_path, language, line_count, chunk_count, imports
                    FROM code_rag.file_metadata
                    WHERE project = %s
                    ORDER BY file_path ASC
                    LIMIT %s;
                    """,
                    (project, limit),
                )
                return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def find_files_importing(self, project: str, module_query: str) -> List[Dict[str, Any]]:
        """Find files whose extracted `imports` array references `module_query`."""
        q = module_query.strip().lower()
        if not q:
            return []
        conn = self._connect(readonly=True)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT file_path, language, imports
                    FROM code_rag.file_metadata
                    WHERE project = %s
                      AND EXISTS (
                          SELECT 1
                          FROM jsonb_array_elements_text(imports) AS imp
                          WHERE lower(imp) LIKE %s
                      )
                    ORDER BY file_path ASC;
                    """,
                    (project, f"%{q}%"),
                )
                return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def find_symbol(self, project: str, symbol_query: str, limit: int = 20) -> List[Dict[str, Any]]:
        q = symbol_query.strip()
        if not q:
            return []
        conn = self._connect(readonly=True)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT file_path, language, symbol_name, chunk_kind,
                           start_line, end_line, commit_hash, summary, content
                    FROM code_rag.code_chunks
                    WHERE project = %s
                      AND symbol_name ILIKE %s
                    ORDER BY
                        CASE WHEN lower(symbol_name) = lower(%s) THEN 0
                             WHEN lower(symbol_name) LIKE lower(%s) THEN 1
                             ELSE 2 END,
                        file_path ASC,
                        start_line ASC
                    LIMIT %s;
                    """,
                    (project, f"%{q}%", q, f"%.{q}", limit),
                )
                rows = [dict(r) for r in cur.fetchall()]
                for r in rows:
                    r["summary"] = redact_secrets(r.get("summary", ""))
                    r["content"] = redact_secrets(r.get("content", ""))
                return rows
        finally:
            conn.close()

    def search_hybrid(
        self,
        project: str,
        query: str,
        query_embedding: List[float],
        limit: int = 12,
    ) -> List[Dict[str, Any]]:
        """
        Hybrid vector + full-text/symbol/path retrieval inside `code_rag.code_chunks`.
        Combines cosine similarity (HNSW) with `ts_rank_cd` and symbol/path matching.
        """
        vec_str = _vector_literal(query_embedding)
        cleaned_tokens = [t for t in re.findall(r"[A-Za-z0-9_]{2,}", query) if len(t) >= 2]
        keyword_query = " ".join(cleaned_tokens[:10]) or query.strip()

        conn = self._connect(readonly=True)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    WITH vec_hits AS (
                        SELECT id,
                               GREATEST(0.0, 1.0 - (embedding <=> %s::vector)) AS vec_score
                        FROM code_rag.code_chunks
                        WHERE project = %s AND embedding IS NOT NULL
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s
                    ),
                    kw_hits AS (
                        SELECT id,
                               ts_rank_cd(search_tsv, plainto_tsquery('simple', %s)) AS kw_score
                        FROM code_rag.code_chunks
                        WHERE project = %s
                          AND search_tsv @@ plainto_tsquery('simple', %s)
                        LIMIT %s
                    ),
                    combined AS (
                        SELECT COALESCE(v.id, k.id) AS id,
                               COALESCE(v.vec_score, 0.0) AS vec_score,
                               COALESCE(k.kw_score, 0.0) AS kw_score
                        FROM vec_hits v
                        FULL OUTER JOIN kw_hits k ON v.id = k.id
                    )
                    SELECT c.file_path, c.language, c.symbol_name, c.chunk_kind,
                           c.start_line, c.end_line, c.commit_hash, c.summary, c.content,
                           comb.vec_score, comb.kw_score
                    FROM combined comb
                    JOIN code_rag.code_chunks c ON c.id = comb.id
                    ORDER BY (0.65 * comb.vec_score + 0.35 * LEAST(1.0, comb.kw_score)) DESC
                    LIMIT %s;
                    """,
                    (
                        vec_str,
                        project,
                        vec_str,
                        limit * 2,
                        keyword_query,
                        project,
                        keyword_query,
                        limit * 2,
                        limit,
                    ),
                )
                rows = [dict(r) for r in cur.fetchall()]
                for r in rows:
                    r["summary"] = redact_secrets(r.get("summary", ""))
                    r["content"] = redact_secrets(r.get("content", ""))
                return rows
        finally:
            conn.close()
