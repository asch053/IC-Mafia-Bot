# community/quirk/getpending.py
import json
import os
import logging

logger = logging.getLogger('discord')
PENDING_PATH = "data/narration/pending_quirks.json"


def get_all_pending() -> dict:
    """Returns a dictionary of all users awaiting quirk approval."""
    if not os.path.exists(PENDING_PATH):
        return {}
    try:
        with open(PENDING_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}

