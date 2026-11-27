#!/usr/bin/env bash
# ==============================================================================
# Fixdesk - Automated Environment & Pipeline Setup Script
# ==============================================================================
# Idempotent setup script that prepares the database, executes the PySpark
# cleaning pipeline, and ingests vectorized policy documents.
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

echo "========================================================================"
echo "                Starting Fixdesk Automated Setup                         "
echo "========================================================================"

# 1. Check Python virtual environment
if [ -d ".venv" ]; then
    PYTHON_BIN=".venv/bin/python3"
else
    PYTHON_BIN="python3"
fi

# 2. Check Java installation for PySpark
if [ -z "${JAVA_HOME}" ]; then
    if [ -d "/usr/lib/jvm/java-21-openjdk-amd64" ]; then
        export JAVA_HOME="/usr/lib/jvm/java-21-openjdk-amd64"
    elif [ -d "/usr/lib/jvm/java-17-openjdk-amd64" ]; then
        export JAVA_HOME="/usr/lib/jvm/java-17-openjdk-amd64"
    else
        echo "Warning: JAVA_HOME is not set. PySpark will use system default java."
    fi
fi
echo "[1/6] Configured JAVA_HOME: ${JAVA_HOME:-system default}"

# 3. Ensure .env exists
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "[2/6] Creating .env from .env.example..."
        cp .env.example .env
    else
        echo "Error: .env.example not found!"
        exit 1
    fi
else
    echo "[2/6] .env configuration file exists."
fi

# 4. Check or start PostgreSQL container
echo "[3/6] Checking PostgreSQL database services..."
if command -v docker &> /dev/null && docker info &> /dev/null; then
    if [ -f "infra/docker-compose.yml" ]; then
        docker compose -f infra/docker-compose.yml up -d 2>/dev/null || docker-compose -f infra/docker-compose.yml up -d 2>/dev/null || true
    fi
fi

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL database connection..."
${PYTHON_BIN} -c "
import os, sys, time, psycopg2
from dotenv import load_dotenv
load_dotenv()
db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres_password@localhost:5434/fixdesk')
max_retries = 20
for attempt in range(max_retries):
    try:
        conn = psycopg2.connect(db_url)
        conn.close()
        print('PostgreSQL is ready and accepting connections.')
        sys.exit(0)
    except Exception as e:
        time.sleep(1)
print('Warning: PostgreSQL not ready yet. Please ensure Docker container is running.')
" || true

# 5. Apply database schemas
echo "[4/6] Applying database schema (init.sql & support_schema.sql)..."
${PYTHON_BIN} -c "
import os, psycopg2
from dotenv import load_dotenv
load_dotenv()
db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres_password@localhost:5434/fixdesk')
conn = psycopg2.connect(db_url)
conn.autocommit = True
cur = conn.cursor()

if os.path.exists('infra/init.sql'):
    with open('infra/init.sql') as f:
        cur.execute(f.read())

if os.path.exists('infra/support_schema.sql'):
    with open('infra/support_schema.sql') as f:
        cur.execute(f.read())

cur.close()
conn.close()
print('Database schemas initialized successfully.')
"

# 6. Run PySpark ETL Pipeline
echo "[5/6] Executing PySpark Sales Cleaning & Quality Audit Pipeline..."
${PYTHON_BIN} pipelines/clean_sales.py

# 7. Run Document Vector Ingestion
echo "[6/6] Executing Document Vector Ingestion into pgvector..."
${PYTHON_BIN} pipelines/ingest_docs.py

echo "========================================================================"
echo " Fixdesk setup complete! Real data is loaded and ready.                  "
echo " Start backend:  .venv/bin/python3 -m uvicorn backend.main:app --port 8000"
echo " Start frontend: cd frontend && npm run dev (or npm run start)"
echo " Open:           http://localhost:3000"
echo "========================================================================"
