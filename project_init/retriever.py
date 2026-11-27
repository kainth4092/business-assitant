"""
Hybrid Codebase Retrieval & Grounded Q&A (`ask_codebase`) for Project Init.
Combines vector similarity (pgvector HNSW), keyword/symbol/path scoring, reranking,
structural import lookups, strict `file:line` citations, and `[REDACTED]` output filtering.
"""

import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from backend.agent.nodes import get_llm, is_valid_gemini_key
from backend.rag.embeddings import get_text_embedding
from project_init.config import get_project_config, resolve_safe_path
from project_init.security import classify_file, load_gitignore_spec, redact_secrets
from project_init.store import PostgresCodeStore


def _rerank_chunks(query: str, candidates: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
    """Rerank hybrid search candidates using exact symbol/path/keyword alignment."""
    tokens = [t.lower() for t in re.findall(r"[A-Za-z0-9_]{2,}", query)]
    q_lower = query.lower().strip()
    seen_keys = set()
    scored: List[Dict[str, Any]] = []

    for row in candidates:
        key = (row["file_path"], int(row["start_line"]), int(row["end_line"]))
        if key in seen_keys:
            continue
        seen_keys.add(key)

        sym_lower = str(row.get("symbol_name", "")).lower()
        path_lower = str(row.get("file_path", "")).lower()
        content_lower = str(row.get("content", "")).lower()
        summary_lower = str(row.get("summary", "")).lower()

        vec_score = float(row.get("vec_score") or 0.0)
        kw_score = min(1.0, float(row.get("kw_score") or 0.0))

        symbol_bonus = 0.0
        path_bonus = 0.0
        term_hits = 0
        for tok in tokens:
            if tok == sym_lower or sym_lower.endswith(f".{tok}"):
                symbol_bonus += 0.45
            elif tok in sym_lower:
                symbol_bonus += 0.25
            if tok in path_lower:
                path_bonus += 0.20
            if tok in content_lower or tok in summary_lower:
                term_hits += 1

        term_ratio = (term_hits / len(tokens)) if tokens else 0.0
        if q_lower and q_lower in sym_lower:
            symbol_bonus += 0.50

        final_score = round(0.45 * vec_score + 0.20 * kw_score + 0.20 * term_ratio + symbol_bonus + path_bonus, 4)

        item = dict(row)
        item["score"] = final_score
        item["summary"] = redact_secrets(str(item.get("summary", "")))
        item["content"] = redact_secrets(str(item.get("content", "")))
        item["citation"] = f"{item['file_path']}:{item['start_line']}-{item['end_line']}"
        scored.append(item)

    scored.sort(key=lambda r: r["score"], reverse=True)
    return scored[:top_k]


def _extract_import_target(question: str) -> Optional[str]:
    """Detect structure questions like 'which files import X'."""
    m = re.search(
        r"(?i)(?:which|what|find)\s+files?\s+(?:import|require|use|depend\s+on)\s+[`'\"]?([A-Za-z0-9_.\-/]+)[`'\"]?",
        question,
    )
    if m:
        return m.group(1).strip()
    return None


def search_codebase(
    project: str,
    query: str,
    top_k: int = 6,
    config_path: Optional[str] = None,
    store: Optional[Any] = None,
    embedder: Optional[Callable[[str], List[float]]] = None,
) -> List[Dict[str, Any]]:
    """
    Hybrid search returning ranked snippets bounded strictly inside the project root
    and excluding any file matching the sensitive-file skip policy.
    """
    from backend.cloud.config import cloud_allowed_scope
    from backend.cloud.factories import get_code_store

    cfg = get_project_config(project, config_path=config_path)
    project_root = cfg.root_path
    gitignore_spec = load_gitignore_spec(project_root)

    active_store = store or get_code_store(project_name=cfg.name, config_path=config_path)
    embed_fn = embedder or get_text_embedding
    with cloud_allowed_scope(cfg.cloud_index_allowed):
        q_vec = embed_fn(query)

    raw_candidates = active_store.search_hybrid(project, query, q_vec, limit=max(top_k * 2, 12))
    reranked = _rerank_chunks(query, raw_candidates, top_k=top_k * 2)

    safe_results: List[Dict[str, Any]] = []
    for item in reranked:
        rel_path = str(item.get("file_path", ""))
        try:
            full = resolve_safe_path(project_root, rel_path)
        except PermissionError:
            continue
        if full.exists():
            decision = classify_file(
                project_root=project_root,
                file_path=full,
                gitignore_spec=gitignore_spec,
                include_globs=cfg.include,
                exclude_globs=cfg.exclude,
            )
            if decision.action == "skip":
                continue

        lines = str(item.get("content", "")).splitlines()
        snippet = redact_secrets("\n".join(lines[:24]))
        safe_results.append(
            {
                "file_path": rel_path,
                "start_line": int(item["start_line"]),
                "end_line": int(item["end_line"]),
                "symbol_name": str(item.get("symbol_name", "")),
                "chunk_kind": str(item.get("chunk_kind", "")),
                "language": str(item.get("language", "")),
                "commit_hash": str(item.get("commit_hash", "")),
                "summary": redact_secrets(str(item.get("summary", ""))),
                "snippet": snippet,
                "citation": f"{rel_path}:{item['start_line']}-{item['end_line']}",
                "score": float(item.get("score", 0.0)),
            }
        )
        if len(safe_results) >= top_k:
            break

    return safe_results


def ask_codebase(
    project: str,
    question: str,
    top_k: int = 6,
    config_path: Optional[str] = None,
    store: Optional[Any] = None,
    embedder: Optional[Callable[[str], List[float]]] = None,
    llm_answerer: Optional[Callable[[str, List[Dict[str, Any]]], str]] = None,
) -> Dict[str, Any]:
    """
    Answer a plain-English question strictly using indexed chunks with `file:line` citations.
    Returns `"not found in the indexed code"` when evidence is absent or irrelevant.
    Applies `[REDACTED]` output scrubbing before returning.
    """
    from backend.cloud.factories import get_code_store

    cfg = get_project_config(project, config_path=config_path)
    active_store = store or get_code_store(project_name=cfg.name, config_path=config_path)
    clean_question = (question or "").strip()
    if not clean_question:
        return {
            "project": project,
            "question": question,
            "answer": "not found in the indexed code",
            "found": False,
            "citations": [],
            "chunks": [],
            "import_matches": [],
        }

    # Check structural import queries ("which files import X")
    import_target = _extract_import_target(clean_question)
    import_matches: List[Dict[str, Any]] = []
    if import_target:
        import_matches = active_store.find_files_importing(project, import_target)

    chunks = search_codebase(
        project=project,
        query=clean_question,
        top_k=top_k,
        config_path=config_path,
        store=active_store,
        embedder=embedder,
    )

    # Check lexical/semantic relevance so unrelated questions yield explicit "not found"
    q_tokens = {
        t.lower()
        for t in re.findall(r"[A-Za-z0-9_]{3,}", clean_question)
        if t.lower() not in {"where", "what", "which", "does", "implemented", "about", "there", "this", "that", "from", "with", "into", "have", "files"}
    }
    relevant_chunks: List[Dict[str, Any]] = []
    for ch in chunks:
        haystack = f"{ch['file_path']} {ch['symbol_name']} {ch['summary']} {ch['snippet']}".lower()
        overlap = sum(1 for t in q_tokens if t in haystack)
        if overlap > 0 or ch["score"] >= 0.42:
            relevant_chunks.append(ch)

    if not relevant_chunks and not import_matches:
        return {
            "project": project,
            "question": clean_question,
            "answer": "not found in the indexed code",
            "found": False,
            "citations": [],
            "chunks": [],
            "import_matches": [],
        }

    citations = [
        {
            "file_path": ch["file_path"],
            "start_line": ch["start_line"],
            "end_line": ch["end_line"],
            "symbol_name": ch["symbol_name"],
            "commit_hash": ch["commit_hash"],
            "ref": ch["citation"],
        }
        for ch in (relevant_chunks or chunks)
    ]

    answer_text: Optional[str] = None
    evidence_list = relevant_chunks or chunks

    if llm_answerer is not None:
        answer_text = llm_answerer(clean_question, evidence_list)
    elif cfg.cloud_index_allowed:
        try:
            llm = get_llm(cloud_allowed=cfg.cloud_index_allowed)
            if llm is not None:
                context_blocks = []
                for idx, ch in enumerate(evidence_list, 1):
                    context_blocks.append(
                        f"[{idx}] {ch['file_path']}:{ch['start_line']}-{ch['end_line']} "
                        f"(symbol: {ch['symbol_name']}, commit: {ch['commit_hash']})\n"
                        f"Summary: {ch['summary']}\n"
                        f"```{ch['language']}\n{ch['snippet']}\n```"
                    )
                imports_note = ""
                if import_matches:
                    imports_note = "\nMatching import graph entries:\n" + "\n".join(
                        f"- {m['file_path']} imports {m['imports']}" for m in import_matches
                    )
                prompt = (
                    "You are answering questions strictly about an indexed codebase.\n"
                    "RULES:\n"
                    "1. Answer ONLY using facts explicitly visible in the retrieved code chunks below.\n"
                    "2. Include exact `file_path:start_line-end_line` citations inline.\n"
                    "3. NEVER invent file paths, symbols, or behavior not shown.\n"
                    "4. If the retrieved chunks do not answer the question, reply with: not found in the indexed code\n\n"
                    f"Question: {clean_question}\n\n"
                    f"Retrieved Code Chunks:\n" + "\n\n".join(context_blocks) + imports_note
                )
                resp = llm.invoke(prompt)
                answer_text = str(getattr(resp, "content", resp)).strip()
        except Exception:
            answer_text = None

    if not answer_text:
        lines: List[str] = []
        if import_matches:
            files_list = ", ".join(f"`{m['file_path']}`" for m in import_matches[:10])
            lines.append(f"Files importing `{import_target}`: {files_list}.")
        for ch in evidence_list[:4]:
            lines.append(
                f"- **{ch['symbol_name']}** (`{ch['file_path']}:{ch['start_line']}-{ch['end_line']}`): {ch['summary']}"
            )
        answer_text = "\n".join(lines) if lines else "not found in the indexed code"

    # Enforce output secret redaction filter across answer and returned chunks
    safe_answer = redact_secrets(answer_text)
    if "not found in the indexed code" in safe_answer.lower() and not import_matches:
        return {
            "project": project,
            "question": clean_question,
            "answer": "not found in the indexed code",
            "found": False,
            "citations": citations,
            "chunks": evidence_list,
            "import_matches": import_matches,
        }

    return {
        "project": project,
        "question": clean_question,
        "answer": safe_answer,
        "found": True,
        "citations": citations,
        "chunks": evidence_list,
        "import_matches": import_matches,
    }
