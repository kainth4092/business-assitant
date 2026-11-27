"""
Thread-safe Daily AI Request & Token Budget Guard for Fixdesk.
Tracks daily Vertex AI / Gemini calls locally in `data/.budget_state.json`
to prevent accidental quota/billing spikes during laptop development.
"""

import json
import os
import threading
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional


class BudgetExceededError(RuntimeError):
    """Raised when daily AI request or token safety limits are reached."""


_LOCK = threading.Lock()


def _get_budget_file_path() -> Path:
    custom = os.environ.get("AI_BUDGET_STATE_PATH", "").strip()
    if custom:
        return Path(custom).expanduser()
    data_dir = os.environ.get("DATA_DIR", "").strip()
    if data_dir:
        return Path(data_dir).expanduser() / ".budget_state.json"
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "data" / ".budget_state.json"


def _int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(name, str(default)).strip()))
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    try:
        val = float(os.environ.get(name, str(default)).strip())
        return min(1.0, max(0.05, val))
    except ValueError:
        return default


def _load_state_unlocked(path: Path) -> Dict[str, Any]:
    today = date.today().isoformat()
    default_state = {"date": today, "requests_used": 0, "tokens_used": 0}
    if not path.exists():
        return default_state
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("date") != today:
            return default_state
        return {
            "date": today,
            "requests_used": int(data.get("requests_used", 0)),
            "tokens_used": int(data.get("tokens_used", 0)),
        }
    except Exception:
        return default_state


def _save_state_unlocked(path: Path, state: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError:
        # Never crash core flows if state file is read-only
        pass


def estimate_tokens(text_or_chars: int | str) -> int:
    if isinstance(text_or_chars, str):
        chars = len(text_or_chars)
    else:
        chars = max(0, int(text_or_chars))
    return max(1, (chars + 3) // 4) if chars > 0 else 0


def get_budget_status() -> Dict[str, Any]:
    """Return current daily AI usage, configured caps, and warning state."""
    req_limit = _int_env("AI_DAILY_REQUEST_LIMIT", 500)
    tok_limit = _int_env("AI_DAILY_TOKEN_LIMIT", 500000)
    warn_ratio = _float_env("AI_BUDGET_WARN_RATIO", 0.8)

    path = _get_budget_file_path()
    with _LOCK:
        state = _load_state_unlocked(path)

    req_used = state["requests_used"]
    tok_used = state["tokens_used"]
    req_ratio = req_used / req_limit
    tok_ratio = tok_used / tok_limit
    usage_ratio = round(max(req_ratio, tok_ratio), 4)

    limit_reached = req_used >= req_limit or tok_used >= tok_limit
    warning_active = usage_ratio >= warn_ratio

    message = None
    if limit_reached:
        message = (
            f"Daily AI safety budget reached ({req_used}/{req_limit} requests, "
            f"{tok_used:,}/{tok_limit:,} tokens). Live cloud calls are paused until tomorrow."
        )
    elif warning_active:
        pct = int(round(usage_ratio * 100))
        message = (
            f"Daily AI budget at {pct}% ({req_used}/{req_limit} requests, "
            f"{tok_used:,}/{tok_limit:,} tokens)."
        )

    return {
        "date": state["date"],
        "requests_used": req_used,
        "request_limit": req_limit,
        "tokens_used": tok_used,
        "token_limit": tok_limit,
        "warn_ratio": warn_ratio,
        "usage_ratio": usage_ratio,
        "warning_active": warning_active,
        "limit_reached": limit_reached,
        "message": message,
    }


def check_budget_available() -> Dict[str, Any]:
    """Raise BudgetExceededError if daily request or token limit has been reached."""
    status = get_budget_status()
    if status["limit_reached"]:
        raise BudgetExceededError(status["message"])
    return status


def record_ai_usage(
    requests: int = 1,
    input_chars: int = 0,
    output_chars: int = 0,
    tokens: Optional[int] = None,
) -> Dict[str, Any]:
    """Atomically increment daily request and estimated/reported token counters."""
    added_tokens = (
        max(0, int(tokens))
        if tokens is not None
        else estimate_tokens(input_chars + output_chars)
    )
    path = _get_budget_file_path()
    with _LOCK:
        state = _load_state_unlocked(path)
        state["requests_used"] += max(0, int(requests))
        state["tokens_used"] += added_tokens
        _save_state_unlocked(path, state)
    return get_budget_status()


def reset_budget_state() -> None:
    """Reset the local daily budget file (used in tests or operator reset)."""
    path = _get_budget_file_path()
    with _LOCK:
        if path.exists():
            path.unlink()
