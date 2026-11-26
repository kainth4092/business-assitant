# 5-Minute Live Manager Demo Script (DEMO_SCRIPT.md)

Follow this step-by-step presentation script to demonstrate the **Fixdesk** to your manager and seniors. It is designed to run in exactly 5 minutes with one line to speak per action.

---

## Pre-Demo Checklist (Do 2 Minutes Before Your Meeting)
1. Terminal 1: Run `docker ps` &rarr; verify `fixdesk_postgres` is running on port 5434.
2. Terminal 2: Run `.venv/bin/python -m uvicorn backend.main:app --port 8000`.
3. Terminal 3: Run `cd frontend && npm run dev`.
4. Browser: Open **`http://localhost:3000`** in Google Chrome or Firefox (Maximize the window).

---

## 5-Minute Presentation Flow

### Minute 1: The Workbench & Live Telemetry (0:00 – 1:00)
- **What to open**: Browser at `http://localhost:3000` on the **Analysis** tab.
- **What to say**: *"Today I am demonstrating the Fixdesk, an autonomous analytics engine that unifies structured SQL numbers and unstructured policy documents into a verified, single source of truth."*
- **What to show**:
  1. Point to the top header: Point out the green **`AGENT READY`** indicator and live database records badge.
  2. Point to the central cards: Show the dynamic telemetry deck (**Cleaned Sales Rows**, **Vector Policy Chunks**, **Active MCP Tools**).
  3. Point to the left utility rail (72px): Show the clean editorial navigation tabs (**Analysis**, **Quality**, **Docs**, **Support**).

---

### Minute 2: Act 1 — The Data Route (SQL Analytics) (1:00 – 2:00)
- **What to do**: Click the route selector pill **`Data`** (or leave on `Auto`). In the chat composer, type:
  > *"What are the top 5 item types by total sales?"*
  and press `Enter`.
- **What to say**: *"First, let's ask a pure data question. The agent autonomously translates my natural language into sanitized SQL without any manual query writing."*
- **What to point out in the Evidence Panel (opens automatically on the right)**:
  1. **Route Badge**: Shows **`DATA (SQL)`** in teal.
  2. **SQL Tab**: Show the exact generated query:
     ```sql
     SELECT item_type, SUM(item_outlet_sales) FROM sales GROUP BY item_type ORDER BY sum DESC LIMIT 5
     ```
  3. **Results Tab**: Point to the zebra-striped table showing top categories like *Fruits and Vegetables* and *Snack Foods*.

---

### Minute 3: Act 2 — The Document Route (Semantic RAG) (2:00 – 3:00)
- **What to do**: Click the route selector pill **`Docs`**. Type:
  > *"What is the return window and policy for perishable items?"*
  and press `Enter`.
- **What to say**: *"Now let's ask about operational policies. The assistant doesn't guess or hallucinate; it performs cosine similarity search across our pgvector document store."*
- **What to point out**:
  1. **Prose Answer**: The answer directly quotes the policy (e.g. *"Perishable goods must be returned within 48 hours..."*).
  2. **Citation Pill `[1]`**: Click the interactive teal `[1]` badge in the answer.
  3. **Sources Tab in Evidence Panel**: Show the retrieved section from `return_policy.md` and highlight the **89% Cosine Similarity** match score.

---

### Minute 4: Act 3 — The Hybrid Route & Groundedness (3:00 – 4:00)
- **What to do**: Click the route selector pill **`Both`**. Type:
  > *"What were total sales for Frozen Foods, and what return rules apply to frozen goods?"*
  and press `Enter`.
- **What to say**: *"Here is where agentic AI shines: a hybrid question where the agent queries the SQL database for real numbers AND vector search for operational rules, combining both into a single verified answer."*
- **What to point out**:
  1. **Answer**: Show that the response has both the dollar revenue ($1.82M) and the 48-hour return rule.
  2. **Trace Tab**: Click the `Trace` tab in the Evidence Panel to show the LangGraph execution chain:
     - `Router` (classified as `both`) &rarr; `Agent` (invoked 2 tools) &rarr; `Answer` &rarr; `Check` (verified factually grounded, 0 retries needed).

---

### Minute 5: Act 4 — Autonomous Support Desk with Human-in-the-Loop (4:00 – 4:30)
- **What to do**: Click **Support** in the left sidebar. Click **"Simulate Client"**. Type:
  > *"In our sales report, some categories have inconsistent casing. Please fix it."*
  and click **Send Ticket**.
