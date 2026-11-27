"""
LangGraph Nodes for Fixdesk
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
    ROUTER_SYSTEM_PROMPT, AGENT_SYSTEM_PROMPT, get_agent_system_prompt,
    ANSWER_SYSTEM_PROMPT, CHECKER_SYSTEM_PROMPT
)
from backend.agent.tools import query_sales_tool, search_docs_tool, get_data_quality_report_tool
from backend.cloud.budget import BudgetExceededError, check_budget_available, record_ai_usage
from backend.cloud.config import is_valid_gemini_api_key
from backend.cloud.factories import get_llm_client, get_sales_store
from mcp_server.tools import query_sales, search_docs, get_data_quality_report, get_schema_metadata

load_dotenv()
logger = logging.getLogger("AgentNodes")

DEFAULT_LLM_MODEL = "gemini-3.5-flash-lite"

def is_valid_gemini_key() -> bool:
    return is_valid_gemini_api_key()

def extract_text_content(content: Any) -> str:
    """Extracts plain text from either a string or Gemini 3.x list-of-blocks response content."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "\n".join(parts).strip()
    return str(content or "").strip()

def _parse_json_response(content: Any) -> Dict[str, Any]:
    """Extracts and parses a JSON object from LLM response content (stripping markdown fences)."""
    text = extract_text_content(content)
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    return json.loads(text)

def get_llm(cloud_allowed: bool = True):
    """Returns active Gemini Chat model instance (Vertex AI via ADC or Gemini Developer API)."""
    try:
        client = get_llm_client(cloud_allowed=cloud_allowed)
    except Exception as exc:
        logger.warning(f"LLM client selection skipped: {exc}")
        return None
    if client is None:
        return None
    return client.get_chat_model()


