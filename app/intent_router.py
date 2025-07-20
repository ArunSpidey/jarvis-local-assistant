from app.memory_manager import query_memory
from app.action_handler import execute_action

def route_intent(parsed_json: dict) -> str:
    action = parsed_json.get("action", "")

    valid_actions = {
        "add_inventory", "update_inventory", "remove_inventory", "query_inventory",
        "add_shopping", "update_shopping", "remove_shopping", "query_shopping",
        "add_todo", "update_todo", "remove_todo", "query_todo",
        "remove_last_inventory", "remove_last_shopping", "remove_last_todo",
        "llm_query_inventory", "llm_query_todo", "llm_query_shopping"
    }

    # Optional: Inject memory context before handling specific actions
    # This can be expanded per action if needed
    if action in {"update_inventory", "remove_inventory"}:
        memory_context = query_memory(parsed_json.get("item", ""))
        parsed_json["memory_context"] = memory_context

    if action in valid_actions:
        return execute_action(parsed_json)
    else:
        return f"❌ Unknown or unsupported action: {action}"
