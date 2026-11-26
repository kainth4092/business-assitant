"""
Cached One-Line Summary Generator for Code Chunks.
Uses `code_rag.summary_cache` (keyed by SHA-256 content_hash) so unchanged chunks
never burn extra LLM tokens. Supports optional Gemini LLM generation with a fast
deterministic fallback when offline or in automated tests.
"""

import os
import re
from typing import Callable, Dict, Optional

from backend.agent.nodes import is_valid_gemini_key, get_llm
from project_init.chunker import CodeChunk
from project_init.security import redact_secrets


def deterministic_summary(chunk: CodeChunk) -> str:
    """Produce a concise, secret-free single-line summary without network calls."""
    header = f"[{chunk.language}] {chunk.symbol_name} ({chunk.chunk_kind}) in {chunk.file_path}:{chunk.start_line}-{chunk.end_line}"
    # Try first docstring or meaningful comment line
    for raw in chunk.content.splitlines()[:12]:
        line = raw.strip()
        if not line:
            continue
        if line.startswith(('"""', "'''")):
            cleaned = line.strip('"\' ').strip()
            if cleaned:
                return redact_secrets(f"{header} — {cleaned[:140]}")
        if line.startswith(("#", "//", "--", "/*")):
            cleaned = re.sub(r"^(#|//|--|/\*+|\*+)\s*", "", line).rstrip("*/").strip()
            if cleaned and not cleaned.startswith("!"):
                return redact_secrets(f"{header} — {cleaned[:140]}")
    return redact_secrets(header)


def generate_chunk_summary(
    chunk: CodeChunk,
    cache: Optional[Dict[str, str]] = None,
    llm_summarizer: Optional[Callable[[CodeChunk], str]] = None,
    use_llm: Optional[bool] = None,
) -> str:
    """
    Generate or retrieve from cache a one-line summary for `chunk`.
    Lookup order:
      1. In-memory / DB cache dict keyed by `chunk.content_hash`
      2. Explicit `llm_summarizer(chunk)` callback (if provided)
      3. Gemini LLM (when GOOGLE_API_KEY is valid and CODE_RAG_LLM_SUMMARY=1)
      4. Deterministic AST summary fallback
    """
    if cache is not None and chunk.content_hash in cache:
        return cache[chunk.content_hash]

    summary: Optional[str] = None
    if llm_summarizer is not None:
        try:
            raw = llm_summarizer(chunk)
            summary = " ".join(str(raw).strip().splitlines())[:220]
        except Exception:
            summary = None
    else:
        should_call_llm = (
            use_llm
            if use_llm is not None
            else (os.environ.get("CODE_RAG_LLM_SUMMARY", "0") == "1" and is_valid_gemini_key())
        )
        if should_call_llm:
            try:
                llm = get_llm()
                if llm is not None:
                    safe_snippet = redact_secrets(chunk.content[:1500])
                    prompt = (
                        "Summarize what this code block does in ONE short sentence (max 20 words, plain text, no secrets):\n"
                        f"File: {chunk.file_path} ({chunk.language}, symbol: {chunk.symbol_name})\n"
                        f"```\n{safe_snippet}\n```"
                    )
                    resp = llm.invoke(prompt)
                    raw = getattr(resp, "content", resp)
                    summary = " ".join(str(raw).strip().splitlines())[:220]
            except Exception:
                summary = None

    if not summary:
        summary = deterministic_summary(chunk)

    summary = redact_secrets(summary)
    if cache is not None:
        cache[chunk.content_hash] = summary
    return summary
