"""
AST-aware Code Chunking & Dependency/Import Extraction for Project Init:
- Python & JavaScript/JSX via tree-sitter
- SQL via sqlparse
- Markdown by headings
- Other text files via line-based sliding window
"""

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import sqlparse
import tree_sitter
import tree_sitter_javascript
import tree_sitter_python

PY_LANGUAGE = tree_sitter.Language(tree_sitter_python.language())
JS_LANGUAGE = tree_sitter.Language(tree_sitter_javascript.language())

EXT_LANGUAGE_MAP: Dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "jsx",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".sql": "sql",
    ".md": "markdown",
    ".mdx": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".css": "css",
    ".sh": "shell",
    ".txt": "text",
}


@dataclass
class CodeChunk:
    """Single structural or windowed chunk extracted from a repository file."""

    project: str
    file_path: str
    language: str
    symbol_name: str
    chunk_kind: str
    start_line: int
    end_line: int
    commit_hash: str
    content: str
    content_hash: str = ""
    summary: str = ""
    chunk_uid: str = ""

    def __post_init__(self):
        if not self.content_hash:
            self.content_hash = hashlib.sha256(self.content.encode("utf-8", errors="ignore")).hexdigest()
        if not self.chunk_uid:
            uid_seed = f"{self.project}:{self.file_path}:{self.start_line}:{self.end_line}:{self.symbol_name}"
            self.chunk_uid = hashlib.sha256(uid_seed.encode("utf-8")).hexdigest()[:40]


@dataclass
class ParsedFileResult:
    """Chunks plus file-level structural metadata (imports & symbols)."""

    file_path: str
    language: str
    line_count: int
    content_hash: str
    imports: List[str] = field(default_factory=list)
    symbols: List[Dict[str, object]] = field(default_factory=list)
    chunks: List[CodeChunk] = field(default_factory=list)


def detect_language(file_path: str) -> str:
    """Infer programming/markup language from file extension or special filename."""
    p = Path(file_path)
    lower = p.name.lower()
    if lower == "makefile":
        return "makefile"
    if lower.startswith("dockerfile"):
        return "dockerfile"
    return EXT_LANGUAGE_MAP.get(p.suffix.lower(), "text")