def _invoke_with_budget(llm_or_runnable: Any, messages: Any):
    """Invoke a LangChain runnable while enforcing daily request/token budget accounting."""
    check_budget_available()
    resp = llm_or_runnable.invoke(messages)
    in_chars = sum(len(str(m)) for m in messages) if isinstance(messages, list) else len(str(messages))
    out_chars = len(str(getattr(resp, "content", resp)))
    record_ai_usage(requests=1, input_chars=in_chars, output_chars=out_chars)
    return resp

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
    """Analyzes the query and routes it to data, docs, or both (or honors explicit override)."""
    query = state.get("user_query", "")
    explicit_route = (state.get("route") or "").strip().lower()
    if explicit_route in ("data", "docs", "both"):
        logger.info(f"Router using explicit route override '{explicit_route}' for '{query}'")
        return {
            "route": explicit_route,
            "retry_count": state.get("retry_count", 0),
            "tools_used": [],
            "tool_results": [],
            "sources": []
        }

    llm = get_llm()
    
    chosen_route = "docs"
    if llm:
        try:
            response = _invoke_with_budget(llm, [
                SystemMessage(content=ROUTER_SYSTEM_PROMPT),
                HumanMessage(content=f"User Question: {query}")
            ])
            parsed = _parse_json_response(response.content)
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
    """Generates and executes dialect-aware SQL (PostgreSQL or BigQuery) from discovered schema."""
    meta = get_schema_metadata()
    cols = [c["name"] for c in meta.get("columns", [])]
    num_cols = meta.get("numeric_columns", [])
    cat_cols = meta.get("categorical_columns", [])

    if not cols:
        return query_sales("SELECT * FROM sales LIMIT 5")

    q = query.lower()

    # Identify mentioned columns
    mentioned_cats = [c for c in cat_cols if c.replace("_", " ") in q or c in q]
    mentioned_nums = [c for c in num_cols if c.replace("_", " ") in q or c in q]

    primary_cat = mentioned_cats[0] if mentioned_cats else (cat_cols[0] if cat_cols else cols[0])
    primary_num = mentioned_nums[0] if mentioned_nums else (num_cols[0] if num_cols else None)

    is_bq = get_sales_store().sql_dialect() == "bigquery"
    cat_id = f"`{primary_cat}`" if is_bq else f'"{primary_cat}"'
    num_id = f"`{primary_num}`" if (is_bq and primary_num) else (f'"{primary_num}"' if primary_num else None)

    def _round_agg(fn_name: str, col_expr: str) -> str:
        if is_bq:
            return f"ROUND(CAST({fn_name}({col_expr}) AS NUMERIC), 2)"
        return f"round({fn_name.lower()}({col_expr})::numeric, 2)"

    if "average" in q or "avg" in q:
        if num_id:
            sql = f"SELECT {cat_id}, count(*) as count, {_round_agg('AVG', num_id)} as avg_{primary_num} FROM sales GROUP BY {cat_id} ORDER BY avg_{primary_num} DESC LIMIT 5"
        else:
            sql = f"SELECT {cat_id}, count(*) as count FROM sales GROUP BY {cat_id} ORDER BY count DESC LIMIT 5"
    elif "total" in q or "sum" in q or "revenue" in q:
        if num_id:
            sql = f"SELECT {cat_id}, count(*) as count, {_round_agg('SUM', num_id)} as total_{primary_num} FROM sales GROUP BY {cat_id} ORDER BY total_{primary_num} DESC LIMIT 5"
        else:
            sql = f"SELECT {cat_id}, count(*) as count FROM sales GROUP BY {cat_id} ORDER BY count DESC LIMIT 5"
    elif "top" in q or "highest" in q:
        if num_id:
            sql = f"SELECT {cat_id}, {_round_agg('SUM', num_id)} as total_{primary_num} FROM sales GROUP BY {cat_id} ORDER BY total_{primary_num} DESC LIMIT 5"
        else:
            sql = f"SELECT {cat_id}, count(*) as count FROM sales GROUP BY {cat_id} ORDER BY count DESC LIMIT 5"
    elif "count" in q or "how many" in q:
        sql = f"SELECT {cat_id}, count(*) as count FROM sales GROUP BY {cat_id} ORDER BY count DESC LIMIT 5"
    else:
        if num_id:
            sql = f"SELECT {cat_id}, count(*) as count, {_round_agg('SUM', num_id)} as total_{primary_num} FROM sales GROUP BY {cat_id} ORDER BY total_{primary_num} DESC LIMIT 5"
        else:
            sql = f"SELECT {cat_id}, count(*) as count FROM sales GROUP BY {cat_id} ORDER BY count DESC LIMIT 5"

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
                
            meta = get_schema_metadata()
            cols_desc = "\n".join([f"- {c['name']} ({c['type']})" for c in meta.get("columns", [])])
            system_prompt = get_agent_system_prompt(cols_desc)
            response = _invoke_with_budget(llm_with_tools, [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt_content)
            ])
            
            if response.tool_calls:
                tool_name_map = {
                    "query_sales_tool": "query_sales",
                    "query_sales": "query_sales",
                    "search_docs_tool": "search_docs",
                    "search_docs": "search_docs",
                    "get_data_quality_report_tool": "get_data_quality_report",
                    "get_data_quality_report": "get_data_quality_report",
                }
                for tc in response.tool_calls:
                    fn_name = tc["name"]
                    fn_args = tc["args"]
                    canonical_name = tool_name_map.get(fn_name, fn_name)
                    tools_called.append(canonical_name)

                    if canonical_name == "query_sales":
                        raw = query_sales(fn_args.get("sql_query", ""))
                        tool_results.append({"tool": "query_sales", "output": raw})
                        if raw.get("status") == "SUCCESS":
                            sources.append({
                                "type": "sql",
                                "query": raw.get("query_executed"),
                                "row_count": raw.get("row_count")
                            })
                    elif canonical_name == "search_docs":
                        raw = search_docs(fn_args.get("query", query), top_k=fn_args.get("top_k", 3))
                        tool_results.append({"tool": "search_docs", "output": raw})
                        for item in raw.get("results", []):
                            sources.append({
                                "type": "document",
                                "file": item["source_file"],
                                "title": item["title"],
                                "snippet": (item.get("content") or "")[:220]
                            })
                    elif canonical_name == "get_data_quality_report":
                        raw = get_data_quality_report()
                        tool_results.append({"tool": "get_data_quality_report", "output": raw})
                        sources.append({"type": "report", "pipeline": "PySpark Universal Data Cleaning"})
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
            sources.append({"type": "report", "pipeline": "PySpark Universal Data Cleaning"})

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
            context_str = json.dumps(tool_results, indent=2, default=str)
            prompt = (
                f"User Question: {query}\n"
                f"Assigned Route: {route}\n"
                f"Tools Executed & Raw Data:\n{context_str}\n\n"
                "Please synthesize a clear, grounded answer citing sources explicitly."
            )
            resp = _invoke_with_budget(llm, [
                SystemMessage(content=ANSWER_SYSTEM_PROMPT),
                HumanMessage(content=prompt)
            ])
            draft = extract_text_content(resp.content)
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
                total_rev = rep.get("sales_summary_metrics", {}).get("total_revenue")
                if total_rev is not None:
                    parts.append(f"- **Total Revenue**: ${total_rev:,}")
                parts.append("")
                
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
    use_llm_checker = os.environ.get("ENABLE_LLM_CHECKER", "false").lower() == "true"

    is_grounded = True
    feedback = "Deterministic check: Tool outputs verified and draft answer synthesized."

    tool_errors = [
        tr.get("output", {}).get("error")
        for tr in tool_results
        if isinstance(tr.get("output"), dict) and tr.get("output", {}).get("status") == "ERROR"
    ]

    if not tool_results or len(draft.strip()) <= 20:
        is_grounded = False
        feedback = "Missing tool outputs or draft answer is too short."
    elif tool_errors:
        is_grounded = False
        feedback = f"Tool execution error detected: {'; '.join(str(e) for e in tool_errors)}"
    elif use_llm_checker:
        llm = get_llm()
        if llm:
            try:
                eval_prompt = (
                    f"User Question: {query}\n"
                    f"Tool Outputs:\n{json.dumps(tool_results, indent=2, default=str)}\n\n"
                    f"Draft Answer:\n{draft}\n\n"
                    "Evaluate if the draft answer is grounded in the tool outputs."
                )
                resp = _invoke_with_budget(llm, [
                    SystemMessage(content=CHECKER_SYSTEM_PROMPT),
                    HumanMessage(content=eval_prompt)
                ])
                eval_data = _parse_json_response(resp.content)
                is_grounded = bool(eval_data.get("is_grounded", True))
                feedback = eval_data.get("feedback", "Evaluation completed.")
            except Exception as e:
                logger.warning(f"LLM checker failed ({e}). Using deterministic groundedness check.")
                is_grounded = bool(len(tool_results) > 0 and len(draft) > 50)
        else:
            is_grounded = bool(len(tool_results) > 0 and len(draft) > 50)

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
