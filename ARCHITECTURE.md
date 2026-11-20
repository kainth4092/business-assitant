# System Architecture & Technical Specifications (ARCHITECTURE.md)

This document details the complete end-to-end architecture of the **Business Assistant** platform.

---

## 1. System Overview Architecture

```mermaid
flowchart TD
    subgraph Client Layer
        Browser[User Browser]
        NextJS[Next.js App Router Frontend:3000]
        Browser <--> NextJS
    end

    subgraph API & Orchestration Layer
        FastAPI[FastAPI Backend Server:8000]
        NextJS <-->|REST: /chat, /health, /data-quality| FastAPI
    end

    subgraph Agentic LangGraph Engine
        RouterNode[1. Router Node: Classify Intent]
        AgentNode[2. Agent Node: Autonomous Tool Calling]
        AnswerNode[3. Answer Node: Synthesize Response]
        CheckNode{4. Check Node: Grounded?}

        FastAPI --> RouterNode
        RouterNode --> AgentNode
        AgentNode --> AnswerNode
        AnswerNode --> CheckNode
        CheckNode -- "Not Grounded & retries < 2" --> AgentNode
        CheckNode -- "Grounded or retries >= 2" --> Output[Final Answer + Trace]
    end

    subgraph MCP Tool Layer
        MCPServer[MCP Server: Python Tools]
        AgentNode <--> MCPServer
        ToolSQL[query_sales: Read-Only SQL]
        ToolRAG[search_docs: pgvector Retrieval]
        ToolDQ[get_data_quality_report]
        MCPServer --> ToolSQL
        MCPServer --> ToolRAG
        MCPServer --> ToolDQ
    end

    subgraph Storage & Database Layer
        Postgres[(PostgreSQL 16 + pgvector:5434)]
        TableSales[(sales Table: 1500 records)]
        TableEmbeddings[(document_embeddings Table: 21 chunks)]
        Parquet[(data/cleaned_sales.parquet)]
        DQFile[(data/data_quality_report.json)]

        ToolSQL -->|sales_readonly SELECT only| TableSales
        ToolRAG -->|Cosine Distance <=> search| TableEmbeddings
        ToolDQ --> DQFile
    end

    subgraph Data Engineering ETL
        RawCSV[data/BigMart_Sales.csv] --> PySparkJob[pipelines/clean_sales.py]
        PySparkJob --> Parquet
        PySparkJob --> DQFile
        PySparkJob -->|JDBC Batch Load| TableSales

        RawDocs[docs/*.md] --> IngestJob[pipelines/ingest_docs.py]
        IngestJob -->|768-dim Embeddings| TableEmbeddings
    end
```

---

## 2. Agentic Workflow Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor User as User / Client
    participant UI as Next.js Frontend
    participant API as FastAPI Backend
    participant Graph as LangGraph Agent
    participant MCP as MCP Tools
    participant DB as PostgreSQL (sales & pgvector)
    participant LLM as Google Gemini LLM

    User->>UI: Submits question ("Which outlet has highest dairy sales + what promotion applies?")
    UI->>API: POST /chat {query, thread_id}
    API->>Graph: invoke(initial_state, config={thread_id})
    
    rect rgb(240, 245, 255)
        Note over Graph,LLM: Step 1: Routing
        Graph->>LLM: Prompt Router (query)
        LLM-->>Graph: Route = "both"
    end

    rect rgb(240, 255, 245)
        Note over Graph,MCP: Step 2: Tool Execution
        Graph->>MCP: query_sales_tool(SELECT outlet_type, sum(sales) WHERE item_type='Dairy')
        MCP->>DB: Execute SELECT as 'sales_readonly' with LIMIT
        DB-->>MCP: Structured sales rows
        MCP-->>Graph: Sales data payload

        Graph->>MCP: search_docs_tool("Dairy promotions and return policy")
        MCP->>DB: Cosine similarity search on document_embeddings
        DB-->>MCP: Top relevant chunks ([promotion_policy.md], [return_policy.md])
        MCP-->>Graph: Policy snippets payload
    end

    rect rgb(255, 250, 240)
        Note over Graph,LLM: Step 3: Synthesis & Verification
        Graph->>LLM: Answer Node: Synthesize response with citations
        LLM-->>Graph: Draft answer text
        Graph->>LLM: Check Node: Evaluate factual groundedness
        LLM-->>Graph: is_grounded = true, feedback = "All facts verified"
    end

    Graph-->>API: final_answer + trace (route, tools_called, retries: 0)
    API-->>UI: 200 OK JSON response
    UI-->>User: Renders message card + "How I Answered" trace panel