def _node_text(source_bytes: bytes, node: tree_sitter.Node) -> str:
    return source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _extract_python_ast(
    project: str,
    rel_path: str,
    text: str,
    commit_hash: str,
) -> Tuple[List[CodeChunk], List[str], List[Dict[str, object]]]:
    """Parse Python with tree-sitter into function, method, class, and module chunks."""
    parser = tree_sitter.Parser(PY_LANGUAGE)
    src = text.encode("utf-8", errors="replace")
    tree = parser.parse(src)
    lines = text.splitlines()

    imports: List[str] = []
    symbols: List[Dict[str, object]] = []
    chunks: List[CodeChunk] = []
    covered_ranges: List[Tuple[int, int]] = []

    def _collect_imports(node: tree_sitter.Node):
        if node.type == "import_statement":
            for child in node.children:
                if child.type in ("dotted_name", "aliased_import"):
                    mod = _node_text(src, child).split(" as ")[0].strip()
                    if mod:
                        imports.append(mod)
        elif node.type == "import_from_statement":
            mod_node = node.child_by_field_name("module_name")
            if mod_node:
                imports.append(_node_text(src, mod_node).strip())
            else:
                txt = _node_text(src, node)
                m = re.match(r"from\s+([\.\w]+)\s+import", txt)
                if m:
                    imports.append(m.group(1))
        for child in node.children:
            _collect_imports(child)

    _collect_imports(tree.root_node)

    def _emit(symbol_name: str, kind: str, start_line: int, end_line: int):
        snippet = "\n".join(lines[start_line - 1 : end_line])
        if not snippet.strip():
            return
        symbols.append(
            {"name": symbol_name, "kind": kind, "start_line": start_line, "end_line": end_line}
        )
        chunks.append(
            CodeChunk(
                project=project,
                file_path=rel_path,
                language="python",
                symbol_name=symbol_name,
                chunk_kind=kind,
                start_line=start_line,
                end_line=end_line,
                commit_hash=commit_hash,
                content=snippet,
            )
        )
        covered_ranges.append((start_line, end_line))

    for child in tree.root_node.children:
        target = child
        if child.type == "decorated_definition":
            def_node = child.child_by_field_name("definition")
            if def_node is not None:
                target = def_node
        s_line = child.start_point[0] + 1
        e_line = child.end_point[0] + 1

        if target.type == "function_definition":
            name_node = target.child_by_field_name("name")
            fn_name = _node_text(src, name_node) if name_node else "function"
            _emit(fn_name, "function", s_line, e_line)
        elif target.type == "class_definition":
            name_node = target.child_by_field_name("name")
            cls_name = _node_text(src, name_node) if name_node else "Class"
            body = target.child_by_field_name("body")
            methods: List[tree_sitter.Node] = []
            if body is not None:
                for member in body.children:
                    m_target = member
                    if member.type == "decorated_definition":
                        inner = member.child_by_field_name("definition")
                        if inner is not None:
                            m_target = inner
                    if m_target.type == "function_definition":
                        methods.append(member)

            if not methods:
                _emit(cls_name, "class", s_line, e_line)
            else:
                # Emit class header up to first method, then each method individually
                first_m_line = methods[0].start_point[0] + 1
                if first_m_line > s_line:
                    _emit(cls_name, "class", s_line, first_m_line - 1)
                else:
                    symbols.append(
                        {"name": cls_name, "kind": "class", "start_line": s_line, "end_line": e_line}
                    )
                for m_node in methods:
                    m_inner = m_node.child_by_field_name("definition") if m_node.type == "decorated_definition" else m_node
                    m_name_node = m_inner.child_by_field_name("name") if m_inner else None
                    m_name = _node_text(src, m_name_node) if m_name_node else "method"
                    _emit(f"{cls_name}.{m_name}", "method", m_node.start_point[0] + 1, m_node.end_point[0] + 1)

    # Collect uncovered top-level module blocks (e.g. FastAPI route bindings, module constants) if substantial
    uncovered_lines: List[int] = []
    for idx in range(1, len(lines) + 1):
        if not any(lo <= idx <= hi for lo, hi in covered_ranges) and lines[idx - 1].strip():
            uncovered_lines.append(idx)
    if uncovered_lines:
        # Group contiguous uncovered line spans
        spans: List[Tuple[int, int]] = []
        span_start = uncovered_lines[0]
        prev = uncovered_lines[0]
        for ln in uncovered_lines[1:]:
            if ln <= prev + 3:
                prev = ln
            else:
                spans.append((span_start, prev))
                span_start = prev = ln
        spans.append((span_start, prev))
        for lo, hi in spans:
            block = "\n".join(lines[lo - 1 : hi])
            if len(block.strip()) >= 40:
                chunks.append(
                    CodeChunk(
                        project=project,
                        file_path=rel_path,
                        language="python",
                        symbol_name="<module>",
                        chunk_kind="module",
                        start_line=lo,
                        end_line=hi,
                        commit_hash=commit_hash,
                        content=block,
                    )
                )

    if not chunks and text.strip():
        chunks.extend(_sliding_window_chunks(project, rel_path, "python", text, commit_hash))

    return chunks, list(dict.fromkeys(imports)), symbols


