# Game Cogs Subsystem Overview

The `/cogs/gamecogs` directory implements the player-facing gameplay commands that drive day-to-day Mafia participation: signups, role lookups, daytime voting, and nighttime secret actions.

## 🧭 Navigation
- **Parent Cog**: [[Cogs_Overview]]
- **Related Modules**: [[Game_Engine_Overview]], [[Game_Actions_Overview]], [[Game_System_Overview]]
- **Requirements Reference**: [[HIGH_LEVEL_REQUIREMENTS#Table-3-Player-Registration--Signups]], [[DETAILED_REQUIREMENTS#FR-VOT-01-Cast-Lynch-Vote]]

---

## 📄 Command Implementations

| File | Slash Command | Description | Context / Preconditions |
| :--- | :--- | :--- | :--- |
| `join.py` | `/mafiajoin` | Registers the invoking user into the upcoming game. | Public Channel; Signup Phase. |
| `leave.py` | `/mafialeave` | Removes a registered user prior to game launch. | Public Channel; Signup Phase. |
| `status.py` | `/mafiastatus` | Displays current game phase, countdown, living player count, and alive/dead roster. | Public Channel; Any Phase. |
| `vote.py` | `/vote [player]` | Casts or changes a lynch vote targeting a living player. | Public Channel; Day Phase; Living Voter. |
| `count.py` | `/mafiacount` | Displays live vote tally showing candidates, vote counts, and voters. | Public Channel; Day Phase. |
| `myrole.py` | `/myrole` | DMs the player their secret role card, abilities, alignment, and win condition. | Direct Messages (DMs) only. |
| `nightactions.py` | `/kill`, `/heal`, `/investigate`, `/block` | Registers secret night action target for the current Night phase. | Direct Messages (DMs) only; Night Phase. |
| `autocomplete.py` | Auto-complete Handler | Provides dynamic autocompletion for player names during `/vote` and `/nightactions`. | Dynamic list of living players. |
| `listener.py` | Event Listener | Monitors game channels for message activity and player engagement. | Discord event dispatcher. |

---

## 🔗 Connected Overviews
- [[Cogs_Overview]]: Return to Cogs Index
- [[Game_Engine_Overview]]: Core state machine executing these player decisions
- [[Game_Actions_Overview]]: Resolution logic for night action commands
