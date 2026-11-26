"""
Command-Line Interface for Project Init:
  project-init index <name> [--full] [--watch] [--config path]
  project-init reindex <name> [--full] [--config path]
  project-init ask <name> "<question>" [--config path]
  project-init status <name> [--config path]
"""

import argparse
import json
import sys
import threading
import time
from typing import List, Optional

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from project_init.config import get_project_config, load_projects_config
from project_init.indexer import index_project
from project_init.retriever import ask_codebase
from project_init.security import SKIP_DIR_NAMES
from project_init.store import PostgresCodeStore


class _DebouncedReindexHandler(FileSystemEventHandler):
    """Trigger incremental re-index after short quiet window on source edits."""

    def __init__(self, project_name: str, config_path: Optional[str], debounce_seconds: float = 1.0):
        self.project_name = project_name
        self.config_path = config_path
        self.debounce_seconds = debounce_seconds
        self._lock = threading.Lock()
        self._timer: Optional[threading.Timer] = None

    def _is_ignored(self, path_str: str) -> bool:
        parts = set(path_str.replace("\\", "/").split("/"))
        return bool(parts & SKIP_DIR_NAMES)

    def _schedule(self):
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self.debounce_seconds, self._run_reindex)
            self._timer.daemon = True
            self._timer.start()

    def _run_reindex(self):
        try:
            stats = index_project(self.project_name, config_path=self.config_path, incremental=True)
            print(
                f"[watch] reindexed {stats.project}: +{stats.indexed_files} files, "
                f"-{stats.removed_files} removed, {stats.indexed_chunks} chunks, "
                f"{len(stats.skipped_files)} skipped",
                flush=True,
            )
        except Exception as exc:
            print(f"[watch] reindex error: {exc}", file=sys.stderr, flush=True)

    def on_any_event(self, event):
        if event.is_directory:
            return
        if self._is_ignored(event.src_path):
            return
        self._schedule()


def run_watch_loop(project_name: str, config_path: Optional[str] = None) -> None:
    """Initial incremental index followed by blocking filesystem watcher."""
    stats = index_project(project_name, config_path=config_path, incremental=True)
    cfg = get_project_config(project_name, config_path=config_path)
    print(
        f"Indexed '{stats.project}' at commit {stats.commit_hash}: "
        f"{stats.indexed_files} updated files, {stats.unchanged_files} unchanged, "
        f"{stats.indexed_chunks} chunks ({len(stats.skipped_files)} skipped)."
    )
    print(f"Watching {cfg.root_path} for changes... Press Ctrl+C to stop.", flush=True)

    handler = _DebouncedReindexHandler(project_name, config_path=config_path)
    observer = Observer()
    observer.schedule(handler, str(cfg.root_path), recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="project-init",
        description="Index and query project codebases safely with secret exclusion.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List projects configured in projects.yaml")
    p_list.add_argument("--config", default=None, help="Path to projects.yaml")

    for cmd_name, cmd_help in (
        ("index", "Index a registered project"),
        ("reindex", "Incrementally re-index a registered project"),
    ):
        p = sub.add_parser(cmd_name, help=cmd_help)
        p.add_argument("name", help="Project name from projects.yaml")
        p.add_argument("--full", action="store_true", help="Force full re-index instead of incremental")
        p.add_argument("--watch", action="store_true", help="Watch repository and re-index on change")
        p.add_argument("--config", default=None, help="Path to projects.yaml")

    p_status = sub.add_parser("status", help="Show index status and skipped count for a project")
    p_status.add_argument("name", help="Project name from projects.yaml")
    p_status.add_argument("--config", default=None, help="Path to projects.yaml")

    p_ask = sub.add_parser("ask", help="Ask a question about an indexed codebase")
    p_ask.add_argument("name", help="Project name from projects.yaml")
    p_ask.add_argument("question", help="Plain-English question")
    p_ask.add_argument("--config", default=None, help="Path to projects.yaml")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "list":
        configs = load_projects_config(config_path=args.config)
        print(json.dumps([{"name": c.name, "local_path": c.local_path, "default_branch": c.default_branch} for c in configs], indent=2))
        return 0

    if args.command in ("index", "reindex"):
        if args.watch:
            run_watch_loop(args.name, config_path=args.config)
            return 0
        stats = index_project(
            args.name,
            config_path=args.config,
            incremental=(not args.full),
        )
        print(
            json.dumps(
                {
                    "project": stats.project,
                    "commit_hash": stats.commit_hash,
                    "incremental": stats.incremental,
                    "scanned_files": stats.scanned_files,
                    "indexed_files": stats.indexed_files,
                    "unchanged_files": stats.unchanged_files,
                    "removed_files": stats.removed_files,
                    "indexed_chunks": stats.indexed_chunks,
                    "dropped_chunks": stats.dropped_chunks,
                    "skipped_count": len(stats.skipped_files),
                },
                indent=2,
            )
        )
        return 0

    if args.command == "status":
        store = PostgresCodeStore()
        status = store.get_project_status(args.name)
        print(json.dumps(status or {"project": args.name, "status": "not_indexed"}, default=str, indent=2))
        return 0

    if args.command == "ask":
        result = ask_codebase(args.name, args.question, config_path=args.config)
        print(result["answer"])
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
