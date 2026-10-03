# Community UI Components Overview

The `/community/ui` directory contains modern `discord.ui` interactive components (Modals, Buttons, and Select Menus) for collecting and moderating community submissions.

## 🧭 Navigation
- **Parent Subsystem**: [[Community_System_Overview]]
- **Related Modules**: [[Community_Cogs_Overview]], [[Community_Quirks_Overview]]
- **Requirements Reference**: [[DETAILED_REQUIREMENTS#FR-COM-01-Submit-Player-Quirk]]

---

## 📄 Component Index

| File | Component Class | UI Type | Purpose |
| :--- | :--- | :--- | :--- |
| `submissionmodal.py` | `QuirkSubmissionModal` | `discord.ui.Modal` | Text input pop-up allowing users to type and submit custom roleplay quirks. |
| `reviewview.py` | `QuirkReviewView` | `discord.ui.View` | Interactive message view with "Approve" (green) and "Reject" (red) buttons for admins. |
| `rejectionselect.py` | `RejectionSelect` | `discord.ui.Select` | Dropdown menu prompting admins to select a standardized rejection reason (NSFW, offensive, nonsense). |

---

## 🔗 Connected Overviews
- [[Community_System_Overview]]: Return to Community System Index
- [[Community_Cogs_Overview]]: Slash commands that deploy these components
- [[Community_Quirks_Overview]]: Data handlers triggered by UI selections