```

---

## 3. Security Architecture & Threat Model

```mermaid
flowchart LR
    subgraph Agent Input
        AgentSQL[Agent Generated SQL Query]
    end

    subgraph Defense Level 1: Application Sanitizer
        Sanitizer{validate_and_sanitize_sql}
        AgentSQL --> Sanitizer
        Sanitizer -- Comments / Semicolons / Non-SELECT / DDL --> Reject[Reject with Security Violation]
        Sanitizer -- Valid SELECT --> EnforceLimit[Enforce LIMIT <= 100]
    end

    subgraph Defense Level 2: Database Role Isolation
        DBSession[PostgreSQL Session: sales_readonly]
        EnforceLimit --> DBSession
        DBSession --> KernelCheck{Kernel Permissions}
        KernelCheck -- SELECT on public.sales --> Permitted[Execute Query]
        KernelCheck -- Mutation / DDL / Sequences --> KernelDeny[PostgreSQL ERROR: Permission Denied]
    end
```

### Key Security Controls:
1. **Zero Secret Hardcoding**: All credentials (`GOOGLE_API_KEY`, `DATABASE_URL`, `READONLY_DATABASE_URL`) are read strictly from environment variables.
2. **Read-Only Database Role**: The `sales_readonly` role is explicitly granted `SELECT` privileges only on `sales` and `document_embeddings`. All mutation privileges (`INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`, `DROP`) are permanently revoked at the PostgreSQL catalog level.
3. **Application SQL Sanitizer**: Semicolons, comments, and non-SELECT keywords are stripped and blocked before opening a database connection.
4. **Mandatory Query Pagination**: Queries lacking a `LIMIT` clause automatically have `LIMIT 100` appended to prevent denial-of-service through memory exhaustion.

---

## 4. PySpark Data Cleaning Pipeline Architecture

```
Raw CSV (/data/BigMart_Sales.csv)
  │
  ├──► Initial Profile: 1,530 rows, 30 duplicates, 226 Item_Weight nulls, 621 Outlet_Size nulls
  │
  ├──► Transformation 1: dropDuplicates() [1,530 -> 1,500 rows]
  │
  ├──► Transformation 2: Label Standardization
  │      Item_Fat_Content: ['LF', 'low fat', ' Regular '] -> ['Low Fat', 'Regular']
  │
  ├──► Transformation 3: Window Imputation
  │      Item_Weight: mean(Item_Weight) over (Window.partitionBy('Item_Identifier'))
  │      coalesce with global mean (12.85 kg)
  │
  ├──► Transformation 4: Domain Mode Imputation
  │      Outlet_Size: imputed based on Outlet_Type (Grocery -> Small, Supermarket -> Medium)
  │
  ├──► Transformation 5: Visibility Imputation (0.0 -> item average visibility)
  │
  ├──► Action 1: Export Parquet (data/cleaned_sales.parquet)
  ├──► Action 2: Export Data Quality Audit (data/data_quality_report.json)
  └──► Action 3: JDBC Write to PostgreSQL 'sales' Table
