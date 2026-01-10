import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

DATABASE_FILE = "text2sql.db"

class DatabaseManager:
    def __init__(self, db_path: str = DATABASE_FILE):
        self.db_path = db_path
        self._initialize_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _initialize_database(self):
        """Create tables if they don't exist."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Schema cache table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_cache (
                    table_name TEXT PRIMARY KEY,
                    schema_json TEXT NOT NULL,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Training examples table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS training_examples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT NOT NULL,
                    sql TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    success_count INTEGER DEFAULT 0,
                    UNIQUE(question, sql)
                )
            """)
            
            # Query history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS query_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_query TEXT NOT NULL,
                    generated_sql TEXT,
                    result_summary TEXT,
                    error TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Metadata table for storing misc key-value pairs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
    
    # --- Schema Cache Methods ---
    
    def save_schema(self, table_name: str, schema_data: Any):
        """Save or update schema for a table."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO schema_cache (table_name, schema_json, last_updated)
                VALUES (?, ?, ?)
            """, (table_name, json.dumps(schema_data), datetime.now()))
    
    def get_schema(self, table_name: str) -> Optional[Any]:
        """Retrieve schema for a table."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT schema_json FROM schema_cache WHERE table_name = ?", (table_name,))
            row = cursor.fetchone()
            return json.loads(row['schema_json']) if row else None
    
    def get_all_schemas(self) -> Dict[str, Any]:
        """Retrieve all cached schemas."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT table_name, schema_json FROM schema_cache")
            return {row['table_name']: json.loads(row['schema_json']) for row in cursor.fetchall()}
    
    # --- Training Examples Methods ---
    
    def save_training_example(self, question: str, sql: str):
        """Save a training example (question-SQL pair)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO training_examples (question, sql)
                VALUES (?, ?)
            """, (question, sql))
    
    def get_training_examples(self, limit: int = None) -> List[Dict[str, Any]]:
        """Retrieve training examples, optionally limited."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT id, question, sql, created_at, success_count FROM training_examples ORDER BY created_at DESC"
            if limit:
                query += f" LIMIT {limit}"
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_recent_training_examples(self, k: int = 3) -> List[Dict[str, str]]:
        """Get the k most recent training examples."""
        examples = self.get_training_examples(limit=k)
        return [{"question": ex["question"], "sql": ex["sql"]} for ex in examples]
    
    def delete_training_example(self, example_id: int):
        """Delete a training example by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM training_examples WHERE id = ?", (example_id,))
    
    def increment_example_success(self, question: str, sql: str):
        """Increment success count for a training example."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE training_examples 
                SET success_count = success_count + 1 
                WHERE question = ? AND sql = ?
            """, (question, sql))
    
    # --- Query History Methods ---
    
    def save_query_history(self, user_query: str, generated_sql: str = None, 
                          result_summary: str = None, error: str = None):
        """Save a query to history."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO query_history (user_query, generated_sql, result_summary, error)
                VALUES (?, ?, ?, ?)
            """, (user_query, generated_sql, result_summary, error))
            return cursor.lastrowid
    
    def get_query_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve query history."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, user_query, generated_sql, result_summary, error, timestamp
                FROM query_history
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def clear_query_history(self):
        """Clear all query history."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM query_history")
    
    # --- Metadata Methods ---
    
    def set_metadata(self, key: str, value: Any):
        """Store a metadata key-value pair."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO metadata (key, value, updated_at)
                VALUES (?, ?, ?)
            """, (key, json.dumps(value), datetime.now()))
    
    def get_metadata(self, key: str) -> Optional[Any]:
        """Retrieve a metadata value."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM metadata WHERE key = ?", (key,))
            row = cursor.fetchone()
            return json.loads(row['value']) if row else None
    
    # --- Migration Utilities ---
    
    def migrate_from_json(self, json_file: str, table_type: str):
        """
        Migrate data from JSON/JSONL files to database.
        
        Args:
            json_file: Path to the JSON/JSONL file
            table_type: 'schema' or 'training'
        """
        import os
        
        if not os.path.exists(json_file):
            return
        
        if table_type == 'schema':
            # Migrate schema_cache.json
            with open(json_file, 'r') as f:
                data = json.load(f)
                for key, value in data.items():
                    if key.startswith('schema_'):
                        table_name = key.replace('schema_', '')
                        self.save_schema(table_name, value)
                    elif key == 'tables':
                        self.set_metadata('tables', value)
        
        elif table_type == 'training':
            # Migrate training_data.jsonl
            with open(json_file, 'r') as f:
                for line in f:
                    if line.strip():
                        entry = json.loads(line)
                        self.save_training_example(entry['question'], entry['sql'])

if __name__ == "__main__":
    # Test the database
    db = DatabaseManager()
    print("✓ Database initialized successfully")
    
    # Test schema operations
    db.save_schema("test_table", {"columns": ["id", "name"]})
    schema = db.get_schema("test_table")
    print(f"✓ Schema test: {schema}")
    
    # Test training examples
    db.save_training_example("What is the total revenue?", "SELECT SUM(revenue) FROM sales")
    examples = db.get_training_examples(limit=1)
    print(f"✓ Training examples test: {len(examples)} examples")
    
    # Test query history
    history_id = db.save_query_history("Test query", "SELECT 1", "Success")
    history = db.get_query_history(limit=1)
    print(f"✓ Query history test: {len(history)} entries")
    
    print("\n✓ All database tests passed!")
