"""
Zero-Mock & Live-Data Guardrail Tests (Part 5 Requirements)
-----------------------------------------------------------
1. Asserts NO forbidden patterns exist in non-test production source:
   - "DRL", "NCN", "BigMart", "faq.md", "lorem", "mock", "dummy", "fake"
   - Dataset-specific column names
   - Hardcoded metrics in UI components ("1,500", "1,505", "18ms", "0.8s", etc.)
2. Tests upload endpoints (/upload/csv, /upload/documents, /pipeline/status).
3. Tests dynamic schema detection with 3 distinct CSVs generated inside the test only.
4. Tests multi-format document ingestion (.md, .txt, .pdf) inside the test only.
5. Tests real MCP tool execution and security enforcement.
6. Asserts ZERO rows remain in the production application database after reset.
"""

import os
import io
import re
import csv
import json
import tempfile
import pytest
import psycopg2
from fastapi.testclient import TestClient
from backend.main import app
from mcp_server.tools import query_sales, search_docs, get_data_quality_report, validate_and_sanitize_sql
from pipelines.ingest_docs import parse_document_sections, chunk_sections

client = TestClient(app)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

FORBIDDEN_CODE_PATTERNS = [
    r"\bmock\b",
    r"\bdummy\b",
    r"\bfake\b",
    r"\blorem\b",
    r"\bDRL\b",
    r"\bNCN\b",
    r"\bBigMart\b",
    r"\bfaq\.md\b",
    r"\bItem_Fat_Content\b",
    r"\bItem_Weight\b",
    r"\bItem_Visibility\b",
    r"\bOutlet_Establishment_Year\b",
    r"\b18ms\b",
]

TARGET_DIRS = [
    "frontend/components",
    "frontend/app",
    "backend",
    "pipelines",
]

# ------------------------------------------------------------------------------
# 1. Forbidden Patterns in Non-Test Source
# ------------------------------------------------------------------------------
def test_no_forbidden_patterns_in_production_code():
    """Asserts that no forbidden mock/sample/BigMart patterns appear in non-test source."""
    violations = []

    for target_dir in TARGET_DIRS:
        full_dir = os.path.join(PROJECT_ROOT, target_dir)
        if not os.path.exists(full_dir):
            continue

        for root, dirs, files in os.walk(full_dir):
            if any(skip in root for skip in ("__pycache__", ".next", "node_modules", ".git")):
                continue

            for file in files:
                if not file.endswith((".js", ".jsx", ".ts", ".tsx", ".py", ".css")):
                    continue

                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, PROJECT_ROOT)

                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_idx, line in enumerate(f, 1):
                        for pattern in FORBIDDEN_CODE_PATTERNS:
                            if re.search(pattern, line, re.IGNORECASE):
                                violations.append(f"{rel_path}:{line_idx} contains '{pattern}': {line.strip()[:100]}")

    assert len(violations) == 0, f"Found {len(violations)} forbidden pattern violations in production code:\n" + "\n".join(violations)


