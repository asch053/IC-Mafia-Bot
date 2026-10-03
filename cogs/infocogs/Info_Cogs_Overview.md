# Info Cogs Subsystem Overview

The `/cogs/infocogs` directory provides reference commands for players to learn game rules, examine role descriptions, and query bot information without interrupting active gameplay.

## 🧭 Navigation
- **Parent Cog**: [[Cogs_Overview]]
- **Related Modules**: [[Game_Data_Overview]], [[Game_Setup_Data_Overview]]
- **Requirements Reference**: [[HIGH_LEVEL_REQUIREMENTS#Table-9-Information--Help-Commands]], [[DETAILED_REQUIREMENTS#FR-INF-06-Information-Delivery]]

---

## 📄 Command Implementations

| File | Slash Command | Description | Data Source |
| :--- | :--- | :--- | :--- |
| `mafiainfo.py` | `/mafiainfo` | Overview of the Mafia bot, current game settings, and general gameplay mechanics. | `data/game_setup/rules.txt` |
| `mafiaroles.py` | `/mafiaroles` | Comprehensive reference of all configured roles, factions, and special powers. | `data/game_setup/role_definition.json` |
| `mafiarules.py` | `/mafiarules` | Complete rules of the game including voting conduct, inactivity policies, and phase timings. | `data/game_setup/rules.json` |

---

## 🔗 Connected Overviews
- [[Cogs_Overview]]: Return to Cogs Index
- [[Game_Data_Overview]]: Dynamic rule parser (`getrules.py`)
- [[Game_Setup_Data_Overview]]: Role definitions and rule text files
