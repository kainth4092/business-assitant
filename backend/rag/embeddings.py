"""
Embedding Utilities for Business Assistant RAG
Provides unified interface for Google Gemini text-embedding-004 embeddings,
with a deterministic 768-dimensional fallback when offline or during automated testing.
"""

import os
import math
import hashlib
import logging
from typing import List
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("RAGEmbeddings")

VECTOR_DIMENSION = 768

def get_fallback_embedding(text: str, dim: int = VECTOR_DIMENSION) -> List[float]:
    """
    Generates a deterministic, normalized vector of dimension `dim` from text.
    Uses MD5/SHA256 rolling hashes and term frequencies to create realistic,
    reproducible embeddings for offline testing and development without API keys.
    """
    # Tokenize and create word-frequency seed
    words = text.lower().split()
    vector = [0.0] * dim
    
    if not words:
        vector[0] = 1.0
        return vector

    for idx, word in enumerate(words):
        # Generate hash buckets for word
        h = int(hashlib.sha256(word.encode("utf-8")).hexdigest(), 16)
        slot = h % dim
        weight = 1.0 / (1.0 + math.log(1.0 + idx))
        vector[slot] += weight
        
        # Cross-dimension interaction
        h2 = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
        slot2 = (h2 + slot) % dim
        vector[slot2] += (weight * 0.5)

    # Normalize vector to unit length for cosine distance computation
    norm = math.sqrt(sum(v * v for v in vector))
    if norm > 0:
        vector = [v / norm for v in vector]
    else:
        vector[0] = 1.0
        
    return vector

def get_text_embedding(text: str) -> List[float]:
    """
    Computes 768-dimensional embedding for a single text string using
    Gemini text-embedding-004 if GOOGLE_API_KEY is available, or fallback.
    """
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    is_valid_key = api_key and not api_key.startswith("your_") and not api_key.startswith("mock_")
    
    if is_valid_key:
        try:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
            model_name = os.environ.get("EMBEDDING_MODEL", "text-embedding-004")
            # Ensure model name is properly prefixed
            if not model_name.startswith("models/"):
                model_name = f"models/{model_name}"
                
            embeddings_client = GoogleGenerativeAIEmbeddings(
                model=model_name,
                google_api_key=api_key
            )
            vec = embeddings_client.embed_query(text)
            if len(vec) == VECTOR_DIMENSION:
                return vec
            logger.warning(f"Gemini returned vector of length {len(vec)}, expected {VECTOR_DIMENSION}. Using fallback.")
        except Exception as e:
            logger.warning(f"Error calling Gemini Embeddings ({e}). Falling back to deterministic local embedding.")
            
    # Deterministic fallback
    return get_fallback_embedding(text, VECTOR_DIMENSION)

def get_texts_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Batch embedding calculation for list of texts.
    """
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    is_valid_key = api_key and not api_key.startswith("your_") and not api_key.startswith("mock_")
    
    if is_valid_key:
        try:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
            model_name = os.environ.get("EMBEDDING_MODEL", "text-embedding-004")
            if not model_name.startswith("models/"):
                model_name = f"models/{model_name}"
                
            embeddings_client = GoogleGenerativeAIEmbeddings(
                model=model_name,
                google_api_key=api_key
            )
            vecs = embeddings_client.embed_documents(texts)
            if len(vecs) == len(texts) and len(vecs[0]) == VECTOR_DIMENSION:
                return vecs
        except Exception as e:
            logger.warning(f"Error calling batch Gemini Embeddings ({e}). Falling back to local embedding.")
            
    return [get_fallback_embedding(t, VECTOR_DIMENSION) for t in texts]
