# Microsoft Teams Integration Requirements (`TEAMS_SETUP.md`)

Microsoft Teams is intentionally implemented as a **stub (`TeamsAdapterStub`)** in [teams.py](backend/support/channels/teams.py) because Microsoft Bot Framework does **not** support outbound-only Socket Mode or simple long polling from a local laptop without cloud registration.

If your organization wants live Microsoft Teams support later, a Microsoft 365 / Azure tenant administrator must provision the following components:

---

## 1. Azure Bot Registration
1. Open the **Azure Portal** -> **Create a resource** -> **Azure Bot** (menu labels may vary slightly across Azure updates).
2. Choose **Multi-tenant** or **Single-tenant** bot type (Microsoft has increasingly restricted new multi-tenant bots in favor of Single-tenant or User-Assigned Managed Identity).
3. Copy the generated **Microsoft App ID** and create a **Client Secret** under *Manage -> Certificates & secrets* (or Microsoft Entra ID App Registrations).

---

## 2. Public HTTPS Messaging Endpoint
Unlike Slack (Socket Mode), which opens an outbound connection directly from your machine, Teams **pushes** HTTP `POST` webhook activities to your server:
1. Expose the FastAPI backend over a **public HTTPS endpoint** with a valid TLS certificate (e.g., via Cloud Run, AWS ALB, Azure App Service, or a reverse tunnel during development).
2. Set the Bot's **Messaging endpoint** in Azure Bot -> *Configuration* to:
   ```text
   https://<your-public-domain>/api/teams/messages
   ```
3. Verify inbound JWT Bearer tokens signed by `https://login.botframework.com` / `https://login.microsoftonline.com` before parsing payloads.

---

## 3. Teams App Manifest & Tenant Permissions
1. Enable the **Microsoft Teams** channel inside Azure Bot -> *Channels*.
2. Package a Teams App Manifest (`manifest.json`) listing the Bot ID and required scopes (`personal`, `team`, `groupChat`).
3. Have a Teams Admin upload/approve the custom app in the **Microsoft Teams Admin Center** (*Teams apps -> Manage apps*).
4. Record the Bot Framework **App ID**, **App Password / Secret**, and **Allowed Tenant / Team / Channel IDs** securely in `.env` (never in git).

---

## 4. Security Notes
- Never bypass JWT signature verification on an inbound Teams endpoint.
- Keep the Support Desk **Human-in-the-Loop approval gate** exclusively in the authenticated Web UI — do not wire Teams Adaptive Card action callbacks to approve production SQL or code changes without separate RBAC verification.
