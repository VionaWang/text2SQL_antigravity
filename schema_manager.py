from google.cloud import bigquery
from typing import List
from db_manager import DatabaseManager

# Dataset: bigquery-public-data.thelook_ecommerce
DATASET_ID = "bigquery-public-data.thelook_ecommerce"

class SchemaManager:
    def __init__(self):
        self.client = bigquery.Client()
        self.dataset_id = DATASET_ID
        self.db = DatabaseManager()
        
        # Migrate old JSON cache if it exists
        self._migrate_old_cache()

    def _migrate_old_cache(self):
        """Migrate from old JSON cache to database (one-time operation)."""
        import os
        old_cache_file = "schema_cache.json"
        if os.path.exists(old_cache_file):
            print(f"Migrating schema cache from {old_cache_file} to database...")
            self.db.migrate_from_json(old_cache_file, 'schema')
            # Optionally rename the old file to prevent re-migration
            os.rename(old_cache_file, f"{old_cache_file}.migrated")
            print("Migration complete!")

    def get_all_tables(self) -> List[str]:
        """Lists all tables in the dataset."""
        # Check database cache first
        cached_tables = self.db.get_metadata("tables")
        if cached_tables:
            return cached_tables
        
        # Fetch from BigQuery
        tables = list(self.client.list_tables(self.dataset_id))
        table_names = [table.table_id for table in tables]
        
        # Save to database
        self.db.set_metadata("tables", table_names)
        return table_names

    def get_table_schema(self, table_name: str) -> str:
        """Fetches schema for a specific table formatted for LLM context."""
        # Check database cache first
        cached_schema = self.db.get_schema(table_name)
        if cached_schema:
            return cached_schema

        # Fetch from BigQuery
        table_ref = f"{self.dataset_id}.{table_name}"
        try:
            table = self.client.get_table(table_ref)
            
            schema_info = f"Table: {table_name}\nColumns:\n"
            for schema_field in table.schema:
                schema_info += f"- {schema_field.name} ({schema_field.field_type})"
                if schema_field.description:
                    schema_info += f": {schema_field.description}"
                schema_info += "\n"
            
            # Save to database
            self.db.save_schema(table_name, schema_info)
            return schema_info
        except Exception as e:
            return f"Error fetching schema for {table_name}: {str(e)}"

    def get_formatted_schema_context(self, relevant_tables: List[str] = None, max_tables: int = 5) -> str:
        """
        Returns a formatted string of schemas for specified tables.
        If None, returns all tables (careful with context limit).
        
        Args:
            relevant_tables: List of table names to include
            max_tables: Maximum number of tables to include (to avoid token limits)
        """
        if relevant_tables is None:
            relevant_tables = self.get_all_tables()
        
        # Limit number of tables to avoid token overflow
        if len(relevant_tables) > max_tables:
            print(f"Warning: Limiting schema context from {len(relevant_tables)} to {max_tables} tables")
            relevant_tables = relevant_tables[:max_tables]
            
        context = "Database Schema:\n\n"
        for table in relevant_tables:
            schema_info = self.get_table_schema(table)
            # Truncate very long schemas to save tokens
            if len(schema_info) > 500:
                schema_info = schema_info[:500] + "...\n(schema truncated for brevity)\n"
            context += schema_info + "\n"
        
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
