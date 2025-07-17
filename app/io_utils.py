"""
io_utils.py

Utility functions for reading/writing JSON data files and date formatting.
"""

import os
import json
import tempfile
from datetime import datetime
DATA_FILES = {
    "inventory": "data/inventory.json",
    "todo": "data/todo.json",
    "shopping": "data/shopping.json"
}

def init_data_files():
    """
    Ensure all required data files exist, create if missing.
    """
    for key, file in DATA_FILES.items():
        if not os.path.exists(file):
            with open(file, "w") as f:
                f.write("[]" if key == "shopping" else "{}")

def read_json(key):
    """
    Read JSON data from file for given key.
    """
    with open(DATA_FILES[key], "r") as f:
        return json.load(f)

def write_json(key, data):
    """
    Write JSON data to file for given key.
    """
    with open(DATA_FILES[key], "w") as f:
        json.dump(data, f, indent=2)

def current_date_str():
    """
    Return current date as DD-MM-YYYY string.
    """
    return datetime.now().strftime("%d-%m-%Y")

def load_json(filepath, default=None):
    """
    Load JSON from a file. If missing or invalid, return default (empty list or dict).
    """
    if default is None:
        default = [] if filepath.endswith('.json') else {}
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        return default

def save_json(filepath, data):
    """
    Write JSON data to file atomically using tempfile + os.replace.
    Compact format, flush and fsync to ensure data is written to disk.
    """
    dirpath = os.path.dirname(filepath)
    with tempfile.NamedTemporaryFile("w", dir=dirpath, delete=False) as tf:
        json.dump(data, tf, separators=(",", ":"))
        tf.flush()
        os.fsync(tf.fileno())
        tempname = tf.name
    try:
        os.replace(tempname, filepath)
    except Exception as e:
        raise RuntimeError(f"Failed to write JSON atomically to {filepath}: {e}")
def init_data_files():
    """
    Ensure all required data files exist, create if missing.
    """
    for key, file in DATA_FILES.items():
        if not os.path.exists(file):
            with open(file, "w") as f:
                f.write("[]" if key == "shopping" else "{}")
def read_json(key):
    """
    Read JSON data from file for given key.
    """
    with open(DATA_FILES[key], "r") as f:
        return json.load(f)
def write_json(key, data):
    """
    Write JSON data to file for given key.
    """
    with open(DATA_FILES[key], "w") as f:
        json.dump(data, f, indent=2)
def current_date_str():
    """
    Return current date as DD-MM-YYYY string.
    """
    return datetime.now().strftime("%d-%m-%Y")

"""
io_utils.py

Utility functions for reading/writing JSON data files and date formatting.
"""

import os
import json
import tempfile
from datetime import datetime

# Data file paths for each type
DATA_FILES = {
    "inventory": "data/inventory.json",
    "todo": "data/todo.json",
    "shopping": "data/shopping.json"
}

def init_data_files():
    """
    Ensure all required data files exist, create if missing.
    """
    for key, file in DATA_FILES.items():
        if not os.path.exists(file):
            with open(file, "w") as f:
                f.write("[]" if key == "shopping" else "{}")

def read_json(key):
    """
    Read JSON data from file for given key.
    """
    with open(DATA_FILES[key], "r") as f:
        return json.load(f)

def write_json(key, data):
    """
    Write JSON data to file for given key.
    """
    with open(DATA_FILES[key], "w") as f:
        json.dump(data, f, indent=2)

def current_date_str():
    """
    Return current date as DD-MM-YYYY string.
    """
    return datetime.now().strftime("%d-%m-%Y")

def load_json(filepath, default=None):
    """
    Load JSON from a file. If missing or invalid, return default (empty list or dict).
    """
    if default is None:
        default = [] if filepath.endswith('.json') else {}
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        return default

def save_json(filepath, data):
    """
    Write JSON data to file atomically using tempfile + os.replace.
    Compact format, flush and fsync to ensure data is written to disk.
    """
    dirpath = os.path.dirname(filepath)
    with tempfile.NamedTemporaryFile("w", dir=dirpath, delete=False) as tf:
        json.dump(data, tf, separators=(",", ":"))
        tf.flush()
        os.fsync(tf.fileno())
        tempname = tf.name
    try:
        os.replace(tempname, filepath)
    except Exception as e:
        raise RuntimeError(f"Failed to write JSON atomically to {filepath}: {e}")
