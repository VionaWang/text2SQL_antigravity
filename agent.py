import os
import json
from typing import Literal

from langchain_google_vertexai import ChatVertexAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END

from state import AgentState
from schema_manager import SchemaManager
from memory_bank import MemoryBank
from validators import validate_sql_safety, SQLSecurityError
from prompts import (
    SCHEMA_SELECTOR_PROMPT,
    SQL_GEN_SYSTEM,
    SQL_GEN_USER,
    SQL_FIX_USER,
    ANSWER_SYNTHESIS_PROMPT,
    ERROR_RESPONSE_PROMPT
)
from google.cloud import bigquery

# Global Lazy Managers
_llm = None
_bq_client = None
_schema_manager = None
_memory_bank = None

def get_llm():
    global _llm
    if _llm is None:
        _llm = ChatVertexAI(model="gemini-2.0-flash-exp", temperature=0)
    return _llm

def get_bq_client():
    global _bq_client
    if _bq_client is None:
        _bq_client = bigquery.Client()
    return _bq_client

def get_schema_manager():
    global _schema_manager
    if _schema_manager is None:
        _schema_manager = SchemaManager()
    return _schema_manager

def get_memory_bank():
    global _memory_bank
    if _memory_bank is None:
        _memory_bank = MemoryBank()
    return _memory_bank

# --- NODES ---

def select_schema_node(state: AgentState):
    """Determines which tables are relevant."""
    print("--- Selecting Schema ---")
    user_q = state["messages"][-1][1] if isinstance(state["messages"][-1], tuple) else state["messages"][-1].content
    
    all_tables = get_schema_manager().get_all_tables()
    
    # Limit to max 8 tables to avoid overwhelming the LLM
    MAX_TABLES_FOR_SELECTION = 8
    if len(all_tables) > MAX_TABLES_FOR_SELECTION:
        print(f"Note: Dataset has {len(all_tables)} tables, showing first {MAX_TABLES_FOR_SELECTION} for selection")
        all_tables = all_tables[:MAX_TABLES_FOR_SELECTION]
    
    prompt = SCHEMA_SELECTOR_PROMPT.format(
        all_tables=", ".join(all_tables),
        user_question=user_q
    )
    
    # Simple JSON extraction (can be improved with JsonOutputParser)
    response = get_llm().invoke(prompt)
    try:
        # Heuristic to find JSON list in response
        content = response.content.replace("```json", "").replace("```", "").strip()
        relevant_tables = json.loads(content)
        # Verify they exist
        relevant_tables = [t for t in relevant_tables if t in all_tables]
    except:
        # Fallback: Use first 3 tables (safer for token limits)
        relevant_tables = all_tables[:3]
    
    # Limit to max 3 tables to reduce token usage
    if len(relevant_tables) > 3:
        print(f"Limiting from {len(relevant_tables)} to 3 tables to reduce token usage")
        relevant_tables = relevant_tables[:3]
        
    schema_context = get_schema_manager().get_formatted_schema_context(relevant_tables, max_tables=3)
    
    return {
        "user_query": user_q,
        "relevant_schema": schema_context,
         # If this is a retry loop, keep existing context
    }

def generate_sql_node(state: AgentState):
    """Generates SQL using Schema + Few-Shot Examples."""
    print("--- Generating SQL ---")
    question = state["user_query"]
    schema = state["relevant_schema"]
    
    # Retrieve examples (limit to 2 to save tokens)
    examples = get_memory_bank().retrieve_examples(question, k=2)
    few_shot_str = "\n".join([f"Q: {e['question']}\nSQL: {e['sql']}" for e in examples])
    
    # Build conversation context (limit to last 3 exchanges to save tokens)
    conversation_history = state.get("conversation_history", [])
    if conversation_history:
        recent_history = conversation_history[-3:]  # Last 3 Q&A pairs
        conv_context = "Recent conversation:\n" + "\n".join([
            f"Previous Q: {item['question']}\nPrevious SQL: {item['sql']}\nPrevious Answer: {item.get('answer', 'N/A')}"
            for item in recent_history
        ])
    else:
        conv_context = "No previous conversation."
    
    if state.get("error"):
        # Fix Mode
        instruction = SQL_FIX_USER.format(
            candidate_sql=state["candidate_sql"],
            error=state["error"]
        )
    else:
        # Normal Mode
        instruction = SQL_GEN_USER.format(user_question=question)
    
    system_prompt = SQL_GEN_SYSTEM.format(
        conversation_context=conv_context,
        schema_context=schema,
        few_shot_examples=few_shot_str,
        instruction=instruction
    )
    
    response = get_llm().invoke(system_prompt)
    
    # Clean up SQL (remove markdown code blocks and language prefixes)
    sql = response.content.replace("```sql", "").replace("```", "").strip()
    
    # Remove common language prefixes that LLM might add
    for prefix in ["googlesql", "sql", "bigquery", "bq"]:
        if sql.lower().startswith(prefix):
            sql = sql[len(prefix):].strip()
            break
    
    # Check if LLM refused to generate SQL due to security policy
    if "SECURITY_VIOLATION" in sql:
        return {"candidate_sql": sql, "error": "Security Alert: Request involves data modification which is not allowed."}
    
    return {"candidate_sql": sql}

