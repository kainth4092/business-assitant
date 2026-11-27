"""
Pytest configuration for Fixdesk
Configures a dedicated test database (fixdesk_test) and enforces strict safety guards
preventing any test from writing to or reading from the production application database.
"""

import sys
import os
import psycopg2
import pytest

# Add root project directory to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Enforce test database URLs
TEST_DB_NAME = os.environ.get("TEST_POSTGRES_DB", "fixdesk_test")
TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    f"postgresql://postgres:postgres_password@localhost:5434/{TEST_DB_NAME}"
)
TEST_READONLY_URL = os.environ.get(
    "TEST_READONLY_DATABASE_URL",
    f"postgresql://sales_readonly:readonly_password@localhost:5434/{TEST_DB_NAME}"
)

# Set environment before any module loads
os.environ["POSTGRES_DB"] = TEST_DB_NAME
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["READONLY_DATABASE_URL"] = TEST_READONLY_URL

# Prevent automated pytest runs from consuming live Gemini API quota unless explicitly requested
if os.environ.get("RUN_LIVE_GEMINI_TESTS", "").strip() != "1":
    os.environ["GOOGLE_API_KEY"] = ""

# Prevent automated pytest runs from calling live GCP / BigQuery / Vertex AI unless explicitly requested
if os.environ.get("RUN_LIVE_GCP_TESTS", "").strip() != "1":
    os.environ["STORAGE_BACKEND"] = "local"
    os.environ["VECTOR_BACKEND"] = "local"
    os.environ["FILE_STORE_BACKEND"] = "local"
    os.environ["LLM_BACKEND"] = "gemini_api"
    os.environ["EMBEDDING_BACKEND"] = "gemini_api"
    os.environ["DOCUMENT_RAG_BACKEND"] = "default"
    os.environ["GCP_PROJECT_ID"] = ""
    os.environ["GCS_BUCKET"] = ""


def pytest_configure(config):
    """
    Strict Safety Guard:
    Refuses to execute tests if DATABASE_URL or POSTGRES_DB points to the production database.
    """
    current_db = os.environ.get("POSTGRES_DB", "")
    current_url = os.environ.get("DATABASE_URL", "")

    if (not current_db.endswith("_test")) or current_db in ("fixdesk", "postgres") or (f"/{TEST_DB_NAME}" not in current_url and "_test" not in current_url):
        raise RuntimeError(
            f"SAFETY GUARD TRIGGERED: Tests are attempting to run against non-test database '{current_db}' / '{current_url}'! "
            f"Tests must strictly use '{TEST_DB_NAME}'."
        )


@pytest.fixture(scope="session", autouse=True)
def ensure_test_database():
    """
    Ensures that the test database exists, has pgvector enabled,
    and has all required base tables initialized.
    """
    # Connect to PostgreSQL server to verify/create test database
    admin_url = "postgresql://postgres:postgres_password@localhost:5434/postgres"
    try:
        conn = psycopg2.connect(admin_url)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(f"SELECT 1 FROM pg_database WHERE datname = '{TEST_DB_NAME}';")
        if not cur.fetchone():
            cur.execute(f"CREATE DATABASE {TEST_DB_NAME};")
        cur.close()
        conn.close()
    except Exception as e:
        # If running in environment without port 5434 admin, warn
        pass

    # Ensure schema in test database
    try:
        init_sql_path = os.path.join(root_dir, "infra", "init.sql")
        code_rag_sql_path = os.path.join(root_dir, "infra", "code_rag_schema.sql")
        if os.path.exists(init_sql_path):
            test_conn = psycopg2.connect(TEST_DB_URL)
            test_cur = test_conn.cursor()
            with open(init_sql_path, "r", encoding="utf-8") as f:
                test_cur.execute(f.read())
            if os.path.exists(code_rag_sql_path):
                with open(code_rag_sql_path, "r", encoding="utf-8") as f:
                    test_cur.execute(f.read())
            test_conn.commit()
            test_cur.close()
            test_conn.close()
    except Exception as e:
        pass
