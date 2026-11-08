import logging
import json
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def save_json_data(filepath, data):
    """Saves a dictionary or list to a JSON file, ensuring lowercase root folder names (data/, stats/, logs/)."""
    try:
        if isinstance(filepath, str):
            norm = filepath.replace("\\", "/")
            for folder in ("data", "stats", "logs"):
                if norm.lower().startswith(f"{folder}/"):
                    filepath = f"{folder}/" + norm[len(folder) + 1:]
                    break
                elif norm.lower().startswith(f"./{folder}/"):
                    filepath = f"./{folder}/" + norm[len(folder) + 3:]
                    break
            parent = os.path.dirname(filepath)
            if parent:
                os.makedirs(parent, exist_ok=True)
        with open(filepath, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save data to {filepath}: {e}")