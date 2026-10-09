# Mafia Discord Bot

A fully-featured, asynchronous Mafia (or Werewolf) bot for Discord, built with Python and the `discord.py` library. This bot manages a complete game loop, from sign-ups and role assignment to night actions, voting, and dynamic story narration.


## 🗺️ Obsidian Knowledge Graph & Architecture Index

This codebase is organized with dedicated architectural overviews and bidirectional Obsidian `[[wikilinks]]` for every subsystem:

* **Master Knowledge Hub**: [[Root_Project_Overview]]
* **Documentation Hub**: [[Documentation_Hub_Overview]]
  * **Core Mafia Bot**: [[Mafia_Bot_Docs_Overview]] | [[HIGH_LEVEL_REQUIREMENTS]] | [[DETAILED_REQUIREMENTS]]
  * **Website Portal**: [[Website_Docs_Overview]] | [[WEBSITE_PORTAL_PLAN]] | [[docs/website/HIGH_LEVEL_REQUIREMENTS|Website HLR]] | [[docs/website/DETAILED_REQUIREMENTS|Website DLR]]
  * **Mafia History Project**: [[History_Project_Docs_Overview]] | [[HISTORIC_PROJECT_PLAN]] | [[docs/history_project/HIGH_LEVEL_REQUIREMENTS|History HLR]] | [[docs/history_project/DETAILED_REQUIREMENTS|History DLR]]
* **Subsystem Overviews**:
  * [[Bot_Setup_Overview]]: Startup & logging initialization
  * [[Cogs_Overview]]: Modular Discord slash command cogs ([[Admin_Cogs_Overview]], [[Game_Cogs_Overview]], [[Info_Cogs_Overview]], [[Stats_Cogs_Overview]], [[Community_Cogs_Overview]], [[Export_Cogs_Overview]])
  * [[Game_System_Overview]]: Core state machine ([[Game_Engine_Overview]]), night abilities ([[Game_Actions_Overview]]), and storytelling ([[Game_Narration_Overview]])
  * [[Community_System_Overview]]: Player roleplay quirks and admin moderation UI ([[Community_Quirks_Overview]], [[Community_UI_Overview]])
  * [[Utilities_Overview]]: Shared Discord helpers and JSON serializers
  * [[Data_Assets_Overview]]: Setups, role definitions, and narrative themes
  * [[Tests_Overview]]: Automated pytest suite and full QA validation
  * [[Stats_Storage_Overview]]: Historic game archives and JSON database
  * [[Logs_Directory_Overview]]: Application, debug, and AI prompt logs
  * [[Website_Portal_Overview]]: Analytics website, dashboards, and data feeds ([[Website_Data_Overview]])
  * [[Other_Projects_Overview]]: Mafia History Project ([[Mafia_History_Project_Overview]]) and Balance Simulations ([[Simulations_Overview]])

---

## ✨ Key Features

  * **Automated Game Management**: Handles the full game lifecycle, including sign-ups, day/night cycles, phase timers, and clear **Day Phase Skip** indicators across rules, headers, and status embeds.
  * **Complex Role Support**: Supports a wide variety of roles with unique night abilities (Doctors, Cops, Role Blockers, Jester, etc.) defined in flexible JSON configurations.
  * **Roleblock Dependency Resolution & Selective Narration**:
    * Priority-1 dependency resolution with cycle handling for mutual roleblocks.
    * **Action-focused narration**: Thwarted actions are described anonymously without exposing living players' hidden roles.
    * **Selective visibility**: Investigation blocks are never shown publicly; blocked heals are only shown if the heal would have prevented an unblocked kill attempt on that patient; blocked kills and blocked blocks are always narrated; blocks on idle players or plain townies remain silent.
  * **9 Narrative Themes & Dynamic Role Reskinning**: Play across 9 rich narrative themes (Classic Mafia, Horror, Explicit Kinky NSFW [R18], Rom Com [SFW Non-Death], Office Restructuring [SFW Non-Death], High Fantasy, Cyberpunk, Comedy, and Lovecraftian Horror). Every canonical role receives a thematic title, DM description, and public skin while keeping underlying mechanics 100% stable.
  * **SFW Non-Death Modes**: Rom Com (dumped, ghosted, wingman saves) and Office Restructuring (laid off, terminated, HR contract protections) completely replace violent death and corpse themes with lighthearted, non-lethal stakes.
  * **Dynamic Role Assignment**: Automatically assigns roles from `mafia_setups.json` based on the number of players who sign up.
  * **Automated Voting**: Manages day-phase lynch votes and inactivity-based voting.
  * **Dynamic Narration**: Generates narrative stories for all game events at the end of each phase using Google Gemini AI or reliable static fallback narration.
  * **Historical Web Analytics Portal**: Multi-era analytics dashboard spanning 202 games across 4 historical eras (Forum, Discourse, Discord Manual, Discord Bot) with an automated build pipeline and production deployment guide (`Website/PRODUCTION_SETUP_GUIDE.md`).
  * **Extensive Unit Testing**: A robust test suite (**117 passing tests**) ensures code stability, invariant enforcement, and parameter validation.

