# Fixdesk — Plain-English Architecture Guide (`EXPLAIN.md`)

## 1. What Fixdesk Does

**Fixdesk** is an internal AI operations control room with three core capabilities backed by PostgreSQL (`pgvector`), PySpark, LangGraph, FastAPI, MCP, and Next.js:

1. **Analytics & Policy Workbench (`01 Analysis`, `03 Quality`, `04 Docs`)**:
   - Analysts upload any CSV dataset (cleaned via PySpark) and policy files (`.md`, `.txt`, `.pdf` chunked into 768-D embeddings).
   - A LangGraph agent classifies whether each question needs read-only SQL (`DATA`), semantic policy retrieval (`DOCS`), or `BOTH`, checks groundedness (`max 2` retries), and streams execution steps + citations into the UI.
2. **Support Desk & Safe Remediation (`02 Support`)**:
   - Receives client issues from Slack (Socket Mode), Email (IMAP/SMTP), Webhook, or UI intake.
   - Investigates and tests proposed SQL/code patches against isolated sandboxes (`sales_sandbox`), then pauses at a LangGraph Human-in-the-Loop checkpoint (`interrupt_before=["apply_fix"]`) until an operator approves or rejects with an audit entry in `audit_log`.
3. **Project Init — Codebase RAG (`05 Projects`)**:
   - Indexes configured git repositories from `projects.yaml` into a dedicated `code_rag` PostgreSQL schema so engineers can ask *"where is feature X implemented?"* or *"which files import module Y?"* with exact `file:line` citations while strictly blocking secrets.

---

## 2. How Project Init Keeps Secrets Out

Project Init applies **five independent layers of defense**:

1. **Path Confinement (`project_init/config.py`)**: Every path resolves via `os.path.realpath()` and fails immediately with `PermissionError` if it escapes the registered project root.
2. **`.gitignore` + Mandatory Skip Rules (`project_init/security.py`)**: Compiles repository `.gitignore` with `pathspec` and unconditionally excludes `.env`, `.env.*`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `id_rsa*`, `*.kdbx`, `credentials*`, `secrets*`, `service-account*.json`, `.npmrc`/`.pypirc` with credentials, `*.tfstate*`, database dumps, `node_modules`, build folders, virtualenvs, `.git`, binaries, and files larger than `CODE_RAG_MAX_FILE_BYTES`. Lockfiles (`package-lock.json`, `poetry.lock`, etc.) emit only a minimal package-count summary.
3. **Pre-Index Secret Scanner (`scan_file_for_secrets`)**: Runs `gitleaks` (when installed) plus built-in high-precision regex rules (private keys, AWS/Google/GitHub/Slack/Stripe/JWT keys, external DSNs) and Shannon entropy assignment checks *before* any chunk is created. Files with findings go straight to `code_rag.skipped_files` (filenames and rules only — never secret values).
4. **Chunk-Level Second Line of Defense (`check_chunk_security`)**: Scans every individual chunk again before summarizing or embedding; any chunk matching a secret pattern or high-entropy credential assignment (including local connection strings) is dropped.
5. **Output Filter (`redact_secrets`)**: Runs on every search snippet, MCP tool JSON payload, API error/response, and LLM answer, replacing any secret-looking substring with `[REDACTED]`.

---

## 3. AST Chunking, Caching & Hybrid Retrieval

- **AST Chunking (`project_init/chunker.py`)**:
  - Python & JS/JSX use `tree-sitter` to split classes, methods (`ClassName.method`), functions, and top-level exports, while extracting structured `imports` lists and symbol tables.
  - SQL uses `sqlparse` to split tables, views, CTEs, and statements with exact line ranges.
  - Markdown splits on headings (`#`–`######`); config/text files use a 60-line overlapping sliding window.
- **Content-Hash Summary Caching & Incremental Diff (`project_init/indexer.py`, `project_init/summarizer.py`)**:
  - Summaries are cached in `code_rag.summary_cache` keyed by SHA-256 `content_hash`.
  - `project-init reindex <name>` compares `git diff` plus stored per-file `content_hash` values so only modified or added files are re-chunked/re-embedded, while deleted or newly sensitive files are purged from `code_rag.code_chunks` and `code_rag.file_metadata`.
- **Hybrid Search & Grounded Answers (`project_init/retriever.py`)**:
  - Queries combine `pgvector` HNSW cosine similarity (`<=>`) with PostgreSQL `tsvector` full-text ranking, path/symbol reranking, and structured `imports` JSONB queries.
  - `ask_codebase` answers strictly from retrieved chunks with `file_path:start_line-end_line` citations, or returns `"not found in the indexed code"` when unsupported.

---

## 4. Hybrid Cloud Mode (Laptop Compute + GCP Data, AI & Vector Services)

Fixdesk keeps all interactive compute (Next.js UI, FastAPI, LangGraph, MCP tools, and local PySpark `master="local[*]"`) on the laptop while allowing each external dependency to switch independently to GCP via `backend/cloud/`:
- **Files (`FILE_STORE_BACKEND=gcp`)**: `GcsFileStore` uploads/downloads CSVs (`raw/`), cleaned Parquet (`clean/`), and policy docs (`docs/`) in a US Cloud Storage bucket.
- **Analytics & Support Sandbox (`STORAGE_BACKEND=gcp`)**: `BigQuerySalesStore` loads Parquet into `fixdesk.sales`, isolates Support Desk previews inside `fixdesk_sandbox.sales_sandbox`, enforces single-`SELECT` + `LIMIT <= 100` + dry-run byte checks + `BQ_MAX_BYTES_BILLED`, and keeps `support_tickets`/`audit_log` safely in local PostgreSQL.
- **AI & Embeddings (`LLM_BACKEND=vertexai`, `EMBEDDING_BACKEND=vertexai`)**: Authenticates strictly via ADC (`google.auth.default()`, blocking service-account JSON key files), applies exponential backoff retries, and enforces daily request/token limits in `data/.budget_state.json`.
- **Vector Search & Codebase Privacy (`VECTOR_BACKEND=gcp`)**: `BigQueryVectorStore` stores 768-D `ARRAY<FLOAT64>` vectors and queries with `VECTOR_SEARCH(..., distance_type => 'COSINE')`, while `cloud_index_allowed: false` in `projects.yaml` guarantees private codebases never leave the laptop unless explicitly enabled.
