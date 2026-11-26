"""
Part 4 Rename Guardrail Test
Scans the repository source (excluding .git, node_modules, .next, .venv, caches,
RENAME_AUDIT.md, MIGRATION.md, RENAME_REPORT.md, and gitignored local .env) and
fails immediately if any old project name variant remains anywhere.
"""

import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

EXCLUDED_DIRS = {
    ".git",
    "node_modules",
    ".next",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "playwright-report",
    "test-results",
    "screenshots",
}

EXCLUDED_FILES = {
    "RENAME_AUDIT.md",
    "MIGRATION.md",
    "RENAME_REPORT.md",
    ".env",  # Local user env may intentionally retain legacy DB name per MIGRATION.md
}

# Construct patterns dynamically so this guardrail file itself remains clean
_OLD_BASE = "busi" + "ness"
_ASST = "assis" + "tant"
LEGACY_NAME_PATTERN = re.compile(
    rf"{_OLD_BASE}[\s_-]?{_ASST}|biz{_ASST}|{_OLD_BASE}_network|{_OLD_BASE}_admin",
    re.IGNORECASE,
)


def test_no_legacy_project_name_variants_remain():
    """Fails if any legacy name variant exists in tracked code, configs, tests, or docs."""
    findings = []

    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        dirnames[:] = sorted([d for d in dirnames if d not in EXCLUDED_DIRS])
        for fname in sorted(filenames):
            if fname in EXCLUDED_FILES:
                continue
            fpath = Path(dirpath) / fname
            rel = fpath.relative_to(REPO_ROOT).as_posix()

            if fname.endswith((".png", ".jpg", ".jpeg", ".jar", ".parquet", ".pyc", ".ico")):
                if LEGACY_NAME_PATTERN.search(rel):
                    findings.append(f"{rel}:0: [filename match]")
                continue

            try:
                content = fpath.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            for lineno, line in enumerate(content.splitlines(), 1):
                if LEGACY_NAME_PATTERN.search(line):
                    findings.append(f"{rel}:{lineno}: {line.strip()[:120]}")

    assert not findings, "Legacy project name occurrences found:\n" + "\n".join(findings[:30])