```

---

## 5. RAG Vector Pipeline Architecture

```
Company Markdown Documents (/docs)
  ├── return_policy.md
  ├── faq.md
  ├── promotion_policy.md
  ├── outlet_guidelines.md
  └── pricing_policy.md
         │
         ▼
  Semantic Section Parser (splits by '##' headers)
         │
         ▼
  Sliding Window Chunker (600 characters, 60 char overlap) -> 21 total chunks
         │
         ▼
  Embedding Generator (Gemini text-embedding-004 / 768-dim vector)
         │
         ▼
  PostgreSQL pgvector Table ('document_embeddings')
         │
         ▼
  Cosine Distance Search (<=>) with 1 - (embedding <=> query_vec) as similarity score
```


---

## 6. Autonomous Support Desk & Safe Remediation Architecture

### LangGraph `support_graph` Workflow

```mermaid
flowchart TD
    Start([Client Problem Message]) --> Classify["1. Classify Node: data_issue / code_bug / question / feature_request"]
    Classify --> Investigate["2. Investigate Node: Run Diagnostics & Profiling"]
    Investigate --> Propose["3. Propose Fix Node: Generate SQL DML or Unified Diff"]
    Propose --> TestFix["4. Test Fix Node: Execute on sales_sandbox"]
    
    TestFix --> CheckPass{"Passes Sandbox?"}
    CheckPass -- "Failure & retries < 2" --> Propose
    CheckPass -- "Failure & retries >= 2" --> HumanEscalate["Escalate to Human Support"]
    CheckPass -- "Passes" --> AwaitApproval["5. Await Approval Node: Issue Token & Pause Graph"]

    AwaitApproval -.->|Checkpointer Pauses State| MemorySaver[("MemorySaver Checkpointer")]
    
    Operator([Human Operator / Frontend]) -->|POST /support/tickets/:id/approve + Token| ResumeAPI["Service Resumption"]
    ResumeAPI -->|Resume Graph| ApplyFix["6. Apply Fix Node: Apply to Production sales"]
    ApplyFix --> WriteAudit[("Write to audit_log Table")]
    ApplyFix --> Notify["7. Notify Node: Format Slack/Teams/Webhook Response"]
    Notify --> Done([Client Notified & Ticket Closed])
```

### Support Desk Sequence Diagram (Human-in-the-Loop)

```mermaid
sequenceDiagram
    autonumber
    actor Client as Client (Slack / Teams / Webhook)
    participant API as FastAPI /support/messages
    participant Graph as LangGraph support_graph
    participant Sandbox as PostgreSQL sales_sandbox
    participant Checkpoint as MemorySaver Checkpointer
    actor Human as Human Operator (Next.js UI)
    participant ProdDB as PostgreSQL Production sales
    participant Audit as PostgreSQL audit_log

    Client->>API: Sends Problem Statement
    API->>Graph: invoke(state)
    Note over Graph: Node 1: Classifies issue & confidence
    Note over Graph: Node 2: Queries schema & finds anomalies
    Note over Graph: Node 3: Synthesizes SQL / Code Patch
    Graph->>Sandbox: Node 4: Runs preview_fix on sales_sandbox
    Sandbox-->>Graph: Before/After Counts & Diff
    Note over Graph: Node 5: Generates approval_token
    Graph->>Checkpoint: State paused (interrupt_before=['apply_fix'])
    Graph-->>API: Returns Ticket (Status: 'fix_ready')
    API-->>Client: Returns Ticket ID & Status
    
    Note over Human,ProdDB: Safe Human-in-the-Loop Gate
    Human->>API: GET /support/tickets/:id (Inspects sandbox diff & SQL)
    Human->>API: POST /support/tickets/:id/approve {operator_name}
    API->>Graph: Resume graph (approval_token validated)
    Graph->>ProdDB: Node 6: apply_fix executes on production sales
    Graph->>Audit: Inserts immutable entry (actor, diff, timestamp)
    Graph->>Client: Node 7: Dispatches formatted resolution notice
```
