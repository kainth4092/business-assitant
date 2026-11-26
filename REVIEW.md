# Senior Code & Security Review: Fixdesk Redesign

**Scope:** Strict review of the frontend redesign, SSE streaming layer, API integration, database/branch isolation, untrusted input handling, test coverage, and runtime verification status.

---

## Problems Identified

### 1. [HIGH — Untrusted Input / XSS] Unsanitized `ticket.thread_url` rendered in `<a href>`
- **Location:** `frontend/components/TicketDetail.jsx`
- **Issue:** `ticket.thread_url` from inbound channel/webhook tickets was passed directly to `<a href={ticket.thread_url}>`. A `javascript:` or `data:` URL in untrusted ticket metadata could execute script when clicked by an operator.
- **Fix Applied:** Added `getSafeExternalUrl()` enforcing `http:` or `https:` protocol via `new URL()` before rendering the anchor element. Covered by Playwright assertion (`a[href^="javascript:"]` count = `0`).

### 2. [HIGH — Untrusted Input / Payload Forwarding] `/api/chat/stream` forwarded arbitrary request JSON without validation
- **Location:** `frontend/app/api/chat/stream/route.js`
- **Issue:** `POST /api/chat/stream` parsed `request.json()` and forwarded arbitrary keys/types directly to `${BACKEND_URL}/chat` without validating `query` or `route`.
- **Fix Applied:** Enforced non-empty string validation on `query` (returning HTTP `400` on invalid/empty input), sanitized `thread_id`, and allowlisted `route` to `auto | data | docs | both`. Covered by `frontend/tests/sse.test.mjs`.

### 3. [MEDIUM — Functional Gap / Misleading Control] UI route selector (`Auto / Data / Docs / Both`) was never sent to or honored by `POST /chat`
- **Location:** `frontend/components/WorkbenchApp.jsx`, `backend/main.py`, `backend/agent/nodes.py`
- **Issue:** `SegmentedControl` let users choose `Data`, `Docs`, or `Both`, but `WorkbenchApp.jsx` omitted `route` from the `POST /chat` body and `ChatRequest` / `router_node` had no explicit route override field.
- **Fix Applied:** Wired `route: effectiveRoute` in `WorkbenchApp.jsx`, added optional `route: Optional[Literal["auto", "data", "docs", "both"]]` to `ChatRequest` in `backend/main.py`, and updated `router_node` in `backend/agent/nodes.py` to honor explicit `"data" | "docs" | "both"` overrides while preserving autonomous routing for `"auto"` or `None`. Covered by `tests/test_router.py` and Playwright Test 4.

### 4. [MEDIUM — Misleading State] False onboarding & `"STANDBY"` status when backend `/status` was loading or offline
- **Location:** `frontend/components/EmptyState.jsx`, `frontend/components/WorkbenchApp.jsx`, `frontend/components/Spine.jsx`, `frontend/components/Timeline.jsx`
- **Issue:**
  - When `systemHealth === null` (during initial fetch or when backend was down), `EmptyState` defaulted counts to `0` and falsely displayed `"Upload a CSV to begin"` onboarding instead of a loading skeleton or offline error state.
  - `Spine.jsx` showed `"STANDBY"` even when `/status` was unreachable or degraded.
  - `Timeline.jsx` marked `SQL` or `RAG` steps completed from `route === "both"` even if `toolsUsed` didn't contain the corresponding tool.
- **Fix Applied:** Tracked `isStatusLoading` and `statusError` in `WorkbenchApp.jsx`; `EmptyState` now renders `Skeleton` while loading, `ErrorState` with `Retry` when `/status` fails, and onboarding strictly when `systemHealth !== null` with `0` rows/chunks. `Spine.jsx` now displays `PG ONLINE`, `DEGRADED`, or `OFFLINE`. `Timeline.jsx` derives completed tool steps from `toolsUsed` when present.