- **What to say**: *"In enterprise systems, clients report bugs. Here, an autonomous support agent investigates the problem, drafts a fix, and tests it in an isolated sandbox table. Notice that production is locked until a human signs off."*
- **What to point out**:
  1. **7-Step Tracker**: Classify &rarr; Investigate &rarr; Propose &rarr; Test &rarr; Await Approval.
  2. **Human-In-The-Loop Approval Strip**: Point out the **`Authorize & Apply Fix`** button with the cryptographic audit token.
  3. Click **"Authorize & Apply Fix"** and confirm. Show that the ticket changes to `DONE` and an entry is logged in the immutable audit trail.

---

### The 30-Second Closing Line (4:30 – 5:00)
> *"To summarize: This architecture replaces brittle dashboards with an autonomous analyst. It enforces read-only SQL safety, eliminates hallucinations through pgvector RAG and verification check steps, and safely remediates production issues using isolated sandboxes and mandatory human-in-the-loop approval gates. Thank you, I'd be happy to take your questions."*

---

## 2-Minute Bonus: Live Channel Demo (Phone to Support Desk & Back)

Use this 2-minute live demo when at least one channel (such as **Slack** or **Email**) is configured in `.env` and showing **`Connected`** in the Support Desk **Communication Channels** panel:

1. **Pre-Check (0:00 – 0:20)**:
   - Open [http://localhost:3000](http://localhost:3000) -> click **Support** in the left sidebar.
   - Show the **Communication Channels** panel at the top confirming **Slack** (or **Email (IMAP/SMTP)**) is **`Connected`**.
2. **Send Message from Your Phone (0:20 – 0:45)**:
   - Open Slack (invited channel/DM) or your Email app on your phone and send:
     > *"Platform category values have inconsistent casing in our sales report. Please standardize them."*
   - **What happens immediately**: Your phone receives a short confirmation reply:
     `"Ticket #tick_... created. Investigating your request now..."`
3. **Watch Live Triage & Sandbox Preview (0:45 – 1:15)**:
   - Within a few seconds, the ticket card automatically appears in the **Support Backlog** with its **Slack** (or **Email**) icon badge, your real sender name, and the **`APPROVAL`** status pill.
   - Your phone receives a second update on the same thread:
     `"Ticket #tick_...: ... Proposed fix passed sandbox testing and is ready, waiting for approval in the Support Desk UI."`
4. **Review & Approve in Web UI (1:15 – 1:45)**:
   - Click the ticket in Support Desk to show the root-cause investigation, proposed SQL patch, sandbox test results, and audit token.
   - Explain: *"Notice that the client cannot approve changes over chat—only an operator in the Support Desk UI can unlock the approval gate."*
   - Click **`APPROVE & APPLY REMEDIATION`**.
5. **See Confirmation Arrive Back on Your Phone (1:45 – 2:00)**:
   - Status turns green **`APPLIED`**, and within 1–2 seconds your phone chat thread receives the final resolution reply:
     `"Ticket #tick_...: Fix approved by operator and applied successfully."`

---

## If Something Fails During the Demo (Quick Fixes)

| Symptom | Cause | 10-Second Quick Fix |
| :--- | :--- | :--- |
| **Browser shows `Failed to fetch` error banner** | The FastAPI backend terminal stopped or crashed. | Open Terminal 2 and restart it: `.venv/bin/python -m uvicorn backend.main:app --port 8000`. Refresh the browser (`Ctrl+R`). |
| **Evidence Panel doesn't open** | Panel was closed manually or screen is narrow. | Click the **`Evidence`** button in the top right header. |
| **Starters say *"No questions generated"*** | Database was reset and CSV was not loaded. | Open another terminal and run `.venv/bin/python pipelines/clean_sales.py`. Refresh browser. |
| **Gemini takes longer than 5 seconds** | Rate limit on free Google API tier. | Don't panic: explain to your manager: *"The agent has an intelligent timeout and deterministic fallback that returns the exact answer even if Google's external API is delayed."* |
| **Port 8000 already in use** | A previous uvicorn process is still running. | Run `fuser -k 8000/tcp` to kill it, then rerun the uvicorn start command. |
