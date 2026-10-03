# Admin Cogs Subsystem Overview

The `/cogs/admincogs` directory houses administrative command handlers restricted to users with the configured Discord Administrator role. These handlers govern game scheduling, emergency stops, phase skips, and server role synchronization.

## 🧭 Navigation
- **Parent Cog**: [[Cogs_Overview]]
- **Related Modules**: [[Game_Engine_Overview]], [[Utilities_Overview]], [[Bot_Setup_Overview]]
- **Requirements Reference**: [[HIGH_LEVEL_REQUIREMENTS#Table-2-Administration--Game-Control]], [[DETAILED_REQUIREMENTS#FR-ADM-01-Permission-Guard]]

---

## 📄 Command Implementations

| File | Slash Command | Description | Key Delegations |
| :--- | :--- | :--- | :--- |
| `startgame.py` | `/mafiastart` | Schedules a new game with configurable parameters (game type, phase length, narration, investigatability, GF/SK night immunity, Battle Royale day skip, role thresholds) and logs configuration to Google Sheets (`Rules Setup` tab). | Calls `Game.start_game()` and [[Export_Cogs_Overview|log_game_setup_to_sheets]]. |
| `stopgame.py` | `/mafiastop` | Immediately terminates the running game, removes server roles, and resets state. | Calls `game.reset_game()`. |
| `forcestart.py` | `/forcestart` | Ends signups immediately and advances to preparation phase if minimum player count is met. | Bypasses scheduled start time; calls `prepare_game()`. |
| `forcephaseend.py` | `/forcephaseend` | Forcibly triggers immediate phase evaluation (resolves Day votes or Night actions instantly). | Advances phase timer in `game/engine/loop.py`. |
| `reinitplayers.py` | `/mafiareinit` | Rebuilds active player cache from server Discord roles following a bot restart. | Reconstructs `game.players` dictionary. |
| `getgameinstance.py` | N/A (Internal) | Thread-safe retrieval helper for `bot.game_instance`. | Returns current `Game` or `None`. |
| `setgameinstance.py` | N/A (Internal) | Safe setter helper for updating or clearing `bot.game_instance`. | Updates `bot.game_instance`. |

---

## 🔒 Permission Guard Architecture
All admin commands are wrapped with `@admin_only()` from [[Utilities_Overview|utils/admincheck.py]], rejecting unauthorized users with an ephemeral warning.

---

## 🔗 Connected Overviews
- [[Cogs_Overview]]: Return to Cogs Index
- [[Game_Engine_Overview]]: See the game engine lifecycle methods triggered by admin actions
- [[Export_Cogs_Overview]]: Google Sheets export and setup logging pipeline
- [[Utilities_Overview]]: Permission guard and role assignment utilities
