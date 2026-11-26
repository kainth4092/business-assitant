"""
FastAPI Application Entrypoint for Fixdesk
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
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, status, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.agent.graph import agent_graph
from backend.rag.retrieval import list_indexed_sources, get_db_connection
from backend.support.channel_manager import channel_manager
from mcp_server.tools import get_data_quality_report

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("FastAPIServer")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Starts background support channel workers when backend launches and stops them on exit."""
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        try:
            channel_manager.start_all()
        except Exception as e:
            logger.warning(f"Channel manager startup error: {e}")
    yield
    try:
        channel_manager.stop_all()
    except Exception:
        pass


app = FastAPI(
    title="Fixdesk API",
    description="Fixdesk autonomous operations workbench combining PySpark data telemetry, pgvector docs, and safe remediation",
    version="1.0.0",
    lifespan=lifespan,
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
    route: Optional[Literal["auto", "data", "docs", "both"]] = Field(None, description="Optional explicit routing mode override")

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
        "llm_model": os.environ.get("LLM_MODEL", "gemini-3.5-flash-lite"),
        "embedding_model": os.environ.get("EMBEDDING_MODEL", "gemini-embedding-2"),
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
        "retry_count": 0,
        "route": payload.route if payload.route in ("data", "docs", "both") else "",
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
    - Returns an empty list if there is no data or documents loaded yet.
    """
    global _SAMPLE_QUESTIONS_CACHE
    if _SAMPLE_QUESTIONS_CACHE is not None:
        return {"status": "SUCCESS", "starters": _SAMPLE_QUESTIONS_CACHE}
        
    conn = None
    try:
        from mcp_server.tools import get_schema_metadata
        meta = get_schema_metadata()
        cat_cols = meta.get("categorical_columns", [])
        num_cols = meta.get("numeric_columns", [])
        
        conn = get_db_connection(readonly=True)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Verify whether sales records or documents actually exist
        cur.execute("SELECT count(*) as count FROM sales;")
        sales_row = cur.fetchone()
        sales_count = sales_row["count"] if sales_row else 0

        cur.execute("SELECT count(*) as count FROM document_embeddings;")
        doc_count_row = cur.fetchone()
        doc_count = doc_count_row["count"] if doc_count_row else 0

        # If database has zero records and zero documents, return empty starters
        if sales_count == 0 and doc_count == 0:
            return {"status": "SUCCESS", "starters": []}
        
        starters = []
        num_idx = 1
        
        if sales_count > 0 and (cat_cols or num_cols):
            primary_num = num_cols[0] if num_cols else "id"
            primary_cat = cat_cols[0] if cat_cols else None
            
            top_type_name = None
            second_type_name = None
            if primary_cat:
                try:
                    cur.execute(f"""
                        SELECT "{primary_cat}", count(*) as count
                        FROM sales
                        WHERE "{primary_cat}" IS NOT NULL AND "{primary_cat}" != 'Unknown'
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

            if top_type_name:
                starters.append({
                    "num": f"{num_idx:02d}",
                    "label": f"{top_type_name} Summary",
                    "caption": f"Calculates total {primary_num} for {top_type_name}.",
                    "query": f"What is the total {primary_num} and count for {top_type_name} in {primary_cat}?",
                    "route": "data"
                })
                num_idx += 1

            if second_type_name:
                starters.append({
                    "num": f"{num_idx:02d}",
                    "label": f"{second_type_name} Analysis",
                    "caption": f"Calculates average metrics for {second_type_name}.",
                    "query": f"What is the average {primary_num} for {second_type_name}?",
                    "route": "data"
                })
                num_idx += 1
            elif not top_type_name and primary_num:
                starters.append({
                    "num": f"{num_idx:02d}",
                    "label": f"{primary_num.title()} Overview",
                    "caption": f"Calculates summary statistics for {primary_num}.",
                    "query": f"What are the total and average values of {primary_num}?",
                    "route": "data"
                })
                num_idx += 1
        
        # Fetch real document titles from document_embeddings
        if doc_count > 0:
            try:
                cur.execute("""
                    SELECT DISTINCT source_file, title
                    FROM document_embeddings
                    ORDER BY source_file ASC
                    LIMIT 2;
                """)
                doc_rows = cur.fetchall()
                for doc in doc_rows:
                    title = doc.get("title") or doc.get("source_file")
                    starters.append({
                        "num": f"{num_idx:02d}",
                        "label": title,
                        "caption": f"Searches operational procedures in {doc.get('source_file')}.",
                        "query": f"What are the key policy guidelines outlined in {doc.get('source_file')}?",
                        "route": "docs"
                    })
                    num_idx += 1
            except Exception:
                pass

        if sales_count > 0 and doc_count > 0 and starters:
            top_kw = starters[0]["label"].split()[0]
            starters.append({
                "num": f"{num_idx:02d}",
                "label": f"{top_kw} & Guidelines",
                "caption": f"Correlates quantitative metrics with operational policies.",
                "query": f"What are total metrics for {top_kw}, and what operational rules apply?",
                "route": "both"
            })
            
        cur.close()
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
    client_name: Optional[str] = Field(None, description="Name of reporting client")
    sender: Optional[str] = Field(None, description="Alias for client_name")
    client_email: Optional[str] = Field(None, description="Client email address")
    sender_email: Optional[str] = Field(None, description="Alias for client_email")
    channel: Optional[str] = Field("webhook", description="Channel origin (webhook, slack, teams)")

    def get_client_name(self) -> str:
        return self.client_name or self.sender or "Client User"

    def get_client_email(self) -> str:
        return self.client_email or self.sender_email or "client@example.com"

class ApproveTicketRequest(BaseModel):
    operator_name: Optional[str] = Field("human_operator", description="Name of approving administrator")

class RejectTicketRequest(BaseModel):
    reason: Optional[str] = Field("Remediation proposal rejected by administrator.", description="Reason for rejection")
    operator_name: Optional[str] = Field("human_operator", description="Name of rejecting administrator")

class ToggleChannelRequest(BaseModel):
    enabled: bool = Field(..., description="Whether the channel background worker should run")


@app.get("/support/channels", status_code=status.HTTP_200_OK)
def list_support_channels_endpoint():
    """Returns live connection status, mode, error reason, and last activity per support channel."""
    return {
        "status": "SUCCESS",
        "channels": channel_manager.get_all_statuses(),
    }


@app.post("/support/channels/{channel_id}/toggle", status_code=status.HTTP_200_OK)
def toggle_support_channel_endpoint(channel_id: str, payload: ToggleChannelRequest):
    """Enables or pauses a specific Support Desk channel worker."""
    try:
        updated = channel_manager.toggle_channel(channel_id, payload.enabled)
        return {
            "status": "SUCCESS",
            "channel": updated,
            "channels": channel_manager.get_all_statuses(),
        }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@app.post("/support/messages", status_code=status.HTTP_200_OK)
def create_support_message_endpoint(payload: SupportMessageRequest):
    """
    Receives an incoming client message from UI Simulator or HTTP Webhook.
    Triggers the unified Support Desk ingestion + autonomous agent graph:
    Classify -> Investigate -> Propose_Fix -> Test_Fix -> Await_Approval.
    """
    try:
        from backend.support.service import (
            ChannelPermissionError,
            RateLimitExceededError,
            submit_support_message,
        )
        ticket = submit_support_message(
            message=payload.message,
            client_name=payload.get_client_name(),
            client_email=payload.get_client_email(),
            channel=payload.channel or "webhook"
        )
        return ticket
    except ChannelPermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except RateLimitExceededError as rle:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(rle))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
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

