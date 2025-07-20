import chromadb
from chromadb.config import Settings

client = chromadb.PersistentClient(path="vector_store")
collection = client.get_or_create_collection("jarvis_memory")

N = 5  # Number of recent items to inspect

entries = collection.get(include=["documents", "metadatas", "embeddings"])  # embeddings optional, for debug

print(f"\n🧠 Inspecting {min(N, len(entries['ids']))} entries from 'jarvis_memory':\n")

for idx, (doc, meta, _id) in enumerate(zip(
    entries["documents"][:N],
    entries["metadatas"][:N],
    entries["ids"][:N]
)):
    print(f"--- Entry {idx+1} ---")
    print(f"🆔 ID: {_id}")
    print(f"📄 Document: {doc}")
    print(f"📎 Metadata: {meta}")
    print()