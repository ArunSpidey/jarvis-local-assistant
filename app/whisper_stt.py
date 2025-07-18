from faster_whisper import WhisperModel
from app.jarvis_logger import logger
import os

model = WhisperModel("small", compute_type="int8")

def transcribe(audio_path):
    if not os.path.exists(audio_path):
        logger.error(f"[STT] → File not found: {audio_path}")
        return ""

    segments, _ = model.transcribe(
        audio_path,
        language="en",
        beam_size=5,
        best_of=5
    )

    result_text = " ".join([seg.text.strip() for seg in segments])
    logger.info(f"[STT] → Result: {result_text}")
    return result_text.strip()
