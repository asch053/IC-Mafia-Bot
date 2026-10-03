# community/quirk/approve.py
import json
import os
import logging
from community.quirk.getpending import get_all_pending, PENDING_PATH
from community.quirk.getapproved import get_all_approved, APPROVED_PATH

logger = logging.getLogger('discord')

_memory_quirks = {}


def approve_quirk_logic(user_id: int, quirk: str = None) -> str:
    """
    Moves a quirk from pending to approved (or directly sets quirk if provided).
    Saves approved quirk to player_concepts.json.
    """
    user_key = str(user_id)
    if quirk is not None:
        quirk_text = quirk[:100]
        _memory_quirks[user_key] = quirk_text
        approved = get_all_approved()
        approved[user_key] = quirk_text

        os.makedirs(os.path.dirname(APPROVED_PATH) or ".", exist_ok=True)
        with open(APPROVED_PATH, 'w') as f:
            json.dump(approved, f, indent=4)

        logger.info(f"Quirk approved: User {user_id}")
        return quirk_text

    # quirk is None: check if already approved/cached first
    if user_key in _memory_quirks:
        return _memory_quirks[user_key]

    pending = get_all_pending()
    if user_key in pending:
        quirk_text = pending.pop(user_key)
        try:
            with open(PENDING_PATH, 'w') as f:
                json.dump(pending, f, indent=4)
        except Exception:
            pass
    else:
        raise ValueError(f"User {user_id} not found in pending queue.")

    approved = get_all_approved()
    approved[user_key] = quirk_text

    os.makedirs(os.path.dirname(APPROVED_PATH) or ".", exist_ok=True)
    with open(APPROVED_PATH, 'w') as f:
        json.dump(approved, f, indent=4)

    logger.info(f"Quirk approved: User {user_id}")
    return quirk_text

