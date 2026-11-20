# 3-Minute Live Demo Script: Business Assistant & Autonomous Support Desk

This script guides an engineer, product manager, or executive through a 3-minute live demonstration of the **Business Assistant** analyst workbench and its **Autonomous Support Desk with Human-in-the-Loop Remediation**.

---

## Demo Overview
- **Goal**: Demonstrate how an AI agent autonomously answers business questions using structured sales data and company policy documents, and how it safely diagnoses and resolves incoming client operational issues with human approval.
- **Estimated Duration**: 3 minutes.
- **Prerequisites**:
  - PostgreSQL container running: `docker ps` shows `business_assistant_postgres` on port 5434.
  - FastAPI backend running: `http://localhost:8000/health`.
  - Next.js frontend running: `http://localhost:3000`.

---

## Act 1: The Analyst Workbench (Minute 0:00 – 1:00)

### 1. The Workbench UI & Navigation
- **Presenter**: *"Welcome to the Business Assistant Workbench. Built like an editorial analyst workbench (Linear / Notion style), it features a warm paper aesthetic, dense information architecture, and zero generic chat bubbles."*
- **Action**: Open `http://localhost:3000` in the browser. Point out:
  1. **Left Sidebar**: Brand mark, database telemetry (`Postgres 16 Connected`, `1,500 sales rows`, `21 vector chunks`), session log, and navigation tabs.
  2. **Main Canvas**: Capabilities strip with animated count-up metrics, starter questions with route badges, and raised composer with segmented route selector (`Auto`, `Data`, `Docs`, `Both`).
  3. **Theme Toggle**: Click the theme toggle at the bottom of the sidebar to show the dark carbon theme and warm paper theme.

### 2. Autonomous Routing & Grounded Evidence
- **Presenter**: *"Let's ask a complex question: 'What were the total sales across Tier 1 outlets, and what is our return policy for opened items?'"*
- **Action**: Click the starter card tagged **`BOTH`** or type the question into the composer and press `Enter`.
- **Result**:
  - The status ticker shows: `Router -> Classifying intent...` -> `Agent -> Invoking tools...` -> `Check -> Groundedness evaluation`.
  - The answer renders with prose explanations and citation chips `[1]`, `[2]`.
  - The **Evidence Panel** slides open on the right showing:
    - **Route Chosen**: `BOTH` (colored indigo).
    - **Trace**: Node execution timeline.
    - **SQL Tab**: The sanitized `SELECT` query executed on PostgreSQL with execution time.
    - **Results Tab**: Clean tabular results returned by the database.
    - **Sources Tab**: The retrieved chunks from `return_policy.md` with cosine similarity scores.

---

## Act 2: Client Problem Ingestion & Autonomous Triage (Minute 1:00 – 2:00)

### 3. Client Issues from External Channels
- **Presenter**: *"Now let's switch to the Support Desk tab. In enterprise operations, clients submit problem reports via Webhook, Slack, or MS Teams. Let's see how our agent processes them."*
- **Action**: Click **Support Desk** in the left sidebar.
- **Presenter**: *"Notice the simulator strip at the top. It lets us dispatch real webhook payloads or simulate messages from Slack and Teams channels."*

### 4. Simulating a Data Fragmentation Incident
- **Presenter**: *"Let's simulate a client reporting inconsistent category labels in their sales reporting."*
- **Action**: Click the preset button: **`[SLACK] Data Issue: Inconsistent Fat Labels`** (`"In the sales reports, LF and Low Fat are showing up as separate categories. Can you merge them?"`).
- **Result**:
  - The agent triggers the LangGraph `support_graph`.
  - Within 2 seconds, a new ticket appears in the backlog and is automatically selected.
  - **Classification**: Autonomous classifier detects `data_issue` with `98.0%` confidence.
  - **Execution Chain**:
    - `1. CLASSIFY`: `data_issue` (Green checkmark)
    - `2. INVESTIGATE`: Diagnosed `LF`, `low fat`, and `reg` anomalies.
    - `3. TEST (SANDBOX)`: Proposed SQL fix is executed in the isolated `sales_sandbox` table.
    - `4. APPROVAL`: Paused! State is safely persisted in checkpointer.

---

## Act 3: Isolated Sandbox Verification & Human Authorization (Minute 2:00 – 3:00)

### 5. Inspecting the Sandbox Diff
- **Presenter**: *"Here is our core enterprise safety feature: The agent prepared the fix, but production `sales` is completely untouched. It executed the proposed update strictly in an isolated sandbox clone."*
- **Action**: Point to the **Isolated Sandbox Verification** table:
  - **Before Fix**: `LF`: 2 records, `low fat`: 1 record, `Low Fat`: 910 records.
  - **After Fix**: `Low Fat`: 913 records (`LF` and `low fat` cleanly standardized to `0`).
  - **Proposed SQL**: Highlight the syntax block:
    ```sql
    UPDATE sales_sandbox SET Item_Fat_Content = 'Low Fat' WHERE Item_Fat_Content IN ('LF', 'low fat');
    ```

### 6. Authorize & Apply (Human-in-the-Loop)
- **Presenter**: *"Safety rule: An autonomous agent must never alter production without explicit human sign-off. An approval token is required."*
- **Action**:
  1. Click the green **`Authorize & Apply Fix`** button.
  2. The confirmation prompt asks for operator verification. Type `Senior Operations Admin` (or keep default).
  3. Click **`Confirm & Apply`**.
- **Result**:
  - The approval token is verified by `/support/tickets/{id}/approve`.
  - The fix is applied to production `sales`.
  - The ticket badge turns green: `DONE`.
  - **Client Resolution Notice** displays the drafted message sent back to the client's Slack channel.
  - **Immutable Audit Log** records the action:
    `APPLY_FIX | Senior Operations Admin | 2026-11-20 10:45:12 | Standardized 3 records`.

### 7. Code Bug Remediation (Optional 30-Second Bonus)
- **Presenter**: *"The exact same pattern works for code bugs in business logic. Let's click the Teams Code Bug scenario."*
- **Action**: Click **`[TEAMS] Code Bug: Inverted Discount Calculation`**.
- **Result**:
  - Agent classifies as `code_bug` (96% confidence).
  - Generates a **Unified Diff Patch** (`+ discount_amount` -> `- discount_amount`).
  - Demonstrates automated test execution (`tests/test_demo_target.py` failing before patch, passing after patch).
  - Pauses for approval before saving the draft patch.

---

## Demo Wrap-Up & Value Proposition
- **Key Takeaways**:
  1. **Dual Data + RAG Intelligence**: Answers queries by uniting structured SQL data and unstructured documents.
  2. **Autonomous Diagnosis**: Classifies and troubleshoots client problems without manual triage overhead.
  3. **Zero Risk Remediation**: Sandboxed dry runs, max 2 retry cap, restricted SQL, and mandatory human authorization.
  4. **Complete Traceability**: Cryptographic approval tokens and immutable audit trail.
