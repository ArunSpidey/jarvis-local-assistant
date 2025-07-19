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
        "stream": False,
        "format": "json"
    }

    try:
        res = requests.post(OLLAMA_URL, json=payload)

        data = res.json()
        parsed = data.get("response", None)

        if not parsed:
            logging.error("LLM returned empty response.")
            return None

        try:
            structured = json.loads(parsed)
        except json.JSONDecodeError as e:
            logging.error("Failed to parse JSON from LLM response: %s", e)
            logging.debug("Response content: %s", parsed)
            return None

        # ✅ Log to clean training log
        llm_logger.info("User Command: %s", user_input)
        llm_logger.info("LLM Parsed: %s", json.dumps(structured, indent=2))

        return structured

    except Exception as e:
        logging.error("LLM error: %s", e)
        return None
