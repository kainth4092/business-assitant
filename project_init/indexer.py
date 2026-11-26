"""
Incremental Indexing & Live Watch Orchestrator for Project Init.
Combines `.gitignore` + skip rules, pre-index secret scanning, AST chunking,
chunk-level security gating, cached summaries, 768-D embeddings, and
git-diff / content-hash incremental updates.
"""

import hashlib
import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from backend.rag.embeddings import get_texts_embeddings
from project_init.chunker import CodeChunk, ParsedFileResult, parse_file_to_chunks
from project_init.config import ProjectConfig, get_project_config, resolve_safe_path
from project_init.security import (
    check_chunk_security,
    classify_file,
    extract_lockfile_summary,
    load_gitignore_spec,
    scan_file_for_secrets,
    SKIP_DIR_NAMES,
)
from project_init.store import PostgresCodeStore
from project_init.summarizer import generate_chunk_summary

logger = logging.getLogger("ProjectInitIndexer")


@dataclass
class IndexStats:
    """Structured telemetry returned after running `index` or `reindex`."""

    project: str
    commit_hash: str
    incremental: bool
    scanned_files: int = 0
    indexed_files: int = 0
    unchanged_files: int = 0
    removed_files: int = 0
    indexed_chunks: int = 0
    dropped_chunks: int = 0
    skipped_files: List[Dict[str, str]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def get_git_head_commit(project_root: Path) -> str:
    """Return current git HEAD short/full SHA, or 'working-tree' if unavailable."""
    try:
        res = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()[:40]
    except Exception:
        pass
    return "working-tree"


def get_git_changed_files(project_root: Path, base_commit: Optional[str]) -> Tuple[set, set]:
    """
    Use `git diff --name-status` to detect modified/added and deleted files since `base_commit`.
    Returns `(changed_or_added_paths, deleted_paths)` as POSIX relative paths.
    """
    changed, deleted = set(), set()
    if not base_commit or base_commit == "working-tree":
        return changed, deleted
    try:
        res = subprocess.run(
            ["git", "-C", str(project_root), "diff", "--name-status", base_commit, "HEAD"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        if res.returncode != 0:
            return changed, deleted
        for line in res.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            status = parts[0].strip()
            if status.startswith("R") and len(parts) >= 3:
                deleted.add(Path(parts[1]).as_posix())
                changed.add(Path(parts[2]).as_posix())
            elif status == "D":
                deleted.add(Path(parts[1]).as_posix())
            else:
                changed.add(Path(parts[1]).as_posix())
    except Exception:
        pass
    return changed, deleted


def _walk_repository(project_root: Path) -> List[Path]:
    """Walk `project_root` safely without recursing into .git / node_modules / venvs."""
    discovered: List[Path] = []
    root_real = Path(os.path.realpath(str(project_root)))
    for dirpath, dirnames, filenames in os.walk(root_real, followlinks=False):
        # Prune skip directories early while keeping top-level skip record awareness minimal
        dirnames[:] = sorted([d for d in dirnames if d not in SKIP_DIR_NAMES])
        for fname in sorted(filenames):
            full = Path(dirpath) / fname
            try:
                resolve_safe_path(root_real, str(full))
                discovered.append(full)
            except PermissionError:
                continue
    return discovered


def index_project(
    project_name: str,
    config_path: Optional[str] = None,
    incremental: bool = True,
    store: Optional[Any] = None,
    embedder: Optional[Callable[[List[str]], List[List[float]]]] = None,
    llm_summarizer: Optional[Callable[[CodeChunk], str]] = None,
) -> IndexStats:
    """
    Index or incrementally re-index `project_name` defined in `projects.yaml`.
    Strictly excludes sensitive files & chunks with secrets before embedding or DB storage.
    """
    cfg: ProjectConfig = get_project_config(project_name, config_path=config_path)
    project_root = cfg.root_path
    if not project_root.exists() or not project_root.is_dir():
        raise FileNotFoundError(f"Project path does not exist: {project_root}")

    active_store = store or PostgresCodeStore()
    active_store.ensure_schema()

    embed_fn = embedder or get_texts_embeddings
    commit_hash = get_git_head_commit(project_root)

    prev_status = active_store.get_project_status(cfg.name)
    prev_commit = prev_status.get("last_commit_hash") if prev_status else None
    active_store.upsert_project(
        name=cfg.name,
        local_path=str(project_root),
        default_branch=cfg.default_branch,
        status="indexing",
        last_commit_hash=commit_hash,
    )

    existing_hashes: Dict[str, str] = active_store.get_file_hashes(cfg.name) if incremental else {}
    git_changed, git_deleted = (
        get_git_changed_files(project_root, prev_commit) if incremental else (set(), set())
    )
    gitignore_spec = load_gitignore_spec(project_root)

    stats = IndexStats(
        project=cfg.name,
        commit_hash=commit_hash,
        incremental=incremental,
    )

    clean_files_on_disk: set = set()
    files_to_index: List[Tuple[str, Path, str, str]] = []  # (rel_path, path, action, content_hash)

    for full_path in _walk_repository(project_root):
        stats.scanned_files += 1
        rel_path = full_path.relative_to(project_root).as_posix()

        decision = classify_file(
            project_root=project_root,
            file_path=full_path,
            gitignore_spec=gitignore_spec,
            include_globs=cfg.include,
            exclude_globs=cfg.exclude,
        )

        if decision.action == "skip":
            stats.skipped_files.append(
                {"file_path": rel_path, "reason": decision.reason, "rule": decision.rule}
            )
            continue

        # Pre-index secret scan for all candidate text/source files
        try:
            text_content = full_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            stats.skipped_files.append(
                {"file_path": rel_path, "reason": f"Read error: {exc}", "rule": "os_error"}
            )
            continue

        if decision.action == "lockfile_summary":
            summary_txt = extract_lockfile_summary(full_path, rel_path)
            content_hash = hashlib.sha256(summary_txt.encode("utf-8")).hexdigest()
        else:
            findings = scan_file_for_secrets(full_path, content=text_content)
            if findings:
                stats.skipped_files.append(
                    {
                        "file_path": rel_path,
                        "reason": f"Secret finding detected ({', '.join(findings[:3])})",
                        "rule": f"secret_scanner:{findings[0]}",
                    }
                )
                continue
            content_hash = hashlib.sha256(text_content.encode("utf-8", errors="ignore")).hexdigest()

        clean_files_on_disk.add(rel_path)

        if (
            incremental
            and rel_path in existing_hashes
            and existing_hashes[rel_path] == content_hash
            and rel_path not in git_changed
        ):
            stats.unchanged_files += 1
            continue

        files_to_index.append((rel_path, full_path, decision.action, content_hash))

    # Delete removed, newly gitignored, or newly flagged secret files
    stale_paths = (set(existing_hashes.keys()) - clean_files_on_disk) | git_deleted
    for old_rel in sorted(stale_paths):
        active_store.delete_file(cfg.name, old_rel)
        stats.removed_files += 1

    # Parse, chunk-filter, summarize (with content_hash cache), and embed updated files
    for rel_path, full_path, action, content_hash in files_to_index:
        if action == "lockfile_summary":
            lock_summary = extract_lockfile_summary(full_path, rel_path)
            parsed = ParsedFileResult(
                file_path=rel_path,
                language="lockfile",
                line_count=1,
                content_hash=content_hash,
                imports=[],
                symbols=[{"name": Path(rel_path).name, "kind": "lockfile_summary", "start_line": 1, "end_line": 1}],
                chunks=[
                    CodeChunk(
                        project=cfg.name,
                        file_path=rel_path,
                        language="lockfile",
                        symbol_name=Path(rel_path).name,
                        chunk_kind="lockfile_summary",
                        start_line=1,
                        end_line=1,
                        commit_hash=commit_hash,
                        content=lock_summary,
                    )
                ],
            )
        else:
            raw_text = full_path.read_text(encoding="utf-8", errors="replace")
            parsed = parse_file_to_chunks(
                project=cfg.name,
                rel_path=rel_path,
                text=raw_text,
                commit_hash=commit_hash,
            )

        # Second line of defense: per-chunk regex + entropy filter
        safe_chunks: List[CodeChunk] = []
        for ch in parsed.chunks:
            rule_hit = check_chunk_security(ch.content)
            if rule_hit:
                stats.dropped_chunks += 1
                stats.skipped_files.append(
                    {
                        "file_path": rel_path,
                        "reason": f"Chunk L{ch.start_line}-{ch.end_line} dropped by second-line filter ({rule_hit})",
                        "rule": rule_hit,
                    }
                )
            else:
                safe_chunks.append(ch)

        if not safe_chunks:
            active_store.delete_file(cfg.name, rel_path)
            continue

        # Summary cache lookup + update
        chunk_hashes = [c.content_hash for c in safe_chunks]
        summary_cache = active_store.get_cached_summaries(chunk_hashes)
        new_summaries: Dict[str, str] = {}
        for ch in safe_chunks:
            was_cached = ch.content_hash in summary_cache
            ch.summary = generate_chunk_summary(
                ch,
                cache=summary_cache,
                llm_summarizer=llm_summarizer,
            )
            if not was_cached:
                new_summaries[ch.content_hash] = ch.summary
        if new_summaries:
            active_store.save_cached_summaries(new_summaries)

        # Compute embeddings in batch for safe chunks only
        embed_inputs = [
            f"{ch.file_path} | {ch.symbol_name} | {ch.summary}\n{ch.content[:1800]}"
            for ch in safe_chunks
        ]
        vectors = embed_fn(embed_inputs)

        active_store.replace_file_chunks(
            project=cfg.name,
            file_path=rel_path,
            language=parsed.language,
            commit_hash=commit_hash,
            content_hash=parsed.content_hash,
            line_count=parsed.line_count,
            imports=parsed.imports,
            symbols=parsed.symbols,
            chunks=safe_chunks,
            embeddings=vectors,
        )
        stats.indexed_files += 1
        stats.indexed_chunks += len(safe_chunks)

    active_store.replace_skipped_files(cfg.name, stats.skipped_files)
    active_store.refresh_project_counts(cfg.name, commit_hash)
    return stats
