# Discord Setup Data Overview

The `/data/discord_setup` directory holds templates and JSON mappings for Discord server role hierarchies and legacy game setup structures.

## 🧭 Navigation
- **Parent Subsystem**: [[Data_Assets_Overview]]
- **Related Modules**: [[Bot_Setup_Overview]], [[Utilities_Overview]]

---

## 📄 File Index

| File | Format | Purpose |
| :--- | :--- | :--- |
| `discord_roles.json` | JSON | Mapping of server role names to Discord snowflake IDs (Admin, Living, Dead, Spectator). |
| `old_discord_roles.json` | JSON | Archive of prior Discord server role configurations. |
| `Old_mafia_setups.json` | JSON | Archive of legacy game role distribution matrices. |

---

## 🔗 Connected Overviews
- [[Data_Assets_Overview]]: Return to Data Assets Index
- [[Utilities_Overview]]: Functions like `updatediscordroles.py` that utilize these mappings
