# Data Assets Subsystem Overview

The `/data` directory stores static configurations, role definitions, game setups, narrative flavor text, in-jokes, and external service account credentials.

## 🧭 Navigation
- **Parent Hub**: [[Root_Project_Overview]]
- **Sub-Directories**:
  - [[Community_Submissions_Data_Overview]] (`/data/community_submissions/`)
  - [[Discord_Setup_Data_Overview]] (`/data/discord_setup/`)
  - [[Game_Setup_Data_Overview]] (`/data/game_setup/`)
  - [[Narration_Data_Overview]] (`/data/narration/`)
- **Connected Systems**: [[Game_System_Overview]], [[Community_System_Overview]], [[Utilities_Overview]]
- **Requirements Reference**: [[DETAILED_REQUIREMENTS#2-Technical-Architecture--Directory-Mapping]]

---

## 📄 Root Data Assets

| File | Content & Purpose | Security / Privacy Note |
| :--- | :--- | :--- |
| `ic-mafia-bot-41a41f61e757.json` | Google Cloud Service Account credentials for Google Sheets export. | Confidential key file. |
| `player_concepts.json` | Master store of active player narrative concepts and quirks. | Infused during AI narration. |

---

## 🔗 Connected Overviews
- [[Root_Project_Overview]]: Return to Master Hub
- [[Game_Setup_Data_Overview]]: Game rules and role balancing setups
- [[Narration_Data_Overview]]: Narrative themes and quirk archives
