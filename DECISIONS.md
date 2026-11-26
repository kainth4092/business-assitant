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

---

### Decision 20: Full Zero-Mock Data-Agnostic Reset & Dedicated Test DB Isolation
- **Context**: The project required a complete reset to a data-agnostic state so any user CSV and documents can be uploaded and processed without hardcoded references to BigMart or sample policies. Additionally, prior test runs polluted the application database with test tickets and audit records.
- **Decision**:
  1. **Test Database Isolation**:
     - Created `business_assistant_test` database for all unit, integration, and guardrail tests.
     - Implemented a strict safety guard in `tests/conftest.py` that raises a `RuntimeError` if any test attempts to connect to or read from `business_assistant`.
  2. **Complete Data & Seed Purge**:
     - Purged all Docker volumes, Parquet files, vector chunks, chat messages, tickets, and audit logs.
     - Emptied `data/` and `docs/` directories, retaining only guidance `README.md` files.
     - Removed `pipelines/generate_data.py` and all sample policies.
     - Verified exactly 0 rows across all tables in `business_assistant`.
  3. **Data-Agnostic PySpark & Ingestion Pipelines**:
     - PySpark pipeline auto-discovers schema, column types (numeric, categorical, date/time, identifier), handles nulls, and dynamically creates the table in PostgreSQL.
     - Document ingestion supports `.md`, `.txt`, and `.pdf` extracting titles directly from first headings or document text, with zero filler descriptions.
     - `/sample-questions` dynamically derives analytical questions from discovered columns and document titles, returning an empty list `[]` when the database is empty.
  4. **First-Run Onboarding & Genuine Empty States**:
     - Main Analysis screen displays "Upload a CSV to begin" with an integrated "Add Data & Run Ingestion" panel (and modal accessible from top header).
     - Data Quality displays "Run the pipeline to see a report".
     - Documents displays "No documents yet".
     - Support Desk displays "No tickets yet", with "Simulate Client" accepting custom user-entered incident messages.
     - All fake metrics ("18ms", "0.8s", "1,500", "21 chunks") removed; values display "—" when no historical runs exist.
  5. **Guardrail Tests**:
     - Implemented `tests/test_zero_mock_guardrails.py` asserting no forbidden patterns appear in production code, testing 3 small synthetic CSVs generated strictly inside the test, and verifying 0 rows remain in the application database.
- **Consequences**: The project is completely clean, robustly tested, and ready for any dataset uploaded via UI or CLI.



---

### Decision 21: Real Communication Channels for Support Desk (Telegram, Email, Slack, Teams Stub)
- **Context**: Previously, Support Desk tickets only arrived via manual submission in the UI (`+ Simulate Client`) or HTTP `POST /support/messages` webhook. Real clients need to report problems directly from Telegram, Email, or Slack without requiring public webhook URLs for local deployments, while keeping sandbox isolation and human approval strictly unchanged.
- **Decision**:
  1. **Unified Adapter & Ingestion Architecture**:
     - Standardized `ChannelAdapter` and `NormalizedChannelMessage` (`sender_name`, `sender_id`, `sender_email`, `channel`, `text`, `timestamp`, `thread_id`, `external_message_id`, `thread_url`, `metadata`) in `backend/support/adapters.py`.
     - Routed both `/support/messages` and all channel workers through a single internal function `ingest_channel_message` in `backend/support/service.py`.
  2. **Zero-Public-URL Transports for Local Workstations**:
     - **Telegram (`TelegramAdapter`)**: HTTP long polling via `httpx` (`getUpdates` / `sendMessage`), no webhook server needed.
     - **Email (`EmailAdapter`)**: Built-in Python `imaplib` 30-second inbox/folder polling for `UNSEEN` messages and `smtplib` threaded replies (`In-Reply-To`, `References`), zero extra packages needed.
     - **Slack (`SlackAdapter`)**: Official `slack_sdk` Socket Mode (`xapp-` app token + `xoxb-` bot token), listening on allowed channels/DMs and replying in thread via `chat.postMessage`.
     - **Microsoft Teams (`TeamsAdapterStub`)**: Retained as a clean stub documented in `docs/TEAMS_SETUP.md` (requires Azure Bot registration & public HTTPS webhook from IT admin).
  3. **Safety, Deduplication, Allowlists & Human-Only Approval**:
     - Added `sender_id`, `external_message_id`, `thread_id`, `thread_url`, `channel_metadata`, `is_flagged`, and `flag_reason` columns with an idempotent runtime migration and unique dedupe index `(channel, external_message_id)` on `support_tickets`.
     - Enforced `.env` fail-closed allowlists (`TELEGRAM_ALLOWED_CHAT_IDS`, `EMAIL_ALLOWED_SENDERS`, `SLACK_ALLOWED_CHANNELS`), per-sender hourly rate limiting (`SUPPORT_RATE_LIMIT_PER_HOUR=10`), untrusted prompt-injection/destructive-SQL flagging (`detect_untrusted_injection`), and secret/SQL/traceback redaction on all outbound replies (`sanitize_channel_reply`).
     - Kept the LangGraph `interrupt_before=["apply_fix"]` checkpoint and `approval_token` gate completely untouched; no inbound channel message can approve or apply fixes.
  4. **Docs Exclusion from User RAG**:
     - Added `is_user_policy_doc` in `pipelines/ingest_docs.py` (reused in `backend/main.py`) to exclude `CHANNELS_SETUP.md` and `TEAMS_SETUP.md` alongside `README.md` so setup documentation never pollutes user company RAG embeddings.
  5. **Background Worker Lifecycle & UI**:
     - Added `ChannelManager` (`backend/support/channel_manager.py`) started automatically via FastAPI `lifespan` AND runnable standalone via `make channels`.
     - Exposed `GET /support/channels` and `POST /support/channels/{channel_id}/toggle`, paired with `ChannelStatusPanel.jsx`, `ChannelBadge.jsx`, thread links, and flagged alerts in the Support Desk UI.
