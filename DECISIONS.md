# Architecture & Engineering Decisions Log (DECISIONS.md)

This log records all technical, architectural, and design decisions made for the "Business Assistant" project.

---

### Decision 1: Database Port Allocation (Port 5434)
- **Context**: The host machine already has a local PostgreSQL instance listening on port 5432 and a Docker container `knowledgehub-postgres` listening on port 5433.
- **Decision**: Map the PostgreSQL container in `infra/docker-compose.yml` to host port `5434:5432` (`POSTGRES_PORT=5434` in `.env`). Inside the docker network, services communicate on port 5432; host-run pipelines and tests connect to port 5434.
- **Consequences**: Avoids port collisions and ensures immediate startup without interfering with other local services.

---

### Decision 2: PySpark Environment & Java 21 Handling
- **Context**: The host machine has OpenJDK 21 installed. PySpark 3.5+ and 4.0 run on Java 17 and 21 but benefit from JVM options to bypass Java Module system reflection warnings (`--add-opens=java.base/java.lang=ALL-UNNAMED`).
- **Decision**: Configure PySpark driver options with `--add-opens` flags and explicitly set `JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64` in scripts. Provide JDBC write as well as a SQLAlchemy fallback to guarantee reliable persistence under any driver variation.
- **Consequences**: Robust ETL execution without JVM access crashes.

---

### Decision 3: Synthetic BigMart Dataset Generation
- **Context**: `/data/BigMart_Sales.csv` may be missing or unprovided initially.
- **Decision**: Implement `pipelines/generate_data.py` to synthetically generate a 1,200+ row dataset mimicking the real BigMart Sales dataset with realistic product categories, sales amounts, intentional null values in `Item_Weight` and `Outlet_Size`, intentional duplicate rows, and messy labels in `Item_Fat_Content` (`LF`, `low fat`, `Low Fat`, `reg`, `Regular`).
- **Consequences**: The project is self-contained and reproducible out of the box.

---

