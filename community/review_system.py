# community/review_system.py
"""
Review system facade module.
Re-exports review view, select, and modal from community.ui.* for clean backward compatibility.
"""

from community.ui.rejectionselect import RejectionReasonSelect, REJECTION_REASONS
from community.ui.reviewview import QuirkReviewView
from community.ui.submissionmodal import QuirkSubmissionModal

__all__ = [
    "REJECTION_REASONS",
    "RejectionReasonSelect",
    "QuirkReviewView",
    "QuirkSubmissionModal",
]

