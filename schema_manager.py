import os
import json
from google.cloud import bigquery
from typing import Dict, List, Any

# Dataset: bigquery-public-data.thelook_ecommerce
DATASET_ID = "bigquery-public-data.thelook_ecommerce"
CACHE_FILE = "schema_cache.json"

class SchemaManager:
    def __init__(self):
        self.client = bigquery.Client()
        self.dataset_id = DATASET_ID
        self.schema_cache = self._load_cache()

    def _load_cache(self) -> Dict[str, Any]:
        """Loads schema from local JSON if available."""
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_cache(self):
        """Saves current schema to local JSON."""
        with open(CACHE_FILE, 'w') as f:
            json.dump(self.schema_cache, f, indent=2)

    def get_all_tables(self) -> List[str]:
        """Lists all tables in the dataset."""
        if "tables" in self.schema_cache:
            return self.schema_cache["tables"]
        
        tables = list(self.client.list_tables(self.dataset_id))
        table_names = [table.table_id for table in tables]
        
        self.schema_cache["tables"] = table_names
        self._save_cache()
        return table_names

    def get_table_schema(self, table_name: str) -> str:
        """Fetches schema for a specific table formatted for LLM context."""
        cache_key = f"schema_{table_name}"
        if cache_key in self.schema_cache:
            return self.schema_cache[cache_key]

        table_ref = f"{self.dataset_id}.{table_name}"
        try:
            table = self.client.get_table(table_ref)
            
            schema_info = f"Table: {table_name}\nColumns:\n"
            for schema_field in table.schema:
                schema_info += f"- {schema_field.name} ({schema_field.field_type})"
                if schema_field.description:
                    schema_info += f": {schema_field.description}"
                schema_info += "\n"
            
            self.schema_cache[cache_key] = schema_info
            self._save_cache()
            return schema_info
        except Exception as e:
            return f"Error fetching schema for {table_name}: {str(e)}"

    def get_formatted_schema_context(self, relevant_tables: List[str] = None) -> str:
        """
        Returns a formatted string of schemas for specified tables.
        If None, returns all tables (careful with context limit).
        """
        if relevant_tables is None:
            relevant_tables = self.get_all_tables()
            
        context = "Database Schema:\n\n"
        for table in relevant_tables:
            context += self.get_table_schema(table) + "\n"
        
        # Add basic relationship hints for TheLook eCommerce
        context += "\nCommon Relationships:\n"
        context += "- users.id = orders.user_id\n"
        context += "- orders.order_id = order_items.order_id\n"
        context += "- products.id = order_items.product_id\n"
        context += "- products.id = inventory_items.product_id\n"
        
        return context

if __name__ == "__main__":
    # Test script
    sm = SchemaManager()
    print("Tables:", sm.get_all_tables())
    print("\nSample Schema (users):")
    print(sm.get_table_schema("users"))
