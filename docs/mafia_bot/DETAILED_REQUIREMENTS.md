<!-- Obsidian Navigation Header -->
> [!NOTE] Knowledge Graph Navigation
> - **Parent Documentation Hub**: [[Documentation_Hub_Overview]]
> - **Mafia Bot Docs Hub**: [[Mafia_Bot_Docs_Overview]]
> - **Companion Document**: [[HIGH_LEVEL_REQUIREMENTS]]
> - **System Overviews**: [[Bot_Setup_Overview]], [[Cogs_Overview]], [[Game_System_Overview]], [[Game_Engine_Overview]], [[Game_Actions_Overview]], [[Community_System_Overview]], [[Utilities_Overview]], [[Tests_Overview]]
> - **Root Index**: [[Root_Project_Overview]]

# IC Mafia Bot — Detailed Requirements & Unit Test Acceptance Criteria

## 1. Document Purpose
This document provides the detailed technical specification for every modular chunk of the **IC Mafia Bot**. Each section describes the component's file path, interface signatures, input/output data contracts, business rules, and the exact **Unit Test Acceptance Criteria** required to verify correct implementation.

---

## 2. Global State Standard: `bot.game_instance`

### Architectural Rule
All components throughout the bot must access the active game state via `bot.game_instance`:
- `bot.game_instance = None` indicates no game is active.
- `bot.game_instance = <Game>` holds the current active `Game` object.
- Helper functions `get_game_instance(bot)` and `set_game_instance(bot, instance)` provide safe access with error logging.

---

## 3. Subsystem Specifications & Unit Test Specifications

### Subsystem A: Core Bot & Lifecycle Setup ([[Bot_Setup_Overview]])

#### A1. Bot Entry Point & Runner
* **File Path**: `bot.py`
* **Dependencies**: `setup.loggersetup`, `setup.cogsetup`, `setup.startbot`, `config`
* **Specification**: Initializes intents (`members=True`, `message_content=True`), instantiates `commands.Bot(command_prefix=config.BOT_PREFIX, owner_id=config.OWNER_ID)`, initializes `bot.game_instance = None`, hooks `setuphook()` to load cogs and sync commands, and invokes `asyncio.run(startbot.main(bot))`.
* **Acceptance Criteria**:
  * `TEST-BOT-01`: Bot instantiates with expected intents enabled.
  * `TEST-BOT-02`: `bot.game_instance` initialized to `None`.
  * `TEST-BOT-03`: `setuphook()` calls `cogsetup.load_cogs(bot)` and awaits tree synchronization.

#### A2. Cog Setup & Extension Loader
* **File Path**: `setup/cogsetup.py`
* **Signature**: `async def load_cogs(bot: commands.Bot) -> None`
* **Specification**: Scans directory `./cogs`. Loads all `.py` files that are direct children of `./cogs/` as bot extensions (e.g. `cogs.admin`, `cogs.game`, `cogs.info`, `cogs.stats`, `cogs.community`, `cogs.export`). Subdirectories (such as `cogs/admincogs/`) must NOT be loaded as independent extensions. After loading, calls `await bot.tree.sync()`.
* **Acceptance Criteria**:
  * `TEST-SETUP-01`: Skips subdirectories and only loads top-level `.py` files in `cogs/`.
  * `TEST-SETUP-02`: Captures and logs exceptions if an individual cog fails to load, continuing to load remaining cogs.
  * `TEST-SETUP-03`: Awaits `bot.tree.sync()` to publish slash commands globally.

#### A3. Logging Configuration
* **File Path**: `setup/loggersetup.py`
* **Signature**: `def setup_logging() -> logging.Logger`
* **Specification**: Sets up root and `discord` loggers with rotating file handlers (`logs/` directory) and console stream handlers with format `[%(asctime)s] [%(levelname)-8s] %(name)s - %(funcName)s:%(lineno)d: %(message)s`.
* **Acceptance Criteria**:
  * `TEST-LOG-01`: Verified by `tests/test_0_logging.py`. Logger handles debug, info, warning, error, and critical levels without unhandled exceptions.

---

