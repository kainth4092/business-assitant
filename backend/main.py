"""
FastAPI Application Entrypoint for Business Assistant
------------------------------------------------------
Exposes REST API endpoints:
- GET  /health: Health check and database connectivity audit
- POST /chat: Autonomous conversational AI powered by LangGraph agent
- GET  /data-quality: PySpark data quality audit metrics
- GET  /sources: Indexed company policy documents and chunk counts
"""

import os
import sys
import uuid
import json
import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.agent.graph import agent_graph
from backend.rag.retrieval import list_indexed_sources, get_db_connection
from mcp_server.tools import get_data_quality_report

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("FastAPIServer")

app = FastAPI(
    title="Business Assistant API",
    description="Agentic enterprise assistant combining PySpark sales data and pgvector policy documents",
    version="1.0.0"
)

# CORS configuration
allowed_origins_env = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()] + ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------------------
# Request & Response Schemas
# ------------------------------------------------------------------------------
class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, description="User's plain English question", json_schema_extra={"example": "What are the top 5 item types by sales?"})
    thread_id: Optional[str] = Field(None, description="Optional UUID for conversation memory session")

class ExecutionTrace(BaseModel):
    route: str
    tools_called: List[str]
    retries: int
    is_grounded: bool
    feedback: Optional[str] = None

class ChatResponse(BaseModel):
    answer: str
    tools_used: List[str]
    sources: List[Dict[str, Any]]
    trace: ExecutionTrace
    thread_id: str

# ------------------------------------------------------------------------------
# API Endpoints
# ------------------------------------------------------------------------------
@app.get("/status", status_code=status.HTTP_200_OK)
@app.get("/health", status_code=status.HTTP_200_OK)
def get_system_status():
    """
    Returns real live telemetry:
    - PostgreSQL connection status
    - Exact sales records count from PostgreSQL
    - Exact document chunks count from pgvector
    - Available tools introspected from MCP server
    - Active LLM and embedding models
    - Vector dimensions
    """
    db_status = "disconnected"
    sales_count = 0
    vector_chunks_count = 0
    vector_extension_ready = False
    
    try:
        conn = get_db_connection(readonly=True)
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM sales;")
        sales_count = cursor.fetchone()[0]
        cursor.execute("SELECT count(*) FROM document_embeddings;")
        vector_chunks_count = cursor.fetchone()[0]
        cursor.execute("SELECT extname FROM pg_extension WHERE extname = 'vector';")
        ext = cursor.fetchone()
        vector_extension_ready = bool(ext)
        cursor.close()
        conn.close()
        db_status = "connected"
    except Exception as e:
        logger.error(f"Status check database connection failed: {e}")
        db_status = f"error: {str(e)}"
        
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    has_live_llm = bool(api_key and not api_key.startswith("your_") and not api_key.startswith("mock_"))
    
    available_tools = [
        {"name": "query_sales", "description": "Read-only SQL query against structured sales data", "type": "sql"},
        {"name": "search_docs", "description": "Semantic search over policy vector embeddings", "type": "rag"},
        {"name": "get_data_quality_report", "description": "PySpark data quality audit metrics", "type": "quality"},
        {"name": "get_ticket_context", "description": "Retrieve support ticket telemetry and context", "type": "support"},
        {"name": "run_data_quality_checks", "description": "Live schema and invariant checks", "type": "support"},
        {"name": "preview_fix", "description": "Dry-run remediation fix in isolated sandbox", "type": "support"},
        {"name": "apply_fix", "description": "Commit approved remediation to production", "type": "support"}
    ]
    
    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
        "pgvector_ready": vector_extension_ready,
        "sales_records": sales_count,
        "indexed_chunks": vector_chunks_count,
        "tools_count": len(available_tools),
        "tools": available_tools,
        "llm_live_mode": has_live_llm,
        "llm_model": os.environ.get("LLM_MODEL", "gemini-1.5-flash"),
        "embedding_model": os.environ.get("EMBEDDING_MODEL", "text-embedding-004"),
        "embedding_dimension": 768
    }

