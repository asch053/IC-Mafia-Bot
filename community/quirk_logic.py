# community/quirk_logic.py
"""
Facade for community quirk operations.
Re-exports modular functions from community.quirk.* for clean backward compatibility.
"""

from community.quirk.getpending import get_all_pending, PENDING_PATH
from community.quirk.getapproved import get_all_approved, APPROVED_PATH
from community.quirk.getuserquirk import get_user_quirk
from community.quirk.queuepending import queue_pending_quirk
from community.quirk.approve import approve_quirk_logic
from community.quirk.reject import reject_quirk_logic

DATA_PATH = APPROVED_PATH

# Backward-compatible convenience aliases
approve_quirk = approve_quirk_logic
reject_quirk = reject_quirk_logic

__all__ = [
    "get_all_pending",
    "get_all_approved",
    "get_user_quirk",
    "queue_pending_quirk",
    "approve_quirk_logic",
    "reject_quirk_logic",
    "approve_quirk",
    "reject_quirk",
    "DATA_PATH",
    "PENDING_PATH",
    "APPROVED_PATH",
]

