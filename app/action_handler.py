def normalize(text: str) -> str:
    if not text: return ""
    return " ".join(sorted(text.lower().strip().split()))

from app.io_utils import read_json, write_json
from app.jarvis_logger import logger

def execute_action(parsed_json: dict) -> str:
    action = parsed_json.get("action")

    if action.startswith("add_") or action.startswith("update_") or action.startswith("remove_"):
        logger.info(f"[ACTION] → Processing structured action: {action}")

    if action in {"add_inventory", "update_inventory"}:
        return _add_or_update_inventory(parsed_json)
    elif action == "remove_inventory":
        return _remove_inventory(parsed_json)
    elif action == "query_inventory":
        return _query("inventory")
    elif action == "remove_last_inventory":
        return _remove_last("inventory")

    elif action == "add_shopping":
        return _add_shopping(parsed_json)
    elif action == "remove_shopping":
        return _remove_shopping(parsed_json)
    elif action == "query_shopping":
        return _query("shopping")
    elif action == "remove_last_shopping":
        return _remove_last("shopping")

    elif action == "add_todo":
        return _add_todo(parsed_json)
    elif action == "remove_todo":
        return _remove_todo(parsed_json)
    elif action == "query_todo":
        return _query("todo")
    elif action == "remove_last_todo":
        return _remove_last("todo")

    elif action.startswith("llm_query_"):
        return "[LLM QUERY] Logic not implemented yet."

    return f"❌ Unknown action: {action}"


# ==== HANDLERS ====

def _add_or_update_inventory(data):
    db = read_json("inventory")
    data.setdefault("previous_location", "")
    items = data["item"] if isinstance(data["item"], list) else [data["item"]]
    updated = []
    added = []

    for item in items:
        matched_entries = [
            entry for entry in db
            if normalize(entry["item"]) == normalize(item)
        ]

        # If update_inventory, try to narrow by location/room if provided
        if data["action"] == "update_inventory":
            if data.get("location"):
                matched_entries = [e for e in matched_entries if normalize(e.get("location", "")) == normalize(data["previous_location"] or "")]
            if data.get("room"):
                matched_entries = [e for e in matched_entries if normalize(e.get("room", "")) == normalize(data["room"])]

        match = matched_entries[0] if matched_entries else None

        if match:
            if data["action"] == "update_inventory":
                if "location" in data:
                    match["location"] = data["location"]
                if "room" in data:
                    match["room"] = data["room"]
                if "quantity" in data:
                    match["quantity"] = data["quantity"]
                updated.append(item)
            else:
                # fallback to additive behavior
                db.append({
                    "item": item,
                    "location": data.get("location", ""),
                    "room": data.get("room", ""),
                    "quantity": data.get("quantity", 1)
                })
                added.append(item)
        else:
            # add if no exact match found
            db.append({
                "item": item,
                "location": data.get("location", ""),
                "room": data.get("room", ""),
                "quantity": data.get("quantity", 1)
            })
            added.append(item)

    write_json("inventory", db)
    status = []
    if added:
        status.append(f"✅ Added {', '.join(added)} to inventory.")
    if updated:
        status.append(f"✅ Updated {', '.join(updated)} in inventory.")
    return " ".join(status)

def _remove_inventory(data):
    db = read_json("inventory")
    items = data["item"] if isinstance(data["item"], list) else [data["item"]]
    original_len = len(db)
    db = [entry for entry in db if normalize(entry["item"]) not in [normalize(i) for i in items]]
    write_json("inventory", db)
    removed_count = original_len - len(db)
    return f"✅ Removed {removed_count} item(s) from inventory."

def _add_shopping(data):
    db = read_json("shopping")
    items = data["item"] if isinstance(data["item"], list) else [data["item"]]
    for item in items:
        db.append({
            "item": item,
            "quantity": data.get("quantity", 1)
        })
    write_json("shopping", db)
    return f"✅ Added {', '.join(items)} to shopping list."

def _remove_shopping(data):
    db = read_json("shopping")
    items = data["item"] if isinstance(data["item"], list) else [data["item"]]
    original_len = len(db)
    db = [entry for entry in db if normalize(entry["item"]) not in [normalize(i) for i in items]]
    write_json("shopping", db)
    removed_count = original_len - len(db)
    return f"✅ Removed {removed_count} item(s) from shopping list."

def _add_todo(data):
    db = read_json("todo")
    db.append({
        "task": data["task"],
        "date": data.get("date", "")
    })
    write_json("todo", db)
    return f"✅ Added todo: {data['task']}"

def _remove_todo(data):
    db = read_json("todo")
    task = data["task"]
    db = [entry for entry in db if normalize(entry["task"]) != normalize(task)]
    write_json("todo", db)
    return f"✅ Removed todo: {task}"

def _query(domain):
    db = read_json(domain)
    if not db:
        return f"📂 No entries found in {domain}."
    lines = []
    for idx, entry in enumerate(db, 1):
        parts = [f"{key}: {value}" for key, value in entry.items() if value]
        lines.append(f"{idx}. " + ", ".join(parts))
    return "\n".join(lines)

def _remove_last(domain):
    db = read_json(domain)
    if not db:
        return f"❌ {domain.capitalize()} is already empty."
    last = db.pop()
    write_json(domain, db)
    if domain == "todo":
        return f"✅ Removed last todo: '{last.get('task')}'"
    return f"✅ Removed last {domain} item: '{last.get('item')}'"