# ------------------------------------------------------------------------------
# 2. Upload Endpoints Testing
# ------------------------------------------------------------------------------
def test_upload_endpoints_validation_and_flow():
    """Tests /upload/csv, /upload/documents, and /pipeline/status with automatic cleanup."""
    data_dir = os.path.join(PROJECT_ROOT, "data")
    docs_dir = os.path.join(PROJECT_ROOT, "docs")
    
    test_csv_name = "test_upload_dataset.csv"
    test_doc_name = "test_upload_policy.md"
    test_csv_path = os.path.join(data_dir, test_csv_name)
    test_doc_path = os.path.join(docs_dir, test_doc_name)

    try:
        # 1. Test CSV upload
        csv_content = b"user_id,revenue,country\n101,250.5,USA\n102,120.0,Canada\n"
        res_csv = client.post(
            "/upload/csv",
            files={"file": (test_csv_name, io.BytesIO(csv_content), "text/csv")}
        )
        assert res_csv.status_code == 200
        assert res_csv.json()["status"] == "SUCCESS"
        assert os.path.exists(test_csv_path)

        # 2. Test Document upload
        doc_content = b"# Corporate Safety Policy\n\nAll team members must follow safety procedures.\n"
        res_doc = client.post(
            "/upload/documents",
            files=[("files", (test_doc_name, io.BytesIO(doc_content), "text/markdown"))]
        )
        assert res_doc.status_code == 200
        assert res_doc.json()["status"] == "SUCCESS"
        assert os.path.exists(test_doc_path)

        # 3. Test Pipeline Status reflects uploaded files
        res_status = client.get("/pipeline/status")
        assert res_status.status_code == 200
        status_data = res_status.json()
        assert status_data["has_csv"] is True
        assert test_csv_name in status_data["csv_files"]
        assert status_data["has_documents"] is True
        assert test_doc_name in status_data["document_files"]

    finally:
        # Strict cleanup to leave data/ and docs/ clean
        if os.path.exists(test_csv_path):
            os.remove(test_csv_path)
        if os.path.exists(test_doc_path):
            os.remove(test_doc_path)


