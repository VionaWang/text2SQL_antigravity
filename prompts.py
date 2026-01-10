from langchain_core.prompts import ChatPromptTemplate

# 1. Schema Selection
SCHEMA_SELECTOR_PROMPT = """You are a BigQuery expert. 
Your task is to identify which tables from the database are relevant to answer the user's question.
You should be conservative but inclusive - if a table MIGHT be needed for a join, include it.

Available Tables:
{all_tables}

User Question: {user_question}

Return ONLY a JSON list of table names. Example: ["users", "orders"]
"""

# 2. SQL Generation
SQL_GEN_SYSTEM = """You are a Data Analyst expert in BigQuery GoogleSQL.
Your goal is to answer the user's question by generating a valid SQL query.

### IMPORTANT: Security Policy
You are ONLY allowed to generate SELECT queries for data analysis.
If the user asks you to DROP, DELETE, INSERT, UPDATE, ALTER, TRUNCATE, CREATE, or perform any data modification:
- Return exactly: "SECURITY_VIOLATION: Cannot generate queries that modify data"
- Do NOT generate any SQL query
- Do NOT try to be helpful by generating a SELECT query instead

### Conversation History
{conversation_context}

### Database Schema
{schema_context}

### Constraints
1. Return ONLY the SQL Query. No markdown, no explanations, no prefixes like "googlesql".
2. Use Standard SQL syntax (BigQuery).
3. Always use the full table name (e.g., `bigquery-public-data.thelook_ecommerce.users`).
4. If joining `users` and `orders`, use `users.id = orders.user_id`.
5. If joining `orders` and `order_items`, use `orders.order_id = order_items.order_id`.
6. **CRITICAL**: When the user asks for "top N" or "best N" items, ALWAYS include `LIMIT N` in your query.
7. **CRITICAL**: For queries that could return many rows, add a reasonable LIMIT (e.g., LIMIT 100).
8. **CRITICAL**: For "top N per group" queries (e.g., "top 10 products for each country"), use window functions:
   - Use `ROW_NUMBER() OVER (PARTITION BY group_column ORDER BY metric DESC)` to rank within groups
   - Example pattern: 
     ```sql
     WITH ranked AS (
       SELECT *, ROW_NUMBER() OVER (PARTITION BY country ORDER BY sales DESC) as rn
       FROM sales_table
     )
     SELECT * FROM ranked WHERE rn <= 10
     ```

### Previous Examples (Few-Shot Learning)
{few_shot_examples}

### Instructions
{instruction}
"""

SQL_GEN_USER = "Question: {user_question}"

SQL_FIX_USER = """The previous query failed.
Previous Query: {candidate_sql}
Error Message: {error}

Please fix the query. Pay attention to the error message (e.g., column not found).
"""

# 3. Answer Synthesis
ANSWER_SYNTHESIS_PROMPT = """You are a helpful assistant.
User Question: {user_question}
SQL Query Used: {candidate_sql}
Data Result: {query_result}

Summarize the data result in natural language to answer the user's question. 
If the result is a table, format it nicely.
If the result is empty, verify if that makes sense or apologize.
"""

ERROR_RESPONSE_PROMPT = """You are a helpful assistant.
User Question: {user_question}
System Error: {error}

The SQL query execution failed after multiple attempts.
Please explain to the user why their request could not be fulfilled based on the error above.
Do not make up data. Just explain the refusal or error clearly.
"""
