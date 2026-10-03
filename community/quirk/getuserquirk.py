# community/quirk/getuserquirk.py
from community.quirk.getapproved import get_all_approved


def get_user_quirk(user_id: int) -> str:
    """Returns the current approved quirk for a user, or an empty string."""
    approved = get_all_approved()
    return approved.get(str(user_id), "")