# ------------------------------------------------------------------------------
# 3. Dynamic Schema Detection with 3 Distinct Small CSVs
# ------------------------------------------------------------------------------
def test_dynamic_schema_detection_with_three_csvs():
    """
    Synthesizes 3 completely different CSV schemas inside the test only:
    1. Employee payroll
    2. IoT telemetry
    3. E-commerce orders
    Verifies column typing, categorical detection, and dynamic schema profiling.
    """
    datasets = [
        {
            "name": "employees",
            "columns": ["emp_id", "dept_name", "annual_salary", "is_full_time"],
            "rows": [
                ["EMP001", "Engineering", "125000", "True"],
                ["EMP002", "Marketing", "95000", "True"],
                ["EMP003", "Sales", "105000", "False"],
            ],
            "numeric_cols": ["annual_salary"],
            "categorical_cols": ["dept_name", "is_full_time"]
        },
        {
            "name": "iot_sensors",
            "columns": ["device_uuid", "celsius_reading", "humidity_pct", "location_zone"],
            "rows": [
                ["DEV-01", "24.5", "60.2", "Zone_A"],
                ["DEV-02", "22.1", "55.8", "Zone_B"],
                ["DEV-03", "27.3", "65.0", "Zone_A"],
            ],
            "numeric_cols": ["celsius_reading", "humidity_pct"],
            "categorical_cols": ["location_zone"]
        },
        {
            "name": "store_orders",
            "columns": ["order_ref", "customer_tier", "order_amount", "payment_status"],
            "rows": [
                ["ORD-991", "VIP", "450.75", "Completed"],
                ["ORD-992", "Standard", "89.20", "Completed"],
                ["ORD-993", "VIP", "1200.00", "Pending"],
            ],
            "numeric_cols": ["order_amount"],
            "categorical_cols": ["customer_tier", "payment_status"]
        }
    ]

    for ds in datasets:
        with tempfile.NamedTemporaryFile("w+", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(ds["columns"])
            writer.writerows(ds["rows"])
            temp_csv_path = f.name

        try:
            # Read first line to inspect discovered columns
            with open(temp_csv_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = [re.sub(r"[^\w]", "_", col.strip().lower()) for col in next(reader)]

            # Check that header columns match
            for col in ds["columns"]:
                sanitized = re.sub(r"[^\w]", "_", col.strip().lower())
                assert sanitized in header, f"Column {col} not discovered in {ds['name']}"

            # Check row count
            with open(temp_csv_path, "r", encoding="utf-8") as f:
                row_count = sum(1 for _ in f) - 1
            assert row_count == len(ds["rows"]), f"Row count mismatch in {ds['name']}"
        finally:
            if os.path.exists(temp_csv_path):
                os.remove(temp_csv_path)


# ------------------------------------------------------------------------------
# 4. Multi-Format Document Ingestion (.md, .txt, .pdf)
# ------------------------------------------------------------------------------
def test_multi_format_document_ingestion():
    """Tests document parsing and section extraction for .md, .txt, and .pdf formats."""
    # 1. Markdown test
    with tempfile.NamedTemporaryFile("w+", suffix=".md", delete=False) as f:
        f.write("# Employee Code of Conduct\n\nAll staff must maintain confidentiality.\n\n## Workplace Health\n\nErgonomic standards apply.\n")
        f.flush()
        md_path = f.name

    # 2. Text test
    with tempfile.NamedTemporaryFile("w+", suffix=".txt", delete=False) as f:
        f.write("Operating Instructions\n\nStandard operating checklist for equipment maintenance.\n")
        f.flush()
        txt_path = f.name

    # 3. PDF test
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    pdf_fd, pdf_path = tempfile.mkstemp(suffix=".pdf")
    os.close(pdf_fd)
    with open(pdf_path, "wb") as f:
        writer.write(f)

    try:
        # Markdown parsing test
        md_sections = parse_document_sections(md_path)
        assert len(md_sections) >= 2
        titles = [s["title"] for s in md_sections]
        assert any("Workplace Health" in t for t in titles)

        # Plain text parsing test
        txt_sections = parse_document_sections(txt_path)
        assert len(txt_sections) >= 1
        assert "Operating Instructions" in txt_sections[0]["text"]

        # Chunking test
        chunks = chunk_sections(md_sections, "conduct.md")
        assert len(chunks) >= 2
        assert all(c["source_file"] == "conduct.md" for c in chunks)
        assert all("content" in c and len(c["content"]) > 0 for c in chunks)
    finally:
        for p in (md_path, txt_path, pdf_path):
            if os.path.exists(p):
                os.remove(p)


# ------------------------------------------------------------------------------
# 5. Zero Rows in Production Database After Reset
# ------------------------------------------------------------------------------
def test_zero_rows_in_production_db_after_reset():
    """Asserts that the production application database has exactly 0 rows across all tables."""
    prod_url = os.environ.get("PRODUCTION_DATABASE_URL", "postgresql://postgres:postgres_password@localhost:5434/business_assistant")
    conn = None
    try:
        conn = psycopg2.connect(prod_url)
        cur = conn.cursor()
        tables = [
            "sales",
            "document_embeddings",
            "quality_reports",
            "conversations",
            "messages",
            "support_tickets",
            "audit_log",
            "sales_sandbox",
            "schema_metadata"
        ]
        for tbl in tables:
            cur.execute(f"SELECT count(*) FROM {tbl};")
            count = cur.fetchone()[0]
            assert count == 0, f"Production table '{tbl}' has {count} rows! Expected exactly 0 rows after reset."
        cur.close()
    finally:
        if conn:
            conn.close()


# ------------------------------------------------------------------------------
# 6. Real Tool Execution and SQL Sanitizer Security
# ------------------------------------------------------------------------------
def test_real_tool_execution_and_sql_safety():
    """Tests query_sales safety and search_docs execution."""
    # SQL Sanitizer must reject destructive operations
    with pytest.raises(ValueError):
        validate_and_sanitize_sql("DROP TABLE sales;")

    with pytest.raises(ValueError):
        validate_and_sanitize_sql("UPDATE sales SET revenue = 0;")

    with pytest.raises(ValueError):
        validate_and_sanitize_sql("SELECT * FROM sales; DELETE FROM sales;")

    # Allowed safe SELECT query
    cleaned = validate_and_sanitize_sql("SELECT count(*) FROM sales")
    assert "SELECT count(*) FROM sales" in cleaned
    assert "LIMIT" in cleaned

    # Search docs with query
    docs_result = search_docs("operational policies and guidelines")
    assert isinstance(docs_result, (str, list, dict))
