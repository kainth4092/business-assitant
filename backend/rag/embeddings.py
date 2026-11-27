"""
Embedding Utilities for Fixdesk RAG
Provides unified 768-dimensional embeddings (`gemini-embedding-2`) across Vertex AI (ADC),
Gemini Developer API key, or deterministic 768-D local fallback when offline or restricted.
"""

import logging
from typing import List
from dotenv import load_dotenv

from backend.cloud.config import is_cloud_allowed_in_context
from backend.cloud.factories import get_embedding_client
from backend.cloud.local_impl import (
    DEFAULT_EMBEDDING_MODEL,
    VECTOR_DIMENSION,
    deterministic_fallback_embedding,
    normalize_vector,
)

load_dotenv()
logger = logging.getLogger("RAGEmbeddings")

__all__ = [
    "VECTOR_DIMENSION",
    "DEFAULT_EMBEDDING_MODEL",
    "normalize_vector",
    "get_fallback_embedding",
    "get_text_embedding",
    "get_texts_embeddings",
]


def get_fallback_embedding(text: str, dim: int = VECTOR_DIMENSION) -> List[float]:
    """Generates a deterministic, unit-normalized vector of dimension `dim` from text."""
    return deterministic_fallback_embedding(text, dim)


def get_text_embedding(text: str, cloud_allowed: bool = True) -> List[float]:
    """
    Computes a unit-normalized 768-dimensional embedding for a single text string
    via the active EmbeddingClient (Vertex AI ADC, Gemini API, or local fallback).
    When `cloud_allowed=False` (or scoped False), cloud clients are refused and deterministic local embeddings are returned.
    """
    if not (cloud_allowed and is_cloud_allowed_in_context()):
        return deterministic_fallback_embedding(text, VECTOR_DIMENSION)
    client = get_embedding_client(cloud_allowed=True)
    return client.embed_query(text)


def get_texts_embeddings(texts: List[str], cloud_allowed: bool = True) -> List[List[float]]:
    """Batch 768-dimensional embedding calculation for a list of texts."""
    if not texts:
        return []
    if not (cloud_allowed and is_cloud_allowed_in_context()):
        return [deterministic_fallback_embedding(t, VECTOR_DIMENSION) for t in texts]
    client = get_embedding_client(cloud_allowed=True)
    return client.embed_documents(texts)
