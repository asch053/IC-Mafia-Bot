# Game Data Helper Overview

The `/game/data` directory houses data access helpers responsible for dynamically loading, parsing, and validating rule definitions from repository data assets.

## 🧭 Navigation
- **Parent Subsystem**: [[Game_System_Overview]]
- **Related Modules**: [[Game_Setup_Data_Overview]], [[Info_Cogs_Overview]]
- **Requirements Reference**: [[HIGH_LEVEL_REQUIREMENTS#Table-9-Information--Help-Commands]], [[DETAILED_REQUIREMENTS#FR-INF-06-Information-Delivery]]

---

## 📄 File Index

| File | Purpose | Key Capabilities & Enhancements | Data Source |
| :--- | :--- | :--- | :--- |
| `getrules.py` | Generates polished Discord protocol embeds for game announcements and `/mafiarules`. | • **Native Dynamic Timestamps**: Parses `start_time` into Discord's `<t:epoch:F> (<t:epoch:R>)` for automatic player timezone localization.<br>• **Unified Conduct Rules**: Renders rules `1.` through `6.` cleanly without splitting into fragmented Part 1/Part 2 fields.<br>• **Clean Configuration Cards**: Formats setup parameters using Discord blockquotes (`> `).<br>• **Collision-Free Objectives**: Lists faction objectives using bullet points (`•`) rather than numeric keys. | `data/game_setup/rules.json`, `data/game_setup/rules.txt` |

---

## 🔗 Connected Overviews
- [[Game_System_Overview]]: Return to Game System Index
- [[Game_Setup_Data_Overview]]: The raw data assets loaded by `getrules.py`
- [[Info_Cogs_Overview]]: Slash commands that expose these rules to Discord users