## 🌐 Production Website & Deployment
To deploy the historical web analytics portal on an Oracle Cloud Free Tier VM or via Google Cloud / GitHub Pages, follow the step-by-step instructions in:
* **[Production Setup Guide](Website/PRODUCTION_SETUP_GUIDE.md)**: Rebuilding databases, Nginx/Caddy HTTPS configuration, systemd services, and automated Git pull webhooks.

## 🚀 Setup & Installation

Follow these steps to get your own instance of the bot running.

### 1\. Prerequisites

  * Python 3.10 or higher
  * A Discord Bot Token (created on the [Discord Developer Portal](https://www.google.com/search?q=https://discord.com/developers/applications))
  * A Discord Server where you have admin permissions to add the bot and get channel/role IDs.

### 2\. Installation

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/your-username/your-repo-name.git
    cd your-repo-name
    ```

2.  **Create and activate a virtual environment:**

      * **Windows:**
        ```cmd
        python -m venv .venv
        .venv\Scripts\activate
        ```
      * **Linux / macOS:**
        ```bash
        python3 -m venv .venv
        source .venv/bin/activate
        ```

3.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

### 3\. Configuration

The bot uses a `config.py` file for secrets and server-specific IDs, which is **not** committed to a version control (via `.gitignore`).

1.  **Bot Configuration:**

      * Copy `config_template.py` to a new file named `config.py`.
      * Open `config.py` and fill in your `BOT_TOKEN` and all the required `CHANNEL_ID`s for your server.

2.  **Discord Role Configuration:**

      * The bot needs to know the Discord Role IDs for `Living Players`, `Dead Players`, etc.
      * Copy the file `discord_roles.json` (or a template, if you have one) into the `Data/` directory.
      * Open `Data/discord_roles.json` and replace the placeholder IDs with your server's actual Role IDs.

## ▶️ Running the Bot

Once your virtual environment is activated and your `config.py` is set up, you can start the bot:

```bash
python bot.py
```

## 🎮 Game Logic Testbed & Sandbox

A standalone, Discord-isolated testbed is available in `sandbox.py` to test, simulate, and debug game mechanics, voting, night actions, and win conditions without connecting to Discord or needing API credentials.

### Interactive CLI Shell
Run the interactive REPL to step through games manually:
```bash
python sandbox.py
```
Inside the interactive shell:
- `new classic Alice Bob Charlie Dave` - Create game with players
- `setrole Alice Godfather` - Manually assign roles
- `autoassign` - Generate and balance roles automatically
- `startnight` / `action Bob heal Alice` / `endnight` - Simulate night phase
- `startday` / `vote Bob Alice` / `endday` - Simulate daytime voting & lynches
- `status` / `checkwin` - Inspect game state and win conditions

### Preset Scenarios
Run targeted rule checks directly from the command line:
```bash
python sandbox.py --list-scenarios
python sandbox.py --scenario doctor_saves_target
python sandbox.py --scenario roleblock_prevents_kill
python sandbox.py --scenario cop_investigates
python sandbox.py --scenario jester_lynch
python sandbox.py --scenario godfather_promotion
python sandbox.py --scenario inactivity_death
```

### Full Game Simulation
Run an end-to-end automated game simulation with turn-by-turn logs:
```bash
python sandbox.py --simulate --players 6
```

## 🧪 Running Tests

To verify that all game logic and sandbox harnesses are working correctly, you can run the full unit test suite:

```bash
python -m unittest discover tests
```

-----
