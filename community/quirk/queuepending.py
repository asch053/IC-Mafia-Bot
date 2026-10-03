# community/quirk/queuepending.py
import json
import os
import logging
from community.quirk.getpending import get_all_pending, PENDING_PATH

logger = logging.getLogger('discord')


def _ensure_data_dir():
    os.makedirs("data/narration", exist_ok=True)


def queue_pending_quirk(user_id: int, quirk_text: str):
    """Saves a user's quirk to the pending queue for review."""
    _ensure_data_dir()
    pending = get_all_pending()
    pending[str(user_id)] = quirk_text[:100]

    with open(PENDING_PATH, 'w', encoding='utf-8') as f:
        json.dump(pending, f, indent=4)
    logger.info(f"Quirk queued for review: User {user_id}")
    return True

