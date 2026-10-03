# Shared Utilities Subsystem Overview

The `/utils` directory provides common utility functions, file I/O wrappers, Discord API message formatters, role permission guards, and data serialization helpers utilized across the entire bot codebase.

## 🧭 Navigation
- **Parent Hub**: [[Root_Project_Overview]]
- **Related Modules**: [[Game_Engine_Overview]], [[Cogs_Overview]], [[Bot_Setup_Overview]]
- **Requirements Reference**: [[DETAILED_REQUIREMENTS]]

---

## 📄 File Index

| File | Purpose | Key Exports |
| :--- | :--- | :--- |
| `utilities.py` | Core helper functions, time parsing, list formatting, and general discord helpers. | `format_time()`, `safe_send()` |
| `admincheck.py` | Permission decorator ensuring slash commands can only be executed by administrators. | `is_admin()`, `admin_only()` |
| `loaddata.py` | Robust JSON file loader with path resolution, caching, and fallback handling. | `load_json_data()` |
| `savejsondata.py` | Atomic JSON writer with directory creation and schema serialization. | `save_json_data()` |
| `sendchunkedmessage.py` | Automatically splits strings exceeding Discord's 2000 character limit across multiple messages. | `send_chunked_message()` |
| `addchunkedfield.py` | Splits large embed field values exceeding 1024 characters into sequential fields. | `add_chunked_field()` |
| `sendroledm.py` | Generates and sends private role card embeds to players via Direct Message. | `send_role_dm()` |
| `sendmafiainfodm.py` | Dispatches informational Mafia rule guides and role lists to player DMs. | `send_mafia_info_dm()` |
| `updatediscordroles.py` | Adds or removes Discord living/dead game roles on guild members asynchronously. | `update_player_roles()` |
| `formattimeremain.py` | Computes remaining duration until phase change and formats as human-readable strings. | `format_time_remaining()` |
| `filtergamesbytime.py` | Filters historical game lists based on date ranges (e.g. past week, past month, all-time). | `filter_games_by_time()` |
| `getrolehierarchy.py` | Sorts player roles based on predefined hierarchy for clean status displays. | `get_role_hierarchy()` |
| `logprompttojson.py` | Archives raw LLM narration prompts, system contexts, and responses to `logs/prompts_archive.json`. | `log_prompt_to_json()` |
| `archivephasedata.py` | Snapshots phase votes, living players, and action targets into timestamped stats archives. | `archive_phase_data()` |

---

## 🔗 Connected Overviews
- [[Root_Project_Overview]]: Return to Master Hub
- [[Game_Engine_Overview]]: Understand how the engine uses these helpers for state transitions
- [[Cogs_Overview]]: See how commands use chunking and permission decorators
- [[Data_Assets_Overview]]: See data files read and written by `loaddata.py` and `savejsondata.py`