### Subsystem B: Utilities & Discord Helpers ([[Utilities_Overview|utils/]])

#### B1. Format Time Remaining
* **File Path**: `utils/formattimeremain.py`
* **Signature**: `def format_time_remaining(time_input: timedelta | datetime) -> str`
* **Specification**: Converts a `timedelta` or future `datetime` object into a human-readable string formatted as `Xh Ym Zs` or `Ym Zs`.
* **Acceptance Criteria**:
  * `TEST-UTL-01` (`tests/test_6_utilities.py:test_format_time_remaining_with_timedelta`): Given `timedelta(hours=2, minutes=30, seconds=15)`, returns `"2h 30m 15s"`.
  * `TEST-UTL-02`: Given `timedelta(minutes=5, seconds=0)`, returns `"5m 0s"`.
  * `TEST-UTL-03`: Given past `datetime` or negative `timedelta`, returns `"0m 0s"`.

#### B2. Role Hierarchy Validation
* **File Path**: `utils/getrolehierarchy.py`
* **Signature**: `def get_role_hierarchy(target_roles: list[discord.Role], bot_role: discord.Role) -> bool`
* **Specification**: Compares Discord role hierarchy positions. Returns `True` if `bot_role.position` is strictly greater than the maximum `position` among all `target_roles`.
* **Acceptance Criteria**:
  * `TEST-UTL-04` (`tests/test_6_utilities.py:test_get_role_hierarchy_success`): Returns `True` when bot role position is 10 and target roles are 5 and 8.
  * `TEST-UTL-05`: Returns `False` when target role position is greater than or equal to bot role.

#### B3. Data Load & Save
* **File Paths**: `utils/loaddata.py`, `utils/savejsondata.py`
* **Signatures**:
  * `def load_data(filepath: str) -> dict | list`
  * `def save_json_data(filepath: str, data: dict | list) -> bool`
* **Specification**: Safely reads/writes JSON data with `utf-8` encoding. For text files, returns a list of stripped lines.
* **Acceptance Criteria**:
  * `TEST-UTL-06`: `load_data` loads valid JSON files and returns python dictionaries/lists.
  * `TEST-UTL-07`: `save_json_data` writes formatted JSON and creates parent directories if needed.

#### B4. Utilities Facade Module
* **File Path**: `utils/utilities.py`
* **Specification**: Imports and re-exports all single-function utilities from `utils/*.py` to ensure complete backwards compatibility with legacy imports (`from utils.utilities import format_time_remaining, get_role_hierarchy`).
* **Acceptance Criteria**:
  * `TEST-UTL-08`: Importing any utility function from `utils.utilities` successfully resolves to the underlying chunk function.

---

### Subsystem C: Player Model & Role Factory (`game/`)

#### C1. Player Model
* **File Path**: `game/player.py`
* **Class**: `Player(user_id: int, discord_name: str, display_name: str)`
* **Specification**:
  * Attributes: `id`, `name`, `display_name`, `is_npc = (user_id <= 0)`, `role = None`, `is_alive = True`, `night_immune = False`, `action_target = None`, `death_info = {}`, `missed_votes = 0`, `votes_on = 0`, `is_winner = None`.
  * Method `assign_role(role: GameRole)`: Binds role and updates `night_immune = role.is_night_immune`.
  * Method `kill(phase_str: str, cause_of_death: str)`: Sets `is_alive = False`, records `death_info = {"phase": phase_str, "how": cause_of_death, "phase_number": ...}`.
  * Method `can_perform_action(action_type: str) -> bool`: Returns `True` if `is_alive` and `action_type in self.role.abilities`.
  * Method `async send_dm(bot, message: str) -> bool`: Fetches user and sends DM; skips if `is_npc`.
* **Acceptance Criteria**:
  * `TEST-PLR-01`: Player initialized with correct default attributes.
  * `TEST-PLR-02`: NPC player has `is_npc == True` when `user_id <= 0`.
  * `TEST-PLR-03`: `kill()` marks player as dead and stores death metadata correctly.
  * `TEST-PLR-04`: `can_perform_action('kill')` returns `True` only when player is alive and role has `'kill'` ability.

