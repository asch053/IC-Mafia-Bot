# Mafia Discord Bot

A fully-featured, asynchronous Mafia (or Werewolf) bot for Discord, built with Python and the `discord.py` library. This bot manages a complete game loop, from sign-ups and role assignment to night actions, voting, and dynamic story narration.

## ✨ Key Features

  * **Automated Game Management**: Handles the full game lifecycle, including sign-ups, day/night cycles, and phase timers.
  * **Complex Role Support**: Supports a wide variety of roles with unique night abilities (Doctors, Cops, Role Blockers, Jester, etc.) defined in flexible JSON configurations.
  * **Dynamic Role Assignment**: Automatically assigns roles from `mafia_setups.json` based on the number of players who sign up.
  * **Automated Voting**: Manages day-phase lynch votes and inactivity-based voting.
  * **Dynamic Narration**: Generates narrative stories for all game events (kills, blocks, lynches) at the end of each phase.
  * **Extensive Unit Testing**: A robust test suite ensures code stability and reliability.

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

## 🧪 Running Tests

To verify that all game logic is working correctly, you can run the full unit test suite:

```bash
python -m unittest discover Tests
```

-----
