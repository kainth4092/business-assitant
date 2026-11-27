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

---

## Hybrid Google Cloud Migration Q&A (BigQuery, GCS, Vertex AI, BigQuery Vector Search)

### 11. Why did Fixdesk choose a Hybrid Laptop + GCP Data/AI architecture instead of deploying everything to Cloud Run or GKE?
Keeping the Next.js frontend, FastAPI backend, LangGraph agents, MCP server, and local PySpark (`master="local[*]"`) on the laptop eliminates all always-on compute costs (Cloud Run, GCE VMs, Cloud SQL, Dataproc clusters, GPUs) while still gaining managed cloud persistence (`GCS`), analytical SQL (`BigQuery`), serverless vector search (`BigQuery Vector Search`), and enterprise IAM-authenticated AI (`Vertex AI Gemini`).

### 12. How do the `backend/cloud/` abstractions keep local and GCP behavior interchangeable?
`backend/cloud/interfaces.py` defines five narrow ABCs (`SalesStore`, `VectorStore`, `FileStore`, `LlmClient`, `EmbeddingClient`). Factory functions in `backend/cloud/factories.py` read independent environment switches (`STORAGE_BACKEND`, `VECTOR_BACKEND`, `FILE_STORE_BACKEND`, `LLM_BACKEND`, `EMBEDDING_BACKEND`) dynamically so any subsystem can run locally or against GCP without changing LangGraph nodes, MCP tools, or FastAPI routes.

### 13. Why does Fixdesk block service-account JSON key files in `backend/cloud/auth.py`?
Downloaded service-account private keys are long-lived static secrets prone to accidental git commits or laptop leakage. `load_adc_credentials()` uses `google.auth.default()` (Application Default Credentials via `gcloud auth application-default login`) and inspects `GOOGLE_APPLICATION_CREDENTIALS` plus credential types to raise `ServiceAccountKeyBlockedError` if a service-account key file is ever supplied.

### 14. How do you prevent runaway BigQuery scan bills from agent-generated SQL?
Every `BigQuerySalesStore.query_sales()` call passes through three gates: (1) `rewrite_sql_for_bigquery()` enforces single-`SELECT`/`WITH`, strips/blocks comments and DDL/DML, clamps `LIMIT <= 100`, and pins table references to `BQ_DATASET` only; (2) a **$0 dry-run** (`QueryJobConfig(dry_run=True, use_query_cache=False)`) rejects queries whose `total_bytes_processed` exceeds `BQ_MAX_BYTES_BILLED` (100 MiB default); and (3) execution sets `maximum_bytes_billed` as a server-side hard stop.

### 15. How does the Support Desk Human-in-the-Loop (HITL) workflow isolate data previews in GCP mode?
When `STORAGE_BACKEND=gcp`, `preview_data_fix()` copies `{project}.{BQ_DATASET}.sales` into `{project}.{BQ_SANDBOX_DATASET}.sales_sandbox` and executes the proposed DML patch strictly in `BQ_SANDBOX_DATASET`, returning before/after counts and sample rows. Production `{BQ_DATASET}.sales` is only modified by `apply_data_fix()` after `mcp_server/support_tools.py` validates the operator's `approval_token` against local PostgreSQL `support_tickets`, while `audit_log` remains transactional and local.

### 16. How does the PySpark ETL pipeline work with GCS and BigQuery without a Dataproc cluster?
`pipelines/clean_sales.py` keeps `SparkSession.builder.master("local[*]")` on the laptop. When `FILE_STORE_BACKEND=gcp`, `GcsFileStore` downloads CSVs from `gs://<bucket>/raw/` to a local staging path, PySpark cleans and writes Parquet locally, `GcsFileStore` uploads Parquet parts to `gs://<bucket>/clean/`, and `BigQuerySalesStore.load_sales_from_parquet()` runs `client.load_table_from_uri(..., SourceFormat.PARQUET)` into `{BQ_DATASET}.sales`, mirrors to `BQ_SANDBOX_DATASET`, and writes `quality_reports` + `schema_metadata`.

### 17. How did you modernize the Gemini SDK and LangChain integration for Vertex AI?
Fixdesk uses `google-genai` (`3.6.x`) with `genai.Client(vertexai=True, project=..., location=...)` and `langchain-google-genai` (`4.5.x`) with `ChatGoogleGenerativeAI(..., vertexai=True, project=..., location=...)` and `GoogleGenerativeAIEmbeddings(..., vertexai=True, project=..., location=...)` authenticated via ADC, replacing deprecated `vertexai.generative_models` and `langchain-google-vertexai`.

### 18. How does `BigQueryVectorStore` implement semantic RAG without paying for dedicated vector index nodes?
`BigQueryVectorStore` stores 768-dimensional embeddings as `ARRAY<FLOAT64>`, issues `CREATE VECTOR INDEX IF NOT EXISTS ... OPTIONS(index_type = 'IVF', distance_type = 'COSINE')` (gracefully deferring if below BigQuery's 5,000-row IVF threshold), and queries with `VECTOR_SEARCH(TABLE ..., 'embedding', (SELECT @query_vec AS embedding), top_k => @top_k, distance_type => 'COSINE')` using parameterized `ArrayQueryParameter` and `maximum_bytes_billed`.

### 19. How do you enforce daily AI cost/quota limits across both Vertex AI and Gemini API mode?
`backend/cloud/budget.py` maintains a thread-safe daily counter in `data/.budget_state.json` tracking requests and estimated/reported tokens against `AI_DAILY_REQUEST_LIMIT` and `AI_DAILY_TOKEN_LIMIT`. Reaching `AI_BUDGET_WARN_RATIO` (default `0.8`) triggers a warning in `GET /status` and renders an amber/seal banner in `WorkbenchApp.jsx`, while reaching `1.0` raises `BudgetExceededError` to pause further cloud calls.

### 20. How does `cloud_index_allowed: false` protect private codebases when cloud backends are enabled?
`projects.yaml` defaults `cloud_index_allowed: false` on every repository. Even when `VECTOR_BACKEND=gcp`, `LLM_BACKEND=vertexai`, or `EMBEDDING_BACKEND=vertexai` is enabled globally, `get_code_store()`, `index_project()`, `ask_codebase()`, and `generate_chunk_summary()` check `cfg.cloud_index_allowed` and refuse to send repository chunks, summaries, or embeddings to BigQuery or Vertex AI unless explicitly opted in (and still apply all 5 secret-filtering layers locally first).
