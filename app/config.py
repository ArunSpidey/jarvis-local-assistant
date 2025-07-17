ALLOWED_ROOMS = [
    "hall",
    "kitchen",
    "balcony",
    "bedroom",
    "computer room",
    "2nd bedroom"
]

ROOM_SYNONYMS = {
    "living room": "hall",
    "main room": "hall",
    "master bedroom": "bedroom",
    "main bedroom": "bedroom",
    "2nd bedroom": "2nd bedroom",
    "other bedroom": "2nd bedroom",
    "single bedroom": "2nd bedroom",
    "small bedroom": "2nd bedroom"
}
# config.py

ALLOWED_ACTIONS = [
    "add_inventory",
    "update_inventory",
    "remove_inventory",
    "query_inventory",
    "add_shopping",
    "update_shopping",
    "remove_shopping",
    "query_shopping",
    "add_todo",
    "update_todo",
    "remove_todo",
    "query_todo",
    "remove_last_inventory",
    "remove_last_shopping",
    "remove_last_todo",
    "llm_query_inventory",
    "llm_query_todo",
    "llm_query_shopping"
]

MODEL_NAME = "mistral"
OLLAMA_URL = "http://localhost:11434/api/generate"
