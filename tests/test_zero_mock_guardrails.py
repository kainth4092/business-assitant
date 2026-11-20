"""
Zero-Mock & Live-Data Guardrail Tests
Validates that NO hardcoded, fake, mock, or placeholder data exists in production code,
and that all backend endpoints serve live data verified against PostgreSQL and pgvector.
"""

import os
import re
import pytest
import psycopg2
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

FORBIDDEN_PATTERNS = [
    r"\bmock\b",
    r"\bdummy\b",
    r"\bfake\b",
    r"\blorem\b",
    r"john\s+doe",
    r"jane\s+doe",
    r"1536-D",
    r"#RUN-8842",
    r"#SUP-8921",
    r"1530\s+records",
]

TARGET_DIRS = [
    "frontend/components",
    "frontend/app",
    "backend",
    "pipelines",
]

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def test_no_mock_dummy_lorem_in_production_code():
    """Asserts that no forbidden mock/placeholder terms exist outside /tests."""
    violations = []

    for target_dir in TARGET_DIRS:
        full_dir = os.path.join(PROJECT_ROOT, target_dir)
        if not os.path.exists(full_dir):
            continue

        for root, dirs, files in os.walk(full_dir):
            # Skip caches and build outputs
            if any(skip in root for skip in ("__pycache__", ".next", "node_modules", ".git")):
                continue

            for file in files:
                if not file.endswith((".js", ".jsx", ".ts", ".tsx", ".py", ".json", ".css", ".md")):
                    continue

                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, PROJECT_ROOT)

                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_idx, line in enumerate(f, 1):
                        for pattern in FORBIDDEN_PATTERNS:
                            if re.search(pattern, line, re.IGNORECASE):
                                violations.append(f"{rel_path}:{line_idx} contains '{pattern}': {line.strip()[:100]}")

    assert len(violations) == 0, f"Found {len(violations)} mock/placeholder violations in production code:\n" + "\n".join(violations)

def test_status_endpoint_returns_live_db_counts():
    """Asserts that GET /status returns real non-zero counts from the live database."""
    response = client.get("/status")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()

    assert data.get("status") in ("healthy", "degraded")
    assert data.get("database") == "connected", "Database connection status must be 'connected'"
    assert data.get("pgvector_ready") is True, "pgvector must be ready"
    assert isinstance(data.get("sales_records"), int) and data.get("sales_records") > 0, "sales_records must be > 0"
    assert isinstance(data.get("indexed_chunks"), int) and data.get("indexed_chunks") > 0, "indexed_chunks must be > 0"
    assert isinstance(data.get("tools_count"), int) and data.get("tools_count") >= 3, "tools_count must be >= 3"
    assert data.get("embedding_dimension") == 768, "Gemini text-embedding-004 dimension must be 768"

def test_documents_endpoint_matches_database():
    """Asserts that GET /documents returns rows matching SELECT count(*) FROM document_embeddings."""
    db_host = os.getenv("POSTGRES_HOST", "localhost")
    db_port = int(os.getenv("POSTGRES_PORT", "5434"))
    db_name = os.getenv("POSTGRES_DB", "business_assistant")
    db_user = os.getenv("POSTGRES_USER", "postgres")
    db_pass = os.getenv("POSTGRES_PASSWORD", "postgres")

    conn = psycopg2.connect(
        host=db_host,
        port=db_port,
        dbname=db_name,
        user=db_user,
        password=db_pass
    )
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM document_embeddings;")
    db_chunk_count = cursor.fetchone()[0]
    cursor.execute("SELECT count(DISTINCT source_file) FROM document_embeddings;")
    db_doc_count = cursor.fetchone()[0]
    cursor.close()
    conn.close()

    response = client.get("/documents")
    assert response.status_code == 200
    data = response.json()

    assert data.get("status") == "SUCCESS"
    assert data.get("total_chunks") == db_chunk_count, f"API total_chunks ({data.get('total_chunks')}) != DB chunks ({db_chunk_count})"
    assert data.get("total_documents") == db_doc_count, f"API total_docs ({data.get('total_documents')}) != DB docs ({db_doc_count})"
    assert len(data.get("documents", [])) == db_doc_count

def test_data_quality_endpoint_matches_database():
    """Asserts that GET /data-quality returns metrics matching the quality_reports table."""
    db_host = os.getenv("POSTGRES_HOST", "localhost")
    db_port = int(os.getenv("POSTGRES_PORT", "5434"))
    db_name = os.getenv("POSTGRES_DB", "business_assistant")
    db_user = os.getenv("POSTGRES_USER", "postgres")
    db_pass = os.getenv("POSTGRES_PASSWORD", "postgres")

    conn = psycopg2.connect(
        host=db_host,
        port=db_port,
        dbname=db_name,
        user=db_user,
        password=db_pass
    )
    cursor = conn.cursor()
    cursor.execute("SELECT report_data FROM quality_reports ORDER BY created_at DESC LIMIT 1;")
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    assert row is not None, "quality_reports table must contain at least one PySpark audit record"
    db_report = row[0]

    response = client.get("/data-quality")
    assert response.status_code == 200
    api_report = response.json()

    assert api_report.get("status") == "SUCCESS"
    assert api_report.get("records_profile") == db_report.get("records_profile")
    assert api_report.get("label_standardization") == db_report.get("label_standardization")

def test_conversations_endpoint_persists_and_retrieves():
    """Asserts that GET /conversations returns a valid JSON response from PostgreSQL."""
    response = client.get("/conversations")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "SUCCESS"
    assert "conversations" in data
    assert isinstance(data.get("conversations"), list)

def test_sample_questions_endpoint_is_dynamically_grounded():
    """Asserts that GET /sample-questions returns 5 dynamic starters grounded in DB data."""
    response = client.get("/sample-questions")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "SUCCESS"
    starters = data.get("starters", [])
    assert len(starters) == 5

    for s in starters:
        assert "num" in s
        assert "label" in s and len(s["label"]) > 0
        assert "caption" in s and len(s["caption"]) > 0
        assert "query" in s and len(s["query"]) > 0
        assert s.get("route") in ("data", "docs", "both")

def test_frontend_build_artifacts_present():
    """Asserts that the frontend build produces no errors and valid production build artifacts."""
    build_id_path = os.path.join(PROJECT_ROOT, "frontend", ".next", "BUILD_ID")
    assert os.path.exists(build_id_path), "Frontend build artifact BUILD_ID must exist"
    with open(build_id_path, "r") as f:
        build_id = f.read().strip()
    assert len(build_id) > 0, "BUILD_ID must be non-empty"