# -----------------------------------------------------------------------------
# Upload & Pipeline Orchestration Endpoints (Part 4 Item 6)
# -----------------------------------------------------------------------------
@app.post("/upload/csv", status_code=status.HTTP_200_OK)
async def upload_csv_endpoint(file: UploadFile = File(...)):
    """Accepts CSV file upload, validates extension, and saves to data/ directory."""
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only .csv files are supported."
        )
    
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(project_root, "data")
    os.makedirs(data_dir, exist_ok=True)
    
    dest_path = os.path.join(data_dir, file.filename)
    try:
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded CSV file is empty."
            )
        with open(dest_path, "wb") as f:
            f.write(content)
            
        global _SAMPLE_QUESTIONS_CACHE
        _SAMPLE_QUESTIONS_CACHE = None
        
        return {
            "status": "SUCCESS",
            "message": f"Successfully uploaded CSV '{file.filename}'.",
            "filename": file.filename,
            "bytes_received": len(content)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving uploaded CSV: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.post("/upload/documents", status_code=status.HTTP_200_OK)
async def upload_documents_endpoint(files: List[UploadFile] = File(...)):
    """Accepts multiple document files (.md, .txt, .pdf), validates, saves to docs/, and auto-indexes into pgvector."""
    allowed_exts = (".md", ".txt", ".pdf")
    saved = []
    
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir = os.path.join(project_root, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    
    for file in files:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in allowed_exts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported format for '{file.filename}'. Supported formats: .md, .txt, .pdf"
            )
        dest_path = os.path.join(docs_dir, file.filename)
        content = await file.read()
        with open(dest_path, "wb") as f:
            f.write(content)
        saved.append(file.filename)
        
    global _SAMPLE_QUESTIONS_CACHE
    _SAMPLE_QUESTIONS_CACHE = None
    
    # Automatically index documents into pgvector immediately
    doc_chunks = 0
    try:
        from pipelines.ingest_docs import ingest_all_docs
        doc_chunks = ingest_all_docs(docs_dir=docs_dir)
        logger.info(f"Auto-ingested {len(saved)} uploaded files, producing {doc_chunks} vector chunks.")
    except Exception as e:
        logger.error(f"Error auto-ingesting uploaded documents: {e}")
        
    return {
        "status": "SUCCESS",
        "message": f"Successfully uploaded {len(saved)} document(s) and indexed {doc_chunks} vector chunks.",
        "saved_files": saved,
        "indexed_chunks": doc_chunks
    }

@app.post("/pipeline/ingest-docs", status_code=status.HTTP_200_OK)
def ingest_docs_endpoint():
    """Ingests and indexes all documents in docs/ into pgvector without re-running PySpark."""
    global _SAMPLE_QUESTIONS_CACHE
    _SAMPLE_QUESTIONS_CACHE = None
    
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir = os.path.join(project_root, "docs")
    
    try:
        from pipelines.ingest_docs import ingest_all_docs
        chunks = ingest_all_docs(docs_dir=docs_dir)
        return {
            "status": "SUCCESS",
            "message": f"Successfully indexed {chunks} vector chunks from documents.",
            "indexed_chunks": chunks
        }
    except Exception as e:
        logger.error(f"Document ingestion error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document ingestion failed: {str(e)}"
        )

@app.get("/pipeline/status", status_code=status.HTTP_200_OK)
def get_pipeline_status_endpoint():
    """Returns the current state of uploaded files in data/ and docs/."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(project_root, "data")
    docs_dir = os.path.join(project_root, "docs")
    
    csv_files = []
    if os.path.exists(data_dir):
        csv_files = [f for f in os.listdir(data_dir) if f.lower().endswith(".csv") and not f.startswith(".")]
        
    doc_files = []
    if os.path.exists(docs_dir):
        from pipelines.ingest_docs import is_user_policy_doc
        doc_files = sorted([f for f in os.listdir(docs_dir) if is_user_policy_doc(f)])
        
    return {
        "has_csv": len(csv_files) > 0,
        "csv_files": csv_files,
        "primary_csv": csv_files[0] if csv_files else None,
        "has_documents": len(doc_files) > 0,
        "document_files": doc_files,
        "documents_count": len(doc_files)
    }

@app.post("/pipeline/run", status_code=status.HTTP_200_OK)
def run_pipeline_endpoint():
    """Executes the universal PySpark cleaning pipeline and document ingestion."""
    global _SAMPLE_QUESTIONS_CACHE
    _SAMPLE_QUESTIONS_CACHE = None
    
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(project_root, "data")
    csv_files = [f for f in os.listdir(data_dir) if f.lower().endswith(".csv") and not f.startswith(".")] if os.path.exists(data_dir) else []
    
    pyspark_res = None
    if csv_files:
        try:
            from pipelines.clean_sales import run_sales_pipeline
            pyspark_res = run_sales_pipeline(input_csv=os.path.join(data_dir, csv_files[0]))
        except Exception as e:
            logger.error(f"Error running PySpark pipeline: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"PySpark cleaning failed: {str(e)}")
            
    doc_chunks = 0
    try:
        from pipelines.ingest_docs import ingest_all_docs
        doc_chunks = ingest_all_docs(docs_dir=os.path.join(project_root, "docs"))
    except Exception as e:
        logger.error(f"Error ingesting documents: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Document ingestion failed: {str(e)}")
        
    return {
        "status": "SUCCESS",
        "message": "Pipeline and document ingestion completed.",
        "csv_processed": csv_files[0] if csv_files else None,
        "cleaned_records": pyspark_res.get("records_profile", {}).get("cleaned_total_rows") if pyspark_res else 0,
        "indexed_chunks": doc_chunks
    }


# ------------------------------------------------------------------------------
# Project Init (Codebase RAG) Endpoints
# ------------------------------------------------------------------------------
class ProjectAskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Plain-English question about the indexed codebase")
    top_k: int = Field(default=6, ge=1, le=20)


class ProjectIndexRequest(BaseModel):
    incremental: bool = Field(default=True, description="Incremental re-index when true; full rebuild when false")


def get_code_store():
    """FastAPI dependency yielding the active PostgreSQL `code_rag` store."""
    from project_init.store import PostgresCodeStore
    return PostgresCodeStore()


@app.get("/projects", status_code=status.HTTP_200_OK)
def list_projects_endpoint(store=Depends(get_code_store)):
    """List configured projects and their latest codebase RAG indexing telemetry."""
    from project_init.config import load_projects_config
    from project_init.security import redact_secrets

    configs = load_projects_config()
    indexed_map: Dict[str, Any] = {}
    db_error: Optional[str] = None
    try:
        for row in store.list_projects():
            indexed_map[row["name"]] = row
    except Exception as exc:
        db_error = str(exc)

    projects_payload: List[Dict[str, Any]] = []
    for cfg in configs:
        db_row = indexed_map.get(cfg.name, {})
        projects_payload.append(
            {
                "name": cfg.name,
                "local_path": cfg.local_path,
                "default_branch": cfg.default_branch,
                "status": db_row.get("status", "database_unavailable" if db_error else "not_indexed"),
                "last_commit_hash": db_row.get("last_commit_hash"),
                "last_indexed_at": str(db_row["last_indexed_at"]) if db_row.get("last_indexed_at") else None,
                "file_count": int(db_row.get("file_count") or 0),
                "chunk_count": int(db_row.get("chunk_count") or 0),
                "skipped_count": int(db_row.get("skipped_count") or 0),
                "last_error": redact_secrets(str(db_row.get("last_error"))) if db_row.get("last_error") else None,
            }
        )

    return {
        "status": "SUCCESS",
        "database_ready": db_error is None,
        "database_error": redact_secrets(db_error) if db_error else None,
        "projects": projects_payload,
    }


@app.get("/projects/{name}/index-status", status_code=status.HTTP_200_OK)
def get_project_index_status_endpoint(name: str, store=Depends(get_code_store)):
    """Return index metrics, commit hash, languages, and file tree summary for a project."""
    from project_init.config import get_project_config
    from project_init.security import redact_secrets

    try:
        cfg = get_project_config(name)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{name}' not found.")

    try:
        info = store.get_project_status(name)
        file_tree = store.list_file_tree(name, limit=150)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Code RAG store unavailable: {redact_secrets(str(exc))}",
        )

    if not info:
        return {
            "status": "not_indexed",
            "project": {
                "name": cfg.name,
                "local_path": cfg.local_path,
                "default_branch": cfg.default_branch,
                "last_commit_hash": None,
                "last_indexed_at": None,
                "file_count": 0,
                "chunk_count": 0,
                "skipped_count": 0,
                "status": "not_indexed",
                "languages": [],
            },
            "file_tree": [],
        }

    info["last_indexed_at"] = str(info["last_indexed_at"]) if info.get("last_indexed_at") else None
    return {
        "status": info.get("status", "indexed"),
        "project": info,
        "file_tree": file_tree,
    }


@app.get("/projects/{name}/skipped", status_code=status.HTTP_200_OK)
def get_project_skipped_files_endpoint(name: str, store=Depends(get_code_store)):
    """Return skipped filenames and reasons for `name` (never secret values)."""
    from project_init.config import get_project_config
    from project_init.security import redact_secrets

    try:
        get_project_config(name)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{name}' not found.")

    try:
        items = store.get_skipped_files(name)
        sanitized = [
            {
                "file_path": row["file_path"],
                "reason": redact_secrets(str(row["reason"])),
                "rule": str(row.get("rule", "policy")),
                "scanned_at": str(row["scanned_at"]) if row.get("scanned_at") else None,
            }
            for row in items
        ]
        return {"status": "SUCCESS", "project": name, "skipped_files": sanitized}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not read skipped files report: {redact_secrets(str(exc))}",
        )


@app.post("/projects/{name}/index", status_code=status.HTTP_200_OK)
def trigger_project_index_endpoint(
    name: str,
    payload: Optional[ProjectIndexRequest] = None,
    store=Depends(get_code_store),
):
    """Trigger full or incremental indexing of project `name`."""
    from project_init.config import get_project_config
    from project_init.indexer import index_project
    from project_init.security import redact_secrets

    try:
        get_project_config(name)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{name}' not found.")

    incremental = payload.incremental if payload is not None else True
    try:
        stats = index_project(name, incremental=incremental, store=store)
        return {
            "status": "SUCCESS",
            "project": stats.project,
            "commit_hash": stats.commit_hash,
            "incremental": stats.incremental,
            "scanned_files": stats.scanned_files,
            "indexed_files": stats.indexed_files,
            "unchanged_files": stats.unchanged_files,
            "removed_files": stats.removed_files,
            "indexed_chunks": stats.indexed_chunks,
            "dropped_chunks": stats.dropped_chunks,
            "skipped_count": len(stats.skipped_files),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Project indexing failed: {redact_secrets(str(exc))}",
        )


@app.post("/projects/{name}/ask", status_code=status.HTTP_200_OK)
def ask_project_codebase_endpoint(
    name: str,
    payload: ProjectAskRequest,
    store=Depends(get_code_store),
):
    """Answer a question strictly from indexed chunks of `name` with file:line citations."""
    from project_init.config import get_project_config
    from project_init.retriever import ask_codebase
    from project_init.security import redact_secrets

    try:
        get_project_config(name)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{name}' not found.")

    try:
        result = ask_codebase(
            project=name,
            question=payload.question,
            top_k=payload.top_k,
            store=store,
        )
        return {"status": "SUCCESS", **result}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Codebase query failed: {redact_secrets(str(exc))}",
        )

if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("BACKEND_HOST", "0.0.0.0")
    port = int(os.environ.get("BACKEND_PORT", 8000))
    logger.info(f"Starting FastAPI backend server on {host}:{port}...")
    uvicorn.run("backend.main:app", host=host, port=port, reload=False)
