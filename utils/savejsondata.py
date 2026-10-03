import logging
import json

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def save_json_data(filepath, data):
    """Saves a dictionary or list to a JSON file."""
    try:
        with open(filepath, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save data to {filepath}: {e}")