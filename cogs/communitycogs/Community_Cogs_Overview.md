# Community Cogs Subsystem Overview

The `/cogs/communitycogs` directory implements community engagement commands allowing players to submit personal quirks, view approved quirks, and enable admins to review pending submissions via Discord UI components.

## 🧭 Navigation
- **Parent Cog**: [[Cogs_Overview]]
- **Related Modules**: [[Community_System_Overview]], [[Community_UI_Overview]], [[Community_Quirks_Overview]], [[Community_Submissions_Data_Overview]]
- **Requirements Reference**: [[HIGH_LEVEL_REQUIREMENTS#Table-7-Community-Submissions--Quirk-Management]], [[DETAILED_REQUIREMENTS#FR-COM-01-Submit-Player-Quirk]]

---

## 📄 Command Implementations

| File | Slash Command | Description | Key Delegations |
| :--- | :--- | :--- | :--- |
| `setquirk.py` | `/setquirk` | Opens an interactive Discord modal for a player to submit their custom roleplay quirk. | Dispatches `submissionmodal.py` in [[Community_UI_Overview]]. |
| `reviewquirks.py` | `/reviewquirks` | Displays pending user quirks to admins with one-click interactive Approve/Reject buttons. | Uses `reviewview.py` and `rejectionselect.py` in [[Community_UI_Overview]]. |
| `displayquirks.py` | `/displayquirks` | Displays all currently approved quirks for players in an embed. | Calls `getapproved.py` in [[Community_Quirks_Overview]]. |

---

## 🔗 Connected Overviews
- [[Cogs_Overview]]: Return to Cogs Index
- [[Community_System_Overview]]: Understand quirk business logic and persistence
- [[Community_UI_Overview]]: Modal and button view interfaces
