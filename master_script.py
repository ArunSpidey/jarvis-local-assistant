# ==============================================================================
# OPTIMIZED JARVIS SCRIPT (FIXED)
# Includes defensive memory update, anti-hallucination prompt, and soft fallback for non-JSON replies.
# ==============================================================================

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
from chromadb import PersistentClient
from sentence_transformers import SentenceTransformer
from flask import Flask, request, jsonify, send_from_directory
from faster_whisper import WhisperModel
from atexit import register

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
    client = PersistentClient(path=DB_DIR)
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

    try:
        doc = f"user_statement: {document_text}"
        embedding = embedding_model.encode([doc], convert_to_tensor=False)[0].tolist()
        collection.add(documents=[doc], embeddings=[embedding], ids=[doc_id], metadatas=[metadata])
        logger.info(f"[MEMORY] Stored: {document_text}")
    except Exception as e:
        logger.error(f"[MEMORY] Failed to add memory: {e}")

def query_memory(user_input: str, top_k=5) -> list:
    if not MEMORY_ENABLED: return []
    try:
        embedding = embedding_model.encode([user_input], convert_to_tensor=False)[0].tolist()
        results = collection.query(query_embeddings=[embedding], n_results=top_k)
        return results.get("documents", [[]])[0]
    except Exception as e:
        logger.error(f"[MEMORY] Failed to query memory: {e}")
        return []

def sync_memory_on_startup():
    if not MEMORY_ENABLED:
        logger.warning("[MEMORY] Sync skipped: Memory Manager is disabled.")
        return
    logger.info("[MEMORY] Syncing from log...")
    try:
        all_ids = collection.get()["ids"]
        if all_ids:
            collection.delete(ids=all_ids)
    except Exception as e:
        logger.error(f"[MEMORY] Failed to clear existing memory: {e}")
    if os.path.exists(llm_memory_log_file):
        with open(llm_memory_log_file, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    update_memory(entry.get("user_command"), metadata=entry.get("llm_response_json"))
                except json.JSONDecodeError as e:
                    logger.error(f"[MEMORY] Failed to parse log line: {e}")
    logger.info("[MEMORY] Sync complete.")

def persist_memory_on_shutdown():
    if client and MEMORY_ENABLED:
        try:
            client.persist()
            logger.info("ChromaDB persisted successfully.")
        except Exception as e:
            logger.error(f"Failed to persist ChromaDB: {e}")

register(persist_memory_on_shutdown)

PROMPT_TEMPLATE = """You are JARVIS, a memory-aware personal assistant. Use MEMORY CONTEXT to avoid hallucination.

- For action commands (add, move, update, etc): respond in structured JSON with fields like item, location, room, etc.
- For vague or open-ended questions: reply in natural English.
- NEVER guess data. If unsure or not present in memory, say so or skip.
- Do not fabricate quantity, room, or items.

MEMORY CONTEXT:
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
    memory_contexts = query_memory(user_input)
    memory_context_str = "\n".join(memory_contexts) if memory_contexts else "(No prior memory)"
    logger.info(f"[LLM] Injected memory:\n{memory_context_str}")
    prompt = PROMPT_TEMPLATE.replace("{memory_context}", memory_context_str).replace("{user_input}", user_input)
    payload = {"model": MODEL_NAME, "prompt": prompt, "stream": False}

    for attempt in range(3):
        try:
            res = requests.post(OLLAMA_URL, json=payload, timeout=20)
            res.raise_for_status()
            raw_response = res.json().get("response", "").strip()
            logger.info(f"[LLM] Raw: {raw_response}")
            parsed_json = try_parse_json(raw_response)

            with open(llm_memory_log_file, "a") as f:
                entry = {"user_command": user_input, "timestamp": datetime.now().isoformat()}
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
    logger.info("========== START JARVIS VOICE COMMAND ==========")
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file"}), 400
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmpfile:
        request.files['audio'].save(tmpfile.name)
        tmp_path = tmpfile.name
    try:
        transcription = transcribe(tmp_path)
        if not transcription or transcription == "[STT model not loaded]":
            return jsonify({"error": "STT failed or model not loaded."}), 500
        response_message = query_llm(transcription)
    finally:
        os.remove(tmp_path)
    duration = round(time.time() - overall_start, 2)
    logger.info(f"========== END JARVIS COMMAND (Total: {duration} sec) ==========")
    return jsonify({"transcription": transcription, "message": response_message, "time_taken": duration})

@app.route("/command", methods=["POST"])
def handle_command():
    overall_start = time.time()
    logger.info("========== START JARVIS TEXT COMMAND ==========")
    data = request.get_json()
    user_input = data.get("command", "").strip()
    if not user_input:
        return jsonify({"message": "❌ Empty command received."}), 400
    response_message = query_llm(user_input)
    duration = round(time.time() - overall_start, 2)
    logger.info(f"========== END JARVIS COMMAND (Total: {duration} sec) ==========")
    return jsonify({"message": response_message})

import signal
import sys

def handle_sigint(sig, frame):
    logger.info("[SIGNAL] Received SIGINT (Ctrl+C). Persisting memory before exit...")
    persist_memory_on_shutdown()
    sys.exit(0)

signal.signal(signal.SIGINT, handle_sigint)

@app.route("/persist", methods=["POST"])
def manual_persist():
    logger.info("[MANUAL] Manual persist triggered via /persist")
    persist_memory_on_shutdown()
    return jsonify({"message": "✅ Memory manually persisted."})

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