### 5. [MEDIUM — Error Handling] Unguarded `JSON.parse()` and `res.json()` calls on non-JSON / malformed responses
- **Location:** `frontend/components/WorkbenchApp.jsx`, `frontend/components/AddDataArea.jsx`, `frontend/components/DocumentsView.jsx`
- **Issue:** `JSON.parse()` in `handleSelectConversation` and `await res.json()` in upload/pipeline handlers could throw uncaught exceptions on malformed DB JSON or HTML 502 error pages.
- **Fix Applied:** Added `safeJsonParse()` in `WorkbenchApp.jsx` and `.json().catch(() => ({}))` in `AddDataArea.jsx` and `DocumentsView.jsx`.

### 6. [LOW — Repo & Artifact Hygiene] Stale compiled bytecode & leftover empty scratch file
- **Location:** `backend/support/channels/__pycache__/telegram.cpython-312.pyc`, `new.jsx`
- **Issue:** A compiled `.pyc` file for the deleted `telegram.py` adapter and an empty `0`-byte `new.jsx` remained in the workspace.
- **Fix Applied:** Removed both files.
- **Remaining Operational Note (Left Intentionally / External):** `data/` still holds `reviews.csv`, `cleaned_sales.parquet/`, `data_quality_report.json`, and `schema_metadata.json` from a prior run (`mcp_server/tools.py` falls back to `data/data_quality_report.json` when DB `5434` is down). Not deleted because those are workspace data files rather than code bugs.

### 7. [MEDIUM — Missing Tests] Gaps in SSE, Proxy Validation, Route Forwarding, Reject Flow, and Offline Recovery
- **Issue:** `sseStream.js` (reconnect, `Last-Event-ID`, `event: error`, JSON fallback), `/api/chat/stream` (`400` validation & SSE encoding), `ticket.thread_url` XSS blocking, `CommandPalette` direct query, `TicketDetail` reject flow, `ChannelStatus` toggle, explicit backend `route` override, and offline `/status` recovery were untested.
- **Fix Applied:** Added `frontend/tests/sse.test.mjs` (`test:unit`), expanded `frontend/tests/workbench.spec.mjs` (Test 4), and added `test_router_node_honors_explicit_route_override` in `tests/test_router.py`.

---

## Checks: Secrets, Writes to Main / Production DB, and Unverified Runtime Paths

1. **Secrets in code or logs:**
   - `.env` is ignored in `.gitignore` and absent from git index and history.
   - Regex scan across `109` tracked files and `git log --all -p` found `0` API keys, tokens, or private keys.
   - Frontend never reads `GOOGLE_API_KEY`, DB URLs, or channel credentials; `/api/chat/stream` keeps `BACKEND_URL` server-side and forwards only `{ query, thread_id, route }`.
2. **Anything that can write to `main` or production database:**
   - Frontend E2E and unit tests never touch git branches or live PostgreSQL (`page.route` and `globalThis.fetch` mocks).
   - Python `tests/conftest.py` enforces `fixdesk_test` and raises `RuntimeError` if `DATABASE_URL` or `POSTGRES_DB` points to `fixdesk`.
   - `tests/test_zero_mock_guardrails.py::test_zero_rows_in_production_db_after_reset` connects read-only (`SELECT count(*)`) to `PRODUCTION_DATABASE_URL`, and `test_upload_endpoints_validation_and_flow` writes temporary files to `data/` and `docs/` and deletes them in `finally:`.
3. **Claims not verified by live execution (Environment Blocker):**
   - Docker daemon is inactive in this environment (`/var/run/docker.sock` does not exist), so PostgreSQL + pgvector on `localhost:5434` is down.
   - Consequently, the `14` DB-dependent pytest cases (Support Desk sandbox/approval/`audit_log`, live pgvector RAG, live SQL execution, DB health check, DB channel dedupe/rate-limit, and `test_zero_rows_in_production_db_after_reset`) could not pass against live Postgres here, and live PySpark / pgvector ingestion / live Slack & Email polling remain **unverified end-to-end** against a running container.
