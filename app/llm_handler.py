"""
llm_handler.py

Handles communication with local LLM (Ollama) for command parsing and fuzzy queries.
Logs LLM interactions for training/debugging.
"""

import requests
import json
import re
import logging
from app.config import MODEL_NAME, OLLAMA_URL

# --- Main app logger will still go to listener.log ---
# --- This new one is for clean LLM-to-pattern log ---
llm_logger = logging.getLogger("llm_commands")
llm_logger.setLevel(logging.INFO)
llm_logger.addHandler(logging.FileHandler("logs/llm_commands.log"))
llm_logger.propagate = False

def query_llm(user_input):
    """
    Send user command to LLM, parse structured JSON response.
    Handles cleaning and logging of LLM output.
    """
    try:
        with open("app/prompt_template.txt", "r") as f:
            template = f.read()
        prompt = template.replace("{user_input}", user_input)
    except Exception as e:
        logging.error("Failed to load prompt template: %s", e)
        return None

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }

    try:
        res = requests.post(OLLAMA_URL, json=payload)
        raw_text = res.text.strip()
        logging.debug("OLLAMA RAW RESPONSE: %s", raw_text)

        data = res.json()
        response_text = data.get("response", "").strip()

        if not response_text:
            logging.error("LLM returned empty response.")
            return None

        if response_text.startswith("```"):
            response_text = re.sub(r"^```(?:json)?", "", response_text, flags=re.IGNORECASE).strip()
            response_text = re.sub(r"```$", "", response_text).strip()

        json_start = response_text.find("{")
        json_end = response_text.rfind("}")
        if json_start == -1 or json_end == -1:
            logging.error("No JSON object found in LLM response.")
            logging.debug("Response content: %s", response_text)
            return None

        cleaned_json = response_text[json_start:json_end + 1]
        logging.debug("CLEANED JSON: %s", cleaned_json)

        # ✅ Log to clean training log
        llm_logger.info("User Command: %s", user_input)
        llm_logger.info("LLM Parsed: %s", cleaned_json)

        return json.loads(cleaned_json)

    except Exception as e:
        logging.error("LLM error: %s", e)
        return None
