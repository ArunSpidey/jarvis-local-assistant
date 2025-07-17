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

    if action in valid_actions:
        return execute_action(parsed_json)
    else:
        return f"❌ Unknown action: {action}"
