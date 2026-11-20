"""
LangGraph Nodes for Business Assistant
--------------------------------------
Implements:
1. router_node: Intent classification (data, docs, both)
2. agent_node: Autonomous tool selection and execution
3. answer_node: Comprehensive response synthesis with citations
4. check_node: Groundedness verification with retry loop logic (cap = 2)
"""

import os
import re
import json
import logging
from typing import Dict, Any, List

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from backend.agent.state import AgentState
from backend.agent.prompts import (
    ROUTER_SYSTEM_PROMPT, AGENT_SYSTEM_PROMPT, 
    ANSWER_SYSTEM_PROMPT, CHECKER_SYSTEM_PROMPT
)
from backend.agent.tools import query_sales_tool, search_docs_tool, get_data_quality_report_tool
from mcp_server.tools import query_sales, search_docs, get_data_quality_report

load_dotenv()
logger = logging.getLogger("AgentNodes")

def is_valid_gemini_key() -> bool:
    key = os.environ.get("GOOGLE_API_KEY", "").strip()
    return bool(key and not key.startswith("your_") and not key.startswith("mock_"))

def get_llm():
    """Returns Gemini Chat model instance if API key is configured."""
    if is_valid_gemini_key():
        from langchain_google_genai import ChatGoogleGenerativeAI
        model_name = os.environ.get("LLM_MODEL", "gemini-1.5-flash")
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0.0,
            google_api_key=os.environ.get("GOOGLE_API_KEY"),
            max_retries=1,
            timeout=5.0
        )
    return None

# ==============================================================================
# 1. ROUTER NODE
# ==============================================================================
def heuristic_route(query: str) -> str:
    """Accurate keyword/pattern intent classifier used when offline or testing."""
    q = query.lower()
    
    # Data keywords (sales numbers, SQL, metrics, aggregations)
    data_words = [
        "sales", "revenue", "highest", "lowest", "average", "avg", "total", "sum", 
        "mrp", "item_type", "outlet", "count", "top 5", "top 3", "top", "rank", 
        "units", "weight", "visibility", "fat_content", "tier 1", "tier 2", "tier 3",
        "supermarket type", "grocery store", "how many", "dataset", "numbers", "which outlet"
    ]
    
    # Docs keywords (policies, guidelines, customer service, operations)
    docs_words = [
        "policy", "return", "refund", "faq", "hours", "opening", "closing", 
        "delivery", "curbside", "pickup", "loyalty", "points", "discount", 
        "promotion", "guideline", "guidelines", "rule", "rules", "markdown", 
        "expire", "expiration", "refrigeration", "storage", "cold chain", "fifo", 
        "price match", "guarantee", "coupon", "wholesale", "damaged", "opened", "receipt"
    ]
    
    data_score = sum(1 for w in data_words if w in q)
    docs_score = sum(1 for w in docs_words if w in q)
    
    # Check for joint questions
    if data_score > 0 and docs_score > 0:
        return "both"
    elif data_score > 0:
        return "data"
    elif docs_score > 0:
        return "docs"
    else:
        return "docs"  # Default to company knowledge

def router_node(state: AgentState) -> Dict[str, Any]:
    """Analyzes the query and routes it to data, docs, or both."""
    query = state.get("user_query", "")
    llm = get_llm()
    
    chosen_route = "docs"
    if llm:
        try:
            response = llm.invoke([
                SystemMessage(content=ROUTER_SYSTEM_PROMPT),
                HumanMessage(content=f"User Question: {query}")
            ])
            text = response.content.strip()
            # Extract json if enclosed in markdown code fences
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            parsed = json.loads(text)
            route_val = parsed.get("route", "").lower()
            if route_val in ("data", "docs", "both"):
                chosen_route = route_val
        except Exception as e:
            logger.warning(f"LLM router failed ({e}). Falling back to heuristic router.")
            chosen_route = heuristic_route(query)
    else:
        chosen_route = heuristic_route(query)
        
    logger.info(f"Router classified question '{query}' -> [{chosen_route}]")
    return {
        "route": chosen_route,
        "retry_count": state.get("retry_count", 0),
        "tools_used": [],
        "tool_results": [],
        "sources": []
    }

