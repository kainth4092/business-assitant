"""
Integration Tests for FastAPI Backend Endpoints
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert data["database"] == "connected"
    assert data["pgvector_ready"] is True
    assert data["sales_records"] > 0

def test_data_quality_endpoint():
    response = client.get("/data-quality")
    assert response.status_code == 200
    data = response.json()
    assert "records_profile" in data
    assert data["records_profile"]["cleaned_total_rows"] == 1500

def test_sources_endpoint():
    response = client.get("/sources")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["total_documents"] >= 5

def test_chat_endpoint_data_query():
    payload = {
        "query": "What are the top 5 item types by sales?"
    }
    response = client.post("/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert data["trace"]["route"] == "data"
    assert "query_sales" in data["tools_used"]
    assert "thread_id" in data

def test_chat_endpoint_docs_query():
    payload = {
        "query": "What is the return policy for dairy items?"
    }
    response = client.post("/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert data["trace"]["route"] == "docs"
    assert "search_docs" in data["tools_used"]

def test_chat_endpoint_both_query():
    payload = {
        "query": "Which outlet sells the most dairy and what promotion or return policies apply?"
    }
    response = client.post("/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert data["trace"]["route"] == "both"
    assert "query_sales" in data["tools_used"]
    assert "search_docs" in data["tools_used"]
