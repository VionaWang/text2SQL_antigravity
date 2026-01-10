# Vertex AI Text2SQL Chatbot with LangGraph & BigQuery

A "Practical MVP" agentic chatbot that converts natural language questions into SQL queries, executes them against Google BigQuery, and explains the results. It is built using **LangGraph** for orchestration and **Vertex AI (Gemini)** for reasoning.

## 🚀 Features

*   **Non-Linear Agent Flow**: Uses LangGraph to orchestrate a cyclic workflow (Schema Selection -> SQL Gen -> Execution -> Self-Correction).
*   **Self-Correction**: If a generated query fails or is unsafe, the agent analyzes the error and retries (up to 3 times).
*   **Security First**: Strict SQL validation prevents `DROP`, `DELETE`, `INSERT`, etc. Only `SELECT` is allowed.
*   **Evolutionary Memory**: Successful Q&A pairs are saved to `training_data.jsonl` and used as few-shot examples for future queries, making the agent smarter over time.
*   **Multi-Table Support**: Works with the complex `thelook_ecommerce` public dataset (7+ tables).
*   **Model Agnostic**: Configured for `gemini-2.0-flash-exp` (but supports other Vertex models).

## 🛠️ Architecture

1.  **SchemaSelector**: Dynamically selects relevant tables based on the user question.
2.  **SQLGenerator**: Generates SQL using few-shot prompts from the Memory Bank.
3.  **SQLSanitizer**: Validates the query for safety (no DML/DDL).
4.  **SQLExecutor**: Runs the query on BigQuery.
5.  **ErrorReflector**: If execution fails, analyzes the error and routes back to SQLGenerator.
6.  **AnswerBuilder**: Converts the data result into a natural language response.
7.  **KnowledgeSaver**: Saves successful transactions to the Memory Bank.

## 📋 Prerequisites

1.  **Google Cloud Project**: You need an active GCP project.
2.  **BigQuery Access**: Access to `bigquery-public-data` (default for all GCP projects).
3.  **Vertex AI**:
    *   API Enabled (`aiplatform.googleapis.com`).
    *   **Crucial**: You must enable the specific model (e.g., **Gemini 2.0 Flash Experimental**) in the **Vertex AI Model Garden**.
4.  **Authentication**: Local credentials via `gcloud auth application-default login`.

## 📦 Installation

1.  Clone the repository:
    ```bash
    git clone <your-repo-url>
    cd text2SQL
    ```

2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

3.  Configure Environment:
    Copy `.env.example` to `.env` (optional if using default `us-central1` and inferred project ID):
    ```bash
    cp .env.example .env
    ```
    *   If needed, edit `.env` to set `GOOGLE_CLOUD_PROJECT` and `BQ_LOCATION`.

## 🏃 Usage

### Web Interface (Streamlit) - Recommended ✨
Run the Streamlit web app for a modern, interactive UI:
```bash
streamlit run streamlit_app.py
```

The web interface provides:
- 💬 **Chat Interface**: Interactive conversation with the agent
- 📊 **Query History**: View and search past queries
- 📚 **Training Data Management**: Add, view, and delete training examples
- 🗂️ **Schema Browser**: Explore database tables and relationships

The app will open automatically in your browser at `http://localhost:8501`

### Interactive Chat (CLI)
Run the main script to start a conversation loop:
```bash
python main.py
```

### Run Automated Verification
Run the test suite to verify connectivity, logic, and safety:
```bash
python test_runner.py
```

### Debugging Model Access
If you encounter `404 Not Found` errors for the LLM, run the debug script to scan available models in your region:
```bash
python check_models.py
```

## 🧠 Memory Bank
The agent "learns" by saving successful queries to a **SQLite database** (`text2sql.db`). This database stores:
- **Training Examples**: Few-shot examples that improve query generation
- **Schema Cache**: Cached BigQuery schema information for faster lookups
- **Query History**: Complete history of all queries and their results

The system automatically migrates data from legacy JSON/JSONL files on first run. You can manage training examples through the Streamlit web interface or by directly accessing the database.

## 🛡️ License
[MIT](LICENSE)
