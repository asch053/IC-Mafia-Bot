# community/quirk/getapproved.py
import json
import os
import logging

logger = logging.getLogger('discord')
APPROVED_PATH = "data/narration/player_concepts.json"


def get_all_approved() -> dict:
    """Returns the entire dictionary of approved player quirks."""
    if not os.path.exists(APPROVED_PATH):
        return {}
    try:
        with open(APPROVED_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}

