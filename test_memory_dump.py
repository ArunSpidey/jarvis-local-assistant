# test_memory_dump.py

import os
import json
from chromadb.config import Settings
import chromadb

# === CONFIGURATION ===
DB_DIR = "vector_store"  # Same directory as main script
COLLECTION_NAME = "jarvis_memory"

def inspect_memory_entries(n: int = 10):
    print(f"🔍 Inspecting up to {n} memory entries from '{COLLECTION_NAME}'...")
    try:
        client = chromadb.Client(Settings(persist_directory=DB_DIR, anonymized_telemetry=False))
        collection = client.get_or_create_collection(COLLECTION_NAME)

        results = collection.get(include=["documents", "metadatas"], limit=n)
        for i in range(len(results["ids"])):
            print(f"\n== Entry {i+1} ==")
            print("📄 Document:", results["documents"][i])
            print("🧾 Metadata:", json.dumps(results["metadatas"][i], indent=2))
    except Exception as e:
        print("❌ Error retrieving memory entries:", e)

if __name__ == "__main__":
    inspect_memory_entries()