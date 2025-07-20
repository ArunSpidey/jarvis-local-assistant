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
from app.memory_manager import query_memory

def query_llm(user_input):
    """
    Send user command to LLM, parse structured JSON response.
    Handles cleaning and logging of LLM output.
    """
    # Step 1 & 2: Query memory across all namespaces and prepare context
    namespaces = ["inventory", "shopping", "todo"]
    memory_contexts = []
    for ns in namespaces:
        slices = query_memory(user_input, ns)
        if slices:
            # Limit to top 5 entries and sanitize newlines
            sanitized = [entry.replace("\n", " ") for entry in slices[:5]]
            block = f"<memory namespace=\"{ns}\">\n" + "\n".join(sanitized) + "\n</memory>"
            memory_contexts.append(block)
    if memory_contexts:
        memory_context = "<BEGIN MEMORY>\n" + "\n\n".join(memory_contexts) + "\n<END MEMORY>"
        logging.info("[RAG] Injected Memory Context:\n%s", memory_context)
    else:
        memory_context = "<BEGIN MEMORY>\n(No previous entries found)\n<END MEMORY>"

    # Log memory context for LLM specifically
    logging.info("========== BEGIN INJECTED MEMORY ==========\n%s\n========== END INJECTED MEMORY ==========", memory_context.strip())

    # Step 3: Inject memory into the prompt
    try:
        with open("app/prompt_template.txt", "r") as f:
            template = f.read()
        prompt = template.replace("{memory_context}", memory_context).replace("{user_input}", user_input)
        logging.info("========== BEGIN FINAL PROMPT ==========\n%s\n========== END FINAL PROMPT ==========", prompt)
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

        logging.info("User Command: %s", user_input)
        logging.info("LLM Parsed: %s", json.dumps(structured, indent=2))

        return structured

    except Exception as e:
        logging.error("LLM error: %s", e)
        return None
