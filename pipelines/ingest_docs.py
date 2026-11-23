"""
RAG Ingestion Pipeline for Business Assistant
---------------------------------------------
Scans company policy markdown documents in /docs, chunks them semantically,
computes 768-dimensional vector embeddings, and stores them in PostgreSQL pgvector.
"""

import os
import re
import glob
import logging
from typing import List, Dict, Any
import psycopg2
from psycopg2.extras import execute_batch
from dotenv import load_dotenv

# Set PYTHONPATH awareness
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.rag.embeddings import get_texts_embeddings

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RAGIngestion")


def parse_markdown_sections(file_path: str) -> List[Dict[str, str]]:
    """
    Parses a markdown document into semantic sections based on headers.
    Returns list of dicts with title and text content.
    """
    filename = os.path.basename(file_path)
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Split document by markdown headers (## or #)
    lines = content.split("\n")
    sections = []
    
    current_title = filename.replace(".md", "").replace("_", " ").title()
    current_lines = []
    
    for line in lines:
        if line.startswith("# ") or line.startswith("## "):
            if current_lines:
                sec_text = "\n".join(current_lines).strip()
                if sec_text:
                    sections.append({
                        "title": current_title,
                        "text": sec_text
                    })
                current_lines = []
            current_title = line.lstrip("#").strip()
        else:
            current_lines.append(line)
            
    if current_lines:
        sec_text = "\n".join(current_lines).strip()
        if sec_text:
            sections.append({
                "title": current_title,
                "text": sec_text
            })
            
    return sections

def chunk_sections(sections: List[Dict[str, str]], filename: str, max_chunk_chars: int = 600, overlap: int = 60) -> List[Dict[str, Any]]:
    """
    Chunks sections into uniform windows while preserving title metadata.
    """
    chunks = []
    chunk_idx = 0
    
    for sec in sections:
        title = sec["title"]
        text = sec["text"]
        
        # If section is small, keep it whole
        if len(text) <= max_chunk_chars:
            chunks.append({
                "source_file": filename,
                "title": title,
                "content": f"{title}\n{text}",
                "chunk_index": chunk_idx
            })
            chunk_idx += 1
        else:
            # Sliding window chunking
            start = 0
            while start < len(text):
                end = min(start + max_chunk_chars, len(text))
                # Try not to break in the middle of a word
                if end < len(text):
                    last_space = text.rfind(" ", start, end)
                    if last_space > start + 100:
                        end = last_space
                        
                sub_text = text[start:end].strip()
                if sub_text:
                    chunks.append({
                        "source_file": filename,
                        "title": title,
                        "content": f"{title}\n{sub_text}",
                        "chunk_index": chunk_idx
                    })
                    chunk_idx += 1
                start = end - overlap if end < len(text) else end
                
    total_chunks = len(chunks)
    for c in chunks:
        c["total_chunks"] = total_chunks
        c["chunk_id"] = f"{filename}_{c['chunk_index']}"
        
    return chunks

def ingest_all_docs(docs_dir: str = "docs") -> int:
    """
    Main ingestion execution function. Dynamically discovers all policy and documentation files (.md, .txt)
    in docs_dir, parses sections, computes vector embeddings, and stores them in PostgreSQL pgvector.
    """
    logger.info(f"Scanning for documentation files in: {docs_dir}")
    
    # Discover all documentation files dynamically in docs_dir
    doc_paths = sorted(glob.glob(os.path.join(docs_dir, "*.md")) + glob.glob(os.path.join(docs_dir, "*.txt")))
    if not doc_paths:
        logger.warning(f"No .md or .txt files discovered in {docs_dir}.")
        return 0
        
    all_chunks = []
    for doc_path in doc_paths:
        doc_name = os.path.basename(doc_path)
        sections = parse_markdown_sections(doc_path)
        doc_chunks = chunk_sections(sections, doc_name)
        all_chunks.extend(doc_chunks)
        logger.info(f"Parsed {len(doc_chunks)} chunks from {doc_name}")
        
    if not all_chunks:
        logger.error("No chunks extracted from documents. Exiting.")
        return 0
        
    logger.info(f"Total chunks across all documents: {len(all_chunks)}. Computing embeddings...")
    
    # Compute embeddings
    texts = [c["content"] for c in all_chunks]
    embeddings = get_texts_embeddings(texts)
    
    # Connect to PostgreSQL with read-write user
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:postgres_password@localhost:5434/business_assistant"
    )
    
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    
    # Clean stale embeddings on fresh batch ingestion
    cursor.execute("TRUNCATE TABLE document_embeddings;")
    conn.commit()
    
    insert_sql = """
        INSERT INTO document_embeddings (
            chunk_id, source_file, title, content, chunk_index, total_chunks, embedding
        ) VALUES (%s, %s, %s, %s, %s, %s, %s::vector)
        ON CONFLICT (chunk_id) DO UPDATE SET
            source_file = EXCLUDED.source_file,
            title = EXCLUDED.title,
            content = EXCLUDED.content,
            chunk_index = EXCLUDED.chunk_index,
            total_chunks = EXCLUDED.total_chunks,
            embedding = EXCLUDED.embedding;
    """
    
    records = []
    for chunk, emb in zip(all_chunks, embeddings):
        vector_str = "[" + ",".join(f"{x:.8f}" for x in emb) + "]"
        records.append((
            chunk["chunk_id"],
            chunk["source_file"],
            chunk["title"],
            chunk["content"],
            chunk["chunk_index"],
            chunk["total_chunks"],
            vector_str
        ))
        
    execute_batch(cursor, insert_sql, records, page_size=100)
    conn.commit()
    cursor.close()
    conn.close()
    
    logger.info(f"Successfully ingested and indexed {len(records)} document chunks into pgvector!")
    return len(records)

if __name__ == "__main__":
    ingest_all_docs()
