

import os
JSON_PATHS = {
    "inventory": "data/inventory.json",
    "shopping": "data/shopping.json",
    "todo": "data/todo.json"
}
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from typing import List, Dict

# --- Setup ---
DB_DIR = "vector_store"
COLLECTION_NAME = "jarvis_memory"
EMBED_MODEL = "nomic-embed-text-v1"

embedding_model = SentenceTransformer(EMBED_MODEL, trust_remote_code=True)
# --- Deterministic Hash ---
import hashlib

def get_deterministic_id(data: Dict):
    canonical_string = json.dumps(data, sort_keys=True).encode('utf-8')
    return hashlib.md5(canonical_string).hexdigest()

client = chromadb.Client(Settings(chroma_db_impl="duckdb+parquet", persist_directory=DB_DIR))
collection = client.get_or_create_collection(COLLECTION_NAME)


# --- Memory Add ---
def add_to_memory(namespace: str, data: Dict):
    """
    Store a record in memory (vector DB) under a namespace like 'inventory' or 'todo'.
    """
    doc_text = f"search_document: {namespace} entry: {str(data)}".strip().lower()
    embedding = embedding_model.encode([doc_text], convert_to_tensor=False)[0]

    doc_id = f"{namespace}-{get_deterministic_id(data)}"

    collection.upsert(
        documents=[doc_text],
        embeddings=[embedding],
        ids=[doc_id],
        metadatas=[{"namespace": namespace, **data}]
    )


# --- Memory Query ---
def query_memory(user_input: str, namespace: str, top_k=3) -> List[Dict]:
    """
    Fetch relevant memory slices from vector DB for the given namespace and user input.
    """
    user_input_with_prefix = f"search_query: {user_input}"
    embedding = embedding_model.encode([user_input_with_prefix], convert_to_tensor=False)[0]

    results = collection.query(
        query_embeddings=[embedding],
        n_results=top_k,
        where={"namespace": namespace}
    )

    return results.get("documents", [[]])[0]


# --- Sync Memory with JSON ---
import json

def sync_memory_with_json(namespace: str):
    """
    Rebuild vector DB for a namespace from the latest JSON file entries.
    """
    file_path = JSON_PATHS.get(namespace)
    if not file_path or not os.path.exists(file_path):
        return  # File not found or invalid namespace

    with open(file_path, "r") as f:
        data = json.load(f)

    # Clear previous entries for this namespace before re-adding
    collection.delete(where={"namespace": namespace})

    for entry in data:
        add_to_memory(namespace, entry)