# ===============================================================================
# OPTIMIZED JARVIS SCRIPT (FIXED)
# Includes defensive memory update, anti-hallucination prompt, and soft fallback for non-JSON replies.
# ===============================================================================

import os
import json
import tempfile
import time
import logging
import requests
import hashlib
import re
from datetime import datetime
from typing import Dict, Optional, Any
import chromadb
from sentence_transformers import SentenceTransformer
from flask import Flask, request, jsonify, send_from_directory
from faster_whisper import WhisperModel

def get_recent_logs(line_count=50):
    try:
        with open(log_file, "r") as f:
            lines = f.readlines()
        return lines[-line_count:]
    except Exception:
        return []

os.makedirs("logs", exist_ok=True)
log_file = "logs/jarvis.log"
llm_memory_log_file = "logs/llm_memory_log.jsonl"
logging.basicConfig(
    filename=log_file,
    filemode="a",
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("jarvis")

MODEL_NAME = "mistral"
OLLAMA_URL = "http://localhost:11434/api/generate"
DEBUG = False

try:
    stt_model = WhisperModel("small", compute_type="int8")
except Exception as e:
    logger.error(f"Failed to load Whisper model: {e}. STT will not function.")
    stt_model = None

def transcribe(audio_path: str) -> str:
    if not stt_model:
        return "[STT model not loaded]"
    if not os.path.exists(audio_path):
        logger.error(f"[STT] → File not found: {audio_path}")
        return ""
    segments, _ = stt_model.transcribe(audio_path, language="en", beam_size=5, best_of=5)
    result_text = " ".join([seg.text.strip() for seg in segments])
    logger.info(f"[STT] → Result: {result_text}")
    return result_text.strip()

DB_DIR = "vector_store"
COLLECTION_NAME = "jarvis_memory"
try:
    embedding_model = SentenceTransformer("nomic-ai/nomic-embed-text-v1", trust_remote_code=True)
    client = chromadb.PersistentClient(path=DB_DIR)
    collection = client.get_or_create_collection(COLLECTION_NAME)
    MEMORY_ENABLED = True
except Exception as e:
    logger.error(f"Failed to initialize Memory Manager: {e}. Memory features will be disabled.")
    embedding_model = None
    client = None
    collection = None
    MEMORY_ENABLED = False

def update_memory(document_text: str, metadata: Optional[Dict[str, Any]] = None):
    if not MEMORY_ENABLED: return

    timestamp = datetime.now().isoformat()
    unique_string = f"{timestamp}-{document_text}"
    doc_id = hashlib.md5(unique_string.encode('utf-8')).hexdigest()

    if not isinstance(metadata, dict):
        metadata = {}
    metadata.update({"timestamp": timestamp, "text": document_text})

    if "item" in metadata:
        thread_key = metadata["item"]
        thread_id = hashlib.md5(thread_key.encode('utf-8')).hexdigest()
        metadata["thread_id"] = thread_id
    else:
        thread_id = None

    # Flatten nested dicts (e.g., location) before passing to ChromaDB
    flat_meta = {}
    for k, v in metadata.items():
        if isinstance(v, dict):
            for subk, subv in v.items():
                flat_meta[f"{k}_{subk}"] = subv
        else:
            flat_meta[k] = v
    metadata = flat_meta

    vague_keywords = ["this", "that", "next", "meant"]
    if any(kw in document_text.lower() for kw in vague_keywords) and thread_id:
        try:
            past_results = collection.get(include=["metadatas", "documents", "ids"])
            for doc, meta, doc_id_old in zip(past_results["documents"], past_results["metadatas"], past_results["ids"]):
                if any(kw in doc.lower() for kw in vague_keywords) and "thread_id" not in meta:
                    patched_meta = meta.copy()
                    patched_meta["thread_id"] = thread_id
                    collection.update(ids=[doc_id_old], metadatas=[patched_meta])
                    logger.info(f"[MEMORY] Patched vague entry {doc_id_old} with thread_id {thread_id}")
        except Exception as e:
            logger.warning(f"[MEMORY] Failed to patch vague references: {e}")

    try:
        doc = f"user_statement: {document_text}"
        embedding = embedding_model.encode([doc], convert_to_tensor=False)[0].tolist()
        collection.add(documents=[doc], embeddings=[embedding], ids=[doc_id], metadatas=[metadata])
        logger.info(f"[MEMORY] Stored: {document_text}")
    except Exception as e:
        logger.error(f"[MEMORY] Failed to add memory: {e}")

def query_memory(user_input: str, top_k=20) -> list:
    if not MEMORY_ENABLED: return []
    try:
        embedding = embedding_model.encode([user_input], convert_to_tensor=False)[0].tolist()
        query_start = time.time()
        results = collection.query(query_embeddings=[embedding], n_results=top_k)
        logger.info(f"[VECTOR] Query took {round(time.time() - query_start, 2)} sec")
        return results.get("documents", [[]])[0], results.get("metadatas", [[]])[0]
    except Exception as e:
        logger.error(f"[MEMORY] Failed to query memory: {e}")
        return [], []

def sync_memory_on_startup():
    if not MEMORY_ENABLED:
        logger.warning("[MEMORY] Sync skipped: Memory Manager is disabled.")
        return
    logger.info("[MEMORY] Skipping rebuild from jsonl – using ChromaDB persistent memory.")

PROMPT_TEMPLATE = """You are JARVIS, a memory-aware personal assistant. Use MEMORY CONTEXT to avoid hallucination.

- For action commands (add, move, update, etc): respond in structured JSON with fields like item, location, room, etc.
- For vague or open-ended questions: reply in natural English.
- NEVER guess data. If unsure or not present in memory, say so or skip.
- Do not fabricate quantity, room, or items. Do not assume location unless explicitly mentioned.
- Prefer short responses when the user asks for short or quick answers.

Examples:

USER INSTRUCTION:
Add 2 green bottles to kitchen shelf.
→ {"action": "add", "item": "green bottles", "quantity": 2, "location": {"room": "kitchen", "specific_location": "shelf"}}

USER INSTRUCTION:
What items do we have in kitchen?
→ Based on memory, you have green bottles in the kitchen shelf.

KNOWN FACTS:
{known_facts}

MEMORY:
{memory_context}

USER INSTRUCTION:
{user_input}

Your response:
"""

def try_parse_json(text: str) -> Optional[Dict]:
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return None

def query_llm(user_input: str) -> str:
    memory_contexts, metadata_contexts = query_memory(user_input)
    memory_context_str = ""
    for doc in memory_contexts:
        match = re.match(r"user_statement: (.*)", doc)
        sentence = match.group(1) if match else doc
        memory_context_str += f"- {sentence}\n"

    known_facts_str = ""
    for meta in metadata_contexts:
        if isinstance(meta, dict) and "item" in meta and "location_room" in meta:
            item = meta.get("item")
            room = meta.get("location_room")
            location = meta.get("location_specific_location", "")
            if item and room:
                loc_string = f"{room} → {location}" if location else room
                known_facts_str += f"- {item} is located in {loc_string}\n"

    if not memory_context_str:
        memory_context_str = "(No prior memory)"
    if not known_facts_str:
        known_facts_str = "(No known facts)"

    logger.info(f"[VECTOR] Retrieved {len(memory_contexts)} memory entries.")
    prompt = PROMPT_TEMPLATE.replace("{memory_context}", memory_context_str).replace("{user_input}", user_input).replace("{known_facts}", known_facts_str)
    if DEBUG:
        logger.info(f"[LLM] Prompt: Injected {len(memory_contexts)} memory lines → model: {MODEL_NAME}")
        logger.info(prompt)
    payload = {"model": MODEL_NAME, "prompt": prompt, "stream": False}

    for attempt in range(3):
        try:
            llm_start = time.time()
            res = requests.post(OLLAMA_URL, json=payload, timeout=20)
            res.raise_for_status()
            raw_response = res.json().get("response", "").strip()
            logger.info(f"[LLM] Response took {round(time.time() - llm_start, 2)} sec → {raw_response}")

            with open(llm_memory_log_file, "a") as f:
                entry = {"user_command": user_input, "timestamp": datetime.now().isoformat()}
                parsed_json = try_parse_json(raw_response)
                if parsed_json:
                    entry["llm_response_json"] = parsed_json
                else:
                    entry["llm_response_text"] = raw_response
                json.dump(entry, f)
                f.write("\n")

            update_memory(user_input, metadata=parsed_json)
            return raw_response

        except requests.exceptions.RequestException as e:
            logger.error(f"[LLM] Request error: {e}")
            time.sleep(2)
    return "I'm sorry, I am unable to process your request."

app = Flask(__name__)
logging.getLogger('werkzeug').setLevel(logging.ERROR)

@app.route("/")
def home():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), "voice.html")