- **Consequences**: Users can connect real messaging accounts by dropping credentials into `.env` without modifying code or exposing public ports, while all security and HITL guarantees stay enforced.

---

### Decision 22: Remove Telegram Communication Channel
- **Context**: User requested removing the Telegram communication channel from Support Desk while keeping Email (IMAP/SMTP), Slack (Socket Mode), Microsoft Teams (stub), Webhook, and Simulated channels active.
- **Decision**:
  - Deleted `backend/support/channels/telegram.py` and removed Telegram exports, factory branch, `ChannelManager` registration/polling branch, and `LIVE_EXTERNAL_CHANNELS` membership.
  - Removed Telegram badge/select options from `frontend/components/ChannelBadge.jsx`, `frontend/components/SupportDeskView.jsx`, and adjusted `frontend/components/ChannelStatusPanel.jsx` to a 3-column grid for Email, Slack, and MS Teams.
  - Removed Telegram env variables from `.env.example` and updated `tests/test_support_channels.py`, `docs/CHANNELS_SETUP.md`, `docs/TEAMS_SETUP.md`, `USAGE.md`, `DEMO_SCRIPT.md`, and `BLOCKED.md`.
- **Consequences**: Support Desk exposes Email, Slack, and Microsoft Teams (stub) alongside Webhook and Simulated intake with zero remaining Telegram channel code or configuration.

---

### Decision 23: Stationery × Flight-Strip Frontend Redesign & Stack Upgrade
- **Context**: The frontend needed a complete visual, structural, and interaction redesign into a distinctive Japanese stationery × air-traffic-control flight-strip workbench while preserving 100% of backend API calls, routes, and data flow, and upgrading frontend dependencies to current stable versions.
- **Verified Package Versions (`npm view <pkg> version`)**:
  - `next`: `16.4.6` (upgraded from `14.2.15`; Turbopack default bundler, async request APIs, `next lint` removed in favor of ESLint flat config)
  - `react` & `react-dom`: `19.3.1` (upgraded from `18.3.1`; modern JSX transform, React 19 compatibility)
  - `tailwindcss` & `@tailwindcss/postcss`: `4.3.5` (upgraded from `3.4.14`; CSS-first `@import "tailwindcss"` and `@theme` token mapping in `app/globals.css`)
  - `motion`: `14.14.0` (replacing `framer-motion` import with `motion/react`)
  - `lucide-react`: `1.81.0` (upgraded from `0.453.0`; thin `1.5px` stroke icons)
  - `eslint-config-next`: `16.4.6` with `eslint@^9` (peer-compatible with `eslint-plugin-react@7.37.x`)
  - `@playwright/test`: `1.65.1` & `@axe-core/playwright`: `4.14.1` (for E2E, WCAG AA axe scans, and multi-viewport/theme screenshot verification)
