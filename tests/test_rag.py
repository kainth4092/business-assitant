"""
Unit Tests for RAG Ingestion, Vector Embeddings, and pgvector Retrieval
"""

import os
import math
import pytest
from backend.rag.embeddings import get_fallback_embedding, VECTOR_DIMENSION
from backend.rag.retrieval import search_documents, list_indexed_sources
from pipelines.ingest_docs import parse_markdown_sections, chunk_sections

def test_fallback_embedding_dimension_and_norm():
    vec = get_fallback_embedding("BigMart return policy for dairy products")
    assert len(vec) == VECTOR_DIMENSION
    assert len(vec) == 768
    # Test vector is unit normalized (length ≈ 1.0)
    norm = math.sqrt(sum(v * v for v in vec))
    assert pytest.approx(norm, 0.001) == 1.0

def test_fallback_embedding_deterministic():
    vec1 = get_fallback_embedding("Refrigeration standards for Supermarket Type 2")
    vec2 = get_fallback_embedding("Refrigeration standards for Supermarket Type 2")
    assert vec1 == vec2

def test_markdown_section_parser():
    import tempfile
    with tempfile.NamedTemporaryFile("w+", suffix=".md") as tmp:
        tmp.write("# Main Header\n\nIntro text.\n\n## Section 1\n\nSection 1 details.\n\n## Section 2\n\nSection 2 details.\n")
        tmp.flush()
        sections = parse_markdown_sections(tmp.name)
        assert len(sections) >= 2
        titles = [s["title"] for s in sections]
        assert any("Section 1" in t for t in titles)

def test_chunk_sections_windowing():
    sections = [
        {"title": "Policy", "text": "Short policy description."}
    ]
    chunks = chunk_sections(sections, "test_policy.md")
    assert len(chunks) == 1
    assert chunks[0]["source_file"] == "test_policy.md"
    assert chunks[0]["chunk_id"] == "test_policy.md_0"

def test_live_search_documents():
    import psycopg2
    from backend.rag.embeddings import get_fallback_embedding
    test_db = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres_password@localhost:5434/business_assistant_test")
    conn = psycopg2.connect(test_db)
    cur = conn.cursor()
    dummy_vec = get_fallback_embedding("return policy for dairy products")
    cur.execute("""
        INSERT INTO document_embeddings (chunk_id, source_file, title, content, chunk_index, total_chunks, embedding)
        VALUES ('test_return_policy_0', 'test_return_policy.md', 'Return Policy', 'Dairy products must be returned within 48 hours.', 0, 1, %s)
        ON CONFLICT (chunk_id) DO NOTHING;
    """, (dummy_vec,))
    conn.commit()
    cur.close()
    conn.close()

    results = search_documents("What is the return window for dairy?", top_k=2)
    assert len(results) > 0
    assert "source_file" in results[0]
    assert "content" in results[0]
    assert "similarity" in results[0]

def test_list_indexed_sources():
    sources = list_indexed_sources()
    assert isinstance(sources, list)
    assert len(sources) >= 1
    assert any(s["source_file"] == "test_return_policy.md" for s in sources)
