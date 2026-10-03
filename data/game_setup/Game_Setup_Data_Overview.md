# Game Setup Data Overview

The `/data/game_setup` directory contains the foundational definitions for game balancing, role powers, rule text, and bot filler names.

## 🧭 Navigation
- **Parent Subsystem**: [[Data_Assets_Overview]]
- **Related Modules**: [[Game_System_Overview]], [[Game_Engine_Overview]], [[Info_Cogs_Overview]]
- **Requirements Reference**: [[DETAILED_REQUIREMENTS#FR-ENG-03-Role-Distribution-Engine]]

---

## 📄 File Index

| File | Content | Key Consumers | Schema Notes |
| :--- | :--- | :--- | :--- |
| `mafia_setups.json` | Matrix of player counts to role distributions across game variants (Classic, Battle Royale, Mini). | `game/setup_generator.py` | Defines required roles, town/mafia thresholds, and special role allocations. |
| `role_definition.json` | Master definitions of all roles, faction alliances, active abilities, and passive immunity tags. | `game/roles.py`, `cogs/infocogs/mafiaroles.py` | JSON object mapping role names to ability tags, priority tiers, and descriptions. |
| `theme_roles.json` | Thematic reskins and descriptive flavor for all 10 canonical roles across all 9 narrative themes (Classic, Horror, Explicit Kinky NSFW, Rom Com, Office Restructuring, High Fantasy, Cyberpunk, Comedy, Lovecraftian Horror). | `game/roles.py`, `game/engine/prepare.py`, `utils/sendroledm.py` | Maps `[Theme][CanonicalRole]` to `display_name`, `description`, and `short_description`. |
| `rules.json` | Structured JSON game rules displayed by `/mafiarules`. | `cogs/infocogs/mafiarules.py`, `game/data/getrules.py` | Refactored v2: 6 concise conduct rules (`1` to `6`) eliminating duplicate numbering. |
| `rules.txt` | Human-readable comprehensive rulebook text. | `cogs/infocogs/mafiainfo.py`, `game/data/getrules.py` | Clean 6-point conduct roster formatted for single-field embed display. |
| `bot_names.txt` | List of unique NPC bot names for automatic lobby filling. | `game/engine/prepare.py` | Line-separated unique character names for NPC players. |

---

## 🔗 Connected Overviews
- [[Data_Assets_Overview]]: Return to Data Assets Index
- [[Game_Engine_Overview]]: Consumes setups during `prepare_game()`
- [[Info_Cogs_Overview]]: Exposes rules to users
