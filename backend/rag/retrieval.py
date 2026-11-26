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
            "postgresql://sales_readonly:readonly_password@localhost:5434/fixdesk"
        )
    else:
        db_url = os.environ.get(
            "DATABASE_URL",
            "postgresql://postgres:postgres_password@localhost:5434/fixdesk"
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
    Returns list of indexed documents, their chunk counts, titles, and real content summaries.
    Titles and summaries are derived directly from the real document content (chunk_index = 0).
    """
    conn = None
    try:
        conn = get_db_connection(readonly=True)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT 
                d.source_file,
                COUNT(*) as total_chunks,
                c.title as sample_title,
                c.content as first_chunk_content
            FROM document_embeddings d
            LEFT JOIN (
                SELECT DISTINCT ON (source_file) source_file, title, content
                FROM document_embeddings
                ORDER BY source_file, chunk_index ASC
            ) c ON d.source_file = c.source_file
            GROUP BY d.source_file, c.title, c.content
            ORDER BY d.source_file ASC;
        """)
        rows = cursor.fetchall()
        cursor.close()
        
        result = []
        for r in rows:
            # Clean first chunk content into a concise excerpt
            content = r.get("first_chunk_content") or ""
            # Strip heading if content starts with title
            lines = [l.strip() for l in content.split("\n") if l.strip()]
            summary_lines = [l for l in lines if not l.startswith("#")]
            summary_text = " ".join(summary_lines) if summary_lines else content
            summary_snippet = summary_text[:180].strip()
            if len(summary_text) > 180:
                summary_snippet += "..."

            result.append({
                "source_file": r["source_file"],
                "total_chunks": r["total_chunks"],
                "sample_title": r.get("sample_title") or r["source_file"],
                "sample_summary": summary_snippet or "No text summary available."
            })
        return result
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
