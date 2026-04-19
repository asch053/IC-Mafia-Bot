import json
import os
import logging

logger = logging.getLogger('discord')

# Using lowercase 'data' directory as requested
PENDING_PATH = "data/narration/pending_quirks.json"
APPROVED_PATH = "data/narration/player_concepts.json"

def _ensure_data_dir():
    """Ensure the data directory exists."""
    os.makedirs("data/narration", exist_ok=True)

def get_all_pending() -> dict:
    """Returns a dictionary of all users awaiting quirk approval."""
    if not os.path.exists(PENDING_PATH):
        return {}
    try:
        with open(PENDING_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}

def get_all_approved() -> dict:
    """Returns the entire dictionary of approved player quirks."""
    if not os.path.exists(APPROVED_PATH):
        return {}
    try:
        with open(APPROVED_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}

def get_user_quirk(user_id: int) -> str:
    """Returns the current approved quirk for a user, or an empty string."""
    approved = get_all_approved()
    return approved.get(str(user_id), "")

def queue_pending_quirk(user_id: int, quirk_text: str):
    """Saves a user's quirk to the pending queue for review."""
    _ensure_data_dir()
    pending = get_all_pending()
    pending[str(user_id)] = quirk_text[:100]  # Hard limit to 100 chars
    
    with open(PENDING_PATH, 'w', encoding='utf-8') as f:
        json.dump(pending, f, indent=4)
    logger.info(f"Quirk queued for review: User {user_id}")

def approve_quirk_logic(user_id: int) -> str:
    """Moves a quirk from pending to approved and returns the text."""
    pending = get_all_pending()
    user_key = str(user_id)
    
    if user_key not in pending:
        raise ValueError("User not found in pending queue.")
        
    quirk_text = pending.pop(user_key)
    
    # Save updated pending list
    with open(PENDING_PATH, 'w', encoding='utf-8') as f:
        json.dump(pending, f, indent=4)
        
    # Save to approved list
    approved = get_all_approved()
    approved[user_key] = quirk_text
    
    _ensure_data_dir()
    with open(APPROVED_PATH, 'w', encoding='utf-8') as f:
        json.dump(approved, f, indent=4)
        
    logger.info(f"Quirk approved: User {user_id}")
    return quirk_text

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