#### C2. Role System & Dynamic Factory
* **File Path**: `game/roles.py`
* **Classes**: `GameRole`, `TownInvestigative`, `TownProtective`, `TownKilling`, `MafiaKilling`, `MafiaSupport`, `NeutralKilling`, `NeutralEvil`, `NeutralRoyale`
* **Signature**: `def get_role_instance(role_name: str) -> GameRole | None`
* **Specification**: Loads definitions from `data/game_setup/role_definition.json`. Instantiates the appropriate subclass with abilities, win conditions, and investigation results.
* **Acceptance Criteria**:
  * `TEST-ROL-01`: `get_role_instance("Godfather")` returns `MafiaKilling` instance with alignment `"Mafia"`, night immunity `True`, and ability `"kill"`.
  * `TEST-ROL-02`: `get_role_instance("Town Doctor")` returns `TownProtective` instance with alignment `"Town"` and ability `"heal"`.
  * `TEST-ROL-03`: Returns `None` for invalid role name without raising unhandled exceptions.

#### C3. Setup Role Generator
* **File Path**: `game/setup_generator.py`
* **Signature**: `def generate_roles(player_count: int, game_type: str, mob_ratio: float, town_rb_req: int, mafia_rb_req: int, sk_player_count: int, min_cop_players: int, min_doctor_players: int) -> list[str]`
* **Specification**:
  * If `game_type != "classic"`, returns `[VIGILANTE] * player_count`.
  * If `player_count < config.min_players`, returns `[]`.
  * Calculates Mafia count: `floor(player_count * mob_ratio)`, at least 1. Always includes 1 `Godfather`, fills rest with `Mob Goon`. If `mafia_count >= mafia_rb_req`, replaces 1 Goon with `Mob Role Blocker`.
  * If `player_count >= sk_player_count`, adds `Serial Killer`.
  * If `player_count >= min_cop_players`, adds `Town Cop`.
  * If `player_count >= min_doctor_players`, adds `Town Doctor`.
  * If `player_count >= town_rb_req`, adds `Town Role Blocker`.
  * Fills remaining slots up to `player_count` with `Plain Townie`.
* **Acceptance Criteria**:
  * `TEST-SET-01` (`tests/test_7_parameters.py`): Validates role counts across 5 to 19 player games for Classic and Battle Royale modes.

---

### Subsystem D: Night Actions (`game/actions/`)

#### D1. Role Block Action
* **File Path**: `game/actions/block.py`
* **Signature**: `def handle_block(game, blocker_id: int, target_id: int, night_outcomes: dict) -> None`
* **Specification**: Adds `target_id` to `game.blocked_players_this_night`. Target's queued actions are marked blocked in `night_outcomes`.
* **Acceptance Criteria**:
  * `TEST-ACT-01` (`tests/test_2_action.py`): Target added to `game.blocked_players_this_night`. Subsequent actions by target are cancelled.

#### D2. Heal / Protection Action
* **File Path**: `game/actions/heal.py`
* **Signature**: `def handle_heal(game, healer_id: int, target_id: int, night_outcomes: dict) -> None`
* **Specification**: Adds `target_id` to `game.protected_players_this_night[target_id] = healer_id`. Prevents self-heals two nights in a row.
* **Acceptance Criteria**:
  * `TEST-ACT-02` (`tests/test_2_action.py`): Target recorded in `protected_players_this_night`. Consecutive self-heal rejected.

#### D3. Kill Action
* **File Path**: `game/actions/kill.py`
* **Signature**: `def handle_kill(game, killer_id: int, victim_id: int, night_outcomes: dict) -> None`
* **Specification**: Evaluates kill attempt. If victim is protected, logs save event. If victim has night immunity (e.g. Godfather / Serial Killer), kill fails. Otherwise, victim added to night deaths list.
* **Acceptance Criteria**:
  * `TEST-ACT-03` (`tests/test_2_action.py`): Attack on protected target results in survival and save event. Attack on unprotected target results in death. Attack on night-immune target fails.

