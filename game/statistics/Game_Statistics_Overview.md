# Game Statistics Subsystem Overview

The `/game/statistics` directory contains in-game record tracking, achievement checking, and Hall of Fame condition validators evaluated during active gameplay.

## 🧭 Navigation
- **Parent Subsystem**: [[Game_System_Overview]]
- **Related Modules**: [[Stats_Cogs_Overview]], [[Stats_Storage_Overview]]
- **Requirements Reference**: [[HIGH_LEVEL_REQUIREMENTS#Table-8-Statistics-Tracking--Analytics]], [[DETAILED_REQUIREMENTS#FR-STA-03-Hall-of-Records-Tracking]]

---

## 📄 File Index

| File | Purpose | Key Functions |
| :--- | :--- | :--- |
| `fame.py` | Evaluates completed games for notable records (e.g. fastest town win, highest kill streak, spotless doctor defense) and updates the Hall of Fame archive. | `check_hall_of_fame_records()`, `update_records()` |

---

## 🔗 Connected Overviews
- [[Game_System_Overview]]: Return to Game System Index
- [[Stats_Cogs_Overview]]: Slash commands (`/hallofrecords`, `/playerstats`) displaying these metrics
- [[Stats_Storage_Overview]]: Directory storing raw stats records
