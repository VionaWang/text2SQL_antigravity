import os
from typing import List, Dict
from db_manager import DatabaseManager

class MemoryBank:
    def __init__(self):
        self.db = DatabaseManager()
        
        # Migrate old JSONL file if it exists
        self._migrate_old_data()

    def _migrate_old_data(self):
        """Migrate from old JSONL file to database (one-time operation)."""
        old_file = "training_data.jsonl"
        if os.path.exists(old_file):
            print(f"Migrating training data from {old_file} to database...")
            self.db.migrate_from_json(old_file, 'training')
            # Optionally rename the old file to prevent re-migration
            os.rename(old_file, f"{old_file}.migrated")
            print("Migration complete!")

    def save_example(self, question: str, sql: str):
        """Saves a verified Q&A pair to the database."""
        self.db.save_training_example(question, sql)

    def retrieve_examples(self, question: str, k: int = 3) -> List[Dict]:
        """
        Retrieves top-k similar examples.
        For MVP, we'll just return the k most recent examples.
        TODO: Implement vector/keyword search for better relevance.
        """
        return self.db.get_recent_training_examples(k)
    
    def get_all_examples(self) -> List[Dict]:
        """Retrieve all training examples."""
        return self.db.get_training_examples()
    
    def delete_example(self, example_id: int):
        """Delete a training example by ID."""
        self.db.delete_training_example(example_id)
