"""
Read-only MCP Tools for Project Init Codebase RAG:
- list_projects
- search_code
- get_file_outline
- find_symbol

Security guarantees:
- Strict project-root confinement via resolve_safe_path
- Mandatory skip-list and .gitignore blocking on every path
- Output redaction replacing any secret-like string with [REDACTED]
"""

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from project_init.chunker import parse_file_to_chunks
from project_init.config import get_project_config, load_projects_config, resolve_safe_path
from project_init.retriever import search_codebase
from project_init.security import classify_file, load_gitignore_spec, redact_secrets, scan_file_for_secrets
from project_init.store import PostgresCodeStore


def _ensure_allowed_project_file(
    project: str,
    file_path: str,
    config_path: Optional[str] = None,
) -> Path:
    """Validate that `file_path` stays inside project root and is NOT on the skip list."""
    cfg = get_project_config(project, config_path=config_path)
    safe_path = resolve_safe_path(cfg.root_path, file_path)
    gitignore_spec = load_gitignore_spec(cfg.root_path)
    decision = classify_file(
        project_root=cfg.root_path,
        file_path=safe_path,
        gitignore_spec=gitignore_spec,
        include_globs=cfg.include,
        exclude_globs=cfg.exclude,
    )
    if decision.action == "skip":
        raise PermissionError(f"Access blocked by sensitive-file policy: {decision.reason}")
    return safe_path


def list_projects(
    config_path: Optional[str] = None,
    store: Optional[Any] = None,
) -> str:
    """List configured projects and their latest indexing telemetry (read-only)."""
    active_store = store or PostgresCodeStore()
    configs = load_projects_config(config_path=config_path)
    indexed_by_name: Dict[str, Dict[str, Any]] = {}
    try:
        for row in active_store.list_projects():
            indexed_by_name[row["name"]] = row
    except Exception:
        indexed_by_name = {}

    results: List[Dict[str, Any]] = []
    for cfg in configs:
        db_row = indexed_by_name.get(cfg.name, {})
        results.append(
            {
                "name": cfg.name,
                "local_path": cfg.local_path,
                "default_branch": cfg.default_branch,
                "status": db_row.get("status", "not_indexed"),
                "last_commit_hash": db_row.get("last_commit_hash"),
                "last_indexed_at": str(db_row["last_indexed_at"]) if db_row.get("last_indexed_at") else None,
                "file_count": int(db_row.get("file_count") or 0),
                "chunk_count": int(db_row.get("chunk_count") or 0),
                "skipped_count": int(db_row.get("skipped_count") or 0),
            }
        )
    return redact_secrets(json.dumps({"status": "SUCCESS", "projects": results}, indent=2))


def search_code(
    project: str,
    query: str,
    top_k: int = 6,
    config_path: Optional[str] = None,
    store: Optional[Any] = None,
    embedder: Optional[Callable[[str], List[float]]] = None,
) -> str:
    """Hybrid search across indexed codebase chunks with file:line citations (read-only)."""
    try:
        get_project_config(project, config_path=config_path)
        hits = search_codebase(
            project=project,
            query=query,
            top_k=max(1, min(int(top_k), 20)),
            config_path=config_path,
            store=store,
            embedder=embedder,
        )
        return redact_secrets(json.dumps({"status": "SUCCESS", "project": project, "results": hits}, indent=2))
    except Exception as exc:
        return json.dumps({"status": "ERROR", "error": str(exc)})


def get_file_outline(
    project: str,
    file_path: str,
    config_path: Optional[str] = None,
    store: Optional[Any] = None,
) -> str:
    """
    Return symbols, imports, line counts, and outline for a safe path within the project.
    Rejects path escapes (e.g., '../..') and sensitive/skipped files.
    """
    try:
        cfg = get_project_config(project, config_path=config_path)
        safe_path = _ensure_allowed_project_file(project, file_path, config_path=config_path)
        rel_path = safe_path.relative_to(cfg.root_path).as_posix()

        active_store = store or PostgresCodeStore()
        try:
            outline = active_store.get_file_outline(project, rel_path)
        except Exception:
            outline = None

        if outline is None:
            if not safe_path.exists():
                return json.dumps({"status": "ERROR", "error": f"File not found: {rel_path}"})
            text = safe_path.read_text(encoding="utf-8", errors="replace")
            if scan_file_for_secrets(safe_path, content=text):
                raise PermissionError("Access blocked: file triggered pre-index secret scanner.")
            parsed = parse_file_to_chunks(project, rel_path, text)
            outline = {
                "file_path": parsed.file_path,
                "language": parsed.language,
                "line_count": parsed.line_count,
                "chunk_count": len(parsed.chunks),
                "imports": parsed.imports,
                "symbols": parsed.symbols,
            }

        return redact_secrets(json.dumps({"status": "SUCCESS", "project": project, "outline": outline}, indent=2))
    except Exception as exc:
        return json.dumps({"status": "ERROR", "error": str(exc)})


def find_symbol(
    project: str,
    symbol_name: str,
    limit: int = 15,
    config_path: Optional[str] = None,
    store: Optional[Any] = None,
) -> str:
    """Locate functions, classes, methods, tables, or headings by symbol name (read-only)."""
    try:
        cfg = get_project_config(project, config_path=config_path)
        gitignore_spec = load_gitignore_spec(cfg.root_path)
        active_store = store or PostgresCodeStore()
        matches = active_store.find_symbol(project, symbol_name, limit=max(1, min(int(limit), 30)))

        safe_matches: List[Dict[str, Any]] = []
        for row in matches:
            rel_path = str(row.get("file_path", ""))
            try:
                full = resolve_safe_path(cfg.root_path, rel_path)
            except PermissionError:
                continue
            if full.exists():
                decision = classify_file(
                    project_root=cfg.root_path,
                    file_path=full,
                    gitignore_spec=gitignore_spec,
                    include_globs=cfg.include,
                    exclude_globs=cfg.exclude,
                )
                if decision.action == "skip":
                    continue
            safe_matches.append(
                {
                    "file_path": rel_path,
                    "symbol_name": row.get("symbol_name"),
                    "chunk_kind": row.get("chunk_kind"),
                    "language": row.get("language"),
                    "start_line": int(row.get("start_line") or 1),
                    "end_line": int(row.get("end_line") or 1),
                    "commit_hash": row.get("commit_hash"),
                    "summary": redact_secrets(str(row.get("summary", ""))),
                    "citation": f"{rel_path}:{row.get('start_line')}-{row.get('end_line')}",
                }
            )

        return redact_secrets(
            json.dumps({"status": "SUCCESS", "project": project, "matches": safe_matches}, indent=2)
        )
    except Exception as exc:
        return json.dumps({"status": "ERROR", "error": str(exc)})
