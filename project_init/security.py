"""
Multi-layer Security & Sensitive-File Filter for Project Init:
1. Path & .gitignore skip rules (env files, keys, credentials, dumps, binaries, .git, lockfile mode).
2. Pre-index secret scanner (optional gitleaks CLI + built-in regex & Shannon entropy).
3. Chunk-level second line of defense before storage.
4. Output redaction filter replacing secret-looking strings with [REDACTED].
"""

import fnmatch
import json
import math
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pathspec

MAX_INDEX_FILE_BYTES = int(os.environ.get("CODE_RAG_MAX_FILE_BYTES", str(512 * 1024)))
ENTROPY_THRESHOLD = float(os.environ.get("CODE_RAG_ENTROPY_THRESHOLD", "3.6"))

SKIP_DIR_NAMES = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "env",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "__pycache__",
    ".next",
    "dist",
    "build",
    "out",
    "target",
    "coverage",
    ".terraform",
    "playwright-report",
    "test-results",
    "screenshots",
}

LOCKFILE_NAMES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "pipfile.lock",
    "uv.lock",
    "cargo.lock",
    "gemfile.lock",
    "composer.lock",
}

ALWAYS_SKIP_NAME_GLOBS = [
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "id_rsa*",
    "id_ed25519*",
    "*.kdbx",
    "credentials*",
    "*credentials*.json",
    "secrets*",
    "*secrets*.yaml",
    "*secrets*.yml",
    "*secrets*.json",
    "service-account*.json",
    "*service_account*.json",
    "*.tfstate",
    "*.tfstate.*",
    "*.dump",
    "*.pgdump",
    "*.bak",
    "*.sqlite",
    "*.sqlite3",
    "*.db",
    "*.sql.gz",
    "*.tar",
    "*.tar.gz",
    "*.tgz",
    "*.zip",
    "*.jar",
    "*.parquet",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.webp",
    "*.ico",
    "*.pdf",
    "*.woff",
    "*.woff2",
    "*.ttf",
    "*.eot",
    "*.so",
    "*.dll",
    "*.exe",
    "*.bin",
    "*.pyc",
    "*.pyo",
    "*.class",
]

AUTH_CONFIG_FILENAMES = {".npmrc", ".pypirc", ".netrc", ".dockercfg"}

# High-precision secret patterns: (rule_name, compiled_regex)
SECRET_PATTERNS: List[Tuple[str, re.Pattern]] = [
    (
        "private_key_block",
        re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z0-9 ]*PRIVATE KEY-----|$)"),
    ),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA|AROA|AIDA)[0-9A-Z]{16}\b")),
    (
        "aws_secret_assignment",
        re.compile(r"(?i)(?:aws_secret_access_key|aws_secret_key)\s*[:=]\s*['\"]?[A-Za-z0-9/+=]{24,}['\"]?"),
    ),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b")),
    ("github_token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[0-9A-Za-z\-]{10,}\b|\bxapp-[0-9A-Za-z\-]{10,}\b")),
    ("stripe_key", re.compile(r"\b(?:sk|rk)_(?:live|test)_[0-9A-Za-z]{16,}\b")),
    ("openai_or_prefixed_key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9\-_]{24,}\b")),
    ("jwt_token", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b")),
    ("bearer_token", re.compile(r"(?i)bearer\s+[A-Za-z0-9\-_\.]{20,}")),
    (
        "connection_string_creds",
        re.compile(r"\b(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|redis|amqp)://[^:\s/]+:[^@\s]{3,}@[^\s'\"]+"),
    ),
    (
        "generic_secret_assignment",
        re.compile(
            r"(?i)\b(?:api_key|apikey|secret_key|client_secret|access_token|auth_token|private_key|db_password|password)\b\s*[:=]\s*['\"]([^'\"]{8,})['\"]"
        ),
    ),
]

PLACEHOLDER_VALUES = {
    "your_gemini_api_key_here",
    "your_api_key_here",
    "changeme",
    "change_me",
    "placeholder",
    "redacted",
    "[redacted]",
    "example",
}


