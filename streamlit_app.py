import streamlit as st
import dotenv
from datetime import datetime
from agent import build_graph
from memory_bank import MemoryBank
from schema_manager import SchemaManager
from db_manager import DatabaseManager
import pandas as pd
from pygments import highlight
from pygments.lexers import SqlLexer
from pygments.formatters import HtmlFormatter

# Load environment variables
dotenv.load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Text2SQL Agent",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .stApp {
        max-width: 100%;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: column;
    }
    .user-message {
        background-color: #e3f2fd;
    }
    .agent-message {
        background-color: #f5f5f5;
    }
    .sql-block {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #4CAF50;
        margin: 0.5rem 0;
    }
    .error-block {
        background-color: #ffebee;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #f44336;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'graph' not in st.session_state:
    st.session_state.graph = None
if 'db' not in st.session_state:
    st.session_state.db = DatabaseManager()

def highlight_sql(sql_code):
    """Syntax highlight SQL code."""
    formatter = HtmlFormatter(style='colorful', noclasses=True)
    highlighted = highlight(sql_code, SqlLexer(), formatter)
    return highlighted

def run_query(user_input):
    """Run a query through the agent."""
    if st.session_state.graph is None:
        with st.spinner("Initializing agent..."):
            st.session_state.graph = build_graph()
    
    # Build conversation history from previous messages
    conversation_history = []
    i = 0
    while i < len(st.session_state.messages):
        msg = st.session_state.messages[i]
        if msg["role"] == "user":
            # Look for the corresponding agent response
            if i + 1 < len(st.session_state.messages) and st.session_state.messages[i + 1]["role"] == "agent":
                agent_msg = st.session_state.messages[i + 1]
                conversation_history.append({
                    "question": msg["content"],
                    "sql": agent_msg.get("sql", ""),
                    "answer": agent_msg.get("content", "")
                })
                i += 2  # Skip both user and agent message
            else:
                i += 1
        else:
            i += 1
    
    # Get previous SQL if available
    previous_sql = None
    if st.session_state.messages:
        for msg in reversed(st.session_state.messages):
            if msg["role"] == "agent" and "sql" in msg and msg["sql"]:
                previous_sql = msg["sql"]
                break
    
    # Initial State
    initial_state = {
        "user_query": user_input,
        "messages": [("user", user_input)],
        "retry_count": 0,
        "error": None,
        "query_result": [],
        "conversation_history": conversation_history,
        "previous_sql": previous_sql
    }
    
    final_response = ""
    generated_sql = ""
    error = None
    result_summary = ""
    
    # Stream through the graph
    with st.spinner("🤔 Thinking..."):
        for event in st.session_state.graph.stream(initial_state):
            for node_name, state_update in event.items():
                if state_update is None:
                    continue
                
                if "candidate_sql" in state_update:
                    generated_sql = state_update["candidate_sql"]
                
                if "error" in state_update and state_update["error"]:
                    error = state_update["error"]
                
                if "final_answer" in state_update:
                    final_response = state_update["final_answer"]
                
                if "query_result" in state_update and state_update["query_result"]:
                    result_summary = f"{len(state_update['query_result'])} rows returned"
    
    # Save to query history
    st.session_state.db.save_query_history(
        user_query=user_input,
        generated_sql=generated_sql if generated_sql else None,
        result_summary=result_summary if result_summary else None,
        error=error
    )
    
    return {
        "response": final_response,
        "sql": generated_sql,
        "error": error
    }

# Sidebar
with st.sidebar:
    st.title("🔍 Text2SQL Agent")
    st.markdown("---")
    
    # Navigation
    page = st.radio(
        "Navigation",
        ["💬 Chat", "📊 Query History", "📚 Training Data", "🗂️ Schema Browser"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    
    # Info
    st.markdown("### ℹ️ Info")
    st.markdown("**Dataset:** `bigquery-public-data.thelook_ecommerce`")
    st.markdown("**Model:** Gemini 2.0 Flash")
    
    st.markdown("---")
    
    # Stats
    st.markdown("### 📈 Stats")
    training_count = len(st.session_state.db.get_training_examples())
    history_count = len(st.session_state.db.get_query_history())
    st.metric("Training Examples", training_count)
    st.metric("Query History", history_count)

# Main content area
if page == "💬 Chat":
    st.title("💬 Chat with your Data")
    st.markdown("Ask questions about the TheLook eCommerce dataset in natural language.")
    
    # Display chat history
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f"""
            <div class="chat-message user-message">
                <strong>You:</strong><br>{msg["content"]}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="chat-message agent-message">
                <strong>Agent:</strong><br>{msg["content"]}
            </div>
            """, unsafe_allow_html=True)
            
            if "sql" in msg and msg["sql"]:
                with st.expander("📝 View Generated SQL"):
                    st.code(msg["sql"], language="sql")
            
            if "error" in msg and msg["error"]:
                st.markdown(f"""
                <div class="error-block">
                    <strong>⚠️ Error:</strong> {msg["error"]}
                </div>
                """, unsafe_allow_html=True)
    
    # Chat input
    user_input = st.chat_input("Ask a question about your data...")
    
    if user_input:
        # Add user message
        st.session_state.messages.append({
            "role": "user",
            "content": user_input
        })
        
        # Get agent response
        result = run_query(user_input)
        
        # Add agent message
        st.session_state.messages.append({
            "role": "agent",
            "content": result["response"],
            "sql": result["sql"],
            "error": result["error"]
        })
        
        # Rerun to display new messages
        st.rerun()
    
    # Clear chat button
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()

elif page == "📊 Query History":
    st.title("📊 Query History")
    st.markdown("View your past queries and their results.")
    
    # Get history
    history = st.session_state.db.get_query_history(limit=100)
    
    if not history:
        st.info("No query history yet. Start chatting to see your queries here!")
    else:
        # Filter options
        col1, col2 = st.columns([3, 1])
        with col1:
            search = st.text_input("🔍 Search queries", "")
        with col2:
            if st.button("🗑️ Clear History"):
                st.session_state.db.clear_query_history()
                st.success("History cleared!")
                st.rerun()
        
        # Display history
        for entry in history:
            if search.lower() in entry["user_query"].lower():
                with st.expander(f"🕐 {entry['timestamp']} - {entry['user_query'][:100]}..."):
                    st.markdown(f"**Query:** {entry['user_query']}")
                    
                    if entry["generated_sql"]:
                        st.markdown("**Generated SQL:**")
                        st.code(entry["generated_sql"], language="sql")
                    
                    if entry["result_summary"]:
                        st.markdown(f"**Result:** {entry['result_summary']}")
                    
                    if entry["error"]:
                        st.error(f"**Error:** {entry['error']}")

elif page == "📚 Training Data":
    st.title("📚 Training Data Management")
    st.markdown("View and manage your training examples for few-shot learning.")
    
    # Get training examples
    examples = st.session_state.db.get_training_examples()
    
    # Add new example
    with st.expander("➕ Add New Training Example"):
        with st.form("add_example"):
            question = st.text_input("Question")
            sql = st.text_area("SQL Query")
            submitted = st.form_submit_button("Add Example")
            
            if submitted and question and sql:
                memory_bank = MemoryBank()
                memory_bank.save_example(question, sql)
                st.success("Example added!")
                st.rerun()
    
    st.markdown("---")
    
    # Display examples
    if not examples:
        st.info("No training examples yet. Add some to improve the agent's performance!")
    else:
        st.markdown(f"### {len(examples)} Training Examples")
        
        # Search
        search = st.text_input("🔍 Search examples", "")
        
        for example in examples:
            if search.lower() in example["question"].lower() or search.lower() in example["sql"].lower():
                col1, col2 = st.columns([10, 1])
                
                with col1:
                    with st.expander(f"Q: {example['question'][:100]}..."):
                        st.markdown(f"**Question:** {example['question']}")
                        st.markdown(f"**SQL:**")
                        st.code(example["sql"], language="sql")
                        st.markdown(f"**Created:** {example['created_at']}")
                        st.markdown(f"**Success Count:** {example['success_count']}")
                
                with col2:
                    if st.button("🗑️", key=f"delete_{example['id']}"):
                        st.session_state.db.delete_training_example(example['id'])
                        st.success("Deleted!")
                        st.rerun()

elif page == "🗂️ Schema Browser":
    st.title("🗂️ Database Schema Browser")
    st.markdown("Explore the structure of your database.")
    
    schema_manager = SchemaManager()
    
    # Get all tables
    tables = schema_manager.get_all_tables()
    
    st.markdown(f"### {len(tables)} Tables Available")
    
    # Table selector
    selected_table = st.selectbox("Select a table to view its schema:", tables)
    
    if selected_table:
        schema_info = schema_manager.get_table_schema(selected_table)
        
        st.markdown(f"### Table: `{selected_table}`")
        st.text(schema_info)
        
        # Show relationships
        st.markdown("### Common Relationships")
        st.markdown("""
        - `users.id` = `orders.user_id`
        - `orders.order_id` = `order_items.order_id`
        - `products.id` = `order_items.product_id`
        - `products.id` = `inventory_items.product_id`
        """)

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666;'>Built with Streamlit • Powered by Gemini 2.0 Flash</div>",
    unsafe_allow_html=True
)
