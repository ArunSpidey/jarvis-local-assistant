"""
action_handler.py

Handles parsed user intents and performs actions on inventory, shopping, and todo lists.
Includes fuzzy matching, LLM escalation, and CRUD operations for each data type.
"""

import json
import requests
import logging
import difflib
from app.io_utils import read_json, write_json, current_date_str
from app.llm_handler import query_llm

def handle_intent(parsed, original_command):
    """
    Main dispatcher for parsed user commands.
    Validates action and fields, then routes to appropriate handler.
    """
    action = parsed.get("action")
    item = parsed.get("item")
    location = parsed.get("location")
    room = parsed.get("room")
    date = parsed.get("date")
    quantity = parsed.get("quantity")

    # Validate required fields for inventory actions
    if action in ["add_inventory", "update_inventory", "remove_inventory", "query_inventory"] and not item:
        return {"error": "Missing 'item' field in command."}

    # Validate allowed actions
    from app.config import ALLOWED_ACTIONS
    if action not in ALLOWED_ACTIONS:
        return {"error": f"Unknown or unsupported action: {action}"}

    if action == "add_todo":
        return add_to_todo(item, date)

    if action == "add_inventory":
        # Normalize and validate room
        normalized_room = None
        if room:
            from app.config import ROOM_SYNONYMS, ALLOWED_ROOMS
            room_val = ROOM_SYNONYMS.get(room.lower().strip(), room.lower().strip())
            if room_val in ALLOWED_ROOMS:
                normalized_room = room_val
            else:
                logging.warning(f"Discarding invalid room: {room}")
        # Support list of items
        if isinstance(item, list):
            messages = []
            for sub_item in item:
                result = add_inventory(sub_item, location, quantity, room=normalized_room)
                msg = result.get("message", str(result))
                messages.append(msg)
            return {"message": " | ".join(messages)}
        else:
            return add_inventory(item, location, quantity, room=normalized_room)

    elif action == "update_inventory":
        # Ignore 'location_from' and 'location_to' if present, log warning for unknown keys
        unknown_keys = set(parsed.keys()) - {"action", "item", "location", "quantity", "date", "room"}
        for key in unknown_keys:
            if key in ["location_from", "location_to"]:
                logging.warning(f"Ignoring unsupported key in update_inventory: {key}")
            else:
                logging.warning(f"Unknown key in update_inventory: {key}")
        # Normalize and validate room
        normalized_room = None
        if room:
            from app.config import ROOM_SYNONYMS, ALLOWED_ROOMS
            room_val = ROOM_SYNONYMS.get(room.lower().strip(), room.lower().strip())
            if room_val in ALLOWED_ROOMS:
                normalized_room = room_val
            else:
                logging.warning(f"Discarding invalid room: {room}")
        # Support list of items
        if isinstance(item, list):
            messages = []
            for sub_item in item:
                result = update_existing_inventory(sub_item, location, quantity, room=normalized_room)
                msg = result.get("message", str(result))
                messages.append(msg)
            return {"message": " | ".join(messages)}
        else:
            return update_existing_inventory(item, location, quantity, room=normalized_room)

    elif action == "remove_inventory":
        return remove_inventory(item, quantity)

    elif action == "add_shopping":
        # Support list of items
        if isinstance(item, list):
            messages = []
            for sub_item in item:
                result = update_shopping(sub_item, quantity)
                msg = result.get("message", str(result))
                messages.append(msg)
            return {"message": " | ".join(messages)}
        else:
            return update_shopping(item, quantity)

    elif action == "query_inventory":
        db = read_json("inventory")
        # If item is a list, this will break:
        match = find_closest_item_key(item, db)
        # Should handle list case or restrict to string.
        if not match:
            logging.info("Item not found, escalating to LLM full inventory check")
            return {"message": ask_llm_about_data("inventory", original_command)}
        info = db[match]
        return {"message": f"{match} is in {info['location']} (Qty: {info['quantity']})"}

    elif action == "query_shopping":
        db = read_json("shopping")
        # If item is a list, this will break:
        match = [x for x in db if x.get("item") == item] if item else db
        # Should handle list case or restrict to string.
        if not match:
            logging.info("Shopping item not found, escalating to LLM full shopping check")
            return {"message": ask_llm_about_data("shopping", original_command)}
        return {"shopping_list": match}

    elif action == "query_todo":
        db = read_json("todo")
        # Only supports single date, not list of tasks.
        date_key = date or current_date_str()
        tasks = db.get(date_key, [])
        if not tasks:
            logging.info("No todos found for date, escalating to LLM full todo check")
            return {"message": ask_llm_about_data("todo", original_command)}
        return {"todo_list": tasks}

    elif action == "llm_query_inventory":
        db = read_json("inventory")
        return {"message": ask_llm_about_data("inventory", original_command)}

    elif action == "remove_last_inventory":
        db = read_json("inventory")
        if db:
            last_key = list(db.keys())[-1]
            del db[last_key]
            write_json("inventory", db)
            return {"message": f"Removed last inventory item: {last_key}"}
        return {"error": "Inventory is empty."}

    elif action == "remove_last_shopping":
        db = read_json("shopping")
        if db:
            last_item = db.pop()
            write_json("shopping", db)
            return {"message": f"Removed last shopping item: {last_item.get('item', last_item)}"}
        return {"error": "Shopping list is empty."}

    elif action == "remove_last_todo":
        db = read_json("todo")
        if db:
            last_date = sorted(db.keys())[-1]
            if db[last_date]:
                last_task = db[last_date].pop()
                write_json("todo", db)
                return {"message": f"Removed last todo: {last_task}"}
        return {"error": "Todo list is empty."}

    return {"error": "Unknown action"}


