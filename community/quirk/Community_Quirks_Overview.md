# Community Quirks Subsystem Overview

The `/community/quirk` directory provides low-level atomic operations for reading, queuing, approving, and rejecting user-submitted quirks in JSON data storage.

## 🧭 Navigation
- **Parent Subsystem**: [[Community_System_Overview]]
- **Related Modules**: [[Community_UI_Overview]], [[Narration_Data_Overview]]
- **Requirements Reference**: [[HIGH_LEVEL_REQUIREMENTS#Table-7-Community-Submissions--Quirk-Management]], [[DETAILED_REQUIREMENTS#FR-COM-02-Admin-Quirk-Review-Workflow]]

---

## 📄 File Index

| File | Operation | Target Storage | Purpose |
| :--- | :--- | :--- | :--- |
| `queuepending.py` | Create / Queue | `data/narration/pending_quirks.json` | Adds a new user quirk to the pending moderation queue. |
| `getpending.py` | Read | `data/narration/pending_quirks.json` | Retrieves pending quirks for admin review views. |
| `getapproved.py` | Read | `data/narration/player_concepts.json` | Retrieves all approved quirks across players. |
| `getuserquirk.py` | Read | `data/narration/player_concepts.json` | Fetches the active approved quirk for a specific user ID. |
| `approve.py` | Update / Transition | Both files | Moves a quirk from pending into approved storage. |
| `reject.py` | Delete / Archive | `data/narration/pending_quirks.json` | Removes a rejected quirk and records reason. |

---

## 🔗 Connected Overviews
- [[Community_System_Overview]]: Return to Community System Index
- [[Community_UI_Overview]]: Discord UI views that call these operations
- [[Narration_Data_Overview]]: The storage files altered by these scripts
