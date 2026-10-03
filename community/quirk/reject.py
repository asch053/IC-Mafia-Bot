# community/quirk/reject.py
import json
import logging
from community.quirk.getpending import get_all_pending, PENDING_PATH

logger = logging.getLogger('discord')


def reject_quirk_logic(user_id: int) -> str:
    """Removes a quirk from pending and returns the text for notification."""
    pending = get_all_pending()
    user_key = str(user_id)

    quirk_text = "Unknown submission"
    if user_key in pending:
        quirk_text = pending.pop(user_key)
        with open(PENDING_PATH, 'w', encoding='utf-8') as f:
            json.dump(pending, f, indent=4)

    logger.info(f"Quirk rejected: User {user_id}")
    return quirk_text