def validate_and_execute_node(state: AgentState):
    """Validates safety and executes against BigQuery."""
    print("--- Executing SQL ---")
    sql = state["candidate_sql"]
    
    # 1. Safety Check
    try:
        validate_sql_safety(sql)
    except SQLSecurityError as e:
        return {"error": str(e), "retry_count": state.get("retry_count", 0) + 1, "query_result": []}
        
    # 2. Execution
    try:
        # Add LIMIT to query if not present to prevent huge result sets
        sql_upper = sql.upper()
        if 'LIMIT' not in sql_upper:
            # Add LIMIT 100 to prevent massive results
            sql = sql.rstrip(';').rstrip() + ' LIMIT 100'
            print(f"⚠️ Added LIMIT 100 to query (no LIMIT clause found)")
        
        query_job = get_bq_client().query(sql)
        
        # Fetch results with a hard limit
        MAX_ROWS = 100
        results = []
        for i, row in enumerate(query_job):
            if i >= MAX_ROWS:
                print(f"⚠️ Truncated results at {MAX_ROWS} rows")
                break
            results.append(dict(row))
        
        # Convert non-serializable types (datetime, date) to str for LLM
        for row in results:
            for k, v in row.items():
                if hasattr(v, 'isoformat'):
                    row[k] = v.isoformat()
                    
        return {"query_result": results, "error": None}
        
    except Exception as e:
        return {"error": str(e), "retry_count": state.get("retry_count", 0) + 1, "query_result": []}

def synthesize_answer_node(state: AgentState):
    """Formats the answer."""
    print("--- Synthesizing ---")
    
    if state.get("error"):
        prompt = ERROR_RESPONSE_PROMPT.format(
            user_question=state["user_query"],
            error=state["error"]
        )
    else:
        # CRITICAL: Limit query result size to prevent token overflow
        query_result = state.get("query_result", [])
        
        # Limit to first 50 rows
        if len(query_result) > 50:
            query_result = query_result[:50]
            result_note = f"\n(Showing first 50 of {len(state.get('query_result', []))} rows)"
        else:
            result_note = ""
        
        # Convert to string and truncate if still too long
        result_str = str(query_result)
        MAX_RESULT_CHARS = 2000  # Limit to ~500 tokens
        if len(result_str) > MAX_RESULT_CHARS:
            result_str = result_str[:MAX_RESULT_CHARS] + f"...\n(truncated, total {len(query_result)} rows)"
        
        result_str += result_note
        
        prompt = ANSWER_SYNTHESIS_PROMPT.format(
            user_question=state["user_query"],
            candidate_sql=state["candidate_sql"],
            query_result=result_str
        )
        
    response = get_llm().invoke(prompt)
    return {"final_answer": response.content}

def human_feedback_node(state: AgentState):
    """
    Placeholder for human feedback. 
    In a real app, this would pause execution.
    For this CLI MVP, we'll assume implicit approval if we reach here, 
    OR we could actually prompt the user in the CLI loop.
    
    For now, let's just pass through to save.
    """
    return {"user_feedback": "approved"} 

def save_knowledge_node(state: AgentState):
    """Saves the successful query to memory bank."""
    print("--- Saving Knowledge ---")
    if not state.get("error"):
        get_memory_bank().save_example(state["user_query"], state["candidate_sql"])
    return {}

# --- EDGES ---

def should_execute_sql(state: AgentState) -> Literal["execute_sql", "synthesize_answer"]:
    """Decide whether to execute SQL or skip to synthesis if there's already an error."""
    if state.get("error"):
        # Error already detected (e.g., from LLM refusing to generate SQL)
        return "synthesize_answer"
    return "execute_sql"

def should_retry(state: AgentState) -> Literal["generate_sql", "synthesize_answer"]:
    if state.get("error"):
        error_msg = str(state["error"])
        # Stop immediate retry if it's a security violation
        if "Security Alert" in error_msg:
            print(f"--- Security Violation: {error_msg} (No Retry) ---")
            return "synthesize_answer"

        if state["retry_count"] <= 3:
            print(f"--- Retry {state['retry_count']} due to error: {state['error']} ---")
            return "generate_sql"
        else:
            print("--- Max retries reached ---")
            # In a real app, we might go to a "failure" node. 
            # Here we just try to explain the error in synthesis
            return "synthesize_answer" 
    return "synthesize_answer"

# --- GRAPH ---

def build_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("select_schema", select_schema_node)
    workflow.add_node("generate_sql", generate_sql_node)
    workflow.add_node("execute_sql", validate_and_execute_node)
    workflow.add_node("synthesize_answer", synthesize_answer_node)
    workflow.add_node("save_knowledge", save_knowledge_node)
    
    workflow.set_entry_point("select_schema")
    
    workflow.add_edge("select_schema", "generate_sql")
    
    workflow.add_conditional_edges(
        "generate_sql",
        should_execute_sql,
    )
    
    workflow.add_conditional_edges(
        "execute_sql",
        should_retry,
    )
    
    workflow.add_edge("synthesize_answer", "save_knowledge")
    workflow.add_edge("save_knowledge", END)
    
    return workflow.compile()
