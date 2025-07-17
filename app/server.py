from flask import Flask, request, jsonify, send_from_directory
from app.whisper_stt import transcribe
from app.jarvis_logger import logger
from app.llm_handler import query_llm
from app.intent_router import route_intent
import tempfile
import os
import time
import logging as flask_logging

flask_logging.getLogger('werkzeug').setLevel(flask_logging.ERROR)

app = Flask(__name__)

@app.route("/")
def index():
    return send_from_directory(os.path.dirname(__file__), "voice.html")

@app.route("/stt", methods=["POST"])
def handle_stt():
    overall_start = time.time()
    logger.info("========== START JARVIS COMMAND ==========")

    stt_start = time.time()

    if 'audio' not in request.files:
        logger.warning("[STT] No audio received in /stt")
        return jsonify({"error": "No audio file"}), 400

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmpfile:
        request.files['audio'].save(tmpfile.name)
        tmp_path = tmpfile.name

    logger.info(f"[STT] Received audio file: {tmp_path}")

    try:
        result = transcribe(tmp_path)
    finally:
        os.remove(tmp_path)

    stt_end = time.time()
    logger.info(f"[STT] STT stage complete in {round(stt_end - stt_start, 2)} sec")

    overall_end = time.time()
    total_duration = round(overall_end - overall_start, 2)
    logger.info(f"========== END JARVIS COMMAND (Total: {total_duration} sec) ==========\n")

    return jsonify({"transcription": result})


@app.route("/command", methods=["POST"])
def handle_command():
    overall_start = time.time()
    logger.info("========== START JARVIS COMMAND ==========")

    try:
        data = request.get_json()
        user_input = data.get("command", "").strip()
        logger.info(f"[STT] → Transcribed Text: {user_input}")

        logger.info("[INTENT] → Sending to LLM...")
        parsed = query_llm(user_input)
        logger.info(f"[INTENT] → Parsed Response: {parsed}")

        logger.info("[ACTION] → Routing Intent...")
        action_result = route_intent(parsed)

        logger.info(f"[ACTION] → Final Message: {action_result}")
        duration = round(time.time() - overall_start, 2)
        logger.info(f"========== END JARVIS COMMAND (Total: {duration} sec) ==========")

        return jsonify({"message": action_result})

    except Exception as e:
        logger.exception("Error in /command:")
        return jsonify({"message": f"❌ Error: {str(e)}"}), 500