@app.route("/stt", methods=["POST"])
def handle_stt():
    overall_start = time.time()
    logger.info("========== START JARVIS COMMAND ==========")
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file"}), 400
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmpfile:
        request.files['audio'].save(tmpfile.name)
        tmp_path = tmpfile.name
    try:
        transcription_start = time.time()
        transcription = transcribe(tmp_path)
        transcription_duration = time.time() - transcription_start
        logger.info(f"[STT] Received audio → Transcribed in {round(transcription_duration, 2)} sec")
        if not transcription or transcription == "[STT model not loaded]":
            return jsonify({"error": "STT failed or model not loaded."}), 500
        response_message = query_llm(transcription)
    finally:
        os.remove(tmp_path)
    duration = round(time.time() - overall_start, 2)
    logger.info(f"========== END JARVIS COMMAND (Total: {duration} sec) ==========")
    return jsonify({
        "transcription": transcription,
        "message": response_message,
        "time_taken": duration,
        "logs": get_recent_logs()
    })

@app.route("/command", methods=["POST"])
def handle_command():
    overall_start = time.time()
    logger.info("========== START JARVIS COMMAND ==========")
    data = request.get_json()
    user_input = data.get("text", "").strip()
    if not user_input:
        return jsonify({"message": "❌ Empty command received."}), 400
    response_message = query_llm(user_input)
    duration = round(time.time() - overall_start, 2)
    logger.info(f"========== END JARVIS COMMAND (Total: {duration} sec) ==========")
    return jsonify({
        "message": response_message,
        "time_taken": duration,
        "logs": get_recent_logs()
    })