def _extract_js_ast(
    project: str,
    rel_path: str,
    language: str,
    text: str,
    commit_hash: str,
) -> Tuple[List[CodeChunk], List[str], List[Dict[str, object]]]:
    """Parse JavaScript / JSX / JS modules with tree-sitter."""
    parser = tree_sitter.Parser(JS_LANGUAGE)
    src = text.encode("utf-8", errors="replace")
    tree = parser.parse(src)
    lines = text.splitlines()

    imports: List[str] = []
    symbols: List[Dict[str, object]] = []
    chunks: List[CodeChunk] = []

    def _collect_imports(node: tree_sitter.Node):
        if node.type == "import_statement":
            src_node = node.child_by_field_name("source")
            if src_node:
                imports.append(_node_text(src, src_node).strip("'\"` "))
        elif node.type == "call_expression":
            fn_node = node.child_by_field_name("function")
            if fn_node and _node_text(src, fn_node) == "require":
                args = node.child_by_field_name("arguments")
                if args and args.named_child_count > 0:
                    imports.append(_node_text(src, args.named_child(0)).strip("'\"` "))
        for child in node.children:
            _collect_imports(child)

    _collect_imports(tree.root_node)

    def _emit(symbol_name: str, kind: str, s_line: int, e_line: int):
        snippet = "\n".join(lines[s_line - 1 : e_line])
        if not snippet.strip():
            return
        symbols.append({"name": symbol_name, "kind": kind, "start_line": s_line, "end_line": e_line})
        chunks.append(
            CodeChunk(
                project=project,
                file_path=rel_path,
                language=language,
                symbol_name=symbol_name,
                chunk_kind=kind,
                start_line=s_line,
                end_line=e_line,
                commit_hash=commit_hash,
                content=snippet,
            )
        )

    for child in tree.root_node.children:
        target = child
        if child.type == "export_statement":
            decl = child.child_by_field_name("declaration")
            if decl is not None:
                target = decl
        s_line = child.start_point[0] + 1
        e_line = child.end_point[0] + 1

        if target.type == "function_declaration":
            name_node = target.child_by_field_name("name")
            fn_name = _node_text(src, name_node) if name_node else "function"
            _emit(fn_name, "function", s_line, e_line)
        elif target.type == "class_declaration":
            name_node = target.child_by_field_name("name")
            cls_name = _node_text(src, name_node) if name_node else "Class"
            body = target.child_by_field_name("body")
            methods = [m for m in (body.children if body else []) if m.type == "method_definition"]
            if not methods:
                _emit(cls_name, "class", s_line, e_line)
            else:
                first_m = methods[0].start_point[0] + 1
                if first_m > s_line:
                    _emit(cls_name, "class", s_line, first_m - 1)
                for m_node in methods:
                    m_name_node = m_node.child_by_field_name("name")
                    m_name = _node_text(src, m_name_node) if m_name_node else "method"
                    _emit(f"{cls_name}.{m_name}", "method", m_node.start_point[0] + 1, m_node.end_point[0] + 1)
        elif target.type in ("lexical_declaration", "variable_declaration"):
            # Catch const MyComponent = (...) => {...} or const fn = function() {...}
            for dec in target.named_children:
                if dec.type == "variable_declarator":
                    v_name = dec.child_by_field_name("name")
                    v_val = dec.child_by_field_name("value")
                    if v_val and v_val.type in ("arrow_function", "function_expression", "function"):
                        sym = _node_text(src, v_name) if v_name else "fn"
                        _emit(sym, "function", s_line, e_line)
                        break

    if not chunks and text.strip():
        chunks.extend(_sliding_window_chunks(project, rel_path, language, text, commit_hash))

    return chunks, list(dict.fromkeys(imports)), symbols


def _extract_sql_chunks(
    project: str,
    rel_path: str,
    text: str,
    commit_hash: str,
) -> Tuple[List[CodeChunk], List[str], List[Dict[str, object]]]:
    """Split SQL into statement/DDL/CTE chunks using sqlparse with exact line ranges."""
    chunks: List[CodeChunk] = []
    symbols: List[Dict[str, object]] = []
    refs: List[str] = []

    raw_statements = sqlparse.split(text)
    search_cursor = 0

    for idx, stmt in enumerate(raw_statements, start=1):
        stripped = stmt.strip()
        if not stripped:
            continue
        pos = text.find(stripped, search_cursor)
        if pos == -1:
            pos = search_cursor
        start_line = text[:pos].count("\n") + 1
        end_line = start_line + stripped.count("\n")
        search_cursor = pos + len(stripped)

        sym_name = f"sql_statement_{idx}"
        kind = "sql_statement"
        m_ddl = re.search(
            r"(?is)\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:UNIQUE\s+)?(TABLE|VIEW|INDEX|FUNCTION|SCHEMA|ROLE|TRIGGER)\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z0-9_.\"]+)",
            stripped,
        )
        if m_ddl:
            kind = m_ddl.group(1).lower()
            sym_name = m_ddl.group(2).strip('"')
        else:
            m_cte = re.search(r"(?is)^\s*WITH\s+([A-Za-z0-9_]+)\s+AS\s*\(", stripped)
            if m_cte:
                kind = "cte"
                sym_name = m_cte.group(1)

        for tbl_m in re.finditer(r"(?is)\b(?:FROM|JOIN|REFERENCES|INTO)\s+([A-Za-z0-9_.\"]+)", stripped):
            refs.append(tbl_m.group(1).strip('"'))

        symbols.append({"name": sym_name, "kind": kind, "start_line": start_line, "end_line": end_line})
        chunks.append(
            CodeChunk(
                project=project,
                file_path=rel_path,
                language="sql",
                symbol_name=sym_name,
                chunk_kind=kind,
                start_line=start_line,
                end_line=end_line,
                commit_hash=commit_hash,
                content=stripped,
            )
        )

    if not chunks and text.strip():
        chunks.extend(_sliding_window_chunks(project, rel_path, "sql", text, commit_hash))

    return chunks, list(dict.fromkeys(refs)), symbols