#### D4. Investigation Action
* **File Path**: `game/actions/investigate.py`
* **Signature**: `def handle_investigation(game, investigator_id: int, target_id: int, night_outcomes: dict) -> None`
* **Specification**: Determines investigative result (Innocent / Suspicious). If Godfather has investigate immunity, returns Innocent. Schedules async DM report to investigator.
* **Acceptance Criteria**:
  * `TEST-ACT-04` (`tests/test_2_action.py`): Cop receives correct result for Townie, Goon, and Godfather (respecting immunity setting).

#### D5. Actions Facade Module
* **File Path**: `game/actions.py`
* **Specification**: Re-exports `handle_block`, `handle_heal`, `handle_kill`, `handle_investigation` from `game/actions/` chunks.
* **Acceptance Criteria**:
  * `TEST-ACT-05`: `tests/test_2_action.py` imports and runs without modification.

---

### Subsystem E: Narration System (`game/narration/`)

#### E1. Narration Manager
* **File Path**: `game/narration.py` (and `game/narration/manager.py`)
* **Class**: `NarrationManager`
* **Specification**:
  * `add_event(event_type: str, **details)`: Stores event in `self.events`.
  * `clear()`: Empties `self.events` for the next phase.
  * `get_full_story_log() -> str`: Combines `self.story_history` into full game log.
  * `async construct_story(game_state: dict) -> str | None`: Calls `ai_storyteller.generate_story()` (passing last 3 chapters). If AI fails or narration type is "No Story", falls back to `static_storyteller.generate_story()`. Appends result to `story_history`.
* **Acceptance Criteria**:
  * `TEST-NAR-01` (`tests/test_4_narration.py:test_add_event_queues_correctly`): Event added to `manager.events`.
  * `TEST-NAR-02` (`tests/test_4_narration.py:test_generate_story_uses_events`): Generated story incorporates queued events.
  * `TEST-NAR-03` (`tests/test_4_narration.py:test_generate_story_empty_events`): Gracefully handles empty event list.

#### E2. AI Storyteller Chunk
* **File Path**: `game/narration/ai_storyteller.py`
* **Signature**: `async def generate_story(game_state: dict, events: list, history: list) -> str | None`
* **Specification**: Constructs structured Gemini prompt including theme story context (`data/narration/themes.json`) and player quirks (`data/narration/player_concepts.json`). Calls `google-genai` client. Returns generated text or `None` on error.
* **Acceptance Criteria**:
  * `TEST-NAR-04`: Mocks Gemini API call; verifies return string on success and `None` on API exception.

#### E3. Static Storyteller Chunk
* **File Path**: `game/narration/static_storyteller.py`
* **Signature**: `def generate_story(header: str, events: list) -> str`
* **Specification**: Deterministically formats standard recap messages for lynches, kills, and peaceful nights.
* **Acceptance Criteria**:
  * `TEST-NAR-05`: Returns formatted string containing header and all phase outcomes.

---

### Subsystem F: Game Engine Subsystem (`game/engine/` & `game/engine.py`)

#### F1. Engine Initializer
* **File Path**: `game/engine/initialise.py`
* **Signature**: `async def initialize_game(self, bot, guild, game_type, phase_hours, start_datetime, narration_type, gf_investigate_choice, sk_investigate_choice, mafia_ratio, town_rb_req, mafia_rb_req, sk_player_count, town_cop_req, town_doctor_req, cleanup_callback) -> None`
* **Specification**: Initializes all engine state dictionaries, locks (`player_lock`, `vote_lock`), and loads data files (`rules.txt`, `bot_names.txt`, `themes.json`, `player_concepts.json`).
* **Acceptance Criteria**:
  * `TEST-ENG-01`: State dictionaries and locks properly created on `game` instance.

#### F2. Signups & Player Management Chunk
* **File Path**: `game/engine/signup.py`
* **Signatures**:
  * `async def add_player(game, user: discord.User, player_name: str, channel: discord.TextChannel) -> bool`
  * `async def remove_player(game, user: discord.User, channel: discord.TextChannel) -> bool`
  * `async def signup_loop(game) -> None`
  * `async def force_start(game, interaction: discord.Interaction) -> None`