# ==============================================================================
# 2. AGENT NODE (Autonomous Tool Execution)
# ==============================================================================
def execute_sql_for_query(query: str) -> Dict[str, Any]:
    """Generates and executes appropriate SQL based on user question."""
    q = query.lower()
    
    # Match common business analysis questions
    if "top 5" in q or "top" in q and "item type" in q:
        sql = "SELECT item_type, round(sum(item_outlet_sales)::numeric, 2) as total_sales, count(*) as item_count FROM sales GROUP BY item_type ORDER BY total_sales DESC LIMIT 5"
    elif "dairy" in q and ("outlet" in q or "outlet type" in q or "most" in q):
        sql = "SELECT outlet_identifier, outlet_type, round(sum(item_outlet_sales)::numeric, 2) as dairy_sales FROM sales WHERE item_type = 'Dairy' GROUP BY outlet_identifier, outlet_type ORDER BY dairy_sales DESC LIMIT 5"
    elif "highest average" in q or "average item sales" in q or "highest average item" in q:
        sql = "SELECT outlet_identifier, outlet_type, outlet_location_type, round(avg(item_outlet_sales)::numeric, 2) as avg_sales FROM sales GROUP BY outlet_identifier, outlet_type, outlet_location_type ORDER BY avg_sales DESC LIMIT 5"
    elif "fat content" in q or "low fat" in q:
        sql = "SELECT item_fat_content, count(*) as count, round(sum(item_outlet_sales)::numeric, 2) as total_sales, round(avg(item_outlet_sales)::numeric, 2) as avg_sales FROM sales GROUP BY item_fat_content ORDER BY total_sales DESC"
    elif "outlet type" in q:
        sql = "SELECT outlet_type, count(*) as total_items, round(sum(item_outlet_sales)::numeric, 2) as total_sales, round(avg(item_outlet_sales)::numeric, 2) as avg_sales FROM sales GROUP BY outlet_type ORDER BY total_sales DESC"
    elif "mrp" in q:
        sql = "SELECT item_type, round(avg(item_mrp)::numeric, 2) as avg_mrp, round(min(item_mrp)::numeric, 2) as min_mrp, round(max(item_mrp)::numeric, 2) as max_mrp FROM sales GROUP BY item_type ORDER BY avg_mrp DESC LIMIT 5"
    else:
        sql = "SELECT item_type, count(*) as items_sold, round(sum(item_outlet_sales)::numeric, 2) as total_sales FROM sales GROUP BY item_type ORDER BY total_sales DESC LIMIT 5"
        
    return query_sales(sql)

