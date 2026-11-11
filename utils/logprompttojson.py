import logging
import os
import json
from datetime import datetime

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def log_prompt_to_json(phase_key, prompt):
    os.makedirs("logs", exist_ok=True)
    log_file = os.path.join("logs", "prompts_archive.json")
    logger.debug(f"Logging prompt for phase '{phase_key}' to {log_file}.")
    data = {}
    if os.path.exists(log_file):
        with open(log_file, 'r', encoding='utf-8') as f:
            data = json.load(f)   
    data[phase_key] = {
        "timestamp": str(datetime.now()),
        "prompt": prompt
    }
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    logger.info(f"Prompt logged for phase '{phase_key}'.")
    return data