"""
Document Retrieval Module for Fixdesk RAG
Delegates semantic similarity searches, source listing, and chunk inspection
to the active VectorStore (`pgvector` locally or `BigQueryVectorStore` on GCP).
"""

import logging
from typing import Any, Dict, List
from dotenv import load_dotenv

from backend.cloud.factories import get_vector_store
from backend.cloud.local_impl import _pg_connect as get_db_connection
from backend.rag.embeddings import get_text_embedding

load_dotenv()
logger = logging.getLogger("RAGRetrieval")

__all__ = [
    "get_db_connection",
    "search_documents",
    "list_indexed_sources",
    "get_document_chunks",
]


def search_documents(query: str, top_k: int = 3, min_similarity: float = 0.0) -> List[Dict[str, Any]]:
    """
    Retrieves the most semantically relevant document chunks matching `query`
    using the active VectorStore (pgvector locally or BigQuery Vector Search on GCP).
    """
    if not query or not query.strip():
        return []

    query_vector = get_text_embedding(query)
    safe_k = max(1, min(int(top_k), 20))
    results = get_vector_store().search_documents(
        query_vector=query_vector,
        top_k=safe_k,
        query_text=query,
    )
    if min_similarity > 0.0:
        results = [r for r in results if float(r.get("similarity", 0.0)) >= min_similarity]
    return results


def list_indexed_sources() -> List[Dict[str, Any]]:
    """Returns list of indexed documents, their chunk counts, titles, and content summaries."""
    return get_vector_store().list_indexed_sources()


def get_document_chunks(source_file: str) -> List[Dict[str, Any]]:
    """Returns all chunks belonging to a specific document."""
    return get_vector_store().get_document_chunks(source_file)
