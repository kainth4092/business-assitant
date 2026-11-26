"""
Embedding Utilities for Fixdesk RAG
Provides unified interface for Google Gemini 768-dimensional embeddings (`gemini-embedding-2`),
with a deterministic 768-dimensional fallback when offline or during automated testing.
"""

import os
import math
import hashlib
import logging
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("RAGEmbeddings")

VECTOR_DIMENSION = 768
DEFAULT_EMBEDDING_MODEL = "gemini-embedding-2"


def normalize_vector(vector: List[float]) -> List[float]:
    """L2-normalizes a vector to unit length for cosine similarity in pgvector."""
    norm = math.sqrt(sum(v * v for v in vector))
    if norm > 0:
        return [v / norm for v in vector]
    if vector:
        out = [0.0] * len(vector)
        out[0] = 1.0
        return out
    return vector


def _get_gemini_embeddings_client():
    """Returns a configured GoogleGenerativeAIEmbeddings client if GOOGLE_API_KEY is valid."""
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    is_valid_key = api_key and not api_key.startswith("your_") and not api_key.startswith("mock_")
    if not is_valid_key:
        return None

    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    model_name = os.environ.get("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL).strip() or DEFAULT_EMBEDDING_MODEL
    if not model_name.startswith("models/"):
        model_name = f"models/{model_name}"

    return GoogleGenerativeAIEmbeddings(
        model=model_name,
        google_api_key=api_key
    )


def get_fallback_embedding(text: str, dim: int = VECTOR_DIMENSION) -> List[float]:
    """
    Generates a deterministic, normalized vector of dimension `dim` from text.
    Uses MD5/SHA256 rolling hashes and term frequencies to create reproducible
    embeddings for offline testing and development without API keys.
    """
    words = text.lower().split()
    vector = [0.0] * dim

    if not words:
        vector[0] = 1.0
        return vector

    for idx, word in enumerate(words):
        h = int(hashlib.sha256(word.encode("utf-8")).hexdigest(), 16)
        slot = h % dim
        weight = 1.0 / (1.0 + math.log(1.0 + idx))
        vector[slot] += weight

        h2 = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
        slot2 = (h2 + slot) % dim
        vector[slot2] += (weight * 0.5)

    return normalize_vector(vector)


def get_text_embedding(text: str) -> List[float]:
    """
    Computes a unit-normalized 768-dimensional embedding for a single text string using
    Google Gemini embeddings (`output_dimensionality=768`), or deterministic fallback.
    """
    try:
        client = _get_gemini_embeddings_client()
        if client is not None:
            vec = client.embed_query(text, output_dimensionality=VECTOR_DIMENSION)
            if len(vec) == VECTOR_DIMENSION:
                return normalize_vector(vec)
            logger.warning(
                f"Gemini returned vector of length {len(vec)}, expected {VECTOR_DIMENSION}. Using fallback."
            )
    except Exception as e:
        logger.warning(f"Error calling Gemini Embeddings ({e}). Falling back to deterministic local embedding.")

    return get_fallback_embedding(text, VECTOR_DIMENSION)


def get_texts_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Batch 768-dimensional embedding calculation for a list of texts.
    """
    if not texts:
        return []

    try:
        client = _get_gemini_embeddings_client()
        if client is not None:
            vecs = client.embed_documents(texts, output_dimensionality=VECTOR_DIMENSION)
            if len(vecs) == len(texts) and all(len(v) == VECTOR_DIMENSION for v in vecs):
                return [normalize_vector(v) for v in vecs]
            logger.warning(
                f"Unexpected batch embedding dimensions (expected {VECTOR_DIMENSION}). Using fallback."
            )
    except Exception as e:
        logger.warning(f"Error calling batch Gemini Embeddings ({e}). Falling back to local embedding.")

    return [get_fallback_embedding(t, VECTOR_DIMENSION) for t in texts]
