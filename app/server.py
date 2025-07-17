# server.py

from flask import Flask, request, jsonify, send_from_directory
from whisper_stt import transcribe
from jarvis_logger import logger
import tempfile
import os
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




@app.route("/benchmark")
def benchmark_page():
    return send_from_directory(os.path.dirname(__file__), "voice_benchmark.html")


from faster_whisper import WhisperModel
import time

@app.route("/benchmark-stt", methods=["POST"])
def benchmark_stt():
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file"}), 400

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmpfile:
        request.files['audio'].save(tmpfile.name)
        tmp_path = tmpfile.name

    combos = [
        {"model": "tiny",  "beam_size": 1, "best_of": 1},
        {"model": "tiny",  "beam_size": 5, "best_of": 5},
        {"model": "base",  "beam_size": 1, "best_of": 1},
        {"model": "base",  "beam_size": 5, "best_of": 5},
        {"model": "small", "beam_size": 1, "best_of": 1},
        {"model": "small", "beam_size": 5, "best_of": 5},
    ]

    results = []
    for cfg in combos:
        model = WhisperModel(cfg["model"], compute_type="int8")
        start = time.time()
        segments, _ = model.transcribe(
            tmp_path,
            language="en",
            beam_size=cfg["beam_size"],
            best_of=cfg["best_of"]
        )
        end = time.time()
        result_text = " ".join([seg.text.strip() for seg in segments])
        results.append({
            "model": cfg["model"],
            "beam_size": cfg["beam_size"],
            "best_of": cfg["best_of"],
            "time": round(end - start, 2),
            "text": result_text
        })

    os.remove(tmp_path)
    return jsonify({"results": results})


if __name__ == "__main__":
    logger.info("========== SERVER STARTED ==========")
    context = ('certs/cert.pem', 'certs/key.pem')
    app.run(host="0.0.0.0", port=5000, ssl_context=context, debug=False)