@dataclass
class FileDecision:
    """Result of classifying whether a repo file should be skipped, summarized, or indexed."""

    action: str  # "index" | "lockfile_summary" | "skip"
    reason: str = ""
    rule: str = ""


def shannon_entropy(text: str) -> float:
    """Compute Shannon entropy (bits/char) to spot random-looking tokens and keys."""
    if not text:
        return 0.0
    freq: Dict[str, int] = {}
    for ch in text:
        freq[ch] = freq.get(ch, 0) + 1
    length = len(text)
    return -sum((count / length) * math.log2(count / length) for count in freq.values())


def load_gitignore_spec(project_root: Path) -> Optional[pathspec.PathSpec]:
    """Compile root .gitignore rules using pathspec (gitignore syntax)."""
    gi_path = project_root / ".gitignore"
    if not gi_path.exists():
        return None
    try:
        lines = gi_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        return pathspec.PathSpec.from_lines("gitignore", lines)
    except Exception:
        return None


def is_binary_file(file_path: Path) -> bool:
    """Heuristic binary detector checking for NUL bytes and non-UTF8 content in header."""
    try:
        with open(file_path, "rb") as fh:
            sample = fh.read(8192)
    except OSError:
        return True
    if not sample:
        return False
    if b"\x00" in sample:
        return True
    try:
        sample.decode("utf-8")
        return False
    except UnicodeDecodeError:
        # Count high control bytes
        non_text = sum(1 for b in sample if b < 9 or (13 < b < 32))
        return (non_text / len(sample)) > 0.1


def is_database_dump_content(rel_path: str, sample_text: str) -> bool:
    """Detect raw database dump exports even when named *.sql."""
    lower = rel_path.lower()
    if any(tok in lower for tok in ("dump", "backup", "pg_dump", "mysqldump")):
        return True
    if "PostgreSQL database dump" in sample_text or "MySQL dump" in sample_text:
        return True
    if re.search(r"(?m)^COPY\s+\S+\s*\([^)]+\)\s+FROM\s+stdin;", sample_text):
        return True
    return False


def classify_file(
    project_root: Path,
    file_path: Path,
    gitignore_spec: Optional[pathspec.PathSpec] = None,
    include_globs: Optional[List[str]] = None,
    exclude_globs: Optional[List[str]] = None,
) -> FileDecision:
    """Decide whether a file is excluded by policy, indexed as lockfile summary, or full-indexed."""
    rel = file_path.relative_to(project_root).as_posix()
    name = file_path.name
    lower_name = name.lower()
    parts = set(file_path.relative_to(project_root).parts[:-1])

    # 1. Hard directory blocks (.git, node_modules, venv, build artifacts)
    blocked_dirs = parts & SKIP_DIR_NAMES
    if blocked_dirs:
        return FileDecision("skip", f"Sensitive/excluded directory ({sorted(blocked_dirs)[0]})", "skip_dir")

    # 2. Mandatory filename & extension skip globs (.env*, keys, certs, dumps, binaries)
    for pat in ALWAYS_SKIP_NAME_GLOBS:
        if fnmatch.fnmatch(lower_name, pat) or fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(rel.lower(), pat):
            return FileDecision("skip", f"Sensitive or non-code file pattern ({pat})", "mandatory_skip_glob")

    # 3. Auth config files (.npmrc, .pypirc, .netrc)
    if lower_name in AUTH_CONFIG_FILENAMES:
        try:
            txt = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            txt = ""
        if re.search(r"(?i)(_authToken|password|api[-_]?key|token\s*=|://[^/\s]+:)", txt):
            return FileDecision("skip", f"Auth configuration file with credentials ({name})", "auth_config_token")
        # Even without explicit tokens, .netrc/.pypirc/.npmrc are risky auth files
        if lower_name in {".pypirc", ".netrc"}:
            return FileDecision("skip", f"Sensitive auth file ({name})", "auth_config_file")

    # 4. Explicit exclude globs from projects.yaml
    if exclude_globs:
        excl_spec = pathspec.PathSpec.from_lines("gitignore", exclude_globs)
        if excl_spec.match_file(rel):
            return FileDecision("skip", "Excluded by projects.yaml exclude glob", "config_exclude")

    # 5. .gitignore enforcement
    if gitignore_spec is not None and gitignore_spec.match_file(rel):
        return FileDecision("skip", "Ignored by repository .gitignore", "gitignore")

    # 6. Include filter from projects.yaml (keep lockfiles handled below if included or root lockfile)
    if lower_name in LOCKFILE_NAMES:
        return FileDecision("lockfile_summary", "Lockfile summarized only", "lockfile_summary")

    if include_globs:
        incl_spec = pathspec.PathSpec.from_lines("gitignore", include_globs)
        if not incl_spec.match_file(rel):
            return FileDecision("skip", "Does not match projects.yaml include globs", "config_include")

    # 7. Size and binary checks
    try:
        size = file_path.stat().st_size
    except OSError:
        return FileDecision("skip", "Unreadable file", "os_error")

    if size == 0:
        return FileDecision("skip", "Empty file", "empty_file")
    if size > MAX_INDEX_FILE_BYTES:
        return FileDecision("skip", f"File exceeds max size limit ({size} bytes)", "large_file")
    if is_binary_file(file_path):
        return FileDecision("skip", "Binary file excluded", "binary_file")

    # 8. Database dump check inside .sql files
    if lower_name.endswith(".sql"):
        try:
            head_txt = file_path.read_text(encoding="utf-8", errors="ignore")[:8192]
            if is_database_dump_content(rel, head_txt):
                return FileDecision("skip", "Database dump file excluded", "db_dump")
        except OSError:
            return FileDecision("skip", "Unreadable SQL file", "os_error")

    return FileDecision("index")


