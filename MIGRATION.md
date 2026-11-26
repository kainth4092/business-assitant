# Rename Migration Guide: Upgrading to `Fixdesk` (`MIGRATION.md`)

This project was renamed to **Fixdesk** (`fixdesk`). Fresh installations use the new identifiers (`fixdesk` database, `fixdesk_test` test database, `fixdesk_pgdata` Docker volume, `fixdesk_network` Docker network, and `fixdesk` project slug).

---

## 1. Existing Local Setups (Database & Environment)

Because renaming a live PostgreSQL database, Docker volume, or `.env` silently can orphan existing tables or cause unexpected data loss, two safe paths are supported:

### Option A: Keep Your Existing Database Without Touching Data (Zero Downtime)
All runtime services read `POSTGRES_DB`, `DATABASE_URL`, and `READONLY_DATABASE_URL` from `.env`. You can run the renamed **Fixdesk** code immediately against an existing database by keeping those values in `.env`:

```env
POSTGRES_DB=business_assistant
DATABASE_URL=postgresql://postgres:postgres_password@localhost:5434/business_assistant
READONLY_DATABASE_URL=postgresql://sales_readonly:readonly_password@localhost:5434/business_assistant
```

*(Note: When running `pytest`, `tests/conftest.py` automatically overrides env vars in memory to use `fixdesk_test` so your existing database stays untouched.)*

### Option B: Migrate to Clean `fixdesk` Database & Volumes
If you want a fresh stack matching the new names cleanly:

```bash
# 1. Stop old containers & optionally remove legacy volumes
docker compose -f infra/docker-compose.yml down -v

# 2. Update .env from .env.example (back up any custom API keys/channel tokens first!)
cp .env.example .env

# 3. Recreate containers, schema, pipelines, and vector indexes using the Fixdesk setup
bash scripts/setup.sh

# 4. Re-index your codebase into code_rag under the new 'fixdesk' project slug
./.venv/bin/project-init index fixdesk
```

---

## 2. Manual Steps Outside Git Repository Scope

The following items live outside source-controlled files or require interactive confirmation and were **intentionally left untouched**:

1. **Local Project Folder Rename** (wait until shutting down active servers/IDEs in this directory):
   ```bash
   cd ..
   mv business-assistant fixdesk
   cd fixdesk
   ```
   *(If moving an existing `.venv`, recreate `.venv` or update the shebang inside `.venv/bin/project-init` so Python virtualenv paths point to the new folder.)*

2. **GitHub / Git Remote Repository Name**:
   - Rename the repository on GitHub/GitLab (`Settings -> Repository name -> fixdesk`), then update your local git remote:
     ```bash
     git remote set-url origin https://github.com/<your-org>/fixdesk.git
     ```

3. **Slack & Chat Bot Display Names**:
   - In the Slack App Dashboard (**App Manifest / Basic Information**), update the App Name and Bot Display Name to `Fixdesk` (or `Fixdesk Support`), and update channel greetings if applicable.
   - If you run any external webhook client or Microsoft Teams Azure Bot registration, update its display name to `Fixdesk Support`.

4. **Cloud Infrastructure Resources (GCP / AWS)**:
   - See updated commands in [infra/DEPLOY_GCP.md](infra/DEPLOY_GCP.md) and [infra/DEPLOY_AWS.md](infra/DEPLOY_AWS.md) (`fixdesk-db`, `fixdesk-backend`, `fixdesk-frontend`, S3/GCS bucket names, Cloud Run/ECS services). Existing deployed cloud resources must either keep their legacy resource names in CI/CD env vars or be provisioned cleanly under the `fixdesk-*` names.
