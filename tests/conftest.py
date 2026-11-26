"""
Pytest configuration for Business Assistant
Configures a dedicated test database (business_assistant_test) and enforces strict safety guards
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
TEST_DB_NAME = os.environ.get("TEST_POSTGRES_DB", "business_assistant_test")
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


def pytest_configure(config):
    """
    Strict Safety Guard:
    Refuses to execute tests if DATABASE_URL or POSTGRES_DB points to the production database.
    """
    current_db = os.environ.get("POSTGRES_DB", "")
    current_url = os.environ.get("DATABASE_URL", "")

    if "business_assistant" in current_url and not "business_assistant_test" in current_url:
        raise RuntimeError(
            f"SAFETY GUARD TRIGGERED: Tests are attempting to run against production database '{current_url}'! "
            f"Tests must strictly use '{TEST_DB_NAME}'."
        )

    if current_db == "business_assistant":
        raise RuntimeError(
            f"SAFETY GUARD TRIGGERED: POSTGRES_DB is set to '{current_db}'! "
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
        if os.path.exists(init_sql_path):
            test_conn = psycopg2.connect(TEST_DB_URL)
            test_cur = test_conn.cursor()
            with open(init_sql_path, "r", encoding="utf-8") as f:
                sql_content = f.read()
            test_cur.execute(sql_content)
            test_conn.commit()
            test_cur.close()
            test_conn.close()
    except Exception as e:
        pass