- **Design & Platform Decisions**:
  1. **Visual System**: Matte paper (`#F3EFE4`), raised (`#FBF9F2`), sunken (`#E8E2D2`), grid line (`#D3CCB9`), ink (`#16202F`), muted ink (`#55524A`), seal red (`#C8372D`), highlighter yellow (`#F2D45C`), sage (`#5E8C6A`), amber (`#B7791F`), and route tokens DATA (`#2F5D8A`), DOCS (`#A8741A`), BOTH (`#5E8C6A`), paired with a Night Shift dark theme (`#10151D` / `#171E29` / `#E9E4D6`). Foreground text on light paper mixes semantic accents with `--ink` via `color-mix()` where needed so every text element exceeds WCAG AA 4.5:1 contrast.
  2. **Typography & Geometry**: `Shippori_Mincho`, `Zen_Kaku_Gothic_New`, and `JetBrains_Mono` via `next/font/google` with real system fallback stacks; `2px` max corner radius, `1px` hairline borders, `4%` CSS grid-paper background, hard offset paper-stack shadows (`2px 2px 0 var(--grid-line)`), and rotated hanko seal stamps.
  3. **Server/Client Split**: `app/layout.jsx` and `app/page.jsx` remain Server Components; interactive workbench state lives in `components/WorkbenchApp.jsx` and modular components (`Spine`, `Strip`, `StripBoard`, `Stamp`, `LogEntry`, `Margin`, `Timeline`, `SqlBlock`, `DataTable`, `QualityBars`, `IndexCard`, `ChannelStatus`, `CommandPalette`, `KeyboardHelpModal`, `EmptyState`, `ErrorState`, `Skeleton`).
  4. **SSE Streaming & Security**: Added `frontend/lib/sseStream.js` (full `text/event-stream` parser with reconnect backoff, `Last-Event-ID`, `AbortController`, and JSON fallback for `POST /chat`) plus server-side `frontend/app/api/chat/stream/route.js` and security headers in `frontend/next.config.js`.
- **Consequences**: Zero TypeScript files, minimal audited frontend dependencies, modern CSS platform features (`@container`, `:has()`, `document.startViewTransition`, `color-mix()`, logical properties, `prefers-reduced-motion`), and full backward compatibility with all FastAPI endpoints.

---

### Decision 24: Project Init (Secret-Safe Project-Aware Codebase RAG)
- **Context**: Engineers and analysts need codebase Q&A with exact `file:line` citations and structural import/symbol lookups without ever indexing or leaking secrets.
- **Decision**:
  1. **Configuration & Dedicated PostgreSQL Schema**:
     - Added multi-project `projects.yaml` (`name`, `local_path`, `include`, `exclude`, `default_branch`).
     - Added an isolated PostgreSQL schema `code_rag` (`infra/code_rag_schema.sql`) separate from `public.sales`: `code_rag.projects`, `code_rag.file_metadata`, `code_rag.code_chunks` (`VECTOR(768)` + HNSW cosine index + generated `tsvector` GIN index), `code_rag.summary_cache` (content-hash keyed), and `code_rag.skipped_files` (never storing secret values).
  2. **AST Parsing & Verified Libraries**:
     - Python & JS/JSX AST chunking uses `tree-sitter==0.27.0` with `tree-sitter-python==0.25.0` and `tree-sitter-javascript==0.25.0`; SQL statements/functions/views use `sqlparse==0.6.1`; `.gitignore` & glob filtering use `pathspec==1.1.1`; `--watch` uses `watchdog==7.1.1`.
  3. **Defense-in-Depth Secret Protection**:
     - Enforces `.gitignore` + mandatory skip list (`.env*`, private keys, keystores, credentials/secrets files, `.npmrc`/`.pypirc` with tokens, Terraform state, DB dumps, lockfile summary-only mode, binaries/large files, `.git`), pre-index file secret scanning (`gitleaks` when installed + built-in regex & Shannon entropy scanner), chunk-level regex & entropy gating, path-confinement validation, and output `[REDACTED]` filtering across CLI, MCP tools, API, and LLM answers.
  4. **Storage Portability Note**:
     - Primary runtime store uses PostgreSQL + `pgvector` in `code_rag`; in environments where the Docker PostgreSQL service on `5434` is unavailable, automated tests isolate via the test suite without modifying production data (`BLOCKED.md` records Docker status honestly).
- **Consequences**: Codebase RAG operates independently alongside sales/document workflows, supports incremental git-diff/hash re-indexing, exposes read-only MCP tools (`search_code`, `get_file_outline`, `find_symbol`, `list_projects`), FastAPI `/projects/*` routes, and the `05 Projects` workbench view.