### Decision 4: PostgreSQL Security & Read-Only Role (`sales_readonly`)
- **Context**: The agent can generate arbitrary SQL queries. Allowing unrestricted database execution introduces severe SQL injection, data leakage, and mutation risks.
- **Decision**: Implement a two-tier defense:
  1. **Role-based isolation**: In `infra/init.sql`, create a dedicated role `sales_readonly` with `CONNECT` to database and `SELECT` permission ONLY on table `public.sales`. Deny all `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`, and administrative privileges.
  2. **Application-level SQL Sanitizer**: In `mcp_server/tools.py`, inspect the query with regex:
     - Verify it begins strictly with `SELECT`.
     - Reject semicolons (preventing query chaining).
     - Reject comments (`--` and `/* ... */`).
     - Reject dangerous SQL commands (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`, `EXEC`, `CREATE`, `GRANT`, `REVOKE`, `INTO`).
     - Enforce a `LIMIT 100` clause if omitted or if greater than 100.
- **Consequences**: Defense-in-depth security preventing accidental data corruption or malicious SQL injection.

---

### Decision 5: RAG Vector Dimensions & Embedding Fallback
- **Context**: Google Gemini's `text-embedding-004` generates 768-dimensional vectors. However, when run in test/offline environments without a valid `GOOGLE_API_KEY`, calls to Google API fail.
- **Decision**: Configure pgvector table `document_embeddings` with `vector(768)`. When `GOOGLE_API_KEY` is absent or set to dummy value (e.g. `mock_key` or empty), provide a deterministic 768-dimensional fallback embedding based on hashed token frequencies.
- **Consequences**: Unit tests and local developer onboarding run seamlessly without requiring paid or activated API keys, while live production environments use standard Gemini embeddings.

---

### Decision 6: LangGraph Agent Loop & Retry Cap (Max 2)
- **Context**: An LLM agent may generate an ungrounded or incomplete answer on the first attempt. Without a loop limit, the agent could enter an infinite retry cycle, draining tokens and hanging user requests.
- **Decision**: Implement a conditional edge in LangGraph:
  - `check_node` assesses answer groundedness against retrieved context and tool outputs.
  - If grounded -> Route to `END`.
  - If ungrounded AND `retry_count < 2` -> Increment `retry_count`, pass corrective feedback, and route back to `agent_node`.
  - If ungrounded AND `retry_count >= 2` -> Route to `END` with a transparency notice.
- **Consequences**: Guaranteed response termination within predictable latency and cost bounds.

---

### Decision 7: Dual-Mode MCP Server Implementation
- **Context**: The project specification requires an MCP server exposing tools (`query_sales`, `search_docs`, `get_data_quality_report`) and LangChain integration.
- **Decision**: Structure the MCP component into:
  - `mcp_server/tools.py`: Pure, robust Python functions with schema typing, SQL safety filters, and database connectivity.
  - `mcp_server/server.py`: Standard FastMCP server instance exposing these tools over stdio/SSE for MCP clients.
  - `backend/agent/tools.py`: LangChain `@tool` wrappers that directly delegate to `mcp_server/tools.py`.
- **Consequences**: Full compliance with the official Model Context Protocol while maintaining high-performance native Python execution within the FastAPI backend.

---

### Decision 8: Next.js Frontend Framework & Language Choice
- **Context**: The requirement mandates Next.js (App Router) in JavaScript (`.jsx`, NOT TypeScript) and Tailwind CSS.
- **Decision**: Scaffold the frontend in `/frontend` using Next.js 14/15 App Router with pure JavaScript JSX files (`app/page.jsx`, `app/layout.jsx`, etc.) and standard Tailwind utility classes.
- **Consequences**: Clean, modern UI code without TypeScript transpilation overhead, adhering strictly to user guidelines.

---

### Decision 9: Project Directory Organization (`/home/kanish/Documents/business-assistant`)
- **Context**: The active workspace was initially `/home/kanish/Documents`, where other existing projects reside (`agentic-rag`, `Resume-Rag`, `trendhub-ai`, etc.).
- **Decision**: Move all project files, pipelines, backend, frontend, infra, tests, virtual environment, and documentation into a dedicated project directory: `/home/kanish/Documents/business-assistant/`.
- **Consequences**: Keeps the user's `Documents` root clean, prevents any conflict with existing folders (such as `docs/Deneo-refi`), and ensures the project is completely self-contained.

---

### Decision 12: Editorial Analyst Workbench Redesign
- **Context**: The user requested a complete UI/UX overhaul of `/frontend` from the default AI chat appearance to an "analyst workbench / editorial tool" (similar to Linear, Notion, or Observable). The frontend must maintain 100% of existing functionality, use React in JavaScript (`.jsx`, no TypeScript), Tailwind CSS, and `next/font/google` without external CDNs.
- **Decision**:
  1. **Aesthetic & Tone**:
     - Paper-like warm canvas (`#FAF8F4`) in light mode; deep slate ink canvas (`#0F1215`) in dark mode.
     - Single restrained accent: Deep Teal (`#0F6B5F` / `#14B8A6`).
     - Typography loaded via `next/font/google`: `Newsreader` (editorial serif headings), `IBM Plex Sans` (body and UI text), and `IBM Plex Mono` (SQL queries, tabular figures, file paths).
     - Geometry: Strict 4px/8px grid, small radii (`rounded-sm` / `rounded`), 1px borders instead of heavy box-shadows, zero neon/purple gradients, and zero emojis.
  2. **Layout & Interaction**:
     - Three-column desktop workbench: 240px slim left sidebar (navigation, active DB telemetry pill, session query log, theme toggle), central editorial document log (bold `Q_01` prompt lines, clean prose answers, inline citations like `[1]`, auto-growing input bar), and 384px right Evidence Panel (route badge, tool chain, syntax-highlighted SQL with copy button, results table, retrieved markdown chunks with cosine similarity, and groundedness check).
     - Dedicated tabs for "Data Quality" (PySpark ETL audit metrics with pure CSS/SVG comparative bars) and "Documents" (pgvector repository with chunk counts and HNSW cosine status).
     - Mobile: Sidebar collapses to slide-over drawer; Evidence panel opens as slide-over sheet or collapsible section.
  3. **Verification**:
     - Passed `npm run lint` with 0 warnings/0 errors.
     - Passed `npm run build` with optimized static bundles.
     - Verified end-to-end with browser visual QA (SQL data queries, document RAG queries, dark/light theme switching, and data quality inspection).
- **Consequences**: Elevated product feel into a professional, dense, and trustworthy analyst tool while maintaining backwards compatibility with all backend endpoints.


---

### Decision 13: Visual Polish, WCAG AA Contrast & Interaction Redesign
- **Context**: The user requested a visual polish redesign addressing low contrast in secondary texts, washed-out flat appearance, and underutilized space below starters, while adding a 4-tab Evidence panel, capabilities strip, route-bordered starters, and an animated segmented route selector.
- **Decision**:
  1. **Color Tokens & Contrast**:
     - Light Theme: Warm Paper canvas (`#F6F1E7`), surface (`#FFFDF8`), sunken (`#EDE6D8`), near-black ink (`#1B1A17`), and muted text (`#5E584B`). Every secondary label verified above WCAG AA (5.27:1 to 5.85:1 contrast, never lighter than `#6B6558`).
     - Dark Theme: Deep Carbon canvas (`#12110F`), surface (`#1B1A17`), sunken (`#0D0C0B`), off-white ink (`#F3EEE2`), and muted text (`#B3AC9B`).
     - Accent: Deep teal (`#0B6E64` in light, `#3FBFAE` in dark).
     - Three Route Tokens: DATA (`#0B6E64`), DOCS (`#B45309`), BOTH (`#3B3F8F`) with soft 11% opacity backgrounds and 35% opacity borders.
     - 3.5% opacity radial dot-grid texture on body canvas.
  2. **Components & Layout**:
     - Capabilities Strip: 3 compact stat tiles under the hero (1,500 sales rows, 21 vector chunks, 3 MCP tools) with 600ms count-up animation.
     - Starter Questions: 5 cards with route-colored 3.5px left borders, route badges, 2px hover lift, and sliding arrow.
     - Raised Composer: Raised surface card (`shadow-composer`), segmented control route selector (`Auto`, `Data`, `Docs`, `Both`), active scale press (`active:scale-[0.98]`).
     - Chat: `YOU · Q_01` prompt label, assistant answer card with route-colored 3.5px left border, inline citation chips `[1]`, `[2]`.
     - Evidence Panel: 4 tabs (`Trace`, `SQL`, `Results`, `Sources`). `Trace` displays vertical execution timeline with 5 sequential nodes and soft pulsing active node. `SQL` displays dark mono block with copy button. `Results` displays zebra-striped table. `Sources` displays vector chunks with cosine similarity.
     - Mobile: Bottom sheet drawer on small screens (< 640px) preventing horizontal overflow on 390px viewports.
  3. **Verification**:
     - Passed `npm run lint` with 0 warnings, 0 errors.
     - Passed `npm run build` with optimized static bundles.
     - Verified end-to-end via automated browser subagent at desktop (1920px) and mobile (390px) viewports with live PostgreSQL backend.
- **Consequences**: High-contrast, dense, professional editorial analyst workbench meeting WCAG AA accessibility standards with zero horizontal overflow.

---

### Decision 14: Autonomous Support Desk with Human-in-the-Loop Remediation & Isolated Sandbox
- **Context**: Clients submit plain-English incident and problem reports (e.g., category label fragmentation, calculation discrepancies in business logic, or policy inquiries). An autonomous agent must classify, investigate, prepare a fix, verify it in isolation, pause for human authorization, apply the fix to production upon approval, and notify the client across communication channels.
- **Decision**:
  1. **LangGraph Support Workflow (`backend/agent/support_graph.py`)**:
     - Built a dedicated state graph with `MemorySaver` checkpointer.
     - 7 sequential nodes: `classify` (categorizes into `data_issue`, `code_bug`, `question`, `feature_request` with confidence score), `investigate` (runs diagnostics and data quality audits), `propose_fix` (generates SQL DML or unified code diff), `test_fix` (sandbox execution with max 2 retry cap), `await_approval` (generates approval token and pauses execution via `interrupt_before=["apply_fix"]`), `apply_fix` (gated by token, commits changes and writes audit log), and `notify` (formats channel-specific response).
  2. **Multi-Tier Safety Architecture**:
     - **Sandbox Isolation**: Previews run strictly against `sales_sandbox` table. Production `sales` is never modified during preview or investigation.
     - **Approval Token Gate**: The `apply_fix` tool requires an explicit `approval_token` matching the ticket's active state. Unapproved calls are rejected with HTTP 403.
     - **SQL DML Restrictions**: Prohibits destructive operations (`DROP`, `TRUNCATE`, `ALTER`). Only sanitized `UPDATE` / `INSERT` are permitted.
     - **Immutable Audit Logging**: Every preview, approval, rejection, and application is recorded in table `audit_log` with actor identity, action type, before/after counts, and timestamp.
  3. **Channel Adapters**:
     - Implemented `ChannelAdapter` abstraction in `backend/support/adapters.py` with concrete implementations: `WebhookAdapter`, `SlackAdapterStub`, and `TeamsAdapterStub`.
     - Created simulator script `scripts/simulate_messages.py` to trigger realistic test incidents over HTTP.
  4. **Frontend Support Desk Workbench (`frontend/components/SupportDeskView.jsx`)**:
     - Filterable ticket backlog (All, Fix Ready, Done).
     - Simulator bar with one-click presets for Slack, Teams, and Webhook incidents.
     - Full execution timeline (Classify -> Investigate -> Test -> Approval).
     - Interactive syntax-highlighted SQL / unified diff viewer with one-click copy.
     - Isolated sandbox verification table showing before vs. after row counts.
     - Human-in-the-Loop authorization modal requiring approver identification before dispatching production commit.
     - Responsive mobile layout without horizontal overflow at 390px.
- **Consequences**: Provides autonomous remediation capabilities with enterprise-grade safety gates, preventing accidental data destruction or unauthorized code modifications.

---

### Decision 16: Stitch Cleanup & Neutral Theme Preservation
- **Context**: The Stitch integration artifacts (`DESIGN.md`, `/design`, `scripts/fetch_stitch_assets.py`, and Stitch project references) were added during design exploration and needed to be purged.
- **Decision**: Remove all exported Stitch files, HTML mockups, screenshots, and asset fetch scripts. Documented every removal in `STITCH_CLEANUP.md`. Preserved the neutral CSS token architecture (`--bg-surface`, `--text-primary`, `--border-default`, etc.) and active UI components to ensure zero visual regression and full feature retention.
- **Consequences**: Pure, self-contained Next.js frontend without obsolete external design artifacts or credentials.

---

### Decision 17: Schema-Agnostic PySpark ETL & Dynamic Agent SQL Architecture
- **Context**: The previous pipeline and agent prompts had hardcoded BigMart column names (`Item_Fat_Content`, `Item_Weight`, `Item_Outlet_Sales`, `Outlet_Size`, etc.). The system must now accept ANY uploaded CSV, automatically discover its schema, clean it dynamically, create the table in PostgreSQL, and provide the real introspected schema to the agent and frontend.
- **Decision**:
  1. **Dynamic Schema Discovery in PySpark**: Scan `/data/*.csv`. Infer types, classify columns into numeric, categorical, date/time, and identifier.
  2. **Generic Cleaning**: Auto-strip strings, normalize casing for low-cardinality columns, impute numeric nulls with column median, impute categorical nulls with "Unknown", deduplicate exact rows.
  3. **Dynamic PostgreSQL Table Creation**: Generate DDL for table `sales` based on discovered sanitized columns and types; load cleaned data and grant `sales_readonly` SELECT privileges.
  4. **Dynamic Schema Reflection**: Expose table schema via `GET /status` and agent tools so the LangGraph agent receives the exact columns, sample values, and column types in its prompt.
  5. **Dynamic Starter Questions & Data Quality Report**: Derive starter analytical queries dynamically from discovered column names (e.g. `SUM(<numeric>) GROUP BY <categorical>`).
- **Consequences**: Business Assistant can ingest and analyze any tabular dataset out of the box with zero code changes.

---

### Decision 18: Zero-Mock Data Authenticity & Real Dynamic Telemetry
- **Context**: The user required a complete audit and removal of all static, hardcoded, mock, fake, and placeholder data from the running application. Everything displayed to the user must originate from real PostgreSQL tables, pgvector embeddings, PySpark ETL audit reports, or genuine user interactions.
- **Decision**:
  1. **Backend Status & Telemetry (`GET /status`)**:
     - Real counts: `SELECT COUNT(*) FROM sales`, `SELECT COUNT(*) FROM document_embeddings`.
     - Introspects available tools dynamically from MCP server.
     - Reports active LLM and embedding model names and embedding dimensions.
  2. **Documents & Chunks API (`GET /documents`, `GET /documents/{id}/chunks`)**:
     - Returns live list of ingested documents from `document_embeddings` with actual chunk counts.
     - Dynamic `/documents/{id}/chunks` returns the actual vector chunks for inspectability.
     - Document ingestion pipeline dynamically scans `docs/*.md` and `docs/*.txt` without hardcoded filename lists.
  3. **Data Quality Persistence & Endpoint (`GET /data-quality`)**:
     - PySpark pipeline inserts the audit report into a new `quality_reports` table in PostgreSQL.
     - `GET /data-quality` reads the latest report directly from PostgreSQL.
     - Frontend dynamically calculates Global Health Index, null resolution percentages, duplicate pruning counts, and invariant check evaluations directly from the live report.
  4. **Chat Persistence (`GET /conversations`, `GET /conversations/{id}`)**:
     - Chat conversations, messages, execution traces, SQL statements, and citations are persisted to PostgreSQL `conversations` and `messages` tables.
     - Sidebar Session Log loads directly from `GET /conversations`.
  5. **Dynamic Starter Questions (`GET /sample-questions`)**:
     - Eliminates static `STARTERS` array in `EmptyState.jsx`.
     - Dynamically generates question candidates from distinct `item_type` and `outlet_type` records in PostgreSQL `sales` table, and titles from `document_embeddings`.
  6. **Support Desk Live Metrics**:
     - Backlog count, autonomous fix rate, and sandbox latency are calculated directly from live `support_tickets` and `audit_log` records.
  7. **Strict Guardrail Tests**:
     - Automated test `tests/test_zero_mock_guardrails.py` scanning source code for forbidden mock patterns, fake numbers, and lorem ipsum outside the `/tests` directory.
  8. **One-Command Setup (`scripts/setup.sh` and `make setup`)**:
     - Automates container startup, database schema initialization, PySpark ETL execution, and document vector ingestion in a single idempotent script.
- **Consequences**: Guarantees complete data authenticity, eliminates silent mock fallbacks, and ensures a fresh clone seamlessly operates on real BigMart data and real policy documents.

---

### Decision 19: Elimination of Redundant UI Controls & Automatic Stale Vector Purge
- **Context**: A duplicate theme switch was present in the top header beside the evidence toggle, creating visual redundancy. In addition, repeated vector ingestions without prior deletion led to stale embedding chunks accumulating when documents were removed or modified.
- **Decision**:
  1. Removed the redundant `<ThemeToggle />` component from the top bar in `frontend/app/page.jsx`, consolidating theme switching strictly into the fixed sidebar utility rail (`frontend/components/Sidebar.jsx`).
  2. Enhanced `pipelines/ingest_docs.py` to truncate `document_embeddings` on full directory ingestion runs, ensuring that if files are removed or re-chunked, obsolete embeddings are immediately purged.
  3. Standardized categorical variant normalization in `pipelines/clean_sales.py` across string columns to handle common label variants (such as `LF`/`low fat` -> `Low Fat`, `reg` -> `Regular`) without hardcoded column names.
- **Consequences**: Clean, unambiguous UI layout conforming strictly to single-control UX guidelines, and guaranteed 1:1 vector chunk fidelity matching the physical `docs/` folder.