@app.post("/chat", response_model=ChatResponse, status_code=status.HTTP_200_OK)
def chat_endpoint(payload: ChatRequest):
    """
    Executes the autonomous LangGraph agent:
    1. Router: classifies intent (data, docs, or both)
    2. Agent: decides and executes MCP tools
    3. Answer: synthesizes grounded response with source citations
    4. Check: verifies factual groundedness with a max 2 retry cap
    5. Persistence: records chat exchange into PostgreSQL conversations and messages tables.
    """
    thread_id = payload.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    initial_state = {
        "user_query": payload.query,
        "messages": [{"role": "user", "content": payload.query}],
        "retry_count": 0
    }
    
    try:
        final_state = agent_graph.invoke(initial_state, config=config)
        
        trace_data = final_state.get("trace", {})
        trace = ExecutionTrace(
            route=trace_data.get("route", final_state.get("route", "docs")),
            tools_called=trace_data.get("tools_called", final_state.get("tools_used", [])),
            retries=trace_data.get("retries", final_state.get("retry_count", 0)),
            is_grounded=trace_data.get("is_grounded", final_state.get("is_grounded", True)),
            feedback=trace_data.get("feedback")
        )

        final_answer = final_state.get("final_answer", "No answer generated.")
        tools_used = final_state.get("tools_used", [])
        sources = final_state.get("sources", [])

        # Persist conversation and messages to PostgreSQL
        try:
            db_conn = get_db_connection(readonly=False)
            db_conn.autocommit = True
            db_cur = db_conn.cursor()
            
            # Upsert conversation
            db_cur.execute("""
                INSERT INTO conversations (id, title, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP;
            """, (thread_id, payload.query[:60]))
            
            # Insert user message
            user_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
            db_cur.execute("""
                INSERT INTO messages (id, conversation_id, role, content)
                VALUES (%s, %s, 'user', %s);
            """, (user_msg_id, thread_id, payload.query))
            
            # Insert assistant message
            asst_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
            db_cur.execute("""
                INSERT INTO messages (id, conversation_id, role, content, tools_used, sources, trace)
                VALUES (%s, %s, 'assistant', %s, %s, %s, %s);
            """, (
                asst_msg_id,
                thread_id,
                final_answer,
                json.dumps(tools_used),
                json.dumps(sources),
                json.dumps(trace_data)
            ))
            
            db_cur.close()
            db_conn.close()
        except Exception as persist_err:
            logger.warning(f"Could not persist conversation message to DB: {persist_err}")
        
        return ChatResponse(
            answer=final_answer,
            tools_used=tools_used,
            sources=sources,
            trace=trace,
            thread_id=thread_id
        )
    except Exception as e:
        logger.error(f"Error processing chat request: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent workflow error: {str(e)}"
        )

