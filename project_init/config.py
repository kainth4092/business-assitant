"""
Configuration loader & path-confinement utilities for Project Init (`projects.yaml`).
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = REPO_ROOT / "projects.yaml"


@dataclass
class ProjectConfig:
    """Configuration entry for a single registered codebase."""

    name: str
    local_path: str
    default_branch: str = "main"
    cloud_index_allowed: bool = False
    include: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)

    @property
    def root_path(self) -> Path:
        raw = Path(self.local_path)
        if not raw.is_absolute():
            raw = (REPO_ROOT / raw).resolve()
        else:
            raw = raw.resolve()
        return raw


def get_config_path(config_path: Optional[str] = None) -> Path:
    """Resolve active projects.yaml path from explicit arg, env var, or repo default."""
    candidate = config_path or os.environ.get("PROJECTS_CONFIG_PATH")
    if candidate:
        return Path(candidate).expanduser().resolve()
    return DEFAULT_CONFIG_PATH


def load_projects_config(config_path: Optional[str] = None) -> List[ProjectConfig]:
    """Load and validate all project entries from projects.yaml."""
    cfg_file = get_config_path(config_path)
    if not cfg_file.exists():
        return []

    with open(cfg_file, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    raw_projects = data.get("projects") or []
    configs: List[ProjectConfig] = []
    base_dir = cfg_file.parent.resolve()

    for entry in raw_projects:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "")).strip()
        local_path_raw = str(entry.get("local_path", ".")).strip()
        if not name or not local_path_raw:
            continue
        # Resolve relative paths against config file directory
        p = Path(local_path_raw)
        resolved = str((base_dir / p).resolve()) if not p.is_absolute() else str(p.resolve())
        configs.append(
            ProjectConfig(
                name=name,
                local_path=resolved,
                default_branch=str(entry.get("default_branch", "main")).strip() or "main",
                cloud_index_allowed=bool(entry.get("cloud_index_allowed", False)),
                include=[str(g) for g in (entry.get("include") or [])],
                exclude=[str(g) for g in (entry.get("exclude") or [])],
            )
        )
    return configs


def get_project_config(project_name: str, config_path: Optional[str] = None) -> ProjectConfig:
    """Lookup a single registered project by name, raising KeyError if missing."""
    for cfg in load_projects_config(config_path=config_path):
        if cfg.name == project_name:
            return cfg
    raise KeyError(f"Project '{project_name}' is not registered in projects.yaml")


def resolve_safe_path(project_root: Path | str, target_path: str) -> Path:
    """
    Resolve `target_path` relative to `project_root` and strictly enforce confinement.
    Blocks '..' escapes, absolute paths outside root, and symlinks pointing outside root.
    """
    root = Path(os.path.realpath(str(project_root)))
    candidate = Path(target_path)
    if candidate.is_absolute():
        resolved = Path(os.path.realpath(str(candidate)))
    else:
        resolved = Path(os.path.realpath(str(root / candidate)))

    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PermissionError(
            f"Access denied: path '{target_path}' escapes project root."
        ) from exc

    return resolved
