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
    ANSWER_SYNTHESIS_PROMPT
)
from google.cloud import bigquery

# Initialize LLM
llm = ChatVertexAI(model="gemini-2.0-flash-exp", temperature=0)

# Initialize Managers
schema_manager = SchemaManager()
memory_bank = MemoryBank()
bq_client = bigquery.Client()

# --- NODES ---

def select_schema_node(state: AgentState):
    """Determines which tables are relevant."""
    print("--- Selecting Schema ---")
    user_q = state["messages"][-1][1] if isinstance(state["messages"][-1], tuple) else state["messages"][-1].content
    
    all_tables = schema_manager.get_all_tables()
    
    prompt = SCHEMA_SELECTOR_PROMPT.format(
        all_tables=", ".join(all_tables),
        user_question=user_q
    )
    
    # Simple JSON extraction (can be improved with JsonOutputParser)
    response = llm.invoke(prompt)
    try:
        # Heuristic to find JSON list in response
        content = response.content.replace("```json", "").replace("```", "").strip()
        relevant_tables = json.loads(content)
        # Verify they exist
        relevant_tables = [t for t in relevant_tables if t in all_tables]
    except:
        # Fallback: All tables (safer for small schema)
        relevant_tables = all_tables
        
    schema_context = schema_manager.get_formatted_schema_context(relevant_tables)
    
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
    
    # Retrieve examples
    examples = memory_bank.retrieve_examples(question)
    few_shot_str = "\n".join([f"Q: {e['question']}\nSQL: {e['sql']}" for e in examples])
    
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
        schema_context=schema,
        few_shot_examples=few_shot_str,
        instruction=instruction
    )
    
    response = llm.invoke(system_prompt)
    
    # Clean up SQL (remove markdown code blocks)
    sql = response.content.replace("```sql", "").replace("```", "").strip()
    
    return {"candidate_sql": sql}

def validate_and_execute_node(state: AgentState):
    """Validates safety and executes against BigQuery."""
    print("--- Executing SQL ---")
    sql = state["candidate_sql"]
    
    # 1. Safety Check
    try:
        validate_sql_safety(sql)
    except SQLSecurityError as e:
        return {"error": str(e), "retry_count": state.get("retry_count", 0) + 1}
        
    # 2. Execution
    try:
        query_job = bq_client.query(sql)
        results = [dict(row) for row in query_job]
        
        # Convert non-serializable types (datetime, date) to str for LLM
        for row in results:
            for k, v in row.items():
                if hasattr(v, 'isoformat'):
                    row[k] = v.isoformat()
                    
        return {"query_result": results, "error": None}
        
    except Exception as e:
        return {"error": str(e), "retry_count": state.get("retry_count", 0) + 1}

def synthesize_answer_node(state: AgentState):
    """Formats the answer."""
    print("--- Synthesizing ---")
    prompt = ANSWER_SYNTHESIS_PROMPT.format(
        user_question=state["user_query"],
        candidate_sql=state["candidate_sql"],
        query_result=str(state["query_result"])
    )
    response = llm.invoke(prompt)
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
        memory_bank.save_example(state["user_query"], state["candidate_sql"])
    return {}

# --- EDGES ---

def should_retry(state: AgentState) -> Literal["generate_sql", "synthesize_answer"]:
    if state.get("error"):
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
    workflow.add_edge("generate_sql", "execute_sql")
    
    workflow.add_conditional_edges(
        "execute_sql",
        should_retry,
    )
    
    workflow.add_edge("synthesize_answer", "save_knowledge")
    workflow.add_edge("save_knowledge", END)
    
    return workflow.compile()