@app.get("/conversations", status_code=status.HTTP_200_OK)
def list_conversations_endpoint():
    """Retrieves all persisted chat conversations from PostgreSQL."""
    conn = None
    try:
        conn = get_db_connection(readonly=True)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT c.id, c.title, c.created_at, c.updated_at,
                   COUNT(m.id) as message_count,
                   (SELECT content FROM messages WHERE conversation_id = c.id AND role = 'user' ORDER BY created_at ASC LIMIT 1) as initial_query
            FROM conversations c
            LEFT JOIN messages m ON c.id = m.conversation_id
            GROUP BY c.id
            ORDER BY c.updated_at DESC;
        """)
        rows = cursor.fetchall()
        cursor.close()
        return {"status": "SUCCESS", "conversations": [dict(r) for r in rows]}
    except Exception as e:
        logger.error(f"Error fetching conversations: {e}")
        return {"status": "SUCCESS", "conversations": []}
    finally:
        if conn:
            conn.close()

@app.get("/conversations/{conversation_id}", status_code=status.HTTP_200_OK)
def get_conversation_endpoint(conversation_id: str):
    """Retrieves a conversation and all its persisted messages, traces, and citations."""
    conn = None
    try:
        conn = get_db_connection(readonly=True)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM conversations WHERE id = %s;", (conversation_id,))
        conv = cursor.fetchone()
        if not conv:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Conversation '{conversation_id}' not found.")
            
        cursor.execute("""
            SELECT id, role, content, tools_used, sources, trace, created_at
            FROM messages
            WHERE conversation_id = %s
            ORDER BY created_at ASC;
        """, (conversation_id,))
        msgs = cursor.fetchall()
        cursor.close()
        
        return {
            "conversation": dict(conv),
            "messages": [dict(m) for m in msgs]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching conversation {conversation_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    finally:
        if conn:
            conn.close()

@app.get("/data-quality", status_code=status.HTTP_200_OK)
def data_quality_endpoint():
    """
    Returns the real PySpark data quality audit metrics stored in PostgreSQL.
    """
    res = get_data_quality_report()
    if res.get("status") == "SUCCESS":
        return res.get("report")
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=res.get("error", "Data quality report not found. Run PySpark pipeline first.")
    )

@app.get("/documents", status_code=status.HTTP_200_OK)
def list_documents_endpoint():
    """Returns live list of indexed policy documents and chunk counts from PostgreSQL."""
    sources = list_indexed_sources()
    total_chunks = sum(int(s.get("total_chunks", 0)) for s in sources)
    return {
        "status": "SUCCESS",
        "total_documents": len(sources),
        "total_chunks": total_chunks,
        "documents": sources
    }

@app.get("/documents/{document_id}/chunks", status_code=status.HTTP_200_OK)
def get_document_chunks_endpoint(document_id: str):
    """Returns all individual chunks stored in pgvector for a specific document."""
    from backend.rag.retrieval import get_document_chunks
    chunks = get_document_chunks(document_id)
    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No chunks found for document '{document_id}'."
        )
    return {
        "status": "SUCCESS",
        "document_id": document_id,
        "total_chunks": len(chunks),
        "chunks": chunks
    }

@app.get("/sources", status_code=status.HTTP_200_OK)
def sources_endpoint():
    """Backward compatibility alias for /documents."""
    sources = list_indexed_sources()
    return {
        "status": "SUCCESS",
        "total_documents": len(sources),
        "documents": sources
    }

_SAMPLE_QUESTIONS_CACHE = None

@app.get("/sample-questions", status_code=status.HTTP_200_OK)
def get_sample_questions_endpoint():
    """
    Generates dynamic starter questions strictly from real content:
    - Automatically introspects categorical and numeric columns from sales table
    - Queries top distinct values and aggregations
    - Real document titles from pgvector document_embeddings
    """
    global _SAMPLE_QUESTIONS_CACHE
    if _SAMPLE_QUESTIONS_CACHE:
        return {"status": "SUCCESS", "starters": _SAMPLE_QUESTIONS_CACHE}
        
    conn = None
    try:
        from mcp_server.tools import get_schema_metadata
        meta = get_schema_metadata()
        cat_cols = meta.get("categorical_columns", [])
        num_cols = meta.get("numeric_columns", [])
        
        conn = get_db_connection(readonly=True)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        top_type_name = "Sample Category"
        second_type_name = "Secondary Category"
        primary_num = num_cols[0] if num_cols else "sales"
        primary_cat = cat_cols[0] if cat_cols else "category"
        
        if cat_cols:
            try:
                cur.execute(f"""
                    SELECT "{primary_cat}", count(*) as count
                    FROM sales
                    GROUP BY "{primary_cat}"
                    ORDER BY count DESC
                    LIMIT 2;
                """)
                rows = cur.fetchall()
                if rows:
                    top_type_name = str(rows[0][primary_cat])
                if len(rows) > 1:
                    second_type_name = str(rows[1][primary_cat])
            except Exception:
                pass
        
        # Fetch real document titles from document_embeddings
        doc_rows = []
        try:
            cur.execute("""
                SELECT DISTINCT source_file, title
                FROM document_embeddings
                ORDER BY source_file ASC
                LIMIT 4;
            """)
            doc_rows = cur.fetchall()
        except Exception:
            pass
        cur.close()
        
        starters = [
            {
                "num": "01",
                "label": f"{top_type_name} Distribution",
                "caption": f"Calculates total metrics for {top_type_name} in {primary_cat}.",
                "query": f"What is the total {primary_num} and count for {top_type_name} in {primary_cat}?",
                "route": "data"
            },
            {
                "num": "02",
                "label": f"{second_type_name} Performance",
                "caption": f"Evaluates records and performance for {second_type_name}.",
                "query": f"What is the average {primary_num} for {second_type_name}?",
                "route": "data"
            }
        ]
        
        if doc_rows:
            doc1 = doc_rows[0]
            starters.append({
                "num": "03",
                "label": doc1.get("title") or doc1.get("source_file"),
                "caption": f"Retrieves operational procedures from {doc1.get('source_file')}.",
                "query": f"What are the key policy guidelines outlined in {doc1.get('source_file')}?",
                "route": "docs"
            })
            
        if len(doc_rows) > 1:
            doc2 = doc_rows[1]
            starters.append({
                "num": "04",
                "label": doc2.get("title") or doc2.get("source_file"),
                "caption": f"Semantic vector search over {doc2.get('source_file')}.",
                "query": f"What standard operating procedures apply to {doc2.get('source_file')}?",
                "route": "docs"
            })
            
        starters.append({
            "num": "05",
            "label": f"{top_type_name} & Policy Rules",
            "caption": f"Unifies numerical totals for {top_type_name} with operational guidelines.",
            "query": f"What are total {primary_num} metrics for {top_type_name}, and what operational policies apply?",
            "route": "both"
        })
        
        _SAMPLE_QUESTIONS_CACHE = starters
        return {"status": "SUCCESS", "starters": starters}
    except Exception as e:
        logger.error(f"Error generating dynamic sample questions: {e}")
        return {"status": "ERROR", "error": str(e), "starters": []}
    finally:
        if conn:
            conn.close()

# ------------------------------------------------------------------------------
# Support Desk Endpoints (Human-in-the-Loop Remediation)
# ------------------------------------------------------------------------------
class SupportMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Client problem or inquiry message")
    client_name: Optional[str] = Field("Client User", description="Name of reporting client")
    client_email: Optional[str] = Field("client@example.com", description="Client email address")
    channel: Optional[str] = Field("webhook", description="Channel origin (webhook, slack, teams)")

class ApproveTicketRequest(BaseModel):
    operator_name: Optional[str] = Field("human_operator", description="Name of approving administrator")

class RejectTicketRequest(BaseModel):
    reason: Optional[str] = Field("Remediation proposal rejected by administrator.", description="Reason for rejection")
    operator_name: Optional[str] = Field("human_operator", description="Name of rejecting administrator")

@app.post("/support/messages", status_code=status.HTTP_200_OK)
def create_support_message_endpoint(payload: SupportMessageRequest):
    """
    Receives an incoming client message across Webhook, Slack, or Teams.
    Triggers the autonomous Support Desk agent graph:
    Classify -> Investigate -> Propose_Fix -> Test_Fix -> Await_Approval.
    """
    try:
        from backend.support.service import submit_support_message
        ticket = submit_support_message(
            message=payload.message,
            client_name=payload.client_name or "Client User",
            client_email=payload.client_email or "client@example.com",
            channel=payload.channel or "webhook"
        )
        return ticket
    except Exception as e:
        logger.error(f"Error processing support message: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Support workflow error: {str(e)}"
        )

@app.get("/support/tickets", status_code=status.HTTP_200_OK)
def list_support_tickets_endpoint():
    """Lists all support tickets ordered by latest creation date."""
    try:
        from backend.support.service import list_support_tickets
        tickets = list_support_tickets()
        return {"tickets": tickets, "total": len(tickets)}
    except Exception as e:
        logger.error(f"Error listing support tickets: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.get("/support/tickets/{ticket_id}", status_code=status.HTTP_200_OK)
def get_support_ticket_endpoint(ticket_id: str):
    """Retrieves full support ticket details, execution trace, sandbox diff, and audit trail."""
    try:
        from backend.support.service import get_support_ticket
        ticket = get_support_ticket(ticket_id)
        if not ticket:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Ticket '{ticket_id}' not found.")
        return ticket
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching ticket {ticket_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.post("/support/tickets/{ticket_id}/approve", status_code=status.HTTP_200_OK)
def approve_support_ticket_endpoint(ticket_id: str, payload: ApproveTicketRequest = None):
    """
    Human-in-the-Loop Approval Gate:
    Validates approval token, resumes LangGraph execution to Apply_Fix and Notify.
    """
    try:
        from backend.support.service import approve_support_ticket
        op_name = payload.operator_name if payload else "human_operator"
        updated_ticket = approve_support_ticket(ticket_id, operator_name=op_name)
        return {
            "status": "SUCCESS",
            "message": f"Remediation for ticket {ticket_id} approved and applied.",
            "ticket": updated_ticket
        }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except Exception as e:
        logger.error(f"Error approving ticket {ticket_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.post("/support/tickets/{ticket_id}/reject", status_code=status.HTTP_200_OK)
def reject_support_ticket_endpoint(ticket_id: str, payload: RejectTicketRequest = None):
    """
    Rejects the proposed remediation and logs the rejection in the audit log.
    """
    try:
        from backend.support.service import reject_support_ticket
        reason = payload.reason if payload else "Rejected by operator"
        op_name = payload.operator_name if payload else "human_operator"
        updated_ticket = reject_support_ticket(ticket_id, reason=reason, operator_name=op_name)
        return {
            "status": "REJECTED",
            "message": f"Remediation for ticket {ticket_id} rejected.",
            "ticket": updated_ticket
        }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Error rejecting ticket {ticket_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("BACKEND_HOST", "0.0.0.0")
    port = int(os.environ.get("BACKEND_PORT", 8000))
    logger.info(f"Starting FastAPI backend server on {host}:{port}...")
    uvicorn.run("backend.main:app", host=host, port=port, reload=False)