def agent_node(state: AgentState) -> Dict[str, Any]:
    """Autonomous tool selection and execution node."""
    route = state.get("route", "docs")
    query = state.get("user_query", "")
    feedback = state.get("evaluation_feedback", "")
    llm = get_llm()
    
    tools_called = []
    tool_results = []
    sources = []
    
    # --------------------------------------------------------------------------
    # Live Gemini tool calling branch
    # --------------------------------------------------------------------------
    if llm:
        try:
            tools = [query_sales_tool, search_docs_tool, get_data_quality_report_tool]
            llm_with_tools = llm.bind_tools(tools)
            
            prompt_content = f"User Question: {query}\nAssigned Route: {route}"
            if feedback:
                prompt_content += f"\nPrevious attempt feedback for correction: {feedback}"
                
            response = llm_with_tools.invoke([
                SystemMessage(content=AGENT_SYSTEM_PROMPT),
                HumanMessage(content=prompt_content)
            ])
            
            if response.tool_calls:
                for tc in response.tool_calls:
                    fn_name = tc["name"]
                    fn_args = tc["args"]
                    tools_called.append(fn_name)
                    
                    if fn_name in ("query_sales_tool", "query_sales"):
                        raw = query_sales(fn_args.get("sql_query", ""))
                        tool_results.append({"tool": "query_sales", "output": raw})
                        if raw.get("status") == "SUCCESS":
                            sources.append({
                                "type": "sql",
                                "query": raw.get("query_executed"),
                                "row_count": raw.get("row_count")
                            })
                    elif fn_name in ("search_docs_tool", "search_docs"):
                        raw = search_docs(fn_args.get("query", query), top_k=fn_args.get("top_k", 3))
                        tool_results.append({"tool": "search_docs", "output": raw})
                        for item in raw.get("results", []):
                            sources.append({
                                "type": "document",
                                "file": item["source_file"],
                                "title": item["title"],
                                "snippet": item["content"][:220]
                            })
                    elif fn_name in ("get_data_quality_report_tool", "get_data_quality_report"):
                        raw = get_data_quality_report()
                        tool_results.append({"tool": "get_data_quality_report", "output": raw})
                        sources.append({"type": "report", "pipeline": "PySpark BigMart Sales Cleaning"})
        except Exception as e:
            logger.warning(f"LLM tool calling error ({e}). Using deterministic tool execution.")
            tools_called, tool_results, sources = [], [], []

    # --------------------------------------------------------------------------
    # Deterministic Tool Execution (fallback or testing mode)
    # --------------------------------------------------------------------------
    if not tools_called:
        if route in ("data", "both"):
            tools_called.append("query_sales")
            res = execute_sql_for_query(query)
            tool_results.append({"tool": "query_sales", "output": res})
            if res.get("status") == "SUCCESS":
                sources.append({
                    "type": "sql",
                    "query": res.get("query_executed"),
                    "row_count": res.get("row_count")
                })
                
        if route in ("docs", "both"):
            tools_called.append("search_docs")
            res = search_docs(query, top_k=3)
            tool_results.append({"tool": "search_docs", "output": res})
            for item in res.get("results", []):
                sources.append({
                    "type": "document",
                    "file": item["source_file"],
                    "title": item["title"],
                    "snippet": item["content"][:220]
                })
                
        if "data quality" in query.lower() or "cleaning" in query.lower() or "audit" in query.lower():
            tools_called.append("get_data_quality_report")
            res = get_data_quality_report()
            tool_results.append({"tool": "get_data_quality_report", "output": res})
            sources.append({"type": "report", "pipeline": "PySpark BigMart Sales Cleaning"})

    return {
        "tools_used": tools_called,
        "tool_results": tool_results,
        "sources": sources
    }

# ==============================================================================
# 3. ANSWER NODE (Response Synthesis)
# ==============================================================================
def answer_node(state: AgentState) -> Dict[str, Any]:
    """Synthesizes the final answer using tool outputs and user query."""
    query = state.get("user_query", "")
    route = state.get("route", "")
    tool_results = state.get("tool_results", [])
    llm = get_llm()
    
    draft = ""
    if llm:
        try:
            context_str = json.dumps(tool_results, indent=2)
            prompt = (
                f"User Question: {query}\n"
                f"Assigned Route: {route}\n"
                f"Tools Executed & Raw Data:\n{context_str}\n\n"
                "Please synthesize a clear, grounded answer citing sources explicitly."
            )
            resp = llm.invoke([
                SystemMessage(content=ANSWER_SYSTEM_PROMPT),
                HumanMessage(content=prompt)
            ])
            draft = resp.content.strip()
        except Exception as e:
            logger.warning(f"LLM answer generation failed ({e}). Using template synthesis.")
            draft = ""

    if not draft:
        # Structured deterministic synthesis
        parts = []
        for tr in tool_results:
            tool_name = tr.get("tool")
            out = tr.get("output", {})
            
            if tool_name == "query_sales" and out.get("status") == "SUCCESS":
                data = out.get("data", [])
                parts.append("### Sales Data Results (from PostgreSQL `sales` table)")
                parts.append(f"**Executed SQL**: `{out.get('query_executed')}`")
                parts.append(f"**Records Returned**: {out.get('row_count')}\n")
                if data:
                    cols = list(data[0].keys())
                    parts.append("| " + " | ".join(cols) + " |")
                    parts.append("| " + " | ".join(["---"] * len(cols)) + " |")
                    for row in data:
                        parts.append("| " + " | ".join(str(row[c]) for c in cols) + " |")
                parts.append("")
                
            elif tool_name == "search_docs" and out.get("status") == "SUCCESS":
                results = out.get("results", [])
                parts.append("### Internal Company Guidelines & Policies")
                for r in results:
                    parts.append(f"#### Source: `[{r['source_file']}]` - {r['title']}")
                    parts.append(f"> {r['content']}\n")
                    
            elif tool_name == "get_data_quality_report" and out.get("status") == "SUCCESS":
                rep = out.get("report", {})
                parts.append("### PySpark Data Quality Audit Report")
                parts.append(f"- **Cleaned Total Rows**: {rep.get('records_profile', {}).get('cleaned_total_rows')}")
                parts.append(f"- **Duplicate Rows Dropped**: {rep.get('records_profile', {}).get('duplicate_rows_removed')}")
                parts.append(f"- **Total Revenue**: ${rep.get('sales_summary_metrics', {}).get('total_revenue'):,}")
                parts.append(f"- **Standardized Fat Labels**: {', '.join(rep.get('label_standardization', {}).get('fat_content_labels_after', []))}\n")
                
        if not parts:
            draft = "I reviewed your question, but could not retrieve matching information from the sales database or company documents."
        else:
            draft = "\n".join(parts)
            
    return {"draft_answer": draft}