def find_closest_item_key(item, db):
    """
    Fuzzy match item name to closest key in database.
    """
    if not item or not db:
        return None
    item = item.lower().strip()
    # Increase similarity threshold to 0.8 (was 0.5)
    matches = difflib.get_close_matches(item, db.keys(), n=1, cutoff=0.8)
    return matches[0] if matches else None


def add_inventory(item, location, quantity=None, room=None):
    """
    Add inventory item(s) with location, quantity, and room.
    Supports both string and list values for 'item'.
    """
    db = read_json("inventory")

    # Handle case where item is None or empty
    if not item:
        return {"message": "No item specified for addition."}

    def make_entry(location, quantity, room):
        entry = {"location": location, "quantity": quantity or 1}
        if room:
            entry["room"] = room
        return entry

    # If item is a list, loop through each sub-item and add it
    if isinstance(item, list):
        messages = []
        for sub_item in item:
            if sub_item in db:
                db[sub_item]["quantity"] += quantity or 1
                messages.append(f"Updated {sub_item} in inventory. Quantity = {db[sub_item]['quantity']}.")
            else:
                db[sub_item] = make_entry(location, quantity, room)
                messages.append(f"Added {sub_item} to inventory.")
        write_json("inventory", db)
        return {"message": " | ".join(messages)}

    # If item is a string, process it as usual
    if item in db:
        db[item]["quantity"] += quantity or 1
        write_json("inventory", db)
        return {"message": f"Updated {item} in inventory. Quantity = {db[item]['quantity']}"}
    else:
        db[item] = make_entry(location, quantity, room)
        write_json("inventory", db)
        return {"message": f"Added {item} to inventory."}


def update_existing_inventory(item, location=None, quantity=None, room=None):
    """
    Update inventory item(s) location, quantity, and room.
    Supports both string and list values for 'item'.
    """
    db = read_json("inventory")

    # Handle case where item is None or empty
    if not item:
        return {"message": "No item specified for update."}

    def update_entry(entry, location, quantity, room):
        if location:
            entry["location"] = location
        if quantity is not None:
            entry["quantity"] = quantity
        if room:
            entry["room"] = room

    # If item is a list, loop through each sub-item and update or add it
    if isinstance(item, list):
        messages = []
        for sub_item in item:
            match = find_closest_item_key(sub_item, db)
            if not match:
                # Upsert: add new item if not found
                entry = {"location": location, "quantity": quantity or 1}
                if room:
                    entry["room"] = room
                db[sub_item] = entry
                messages.append(f"Added {sub_item} to inventory.")
                continue
            update_entry(db[match], location, quantity, room)
            messages.append(f"Updated {match} in inventory. Location = {db[match]['location']}, Quantity = {db[match]['quantity']}{' Room: ' + db[match]['room'] if 'room' in db[match] else ''}.")
        write_json("inventory", db)
        return {"message": " | ".join(messages)}

    # If item is a string, process it as usual
    match = find_closest_item_key(item, db)
    if not match:
        # Upsert: add new item if not found
        entry = {"location": location, "quantity": quantity or 1}
        if room:
            entry["room"] = room
        db[item] = entry
        write_json("inventory", db)
        return {"message": f"Added {item} to inventory."}
    update_entry(db[match], location, quantity, room)
    write_json("inventory", db)
    return {"message": f"Updated {match} in inventory. Location = {db[match]['location']}, Quantity = {db[match]['quantity']}{' Room: ' + db[match]['room'] if 'room' in db[match] else ''}."}


