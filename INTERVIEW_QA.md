# Technical & Architecture Interview Q&A (`INTERVIEW_QA.md`)

Focused engineering Q&A covering the **Project Init (Secret-Safe Codebase RAG)** architecture and core platform design.

---

### 1. Why store codebase RAG tables in a separate `code_rag` PostgreSQL schema instead of reusing `document_embeddings`?
Because codebase search needs structured code metadata (`symbol_name`, `chunk_kind`, `start_line`, `end_line`, `commit_hash`, `imports` JSONB, `file_metadata` tree, and `skipped_files` audit rows) plus its own HNSW and GIN `tsvector` indexes. Keeping it in `code_rag` prevents policy document queries from accidentally retrieving source code snippets and lets `public.sales` stay isolated.

### 2. How do you guarantee a secret file or hardcoded token never ends up inside pgvector embeddings?
Through defense in depth before embedding ever runs:
1. Path/glob blocking + `.gitignore` matching via `pathspec` skips `.env*`, keys, certs, dumps, and binaries.
2. Pre-index secret scanning (`gitleaks` if installed + built-in regex & Shannon entropy checks) aborts risky files completely before parsing and records only `(file_path, reason, rule)` in `code_rag.skipped_files`.
3. Every chunk undergoes a second-line `check_chunk_security()` check before calling the embedder.
4. Outputs from search, MCP tools, API routes, and LLM synthesis pass through `redact_secrets()` (`[REDACTED]`).

### 3. Why use Tree-sitter instead of fixed character-count splitting for Python and JavaScript/JSX?
Character windows cut functions in half and lose exact symbol boundaries and line numbers. Tree-sitter parses real CST/AST nodes (`function_definition`, `class_definition`, `function_declaration`, `arrow_function`), letting each chunk capture a self-contained symbol (`ClassName.method`), exact 1-based `(start_line, end_line)`, and structured `import` dependencies in the same pass.

### 4. How does incremental re-indexing avoid re-embedding the whole repository and clean up deleted files?
`index_project()` stores per-file `content_hash` in `code_rag.file_metadata` and `last_commit_hash` in `code_rag.projects`. On incremental runs, it checks `git diff --name-status` since `last_commit_hash` alongside current working-tree `content_hash` values. Unchanged files are skipped; modified/added files replace only their own `file_path` chunks; deleted or newly skipped files are purged via `store.delete_file()`.

### 5. How does caching chunk summaries by `content_hash` save tokens?
`code_rag.summary_cache` keys summaries by the SHA-256 hash of each chunk's source text. If a file is touched (or shifted lines during an unrelated edit) and a function's body hash already exists in `summary_cache`, the summary is reused without calling the LLM.

### 6. Why combine `pgvector` HNSW vector similarity with `tsvector` keyword and symbol matching?
Code queries mix conceptual phrasing (*"where are MCP tools registered?"*) with exact identifiers (*"check_chunk_security"*, *"orders_api.py"*). Dense embeddings alone can miss rare identifier tokens, while pure BM25/FTS misses paraphrases. Hybrid scoring (`FULL OUTER JOIN` over HNSW cosine hits and `ts_rank_cd` GIN hits) followed by symbol/path reranking gives strong recall on both.

### 7. How can the system answer structure questions like "which files import `db_client`"?
During AST parsing, `parse_file_to_chunks()` extracts `import`/`from ... import`/`require` targets into `code_rag.file_metadata.imports` (`JSONB` indexed with GIN). When `ask_codebase()` detects an import question, it queries `find_files_importing()` directly instead of hoping a chunk snippet happened to include line 1 imports.

### 8. How do the read-only MCP tools (`search_code`, `get_file_outline`, `find_symbol`, `list_projects`) prevent directory traversal?
Every path argument passes through `resolve_safe_path()` using `os.path.realpath()` and `Path.relative_to(project_root)`. Any `..` escape, external absolute path, or symlink resolving outside the project root raises `PermissionError`, and every path is re-validated against `classify_file()` so `.env` or skipped files cannot be read even via direct path arguments.

### 9. How does `ask_codebase` prevent hallucinated code answers?
1. Retrieved candidates must pass lexical/score relevance gating; otherwise it immediately returns `"not found in the indexed code"`.
2. When an LLM synthesizes the response, the system prompt restricts facts strictly to retrieved chunks and demands inline `file:line` citations, instructing the model to reply `"not found in the indexed code"` if unverified.
3. Offline mode returns only structured chunk citations directly from the retrieved rows.

### 10. How did you test all of this safely without an API key or touching the production database?
`tests/conftest.py` enforces `fixdesk_test` and clears `GOOGLE_API_KEY`. `tests/test_project_init.py` builds a temporary git repo containing fake `.env`, private key, AWS-style key, inline DSNs, `.npmrc`, lockfiles, and multi-language code, uses deterministic 768-D local embeddings + counting LLM callbacks, verifies zero secret values across chunks, store rows, logs, FastAPI JSON, MCP JSON, and answers, and verifies `PostgresCodeStore` SQL statements + live DB isolation.
