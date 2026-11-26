# System Readiness & User Action Items (`BLOCKED.md`)

## Core Platform Status: Operational & Verified

- **PostgreSQL + pgvector (`business_assistant`)**, **FastAPI Backend (`:8000`)**, **Next.js Frontend (`:3000`)**, **PySpark Universal Pipeline**, **Gemini 3.5 Flash Lite + Gemini Embedding 2 (768-D)**, and **Support Desk Channels Architecture** are implemented and tested (offline/fake payloads in pytest).

---

## Blocked / Pending User Configuration for Live External Support Channels

Real channel listeners are implemented and ready to start automatically with the backend (or via `make channels`), **but cannot connect to live external services yet because credentials are not configured in `.env`**:

| Channel | Current UI Status | Missing `.env` Credentials / Action Needed | Setup Guide |
| :--- | :--- | :--- | :--- |
| **Email (IMAP/SMTP)** | `Not configured` | Set `IMAP_HOST`, `IMAP_USER`, `IMAP_APP_PASSWORD` (Gmail App Password), `SMTP_HOST`, `SMTP_PORT`, and `EMAIL_ALLOWED_SENDERS` in `.env` | [docs/CHANNELS_SETUP.md](file:///home/kanish/Documents/business-assistant/docs/CHANNELS_SETUP.md) |
| **Slack (Socket Mode)** | `Not configured` | Set `SLACK_BOT_TOKEN` (`xoxb-...`), `SLACK_APP_TOKEN` (`xapp-...`), and `SLACK_ALLOWED_CHANNELS` in `.env` | [docs/CHANNELS_SETUP.md](file:///home/kanish/Documents/business-assistant/docs/CHANNELS_SETUP.md) |
| **Microsoft Teams** | `Not configured` (Stub) | Requires Microsoft 365 / Azure tenant admin to register an Azure Bot, approve Entra ID permissions, and provide a public HTTPS messaging endpoint | [docs/TEAMS_SETUP.md](file:///home/kanish/Documents/business-assistant/docs/TEAMS_SETUP.md) |

---

## Optional Gemini API Key Note

- `.env` already contains an active `GOOGLE_API_KEY` configured with `LLM_MODEL=gemini-3.5-flash-lite` and `EMBEDDING_MODEL=gemini-embedding-2`.
- Keep `.env` strictly untracked (ignored by `.gitignore`) so credentials are never committed to Git.
