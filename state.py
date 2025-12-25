from typing import TypedDict, List, Dict, Any, Optional

class AgentState(TypedDict):
    messages: List[Any]  # Standard LangChain/LangGraph messages
    
    # Context
    user_query: str
    relevant_schema: str
    
    # SQL Generation & execution
    candidate_sql: str
    query_result: List[Dict[str, Any]]
    
    # Error Handling & Feedback Loop
    error: Optional[str]
    retry_count: int
    
    # Human Feedback Loop
    user_feedback: Optional[str]  # e.g., "That looks wrong, filter by X"
    
    # Output
    final_answer: str