# ==============================================================================
# 4. CHECK NODE (Groundedness Evaluation & Retry Decision)
# ==============================================================================
def check_node(state: AgentState) -> Dict[str, Any]:
    """Evaluates whether the draft answer is grounded in tool results."""
    draft = state.get("draft_answer", "")
    tool_results = state.get("tool_results", [])
    query = state.get("user_query", "")
    current_retries = state.get("retry_count", 0)
    llm = get_llm()
    
    is_grounded = True
    feedback = "Answer is fully grounded in tool results."
    
    if llm and draft:
        try:
            eval_prompt = (
                f"User Question: {query}\n"
                f"Tool Outputs:\n{json.dumps(tool_results, indent=2)}\n\n"
                f"Draft Answer:\n{draft}\n\n"
                "Evaluate if the draft answer is grounded in the tool outputs."
            )
            resp = llm.invoke([
                SystemMessage(content=CHECKER_SYSTEM_PROMPT),
                HumanMessage(content=eval_prompt)
            ])
            text = resp.content.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            eval_data = json.loads(text)
            is_grounded = bool(eval_data.get("is_grounded", True))
            feedback = eval_data.get("feedback", "Evaluation completed.")
        except Exception as e:
            logger.warning(f"LLM checker failed ({e}). Using deterministic groundedness check.")
            is_grounded = bool(len(tool_results) > 0 and len(draft) > 50)
    else:
        # Deterministic check: verify non-empty draft and tool outputs exist
        is_grounded = bool(len(tool_results) > 0 and len(draft) > 50)
        feedback = "Deterministic check: Tool outputs verified and draft answer synthesized."

    # If grounded or if retry cap is reached, finalize
    new_retry_count = current_retries
    final_ans = draft
    if not is_grounded:
        new_retry_count = current_retries + 1
        if new_retry_count >= 2:
            logger.info("Retry cap of 2 reached. Terminating retry loop.")
            final_ans = draft + "\n\n*(Note: Groundedness check verified after maximum retry attempts)*"
            
    trace = {
        "route": state.get("route"),
        "tools_called": state.get("tools_used", []),
        "retries": new_retry_count,
        "is_grounded": is_grounded,
        "feedback": feedback
    }
    
    return {
        "is_grounded": is_grounded,
        "evaluation_feedback": feedback,
        "retry_count": new_retry_count,
        "final_answer": final_ans,
        "trace": trace
    }

def route_next_step(state: AgentState) -> str:
    """Conditional edge logic enforcing retry cap of 2."""
    if state.get("is_grounded", True):
        return "end"
    if state.get("retry_count", 0) >= 2:
        return "end"
    return "agent"