@app.route("/restart-server", methods=["POST"])
def restart_server():
    logger.warning("Server restart requested via frontend. Exiting.")
    os._exit(1)

@app.route("/vectors", methods=["GET"])
def fetch_vectors():
    count = int(request.args.get("count", 10))
    if not MEMORY_ENABLED:
        return jsonify({"error": "Memory disabled."}), 400
    try:
        results = collection.get(include=["metadatas", "documents"], limit=count)
        entries = []
        for doc, meta in zip(results.get("documents", []), results.get("metadatas", [])):
            entries.append({"text": doc, "metadata": meta})
        return jsonify({"entries": entries})
    except Exception as e:
        logger.error(f"[VECTOR] Failed to fetch entries: {e}")
        return jsonify({"error": "Vector fetch failed"}), 500

if __name__ == "__main__":
    sync_memory_on_startup()
    ssl_cert_path = os.path.join("certs", "cert.pem")
    ssl_key_path = os.path.join("certs", "key.pem")
    if os.path.exists(ssl_cert_path) and os.path.exists(ssl_key_path):
        logger.info("Launching with HTTPS (SSL context enabled).")
        app.run(host="0.0.0.0", port=5000, debug=False, ssl_context=(ssl_cert_path, ssl_key_path))
    else:
        logger.warning("SSL certs not found. Falling back to HTTP.")
        app.run(host="0.0.0.0", port=5000, debug=False)