* **Specification**: Uses `game.player_lock` for safe concurrency. Enforces `signup` phase, assigns/removes `Living` Discord role.
* **Acceptance Criteria**:
  * `TEST-ENG-02`: Concurrent `add_player` calls do not corrupt `game.players` dictionary.
  * `TEST-ENG-03`: `remove_player` removes player and cleans up roles.

#### F3. Voting & Daytime Resolution Chunk
* **File Path**: `game/engine/voting.py`
* **Signatures**:
  * `async def process_lynch_vote(game, interaction, voter: discord.User, target_name: str) -> str`
  * `async def process_npc_votes(game) -> None`
  * `async def send_vote_count(game, channel: discord.TextChannel) -> None`
  * `async def tally_votes(game) -> None`
* **Specification**:
  * Validates voter and target are living players.
  * Majority trigger: if target receives `> len(living_players) // 2` votes, triggers early day end.
  * `process_npc_votes`: Automatically selects and casts random lynch votes for living unvoted NPCs at phase end (Mafia NPCs prefer non-Mafia targets).
  * `tally_votes`: executes player with highest votes (or ties result in no lynch). Increments `missed_votes` for non-voters.
* **Acceptance Criteria**:
  * `TEST-ENG-04` (`tests/test_1_engine.py`): Voting updates `game.lynch_votes`.
  * `TEST-ENG-05`: Majority vote ends Day phase immediately and schedules lynch.
  * `TEST-ENG-06`: Inactivity penalty kills player after exceeding `MAX_MISSED_VOTES`.
  * `TEST-ENG-06B` (`tests/test_1_engine.py:test_npc_day_voting_auto_vote`): Unvoted NPCs cast random valid votes and are not penalized for inactivity.

#### F4. Night Phase & Death Resolution Chunk
* **File Path**: `game/engine/night.py`
* **Signatures**:
  * `async def record_night_action(game, interaction, action_type: str, target_name: str) -> str`
  * `async def process_npc_night_actions(game) -> None`
  * `async def process_night_actions(game) -> None`
  * `async def _resolve_night_deaths(game) -> None`
  * `def _handle_promotions(game, dead_player: Player) -> None`
* **Specification**:
  * `process_npc_night_actions`: Automatically queues valid night abilities for living NPCs (Godfather/SK kills random target; Doctor heals random player without consecutive repeats; Blocker blocks; Cop investigates).
  * Collects night actions in `game.night_actions`.
  * Evaluates actions in priority order: Block -> Heal -> Kill -> Investigate.
  * If Godfather dies and living Mob Goons exist, promotes the first Mob Goon to Godfather.
* **Acceptance Criteria**:
  * `TEST-ENG-07`: `process_night_actions` correctly cancels blocked actions and saves healed players.
  * `TEST-ENG-07B` (`tests/test_1_engine.py:test_npc_night_actions_auto_queue`): Living NPC power roles automatically queue valid night actions against eligible targets.
  * `TEST-ENG-08`: `_handle_promotions` promotes Mob Goon to Godfather upon Godfather death.

#### F5. Win Condition Evaluator Chunk
* **File Path**: `game/engine/win.py`
* **Signature**: `def check_win_conditions(game) -> str | None`
* **Specification**:
  * Returns `"Town"` if all Mafia and Serial Killer are dead and >= 1 Town alive.
  * Returns `"Mafia"` if Mafia players >= living Town players and Serial Killer is dead.
  * Returns `"Serial Killer"` if Serial Killer is alive and total other living players <= 1.
  * Returns `"Draw"` if all players are dead.
  * Returns `None` if game should continue.
* **Acceptance Criteria**:
  * `TEST-ENG-09`: Correctly detects Town victory, Mafia parity victory, SK solo victory, and ongoing game.

#### F6. Game Coordinator Class
* **File Path**: `game/engine.py`
* **Class**: `Game(bot, guild, cleanup_callback=None, game_type="classic")`
* **Specification**: Exposes all public methods (`start`, `add_player`, `remove_player`, `process_lynch_vote`, `process_night_actions`, `reset`, `get_status_message`) by delegating directly to the modular chunk files under `game/engine/`.
* **Acceptance Criteria**:
  * `TEST-ENG-10`: `tests/test_1_engine.py` and `tests/test_7_parameters.py` run against `Game` class with 100% pass rate.

