import json
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def load_data(filepath, error_default=None):
    """Loads data from a JSON or TXT file."""
    filepath = filepath.lower()
    logger.debug(f"Loading data from {filepath}.")
    try:
        with open(filepath, "r", encoding='utf-8') as f:
            if filepath.endswith(".json"):
                logger.debug(f"Detected JSON file format for {filepath}.")
                return json.load(f)
            else:
                logger.debug(f"Detected TXT file format for {filepath}.")
                return [line.strip() for line in f]
    except FileNotFoundError:
        logger.error(f"File not found: {filepath}. Returning empty default.")
        return error_default if error_default is not None else ({} if filepath.endswith(".json") else [])
    except Exception as e:
        logger.exception(f"An unexpected error occurred loading {filepath}: {e}")
        return error_default if error_default is not None else None