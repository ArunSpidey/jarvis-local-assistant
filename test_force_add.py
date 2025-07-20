import os
import hashlib
from datetime import datetime
from sentence_transformers import SentenceTransformer
from chromadb import PersistentClient

# ========== CONFIG ==========
DB_DIR = "vector_store"
COLLECTION_NAME = "jarvis_memory"
TEXT = "The umbrella is in the hallway stand."

# ========== EMBEDDING ==========
embedding_model = SentenceTransformer("nomic-ai/nomic-embed-text-v1", trust_remote_code=True)

# ========== CHROMA INIT ==========
client = PersistentClient(path=DB_DIR)
collection = client.get_or_create_collection(COLLECTION_NAME)

# ========== MEMORY INSERT ==========
timestamp = datetime.now().isoformat()
doc_id = hashlib.md5(f"{timestamp}-{TEXT}".encode()).hexdigest()
embedding = embedding_model.encode([TEXT])[0].tolist()
metadata = {
    "timestamp": timestamp,
    "item": "umbrella",
    "location": "hallway stand"
}

collection.add(
    documents=[TEXT],
    embeddings=[embedding],
    ids=[doc_id],
    metadatas=[metadata]
)

print("✅ Memory added to ChromaDB with PersistentClient.")
print("💾 Check 'vector_store/' for .parquet files and index now.")