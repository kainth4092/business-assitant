"""
Unit Tests for RAG Ingestion, Vector Embeddings, and pgvector Retrieval
"""

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
    results = search_documents("What is the return window for dairy?", top_k=2)
    assert len(results) > 0
    assert "source_file" in results[0]
    assert "content" in results[0]
    assert "similarity" in results[0]

def test_list_indexed_sources():
    sources = list_indexed_sources()
    assert len(sources) >= 5
    filenames = [s["source_file"] for s in sources]
    assert "return_policy.md" in filenames
    assert "faq.md" in filenames