---

### Subsystem G: Discord Cogs & Command Handlers (`cogs/`)

#### G1. Admin Cog & Chunks
* **Cog**: `cogs/admin.py` (`AdminCog`)
* **Chunks in `cogs/admincogs/`**:
  * `startgame.py`: `/mafiastart` validation, instantiates `Game`, calls `game.start()`, sets `bot.game_instance = game`.
  * `stopgame.py`: `/mafiastop` calls `game.reset()`, sets `bot.game_instance = None`.
  * `forcestart.py`: `/forcestart` checks `game.game_settings["current_phase"] == "signup"`, calls `game.force_start()`.
  * `reinitplayers.py`: `/mafiareinit` iterates guild members, rebuilds `game.players` from `Living`/`Dead` roles.
  * `forcephaseend.py`: `/forcephaseend` calls `game.force_end_phase()`.
  * `getgameinstance.py`: `get_game_instance(bot)` returns `getattr(bot, 'game_instance', None)`.
  * `setgameinstance.py`: `set_game_instance(bot, instance)` sets `bot.game_instance = instance`.
* **Acceptance Criteria**:
  * `TEST-COG-ADM-01`: Commands decorated with `@is_admin()` reject non-admin users.
  * `TEST-COG-ADM-02`: `/mafiastart` properly assigns `bot.game_instance`.
  * `TEST-COG-ADM-03`: `/mafiastop` properly resets `bot.game_instance` to `None`.

#### G2. Game Cog & Chunks
* **Cog**: `cogs/game.py` (`GameCog`)
* **Chunks in `cogs/gamecogs/`**:
  * `join.py`: Handles `/mafiajoin`.
  * `leave.py`: Handles `/mafialeave`.
  * `status.py`: Handles `/mafiastatus`.
  * `vote.py`: Handles `/vote [player]`.
  * `count.py`: Handles `/mafiacount`.
  * `myrole.py`: Handles `/myrole` in DMs.
  * `nightactions.py`: Handles `/kill`, `/heal`, `/investigate`, `/block` in DMs.
  * `autocomplete.py`: Dynamic living player suggestions for slash command autocomplete.
* **Acceptance Criteria**:
  * `TEST-COG-GAM-01`: `/myrole` and night actions reject usage in guild channels (DM only).
  * `TEST-COG-GAM-02`: `/vote` and `/mafiacount` reject usage when no game is active.

#### G3. Info Cog & Chunks
* **Cog**: `cogs/info.py` (`InfoCog`)
* **Chunks in `cogs/infocogs/`**:
  * `mafiarules.py`: `/mafiarules` loads rules text and builds rules embed via `game/data/getrules.py`.
  * `mafiaroles.py`: `/mafiaroles` calculates alive/total role counts from `bot.game_instance` and displays alignment embed.
  * `mafiainfo.py`: `/mafiainfo` sends full categorized command list.
* **Embed Formatting Standards (`game/data/getrules.py`)**:
  * Start times formatted using Discord native timestamp syntax: `<t:{epoch}:F> (<t:{epoch}:R>)`.
  * Server conduct rules rendered as an unbroken single-field list (`1.` to `6.`) avoiding fragmented "Part 1 / Part 2" embed splits.
  * Dynamic setup parameters formatted with Discord blockquotes (`> `).
  * Faction objectives formatted with bullet points (`•`) to prevent numeric collision with conduct rules.
* **Acceptance Criteria**:
  * `TEST-COG-INF-01`: `/mafiarules` sends ephemeral embed with rules matching protocol layout standards.
  * `TEST-COG-INF-02`: `/mafiaroles` displays correct alive vs total counts grouped by alignment.

#### G4. Stats Cog & Chunks
* **Cog**: `cogs/stats.py` (`StatsCog`)
* **Chunks in `cogs/statscogs/`**:
  * `gamestats.py`: `/gamestats` aggregates past game data from `stats/`.
  * `playerstats.py`: `/playerstats` queries player history and computes stats.
  * `skillscore.py`: `/skillscore` computes Classic skill score formula.
  * `leaderboard.py`: `/leaderboard` displays top 10 rankings.
  * `hallofrecords.py`: `/hall_of_records` displays records.
