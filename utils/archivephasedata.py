import logging
import os
import json
from datetime import datetime

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def archive_phase_data(phase_key: str, prompt: str, thoughts: str, result: str):
    """Stores the complete AI transaction for debugging and observability."""
    archive_path = os.path.join("Logs", "prompts_archive.json")
    logger.debug(f"Archiving phase data for phase '{phase_key}' to {archive_path}.")
    os.makedirs("Logs", exist_ok=True)
    archive_data = {}
    if os.path.exists(archive_path):
        try:
            with open(archive_path, 'r', encoding='utf-8') as f:
                archive_data = json.load(f)
                logger.debug(f"Loaded existing archive data from {archive_path}.")
        except json.JSONDecodeError:
            archive_data = {}
            logger.warning(f"Existing archive file {archive_path} is not valid JSON. Starting with an empty archive.")
    archive_data[phase_key] = {
        "timestamp": datetime.now().isoformat(),
        "prompt_sent": prompt,
        "ai_reasoning": thoughts if thoughts else "No thoughts recorded.",
        "final_story": result
    }
    with open(archive_path, 'w', encoding='utf-8') as f:
        json.dump(archive_data, f, indent=4)
        logger.info(f"Phase data for '{phase_key}' archived successfully.")
    logger.debug(f"Archived data for '{phase_key}': {archive_data[phase_key]}")
    return archive_data