def _extract_markdown_chunks(
    project: str,
    rel_path: str,
    text: str,
    commit_hash: str,
) -> Tuple[List[CodeChunk], List[Dict[str, object]]]:
    """Split Markdown documents by headings (#, ##, ###...) preserving exact line bounds."""
    lines = text.splitlines()
    headings: List[Tuple[int, str]] = []
    in_fence = False

    for idx, line in enumerate(lines, start=1):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            m = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
            if m:
                headings.append((idx, m.group(2).strip()))

    if not headings:
        return _sliding_window_chunks(project, rel_path, "markdown", text, commit_hash), []

    chunks: List[CodeChunk] = []
    symbols: List[Dict[str, object]] = []

    if headings[0][0] > 1:
        intro = "\n".join(lines[: headings[0][0] - 1]).strip()
        if intro:
            chunks.append(
                CodeChunk(
                    project=project,
                    file_path=rel_path,
                    language="markdown",
                    symbol_name="Preamble",
                    chunk_kind="heading",
                    start_line=1,
                    end_line=headings[0][0] - 1,
                    commit_hash=commit_hash,
                    content=intro,
                )
            )

    for i, (s_line, title) in enumerate(headings):
        e_line = (headings[i + 1][0] - 1) if (i + 1 < len(headings)) else len(lines)
        body = "\n".join(lines[s_line - 1 : e_line]).strip()
        if not body:
            continue
        symbols.append({"name": title, "kind": "heading", "start_line": s_line, "end_line": e_line})
        chunks.append(
            CodeChunk(
                project=project,
                file_path=rel_path,
                language="markdown",
                symbol_name=title,
                chunk_kind="heading",
                start_line=s_line,
                end_line=e_line,
                commit_hash=commit_hash,
                content=body,
            )
        )

    return chunks, symbols


def _sliding_window_chunks(
    project: str,
    rel_path: str,
    language: str,
    text: str,
    commit_hash: str,
    window_lines: int = 60,
    overlap: int = 10,
) -> List[CodeChunk]:
    """Sliding line-window chunker fallback for text, config, YAML, JSON, and unknown formats."""
    lines = text.splitlines()
    if not lines:
        return []
    chunks: List[CodeChunk] = []
    step = max(1, window_lines - overlap)
    start = 0
    block_idx = 1

    while start < len(lines):
        end = min(len(lines), start + window_lines)
        snippet = "\n".join(lines[start:end]).strip()
        if snippet:
            chunks.append(
                CodeChunk(
                    project=project,
                    file_path=rel_path,
                    language=language,
                    symbol_name=f"{Path(rel_path).name}#L{start + 1}-{end}",
                    chunk_kind="window",
                    start_line=start + 1,
                    end_line=end,
                    commit_hash=commit_hash,
                    content=snippet,
                )
            )
        if end >= len(lines):
            break
        start += step
        block_idx += 1

    return chunks


def parse_file_to_chunks(
    project: str,
    rel_path: str,
    text: str,
    commit_hash: str = "working-tree",
    language_override: Optional[str] = None,
) -> ParsedFileResult:
    """Chunk a file AST-aware where supported and extract structural imports & symbols."""
    language = language_override or detect_language(rel_path)
    content_hash = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
    line_count = len(text.splitlines())

    imports: List[str] = []
    symbols: List[Dict[str, object]] = []

    if language == "python":
        chunks, imports, symbols = _extract_python_ast(project, rel_path, text, commit_hash)
    elif language in ("javascript", "jsx"):
        chunks, imports, symbols = _extract_js_ast(project, rel_path, language, text, commit_hash)
    elif language == "sql":
        chunks, imports, symbols = _extract_sql_chunks(project, rel_path, text, commit_hash)
    elif language == "markdown":
        chunks, symbols = _extract_markdown_chunks(project, rel_path, text, commit_hash)
    else:
        chunks = _sliding_window_chunks(project, rel_path, language, text, commit_hash)

    return ParsedFileResult(
        file_path=rel_path,
        language=language,
        line_count=line_count,
        content_hash=content_hash,
        imports=imports,
        symbols=symbols,
        chunks=chunks,
    )
