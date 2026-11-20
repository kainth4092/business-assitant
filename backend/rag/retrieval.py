"""
pgvector Document Retrieval Module
Performs semantic similarity searches over ingested company documents using pgvector.
"""

import os
import logging
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

from backend.rag.embeddings import get_text_embedding

load_dotenv()
logger = logging.getLogger("RAGRetrieval")

def get_db_connection(readonly: bool = True):
    """
    Returns a PostgreSQL database connection.
    If readonly=True, connects using the dedicated sales_readonly role.
    """
    if readonly:
        db_url = os.environ.get(
            "READONLY_DATABASE_URL",
            "postgresql://sales_readonly:readonly_password@localhost:5434/business_assistant"
        )
    else:
        db_url = os.environ.get(
            "DATABASE_URL",
            "postgresql://postgres:postgres_password@localhost:5434/business_assistant"
        )
        
    return psycopg2.connect(db_url)

def search_documents(query: str, top_k: int = 3, min_similarity: float = 0.0) -> List[Dict[str, Any]]:
    """
    Retrieves the most semantically relevant document chunks matching `query`.
    Uses pgvector cosine distance operator (<=>).
    Cosine similarity is computed as: 1 - (embedding <=> query_vector).
    
    Returns:
        List of dicts: [
            {
                "chunk_id": str,
                "source_file": str,
                "title": str,
                "content": str,
                "similarity": float,
                "chunk_index": int
            }, ...
        ]
    """
    if not query or not query.strip():
        return []

    # Compute query embedding (768 dimensions)
    query_vector = get_text_embedding(query)
    query_vector_str = "[" + ",".join(f"{x:.8f}" for x in query_vector) + "]"
    
    conn = None
    try:
        conn = get_db_connection(readonly=True)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # pgvector query: order by cosine distance <=>
        search_sql = """
            SELECT 
                chunk_id,
                source_file,
                title,
                content,
                chunk_index,
                ROUND((1 - (embedding <=> %s::vector))::numeric, 4) AS similarity
            FROM document_embeddings
            ORDER BY embedding <=> %s::vector ASC
            LIMIT %s;
        """
        cursor.execute(search_sql, (query_vector_str, query_vector_str, max(1, min(top_k, 20))))
        rows = cursor.fetchall()
        
        results = []
        for r in rows:
            results.append({
                "chunk_id": r["chunk_id"],
                "source_file": r["source_file"],
                "title": r["title"] or r["source_file"],
                "content": r["content"],
                "similarity": float(r["similarity"]),
                "chunk_index": r["chunk_index"]
            })
            
        cursor.close()
        return results
    except Exception as e:
        logger.error(f"Error during pgvector search_documents: {e}")
        return []
    finally:
        if conn:
            conn.close()

def list_indexed_sources() -> List[Dict[str, Any]]:
    """
    Returns list of indexed documents and their chunk counts.
    """
    conn = None
    try:
        conn = get_db_connection(readonly=True)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT 
                source_file,
                COUNT(*) as total_chunks,
                MIN(title) as sample_title
            FROM document_embeddings
            GROUP BY source_file
            ORDER BY source_file ASC;
        """)
        rows = cursor.fetchall()
        cursor.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Error listing indexed sources: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_document_chunks(source_file: str) -> List[Dict[str, Any]]:
    """
    Returns all chunks belonging to a specific document.
    """
    conn = None
    try:
        conn = get_db_connection(readonly=True)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT 
                chunk_id,
                source_file,
                title,
                content,
                chunk_index,
                total_chunks
            FROM document_embeddings
            WHERE source_file = %s OR source_file LIKE %s
            ORDER BY chunk_index ASC;
        """, (source_file, f"%{source_file}%"))
        rows = cursor.fetchall()
        cursor.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Error fetching document chunks for {source_file}: {e}")
        return []
    finally:
        if conn:
            conn.close()