def remove_inventory(item, quantity=None):
    """
    Remove inventory item(s) or decrease quantity.
    Handles special case for removing last entry.
    Supports both string and list values for 'item'.
    """
    db = read_json("inventory")

    # Handle special case: remove last entry
    if isinstance(item, str) and item.lower().strip() in ["last entry", "last item", "most recent"]:
        if db:
            last_key = list(db.keys())[-1]
            del db[last_key]
            write_json("inventory", db)
            return {"message": f"Removed {last_key} (last entry) completely from inventory."}
        else:
            return {"message": "Inventory is empty."}

    # Handle case where item is None or empty
    if not item:
        return {"message": "No item specified for removal."}

    # If item is a list, loop through each sub-item and remove it
    if isinstance(item, list):
        messages = []
        for sub_item in item:
            match = find_closest_item_key(sub_item, db)
            if not match:
                messages.append(f"{sub_item} not found in inventory.")
                continue
            if quantity is None or quantity >= db[match]["quantity"]:
                del db[match]
                messages.append(f"Removed {match} completely from inventory.")
            else:
                db[match]["quantity"] -= quantity
                messages.append(f"Removed {quantity} of {match}. Remaining = {db[match]['quantity']}")
        write_json("inventory", db)
        return {"message": " | ".join(messages)}

    # If item is a string, process it as usual
    match = find_closest_item_key(item, db)
    if not match:
        return {"message": f"{item} not found in inventory."}
    if quantity is None or quantity >= db[match]["quantity"]:
        del db[match]
        write_json("inventory", db)
        return {"message": f"Removed {match} completely from inventory."}
    else:
        db[match]["quantity"] -= quantity
        write_json("inventory", db)
        return {"message": f"Removed {quantity} of {match}. Remaining = {db[match]['quantity']}"}


def query_inventory(item, original_command):
    """
    Query inventory for item details, escalate to LLM if not found.
    """
    db = read_json("inventory")
    match = find_closest_item_key(item, db)
    if not match:
        logging.info("Item not found, escalating to LLM full inventory check")
        return {"message": ask_llm_about_data("inventory", original_command)}
    info = db[match]
    return {"message": f"{match} is in {info['location']} (Qty: {info['quantity']})"}


def add_shopping(item, quantity=None):
    """
    Add shopping item(s) with quantity.
    Supports both string and list values for 'item'.
    """
    db = read_json("shopping")

    # Handle case where item is None or empty
    if not item:
        return {"message": "No item specified for addition."}

    # If item is a list, loop through each sub-item and add it
    if isinstance(item, list):
        messages = []
        for sub_item in item:
            if sub_item in db:
                db[sub_item]["quantity"] += quantity or 1
                messages.append(f"Updated {sub_item} in shopping list. Quantity = {db[sub_item]['quantity']}.")
            else:
                db[sub_item] = {"quantity": quantity or 1}
                messages.append(f"Added {sub_item} to shopping list.")
        write_json("shopping", db)
        return {"message": " | ".join(messages)}

    # If item is a string, process it as usual
    if item in db:
        db[item]["quantity"] += quantity or 1
        write_json("shopping", db)
        return {"message": f"Updated {item} in shopping list. Quantity = {db[item]['quantity']}"}
    else:
        db[item] = {"quantity": quantity or 1}
        write_json("shopping", db)
        return {"message": f"Added {item} to shopping list."}


def update_shopping(item, quantity=None):
    """
    Update shopping item(s) quantity.
    Supports both string and list values for 'item'.
    """
    db = read_json("shopping")

    # Handle case where item is None or empty
    if not item:
        return {"message": "No item specified for update."}

    # If item is a list, loop through each sub-item and update it
    if isinstance(item, list):
        messages = []
        for sub_item in item:
            match = find_closest_item_key(sub_item, db)
            if not match:
                messages.append(f"{sub_item} not found in shopping list.")
                continue
            if quantity is not None:
                db[match]["quantity"] = quantity
            messages.append(f"Updated {match} in shopping list. Quantity = {db[match]['quantity']}.")
        write_json("shopping", db)
        return {"message": " | ".join(messages)}

    # If item is a string, process it as usual
    match = find_closest_item_key(item, db)
    if not match:
        return {"message": f"{item} not found in shopping list."}
    if quantity is not None:
        db[match]["quantity"] = quantity
    write_json("shopping", db)
    return {"message": f"Updated {match} in shopping list. Quantity = {db[match]['quantity']}"}


def add_to_todo(task, date=None):
    """
    Add task to todo list for a specific date.
    """
    db = read_json("todo")
    date_key = date or current_date_str()
    db.setdefault(date_key, []).append(task)
    write_json("todo", db)
    return {"message": f"Added task '{task}' for {date_key}"}


def ask_llm_about_data(datatype, question):
    """
    Escalate query to LLM with full data context for fuzzy/natural language questions.
    """
    db = read_json(datatype)

    prompt = f"""
You are JARVIS, a home assistant. Here is the current {datatype} data:

{json.dumps(db, indent=2)}

Now answer the user's question:
\"{question}\"

Use your best judgment to match fuzzy phrasing, synonyms, or locations.
If nothing relevant is found, say so clearly.
Respond naturally and helpfully.
"""
    payload = {
        "model": "mistral",
        "prompt": prompt,
        "stream": False
    }

    try:
        res = requests.post("http://localhost:11434/api/generate", json=payload)
        return res.json().get("response", "").strip()
    except Exception as e:
        logging.error("LLM error during full data query: %s", e)
        return "I'm not sure how to answer that."
