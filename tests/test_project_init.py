"""
Comprehensive offline pytest suite for Stage 9 (Project Init / Codebase RAG):
- Security & secret filtering (.gitignore, .env*, private keys, AWS keys, chunk entropy/regex, [REDACTED] output)
- AST-aware chunking (Python, JS/JSX via tree-sitter; SQL via sqlparse; Markdown headings; sliding window; lockfile summary)
- Content-hash summary caching & incremental re-index (modify, add, delete files)
- Hybrid retrieval, import graph structure queries, exact file:line citations & "not found in the indexed code"
- MCP read-only tools & path traversal / skip-list enforcement
- FastAPI /projects endpoints & zero secret leakage across chunks, store, logs, API responses, and answers
"""

import json
import logging
import math
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import psycopg2
import pytest
from fastapi.testclient import TestClient

from backend.main import app, get_code_store
from backend.rag.embeddings import get_fallback_embedding
from mcp_server.code_tools import find_symbol, get_file_outline, list_projects, search_code
from project_init.chunker import parse_file_to_chunks
from project_init.indexer import index_project
from project_init.retriever import ask_codebase, search_codebase
from project_init.security import check_chunk_security, redact_secrets, scan_file_for_secrets
from project_init.store import PostgresCodeStore


def _cosine_sim(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


class InMemoryCodeStore:
    """Deterministic isolated test double mirroring `PostgresCodeStore` methods."""

    def __init__(self):
        self.projects: Dict[str, Dict[str, Any]] = {}
        self.file_metadata: Dict[tuple, Dict[str, Any]] = {}
        self.chunks: Dict[str, Dict[str, Any]] = {}
        self.summary_cache: Dict[str, str] = {}
        self.skipped_files: Dict[str, List[Dict[str, Any]]] = {}

    def ensure_schema(self) -> None:
        return None

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
        cur = self.projects.get(name, {})
        self.projects[name] = {
            "name": name,
            "local_path": local_path,
            "default_branch": default_branch,
            "last_commit_hash": last_commit_hash or cur.get("last_commit_hash"),
            "last_indexed_at": "2026-11-26T15:30:00Z",
            "file_count": file_count if file_count is not None else cur.get("file_count", 0),
            "chunk_count": chunk_count if chunk_count is not None else cur.get("chunk_count", 0),
            "skipped_count": skipped_count if skipped_count is not None else cur.get("skipped_count", 0),
            "status": status,
            "last_error": last_error,
        }

    def get_file_hashes(self, project: str) -> Dict[str, str]:
        return {
            fpath: meta["content_hash"]
            for (proj, fpath), meta in self.file_metadata.items()
            if proj == project
        }

    def get_cached_summaries(self, content_hashes: List[str]) -> Dict[str, str]:
        return {h: self.summary_cache[h] for h in content_hashes if h in self.summary_cache}

    def save_cached_summaries(self, summaries: Dict[str, str]) -> None:
        for k, v in summaries.items():
            self.summary_cache[k] = redact_secrets(v)

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
        self.delete_file(project, file_path)
        for ch, vec in zip(chunks, embeddings):
            self.chunks[ch.chunk_uid] = {
                "chunk_uid": ch.chunk_uid,
                "project": project,
                "file_path": ch.file_path,
                "language": ch.language,
                "symbol_name": ch.symbol_name,
                "chunk_kind": ch.chunk_kind,
                "start_line": ch.start_line,
                "end_line": ch.end_line,
                "commit_hash": ch.commit_hash,
                "content_hash": ch.content_hash,
                "summary": redact_secrets(ch.summary),
                "content": redact_secrets(ch.content),
                "embedding": vec,
            }
        self.file_metadata[(project, file_path)] = {
            "file_path": file_path,
            "language": language,
            "commit_hash": commit_hash,
            "content_hash": content_hash,
            "line_count": line_count,
            "chunk_count": len(chunks),
            "imports": list(imports),
            "symbols": list(symbols),
        }

    def delete_file(self, project: str, file_path: str) -> None:
        self.file_metadata.pop((project, file_path), None)
        doomed = [
            uid
            for uid, row in self.chunks.items()
            if row["project"] == project and row["file_path"] == file_path
        ]
        for uid in doomed:
            self.chunks.pop(uid, None)

    def replace_skipped_files(self, project: str, skipped: List[Dict[str, str]]) -> None:
        self.skipped_files[project] = [
            {
                "file_path": s["file_path"],
                "reason": redact_secrets(s["reason"]),
                "rule": s.get("rule", "policy"),
                "scanned_at": "2026-11-26T15:30:00Z",
            }
            for s in skipped
        ]

    def refresh_project_counts(self, project: str, commit_hash: str) -> Dict[str, int]:
        fc = sum(1 for (p, _) in self.file_metadata if p == project)
        cc = sum(1 for c in self.chunks.values() if c["project"] == project)
        sc = len(self.skipped_files.get(project, []))
        proj = self.projects[project]
        proj.update(
            {
                "file_count": fc,
                "chunk_count": cc,
                "skipped_count": sc,
                "last_commit_hash": commit_hash,
                "status": "indexed",
            }
        )
        return {"file_count": fc, "chunk_count": cc, "skipped_count": sc}

    def list_projects(self) -> List[Dict[str, Any]]:
        return [dict(v) for v in self.projects.values()]

    def get_project_status(self, project: str) -> Optional[Dict[str, Any]]:
        if project not in self.projects:
            return None
        info = dict(self.projects[project])
        langs: Dict[str, int] = {}
        for (p, _), meta in self.file_metadata.items():
            if p == project:
                langs[meta["language"]] = langs.get(meta["language"], 0) + 1
        info["languages"] = [{"language": k, "files": v} for k, v in langs.items()]
        return info

    def get_skipped_files(self, project: str) -> List[Dict[str, Any]]:
        return list(self.skipped_files.get(project, []))

    def get_file_outline(self, project: str, file_path: str) -> Optional[Dict[str, Any]]:
        meta = self.file_metadata.get((project, file_path))
        return dict(meta) if meta else None

    def list_file_tree(self, project: str, limit: int = 200) -> List[Dict[str, Any]]:
        rows = [
            dict(meta)
            for (p, _), meta in sorted(self.file_metadata.items(), key=lambda kv: kv[0][1])
            if p == project
        ]
        return rows[:limit]

    def find_files_importing(self, project: str, module_query: str) -> List[Dict[str, Any]]:
        q = module_query.strip().lower()
        out = []
        for (p, _), meta in sorted(self.file_metadata.items(), key=lambda kv: kv[0][1]):
            if p != project:
                continue
            if any(q in str(imp).lower() for imp in meta.get("imports", [])):
                out.append(
                    {
                        "file_path": meta["file_path"],
                        "language": meta["language"],
                        "imports": meta["imports"],
                    }
                )
        return out

    def find_symbol(self, project: str, symbol_query: str, limit: int = 20) -> List[Dict[str, Any]]:
        q = symbol_query.strip().lower()
        out = [
            dict(c)
            for c in self.chunks.values()
            if c["project"] == project and q in c["symbol_name"].lower()
        ]
        out.sort(key=lambda r: (0 if r["symbol_name"].lower() == q else 1, r["file_path"], r["start_line"]))
        return out[:limit]

    def search_hybrid(
        self, project: str, query: str, query_embedding: List[float], limit: int = 12
    ) -> List[Dict[str, Any]]:
        tokens = [t.lower() for t in query.split() if len(t) >= 2]
        scored = []
        for ch in self.chunks.values():
            if ch["project"] != project:
                continue
            vec_score = max(0.0, _cosine_sim(query_embedding, ch["embedding"]))
            hay = f"{ch['file_path']} {ch['symbol_name']} {ch['summary']} {ch['content']}".lower()
            kw_score = sum(1.0 for t in tokens if t in hay) / max(1, len(tokens))
            row = dict(ch)
            row["vec_score"] = vec_score
            row["kw_score"] = kw_score
            scored.append(row)
        scored.sort(key=lambda r: 0.65 * r["vec_score"] + 0.35 * r["kw_score"], reverse=True)
        return scored[:limit]


def _make_fake_embed_batch(texts: List[str]) -> List[List[float]]:
    return [get_fallback_embedding(t) for t in texts]


def _make_fake_embed_one(text: str) -> List[float]:
    return get_fallback_embedding(text)


# Synthetic test secrets constructed dynamically and strictly confined inside tmp_path
SECRET_ENV_VAL = "SUPER_SECRET_DB_PASS_998877"
SECRET_PEM_BODY = "MIIEowIBAAKCAQEA9999FAKERESERVEDKEYMATERIAL8888"
SECRET_AWS_KEY = "AKIA" + "IOSFODNN7EXAMPLE"
SECRET_NPM_TOKEN = "npm_" + "AbCdEf1234567890GhIjKlMnOpQr"
SECRET_CONN_DSN = "postgresql://svc_orders:UltraSecretConn91@" + "localhost:5432/orders_db"


@pytest.fixture()
def fixture_repo(tmp_path: Path):
    """Create a temporary git repo with intentional secrets and clean multi-language code."""
    repo = tmp_path / "sample_orders_repo"
    repo.mkdir()

    subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "ci@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "CI Runner"], check=True)

    # .gitignore + gitignored file
    (repo / ".gitignore").write_text("ignored_secret_dump.txt\nbuild/\n", encoding="utf-8")
    (repo / "ignored_secret_dump.txt").write_text(f"PASSWORD={SECRET_ENV_VAL}\n", encoding="utf-8")

    # Forbidden secret files
    (repo / ".env").write_text(f"DATABASE_PASSWORD={SECRET_ENV_VAL}\n", encoding="utf-8")
    (repo / ".env.local").write_text(f"API_SECRET={SECRET_ENV_VAL}\n", encoding="utf-8")
    (repo / "server.key").write_text(
        f"-----BEGIN RSA PRIVATE KEY-----\n{SECRET_PEM_BODY}\n-----END RSA PRIVATE KEY-----\n",
        encoding="utf-8",
    )
    (repo / ".npmrc").write_text(f"//registry.npmjs.org/:_authToken={SECRET_NPM_TOKEN}\n", encoding="utf-8")
    (repo / "aws_leak.py").write_text(
        f'def get_aws_credentials():\n    return "{SECRET_AWS_KEY}"\n',
        encoding="utf-8",
    )

    # File mixing safe function + chunk containing inline localhost connection string
    (repo / "dsn_mixed.py").write_text(
        "def healthy_helper():\n"
        '    """Returns clean helper label."""\n'
        '    return "clean-helper-ok"\n\n'
        "def unsafe_local_dsn():\n"
        f'    return "{SECRET_CONN_DSN}"\n',
        encoding="utf-8",
    )

    # Lockfile (should summarize package count without raw tarball hashes)
    (repo / "package-lock.json").write_text(
        json.dumps(
            {
                "name": "orders-service",
                "lockfileVersion": 3,
                "packages": {
                    "": {"name": "orders-service", "version": "1.0.0"},
                    "node_modules/react": {"version": "19.3.1", "integrity": "sha512-superlonghash"},
                },
            }
        ),
        encoding="utf-8",
    )

    # Clean Python code importing db_client
    (repo / "src").mkdir()
    (repo / "src" / "orders_api.py").write_text(
        '"""Orders REST API handlers."""\n\n'
        "import db_client\n\n"
        "class OrdersController:\n"
        '    """Coordinates order creation and lookup."""\n\n'
        "    def create_order(self, item_id: str, qty: int) -> dict:\n"
        "        return db_client.insert_order(item_id, qty)\n\n"
        "    def get_order_status(self, order_id: str) -> str:\n"
        "        return db_client.fetch_status(order_id)\n\n\n"
        "def list_recent_orders(limit: int = 10) -> list:\n"
        '    """List latest customer orders."""\n'
        "    return db_client.select_recent(limit)\n",
        encoding="utf-8",
    )

    # Clean JSX component
    (repo / "src" / "OrdersPanel.jsx").write_text(
        "import React from 'react';\n"
        "import { fetchOrders } from './api';\n\n"
        "export function OrdersPanel({ status }) {\n"
        "  return <div>{status}</div>;\n"
        "}\n",
        encoding="utf-8",
    )

    # Clean SQL schema
    (repo / "schema.sql").write_text(
        "CREATE TABLE orders (\n"
        "    id SERIAL PRIMARY KEY,\n"
        "    customer_id INT NOT NULL,\n"
        "    total NUMERIC(10, 2) NOT NULL\n"
        ");\n\n"
        "CREATE VIEW high_value_orders AS\n"
        "SELECT id, customer_id, total FROM orders WHERE total > 500;\n",
        encoding="utf-8",
    )

    # Clean Markdown doc
    (repo / "README.md").write_text(
        "# Orders Service\n\nHandles order lifecycle.\n\n## Endpoints\n\nImplemented in src/orders_api.py.\n",
        encoding="utf-8",
    )

    # Config text for sliding window fallback
    (repo / "settings.txt").write_text(
        "\n".join(f"setting_{i}=value_{i}" for i in range(1, 75)),
        encoding="utf-8",
    )

    subprocess.run(["git", "-C", str(repo), "add", "src", "schema.sql", "README.md", "settings.txt", ".gitignore"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "Initial fixture commit"], check=True, capture_output=True)

    cfg_file = tmp_path / "projects.yaml"
    cfg_file.write_text(
        f"""
projects:
  - name: demo-orders
    local_path: {repo}
    default_branch: main
    include:
      - "**/*.py"
      - "**/*.jsx"
      - "**/*.sql"
      - "**/*.md"
      - "**/*.txt"
    exclude:
      - "build/**"
""".strip(),
        encoding="utf-8",
    )

    return {"repo": repo, "config": str(cfg_file), "tmp": tmp_path}


def _assert_no_secrets_anywhere(store: InMemoryCodeStore, extra_texts: Optional[List[str]] = None):
    forbidden = [SECRET_ENV_VAL, SECRET_PEM_BODY, SECRET_AWS_KEY, SECRET_NPM_TOKEN, "UltraSecretConn91"]
    blobs = []
    for ch in store.chunks.values():
        blobs.extend([ch["content"], ch["summary"], ch["file_path"], ch["symbol_name"]])
    for sk_list in store.skipped_files.values():
        for sk in sk_list:
            blobs.extend([sk["file_path"], sk["reason"], sk["rule"]])
    for summ in store.summary_cache.values():
        blobs.append(summ)
    if extra_texts:
        blobs.extend(extra_texts)

    combined = "\n".join(str(b) for b in blobs)
    for sec in forbidden:
        assert sec not in combined, f"Secret '{sec}' leaked into stored/returned output!"


def test_secrets_excluded_across_files_chunks_store_and_logs(fixture_repo, caplog):
    """Prove no secret values enter chunks, store, skipped_files report, logs, or answers."""
    caplog.set_level(logging.DEBUG)
    store = InMemoryCodeStore()

    stats = index_project(
        "demo-orders",
        config_path=fixture_repo["config"],
        incremental=False,
        store=store,
        embedder=_make_fake_embed_batch,
    )

    skipped_paths = {s["file_path"] for s in stats.skipped_files}
    assert ".env" in skipped_paths
    assert ".env.local" in skipped_paths
    assert "server.key" in skipped_paths
    assert ".npmrc" in skipped_paths
    assert "aws_leak.py" in skipped_paths
    assert "ignored_secret_dump.txt" in skipped_paths
    assert stats.dropped_chunks >= 1  # dsn_mixed.py's unsafe_local_dsn dropped by chunk filter

    # Clean helper in dsn_mixed.py stays indexed, unsafe function dropped
    dsn_chunks = [c for c in store.chunks.values() if c["file_path"] == "dsn_mixed.py"]
    assert any(c["symbol_name"] == "healthy_helper" for c in dsn_chunks)
    assert not any(c["symbol_name"] == "unsafe_local_dsn" for c in dsn_chunks)

    # Lockfile summary indexed without raw hash strings
    lock_chunks = [c for c in store.chunks.values() if c["file_path"] == "package-lock.json"]
    assert len(lock_chunks) == 1
    assert "sha512-superlonghash" not in lock_chunks[0]["content"]
    assert "tracked_packages=2" in lock_chunks[0]["content"]

    log_blob = "\n".join(rec.getMessage() for rec in caplog.records)
    _assert_no_secrets_anywhere(store, extra_texts=[log_blob])


def test_ast_chunking_languages_and_line_citations(fixture_repo):
    """Verify AST symbol splitting for Python, JSX, SQL, Markdown, and sliding window fallback."""
    repo = fixture_repo["repo"]

    py_res = parse_file_to_chunks("demo-orders", "src/orders_api.py", (repo / "src" / "orders_api.py").read_text())
    py_syms = {c.symbol_name for c in py_res.chunks}
    assert "OrdersController.create_order" in py_syms
    assert "OrdersController.get_order_status" in py_syms
    assert "list_recent_orders" in py_syms
    assert "db_client" in py_res.imports

    jsx_res = parse_file_to_chunks("demo-orders", "src/OrdersPanel.jsx", (repo / "src" / "OrdersPanel.jsx").read_text())
    jsx_syms = {c.symbol_name for c in jsx_res.chunks}
    assert "OrdersPanel" in jsx_syms
    assert "./api" in jsx_res.imports

    sql_res = parse_file_to_chunks("demo-orders", "schema.sql", (repo / "schema.sql").read_text())
    sql_syms = {c.symbol_name for c in sql_res.chunks}
    assert "orders" in sql_syms
    assert "high_value_orders" in sql_syms

    md_res = parse_file_to_chunks("demo-orders", "README.md", (repo / "README.md").read_text())
    md_syms = {c.symbol_name for c in md_res.chunks}
    assert "Orders Service" in md_syms
    assert "Endpoints" in md_syms

    txt_res = parse_file_to_chunks("demo-orders", "settings.txt", (repo / "settings.txt").read_text())
    assert len(txt_res.chunks) == 2
    assert txt_res.chunks[0].start_line == 1
    assert txt_res.chunks[0].end_line == 60
    assert txt_res.chunks[1].start_line == 51


def test_summary_caching_and_incremental_reindex_with_deletion(fixture_repo):
    """Prove unchanged chunks reuse cached summaries, modified files re-embed, and deleted files purge chunks."""
    store = InMemoryCodeStore()
    repo = fixture_repo["repo"]
    llm_calls = []

    def counting_summarizer(chunk):
        llm_calls.append(chunk.symbol_name)
        return f"Summary of {chunk.symbol_name}"

    stats1 = index_project(
        "demo-orders",
        config_path=fixture_repo["config"],
        incremental=True,
        store=store,
        embedder=_make_fake_embed_batch,
        llm_summarizer=counting_summarizer,
    )
    first_call_count = len(llm_calls)
    assert first_call_count > 0
    assert stats1.indexed_files >= 5

    # Run incremental again with zero edits -> 0 files re-indexed, 0 extra LLM summary calls
    stats2 = index_project(
        "demo-orders",
        config_path=fixture_repo["config"],
        incremental=True,
        store=store,
        embedder=_make_fake_embed_batch,
        llm_summarizer=counting_summarizer,
    )
    assert stats2.indexed_files == 0
    assert stats2.unchanged_files >= 5
    assert len(llm_calls) == first_call_count

    # Modify one file, add one new file, delete settings.txt -> re-index only those 2 files + delete 1
    (repo / "src" / "orders_api.py").write_text(
        (repo / "src" / "orders_api.py").read_text() + "\ndef cancel_order(order_id: str) -> bool:\n    return True\n",
        encoding="utf-8",
    )
    (repo / "src" / "billing.py").write_text(
        "def charge_invoice(inv_id: str) -> str:\n    return inv_id\n",
        encoding="utf-8",
    )
    (repo / "settings.txt").unlink()

    stats3 = index_project(
        "demo-orders",
        config_path=fixture_repo["config"],
        incremental=True,
        store=store,
        embedder=_make_fake_embed_batch,
        llm_summarizer=counting_summarizer,
    )
    assert stats3.indexed_files == 2
    assert stats3.removed_files == 1
    assert not any(c["file_path"] == "settings.txt" for c in store.chunks.values())
    assert any(c["symbol_name"] == "cancel_order" for c in store.chunks.values())
    assert any(c["symbol_name"] == "charge_invoice" for c in store.chunks.values())
    # Cached summaries for unmodified create_order were reused without re-invoking LLM
    assert llm_calls.count("OrdersController.create_order") == 1


def test_ask_codebase_citations_imports_not_found_and_output_redaction(fixture_repo):
    """Test grounded Q&A, structural import questions, not-found fallback, and [REDACTED] output scrub."""
    store = InMemoryCodeStore()
    index_project(
        "demo-orders",
        config_path=fixture_repo["config"],
        incremental=False,
        store=store,
        embedder=_make_fake_embed_batch,
    )

    # Normal codebase question returns citations with file:line
    ans = ask_codebase(
        "demo-orders",
        "Where is the orders API implemented?",
        config_path=fixture_repo["config"],
        store=store,
        embedder=_make_fake_embed_one,
    )
    assert ans["found"] is True
    assert any(c["file_path"] == "src/orders_api.py" for c in ans["citations"])
    assert "orders_api.py:" in ans["answer"]

    # Structure import question ("which files import X")
    imp_ans = ask_codebase(
        "demo-orders",
        "Which files import db_client?",
        config_path=fixture_repo["config"],
        store=store,
        embedder=_make_fake_embed_one,
    )
    assert imp_ans["found"] is True
    assert any(m["file_path"] == "src/orders_api.py" for m in imp_ans["import_matches"])

    # Unrelated question -> explicit "not found in the indexed code"
    missing = ask_codebase(
        "demo-orders",
        "Where is the quantum flux capacitor warp drive calibrated?",
        config_path=fixture_repo["config"],
        store=store,
        embedder=_make_fake_embed_one,
    )
    assert missing["found"] is False
    assert missing["answer"] == "not found in the indexed code"

    # Output filter redacts any accidental secret echoed by LLM
    leaking_ans = ask_codebase(
        "demo-orders",
        "Where is create_order implemented?",
        config_path=fixture_repo["config"],
        store=store,
        embedder=_make_fake_embed_one,
        llm_answerer=lambda q, ev: f"Look at src/orders_api.py:8-9; token is {SECRET_AWS_KEY} and {SECRET_CONN_DSN}",
    )
    assert "[REDACTED]" in leaking_ans["answer"]
    assert SECRET_AWS_KEY not in leaking_ans["answer"]
    assert "UltraSecretConn91" not in leaking_ans["answer"]


def test_mcp_tools_path_traversal_and_skip_enforcement(fixture_repo):
    """MCP tools return accurate code info while blocking path traversal and skipped files."""
    store = InMemoryCodeStore()
    index_project(
        "demo-orders",
        config_path=fixture_repo["config"],
        incremental=False,
        store=store,
        embedder=_make_fake_embed_batch,
    )

    proj_json = json.loads(list_projects(config_path=fixture_repo["config"], store=store))
    assert proj_json["status"] == "SUCCESS"
    assert proj_json["projects"][0]["name"] == "demo-orders"
    assert proj_json["projects"][0]["file_count"] >= 4

    search_res = json.loads(
        search_code(
            "demo-orders",
            "create_order",
            config_path=fixture_repo["config"],
            store=store,
            embedder=_make_fake_embed_one,
        )
    )
    assert search_res["status"] == "SUCCESS"
    assert any(r["file_path"] == "src/orders_api.py" for r in search_res["results"])

    sym_res = json.loads(
        find_symbol("demo-orders", "create_order", config_path=fixture_repo["config"], store=store)
    )
    assert sym_res["status"] == "SUCCESS"
    assert sym_res["matches"][0]["symbol_name"] == "OrdersController.create_order"

    outline_ok = json.loads(
        get_file_outline("demo-orders", "src/orders_api.py", config_path=fixture_repo["config"], store=store)
    )
    assert outline_ok["status"] == "SUCCESS"
    assert "db_client" in outline_ok["outline"]["imports"]

    # Path traversal attack must be rejected
    traversal = json.loads(
        get_file_outline("demo-orders", "../../etc/passwd", config_path=fixture_repo["config"], store=store)
    )
    assert traversal["status"] == "ERROR"
    assert "escapes project root" in traversal["error"]

    # Sensitive skipped files must be rejected
    env_block = json.loads(
        get_file_outline("demo-orders", ".env", config_path=fixture_repo["config"], store=store)
    )
    assert env_block["status"] == "ERROR"
    assert "policy" in env_block["error"].lower()

    key_block = json.loads(
        get_file_outline("demo-orders", "server.key", config_path=fixture_repo["config"], store=store)
    )
    assert key_block["status"] == "ERROR"


def test_fastapi_projects_endpoints_zero_secret_leakage(fixture_repo, monkeypatch):
    """Verify FastAPI /projects endpoints expose real counts, skipped filenames without values, and cited answers."""
    store = InMemoryCodeStore()
    monkeypatch.setenv("PROJECTS_CONFIG_PATH", fixture_repo["config"])
    monkeypatch.setattr("project_init.indexer.get_texts_embeddings", _make_fake_embed_batch)
    monkeypatch.setattr("project_init.retriever.get_text_embedding", _make_fake_embed_one)
    app.dependency_overrides[get_code_store] = lambda: store

    try:
        client = TestClient(app)

        idx_resp = client.post("/projects/demo-orders/index", json={"incremental": False})
        assert idx_resp.status_code == 200
        idx_data = idx_resp.json()
        assert idx_data["indexed_files"] >= 4
        assert idx_data["skipped_count"] >= 5

        list_resp = client.get("/projects")
        assert list_resp.status_code == 200
        assert list_resp.json()["projects"][0]["name"] == "demo-orders"

        status_resp = client.get("/projects/demo-orders/index-status")
        assert status_resp.status_code == 200
        st = status_resp.json()
        assert st["project"]["chunk_count"] > 0
        assert len(st["file_tree"]) >= 4

        skipped_resp = client.get("/projects/demo-orders/skipped")
        assert skipped_resp.status_code == 200
        sk_payload = json.dumps(skipped_resp.json())
        assert ".env" in sk_payload
        assert "server.key" in sk_payload

        ask_resp = client.post("/projects/demo-orders/ask", json={"question": "Where is OrdersPanel rendered?"})
        assert ask_resp.status_code == 200
        ask_data = ask_resp.json()
        assert ask_data["found"] is True
        assert any(c["file_path"] == "src/OrdersPanel.jsx" for c in ask_data["citations"])

        unknown_resp = client.get("/projects/does-not-exist/index-status")
        assert unknown_resp.status_code == 404

        _assert_no_secrets_anywhere(
            store,
            extra_texts=[
                idx_resp.text,
                list_resp.text,
                status_resp.text,
                skipped_resp.text,
                ask_resp.text,
            ],
        )
    finally:
        app.dependency_overrides.clear()


def test_security_redaction_and_scanner_direct():
    """Unit test file scanner, chunk filter, and output redactor across multiple credential formats."""
    sample = (
        f"aws={SECRET_AWS_KEY}\n"
        f"gh=ghp_1234567890abcdef1234567890abcdef\n"
        f"dsn={SECRET_CONN_DSN}\n"
        'api_key = "randomHighEntr0pyValue_XYZ987654"\n'
    )
    assert len(scan_file_for_secrets(Path("dummy.py"), content=sample)) >= 2
    assert check_chunk_security(sample) is not None

    scrubbed = redact_secrets(sample)
    assert "[REDACTED]" in scrubbed
    assert SECRET_AWS_KEY not in scrubbed
    assert "ghp_1234567890abcdef" not in scrubbed
    assert "UltraSecretConn91" not in scrubbed


def test_postgres_code_rag_schema_and_secret_free_when_db_running(fixture_repo, monkeypatch):
    """
    When PostgreSQL test instance (5434) is up, execute full schema + index against
    `business_assistant_test.code_rag` and verify HNSW table contains zero secret strings.
    Skips cleanly when PostgreSQL test container is offline.
    """
    test_db_url = os.environ["DATABASE_URL"]
    try:
        conn = psycopg2.connect(test_db_url, connect_timeout=2)
        conn.close()
    except Exception as exc:
        pytest.skip(f"PostgreSQL test database offline on 5434 ({exc}); recorded in BLOCKED.md.")

    pg_store = PostgresCodeStore(database_url=test_db_url, readonly_url=os.environ["READONLY_DATABASE_URL"])
    pg_store.ensure_schema()

    index_project(
        "demo-orders",
        config_path=fixture_repo["config"],
        incremental=False,
        store=pg_store,
        embedder=_make_fake_embed_batch,
    )

    conn = psycopg2.connect(test_db_url)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT content, summary, file_path FROM code_rag.code_chunks WHERE project = 'demo-orders';")
            rows = cur.fetchall()
            assert len(rows) > 0
            blob = "\n".join(f"{r[0]} {r[1]} {r[2]}" for r in rows)
            for sec in (SECRET_ENV_VAL, SECRET_PEM_BODY, SECRET_AWS_KEY, SECRET_NPM_TOKEN, "UltraSecretConn91"):
                assert sec not in blob
    finally:
        conn.close()


def test_postgres_store_sql_isolation_and_cli_roundtrip(fixture_repo, monkeypatch):
    """
    Validate PostgresCodeStore SQL schema statements (isolated `code_rag` schema + HNSW index)
    and CLI `project-init list` / `index` / `reindex` execution using a cursor recorder.
    """
    executed_sql: List[str] = []

    class _SpyCursor:
        def __init__(self):
            self._rows = []

        def execute(self, sql, params=None):
            executed_sql.append(str(sql))
            if "SELECT file_path, content_hash" in str(sql):
                self._rows = []
            elif "SELECT count(*)" in str(sql):
                self._rows = [(0,)]
            elif "SELECT content_hash, summary" in str(sql):
                self._rows = []
            else:
                self._rows = []

        def fetchall(self):
            return list(self._rows)

        def fetchone(self):
            return self._rows[0] if self._rows else None

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class _SpyConn:
        def cursor(self, *args, **kwargs):
            return _SpyCursor()

        def commit(self):
            return None

        def close(self):
            return None

    pg_store = PostgresCodeStore()
    monkeypatch.setattr(pg_store, "_connect", lambda readonly=False: _SpyConn())
    monkeypatch.setattr("project_init.indexer.get_texts_embeddings", _make_fake_embed_batch)

    stats = index_project(
        "demo-orders",
        config_path=fixture_repo["config"],
        incremental=True,
        store=pg_store,
    )
    assert stats.indexed_files >= 4

    joined_sql = "\n".join(executed_sql)
    assert "CREATE SCHEMA IF NOT EXISTS code_rag" in joined_sql
    assert "USING hnsw (embedding vector_cosine_ops)" in joined_sql
    assert "INSERT INTO code_rag.code_chunks" in joined_sql
    assert "INSERT INTO code_rag.file_metadata" in joined_sql
    assert "INSERT INTO code_rag.skipped_files" in joined_sql
    for sec in (SECRET_ENV_VAL, SECRET_PEM_BODY, SECRET_AWS_KEY, SECRET_NPM_TOKEN, "UltraSecretConn91"):
        assert sec not in joined_sql

    # CLI list check on real projects.yaml
    proc = subprocess.run(
        ["./.venv/bin/project-init", "list"],
        capture_output=True,
        text=True,
        check=True,
    )
    listed = json.loads(proc.stdout)
    assert any(item["name"] == "business-assistant" for item in listed)
