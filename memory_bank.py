import json
import os
from typing import List, Dict

MEMORY_FILE = "training_data.jsonl"

class MemoryBank:
    def __init__(self):
        self.file_path = MEMORY_FILE
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w') as f:
                pass

    def save_example(self, question: str, sql: str):
        """Saves a verified Q&A pair to the JSONL file."""
        with open(self.file_path, 'a') as f:
            entry = {"question": question, "sql": sql}
            f.write(json.dumps(entry) + "\n")

    def retrieve_examples(self, question: str, k: int = 3) -> List[Dict]:
        """
        Retrieves top-k similar examples.
        For MVP, we'll just return the 3 most recent examples.
        TODO: Implement vector/keyword search for better relevance.
        """
        examples = []
        if os.path.exists(self.file_path):
            with open(self.file_path, 'r') as f:
                for line in f:
                    if line.strip():
                        examples.append(json.loads(line))
        
        # Return last k examples (hack for MVP context)
        return examples[-k:]
