"""
Project Init — Project-aware codebase RAG package with defense-in-depth secret exclusion.
"""

from project_init.config import ProjectConfig, load_projects_config, get_project_config, resolve_safe_path
from project_init.security import (
    classify_file,
    scan_file_for_secrets,
    check_chunk_security,
    redact_secrets,
    extract_lockfile_summary,
)

__all__ = [
    "ProjectConfig",
    "load_projects_config",
    "get_project_config",
    "resolve_safe_path",
    "classify_file",
    "scan_file_for_secrets",
    "check_chunk_security",
    "redact_secrets",
    "extract_lockfile_summary",
]
