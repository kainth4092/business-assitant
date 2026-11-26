# Support Desk Communication Channels Setup Guide (`CHANNELS_SETUP.md`)

This guide walks step-by-step through connecting **Email (IMAP/SMTP)**, **Slack (Socket Mode)**, and **Microsoft Teams** to the Business Assistant Support Desk.

> [!IMPORTANT]
> **Security Rule**: Every secret/token goes **only** in your local `.env` file (ignored by `.gitignore`). Never commit `.env` or paste tokens into docs or source files.
> **Allowlist Rule**: External channels fail closed — only messages from allowlisted email addresses/domains or Slack channels explicitly listed in your `.env` allowlists are accepted. Everything else is ignored and logged.

---

## 1. Email (IMAP Polling + SMTP Reply)

The Email worker checks an inbox/folder every **30 seconds** for `UNSEEN` messages and replies on the same email thread via SMTP.

### Step 1: Enable IMAP in Gmail *(menu names may change across updates)*
1. Open Gmail in a desktop browser -> Click the **Gear icon (Settings)** -> **See all settings**.
2. Open the **Forwarding and POP/IMAP** tab.
3. Under **IMAP access**, select **Enable IMAP** -> click **Save Changes**. *(Note: Gmail has been phasing out the manual toggle on some accounts where IMAP is always enabled by default — if the toggle isn't visible, IMAP is already active.)*

### Step 2: Create a Dedicated Gmail Label/Folder *(Recommended)*
1. In Gmail left sidebar, scroll down and click **`+` Create new label** -> name it e.g. `Support`.
2. *(Optional)* Create a Gmail filter (`Filter messages like these`) to apply the `Support` label automatically to incoming support emails and skip Inbox if desired, OR leave `IMAP_FOLDER=INBOX`.

### Step 3: Generate a Gmail App Password
*(Regular Google account passwords are rejected by IMAP/SMTP.)*
1. Ensure **2-Step Verification** is enabled on your Google Account ([myaccount.google.com/security](https://myaccount.google.com/security)).
2. Visit **Google Account -> Security -> 2-Step Verification -> App passwords** (or search `"App passwords"` in the Google Account search bar, as Google occasionally moves this link).
3. Enter app name `Business Assistant` -> click **Create**.
4. Copy the 16-character app password (spaces optional).

### Step 4: Add to `.env`
```ini
IMAP_HOST=imap.gmail.com
IMAP_USER=your.support@gmail.com
IMAP_APP_PASSWORD=abcd_efgh_ijkl_mnop
IMAP_FOLDER=INBOX
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
EMAIL_ALLOWED_SENDERS=manager@company.com,your.personal@gmail.com
```
*(You can also allow an entire company domain using `@company.com`.)*

---

## 2. Slack App (Socket Mode — No Public URL Needed)

Slack **Socket Mode** opens an outbound WebSocket connection (`xapp-...`) to Slack, so no public webhook URL is required.

### Step 1: Create App & Enable Socket Mode
*(Slack dashboard section names may vary slightly over time.)*
1. Go to [api.slack.com/apps](https://api.slack.com/apps) -> **Create New App** -> **From scratch**.
2. Name it `Business Assistant Support`, pick your workspace, and click **Create App**.
3. In left sidebar -> **Socket Mode** -> toggle **Enable Socket Mode** ON.
4. Prompted to create an App-Level Token: name it `socket-token`, add scope **`connections:write`**, click **Generate**, and copy the **`xapp-...`** token (`SLACK_APP_TOKEN`).

### Step 2: Add Bot Token Scopes
1. Left sidebar -> **OAuth & Permissions** -> scroll to **Scopes -> Bot Token Scopes**.
2. Add these scopes:
   - `app_mentions:read` (for `@bot` mentions in channels)
   - `channels:history` (read messages in public channels)
   - `groups:history` (read messages in private channels)
   - `im:history` (read direct messages to the bot)
   - `chat:write` (send status & resolution replies in thread)
   - `users:read` (display sender names cleanly)

### Step 3: Subscribe to Events
1. Left sidebar -> **Event Subscriptions** -> toggle **Enable Events** ON.
2. Expand **Subscribe to bot events** -> **Add Bot User Event**:
   - `app_mention`
   - `message.channels`
   - `message.groups`
   - `message.im`
3. Click **Save Changes**.

### Step 4: Install App & Invite Bot
1. Left sidebar -> **Install App** -> **Install to Workspace** -> **Allow**.
2. Copy the **Bot User OAuth Token** starting with **`xoxb-...`** (`SLACK_BOT_TOKEN`).
3. In Slack, open your target channel (e.g. `#support-desk`) and send:
   ```text
   /invite @Business Assistant Support
   ```
4. Right-click the channel name -> **View channel details** -> scroll to the bottom to copy the **Channel ID** (looks like `C0123456789`).
   *(To also allow Direct Messages to the bot, include `dm` or your Slack user ID `U01234567` in `SLACK_ALLOWED_CHANNELS`.)*

### Step 5: Add to `.env`
```ini
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
SLACK_ALLOWED_CHANNELS=C0123456789,dm
```

---

## 3. Microsoft Teams (Admin Setup Only)

Microsoft Teams is provided as a stub and does **not** run automatically in local mode because Microsoft Bot Framework requires Azure Bot registration and a public HTTPS endpoint. See [TEAMS_SETUP.md](file:///home/kanish/Documents/business-assistant/docs/TEAMS_SETUP.md) for full details.

---

## 4. Starting & Checking Channels

- **Automatic with Backend**: Running `uvicorn backend.main:app --host 0.0.0.0 --port 8000` (or `make start-backend`) automatically starts every configured channel worker and skips unconfigured ones with an info log line.
- **Standalone Worker Process**: You can also run workers separately via:
  ```bash
  make channels
  ```
- **Live Status & Toggles**: Open **Support** in the web UI ([http://localhost:3000](http://localhost:3000)) to see each channel's live status (`Connected`, `Not configured`, `Paused`, or `Error`), last received message timestamp, and On/Off switches.