* **Acceptance Criteria**:
  * `TEST-COG-STA-01`: `tests/test_5_statistics.py` imports `StatsCog` and tests run without failure.

#### G5. Community Cog & Chunks
* **Cog**: `cogs/community.py` (`CommunityCog`)
* **Chunks in `cogs/communitycogs/`**:
  * `setquirk.py`: `/set_quirk` opens `QuirkSubmissionModal`.
  * `reviewquirks.py`: `/review_quirks` renders `QuirkReviewView`.
  * `displayquirks.py`: `/display_all_quirks` lists approved quirks.
* **Chunks in `community/quirk/`**:
  * `getpending.py`, `getapproved.py`, `getuserquirk.py`, `queuepending.py`, `approve.py`, `reject.py`.
* **Facades**: `community/quirk_logic.py`, `community/review_system.py`.
* **Acceptance Criteria**:
  * `TEST-COG-COM-01`: `tests/test_3_community.py` passes all quirk approval, rejection, and retrieval tests.

#### G6. Export Cog & Chunks
* **Cog**: `cogs/export.py` (`ExportCog`)
* **Chunks in `cogs/exportcogs/`**:
  * `exportstats.py`: `/exportstats` reads game stats and updates Google Sheets via `gspread`.
* **Acceptance Criteria**:
  * `TEST-COG-EXP-01`: `/exportstats` validates admin permissions and handles network/auth errors gracefully.

---

## 4. Test Verification Matrix & Test Execution Plan

### Automated Test Suites
All unit tests will be executed via pytest in the `.venv` virtual environment:

```powershell
.venv\Scripts\python.exe -m pytest tests/ -v
```

| Test Suite File | Subsystem Under Test | Expected Test Cases | Target Pass Rate |
| :--- | :--- | :--- | :--- |
| `tests/test_0_logging.py` | Setup & Logging | Logger configuration, file output | 100% (Pass) |
| `tests/test_1_engine.py` | Game Engine Lifecycle | Game start, voting, player management, loops | 100% (Pass) |
| `tests/test_2_action.py` | Night Actions | Block, heal, kill, investigate, priority | 100% (Pass) |
| `tests/test_3_community.py` | Community Quirks | Queue, approve, reject, get quirks | 100% (Pass) |
| `tests/test_4_narration.py` | Narration System | Event queue, AI storyteller, static fallback | 100% (Pass) |
| `tests/test_5_statistics.py` | Stats & Analytics | StatsCog, analytics, player rankings | 100% (Pass) |
| `tests/test_6_utilities.py` | Utilities Subsystem | Time formatting, role hierarchy | 100% (Pass) |
| `tests/test_7_parameters.py` | Setup Generator | Parameter validation, role balancing | 100% (Pass) |

---

## 🔗 Obsidian Knowledge Graph Links
- **Master Root Index**: [[Root_Project_Overview]]
- **Documentation Hub**: [[Documentation_Hub_Overview]]
- **Mafia Bot Docs Hub**: [[Mafia_Bot_Docs_Overview]]
- **High-Level Requirements**: [[HIGH_LEVEL_REQUIREMENTS]]
- **Subsystem Overviews**:
  - [[Bot_Setup_Overview]]: Bot initialization & logging
  - [[Utilities_Overview]]: Helpers and serializers
  - [[Game_Engine_Overview]]: Game state machine
  - [[Game_Actions_Overview]]: Night action priorities
  - [[Admin_Cogs_Overview]]: Admin commands
  - [[Game_Cogs_Overview]]: Player slash commands
  - [[Info_Cogs_Overview]]: Information commands
  - [[Stats_Cogs_Overview]]: Stats and skill scores
  - [[Community_System_Overview]]: Quirks & moderation
  - [[Game_Narration_Overview]]: AI & static narration
  - [[Export_Cogs_Overview]]: Google Sheets sync
  - [[Tests_Overview]]: QA test suite