def _extract_high_entropy_assignments(text: str) -> List[str]:
    """Find suspicious variable/config assignments containing high-entropy token strings."""
    findings: List[str] = []
    assign_re = re.compile(
        r"(?i)\b([A-Za-z0-9_]*(?:key|secret|token|pass|pwd|auth|cred)[A-Za-z0-9_]*)\b\s*[:=]\s*['\"]([A-Za-z0-9+/=_\-!@#$%^&*]{16,})['\"]"
    )
    for m in assign_re.finditer(text):
        var_name, val = m.group(1), m.group(2)
        if val.lower() in PLACEHOLDER_VALUES or val.startswith("your_"):
            continue
        # Skip obvious prose messages with spaces (regex already excludes spaces) or repeated characters
        if shannon_entropy(val) >= ENTROPY_THRESHOLD:
            findings.append(f"high_entropy_assignment:{var_name}")
    return findings


def _run_gitleaks_file_scan(file_path: Path) -> List[str]:
    """Run gitleaks CLI in no-git mode if installed; return rule names (never secret values)."""
    gitleaks_bin = shutil.which("gitleaks")
    if not gitleaks_bin:
        return []
    try:
        proc = subprocess.run(
            [
                gitleaks_bin,
                "detect",
                "--no-git",
                "--source",
                str(file_path),
                "--report-format",
                "json",
                "--report-path",
                "-",
                "--exit-code",
                "1",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode == 0:
            return []
        try:
            items = json.loads(proc.stdout or "[]")
            if isinstance(items, list) and items:
                return [f"gitleaks:{item.get('RuleID', 'secret')}" for item in items]
        except json.JSONDecodeError:
            pass
        return ["gitleaks:finding"]
    except Exception:
        return []


def scan_file_for_secrets(file_path: Path, content: Optional[str] = None) -> List[str]:
    """
    Pre-index secret scanner returning rule names ONLY (never secret values).
    Combines gitleaks (if installed) with built-in regex and Shannon entropy checks.
    """
    findings: List[str] = []
    if content is None:
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return ["unreadable_file"]

    findings.extend(_run_gitleaks_file_scan(file_path))

    for rule_name, pattern in SECRET_PATTERNS:
        # Let connection_string_creds pass only if it's clearly a synthetic/regex definition? No, scan code strictly
        # Wait: guard against security.py itself regex literals by avoiding raw prefixes? Regex patterns contain `\b...` so won't match.
        for match in pattern.finditer(content):
            snippet = match.group(0)
            if rule_name == "generic_secret_assignment":
                val = match.group(1).strip()
                if val.lower() in PLACEHOLDER_VALUES or val.startswith(("your_", "<", "${", "os.environ")):
                    continue
                if " " in val and len(val) < 32 and shannon_entropy(val) < 3.4:
                    continue
            if rule_name == "connection_string_creds":
                if "<" in snippet or "${" in snippet or "user:pass" in snippet.lower():
                    continue
                if "@localhost" in snippet or "@127.0.0.1" in snippet or "@postgres:" in snippet:
                    # Dev container localhost defaults are handled at chunk level instead of skipping entire modules
                    continue
            findings.append(rule_name)
            break

    findings.extend(_extract_high_entropy_assignments(content))
    # Deduplicate preserving order
    return list(dict.fromkeys(findings))


def check_chunk_security(chunk_text: str) -> Optional[str]:
    """
    Second line of defense on each chunk prior to storage/embedding.
    Returns triggered rule name if suspicious, or None when safe.
    """
    for rule_name, pattern in SECRET_PATTERNS:
        for match in pattern.finditer(chunk_text):
            snippet = match.group(0)
            if rule_name == "generic_secret_assignment":
                val = match.group(1).strip()
                if val.lower() in PLACEHOLDER_VALUES or val.startswith(("your_", "<", "${")):
                    continue
                if " " in val and len(val) < 32 and shannon_entropy(val) < 3.4:
                    continue
            if rule_name == "connection_string_creds":
                if "<" in snippet or "${" in snippet or "user:pass" in snippet.lower():
                    continue
            return f"chunk_filter:{rule_name}"

    entropy_hits = _extract_high_entropy_assignments(chunk_text)
    if entropy_hits:
        return f"chunk_filter:{entropy_hits[0]}"
    return None


def redact_secrets(text: str) -> str:
    """Output filter: scrub any secret-looking string and replace with [REDACTED]."""
    if not text:
        return text
    cleaned = text
    for rule_name, pattern in SECRET_PATTERNS:
        if rule_name == "generic_secret_assignment":
            def _repl_assign(m: re.Match) -> str:
                val = m.group(1)
                if val.lower() in PLACEHOLDER_VALUES or val.startswith(("your_", "<", "${")):
                    return m.group(0)
                return m.group(0).replace(val, "[REDACTED]")
            cleaned = pattern.sub(_repl_assign, cleaned)
        elif rule_name == "connection_string_creds":
            def _repl_dsn(m: re.Match) -> str:
                s = m.group(0)
                if "<" in s or "${" in s:
                    return s
                return re.sub(r"://([^:\s/]+):([^@\s]+)@", r"://\1:[REDACTED]@", s)
            cleaned = pattern.sub(_repl_dsn, cleaned)
        else:
            cleaned = pattern.sub("[REDACTED]", cleaned)
    return cleaned


def extract_lockfile_summary(file_path: Path, rel_path: str) -> str:
    """Create a short non-secret summary for dependency lockfiles without indexing raw hashes/tarballs."""
    name = file_path.name.lower()
    try:
        raw = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return f"Lockfile {rel_path} (unreadable)."

    line_count = len(raw.splitlines())
    if name == "package-lock.json":
        try:
            data = json.loads(raw)
            pkg_name = data.get("name", "unknown")
            lock_ver = data.get("lockfileVersion", "unknown")
            pkgs = data.get("packages") or data.get("dependencies") or {}
            sample_names = [k.replace("node_modules/", "") for k in list(pkgs.keys()) if k][:12]
            return (
                f"Lockfile summary for {rel_path}: project={pkg_name}, "
                f"lockfileVersion={lock_ver}, tracked_packages={len(pkgs)}, "
                f"sample_dependencies={', '.join(sample_names)}"
            )
        except Exception:
            pass
    return f"Lockfile summary for {rel_path}: format={file_path.name}, total_lines={line_count}."
