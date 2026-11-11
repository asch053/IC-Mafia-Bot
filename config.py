# config.py
"""Configuration file for the IC Mafia Bot. This file contains all the constants and settings used throughout the bot's codebase.
It is designed to be easily editable for different environments (development, testing, production) and can be overridden by environment variables
for secure deployment."""

import os

# Automatically load from the first available .env file if env vars are not already set.
# IMPORTANT: We break after loading the highest-priority .env file so that committed test
# files (.env.test) NEVER pollute or fall through into a production or local .env environment!
_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
for _env_file in [".env", ".env.prod", ".env.production", ".env.beta", ".env.test"]:
    _env_path = os.path.join(_ROOT_DIR, _env_file)
    if os.path.exists(_env_path):
        try:
            from dotenv import load_dotenv
            load_dotenv(_env_path, override=False)
        except Exception:
            try:
                with open(_env_path, "r", encoding="utf-8") as _f:
                    for _line in _f:
                        _line = _line.strip()
                        if _line and not _line.startswith("#") and "=" in _line:
                            _k, _v = _line.split("=", 1)
                            _v = _v.strip()
                            if not (_v.startswith('"') or _v.startswith("'")):
                                _v = _v.split("#", 1)[0].strip()
                            else:
                                _q = _v[0]
                                _eq = _v.find(_q, 1)
                                if _eq != -1:
                                    _v = _v[1:_eq]
                            os.environ.setdefault(_k.strip(), _v.strip())
            except Exception:
                pass
        break

# --- Helper Function for Strict Loading ---
def get_required_env(var_name: str, default: str = None, aliases: list = None) -> str:
    """
    Fetches an environment variable and fails gracefully if missing.
    Supports fallback aliases (e.g. GOOGLE_SHEET_KEY for GOOGLE_SHEET_ID).
    """
    value = os.getenv(var_name)
    if not value and aliases:
        for alias in aliases:
            value = os.getenv(alias)
            if value:
                break
    if not value:
        if default is not None:
            return default
        raise ValueError(
            f"CRITICAL STARTUP ERROR: '{var_name}' environment variable is missing! "
            f"Please ensure your .env file is correctly configured and loaded by Docker."
        )
    return value


# --- BOT AUTHENTICATION TOKENS ---
BOT_TOKEN = get_required_env("BOT_TOKEN", aliases=["DISCORD_TOKEN"])  # Bot Token

# --- DISCORD SERVER AND CHANNEL IDS ---
SERVER_ID                           =   int(get_required_env("SERVER_ID"))                   # The Server ID for the IC Mafia Testing Server
TALKY_TALKY_CHANNEL_ID              =   int(get_required_env("TALKY_TALKY_CHANNEL_ID"))      # The channel ID for the #talky-talky channel
STORIES_CHANNEL_ID                  =   int(get_required_env("STORIES_CHANNEL_ID"))          # The channel ID for the #stories channel
VOTING_CHANNEL_ID                   =   int(get_required_env("VOTING_CHANNEL_ID"))           # The channel ID for the #voting-channel channel
RULES_AND_ROLES_CHANNEL_ID          =   int(get_required_env("RULES_AND_ROLES_CHANNEL_ID"))  # The channel ID for the #rules-and-roles channel
DEADZOR_CHANNEL_ID                  =   int(get_required_env("DEADZOR_CHANNEL_ID"))          # The channel ID for the #deadzor channel
SIGN_UP_HERE_CHANNEL_ID             =   int(get_required_env("SIGN_UP_HERE_CHANNEL_ID"))     # The channel ID for the #sign-up-here channel
MOD_CHANNEL_ID                      =   int(get_required_env("MOD_CHANNEL_ID"))              # The channel ID for the #mod channel
ANNOUNCEMENT_CHANNEL_ID             =   int(get_required_env("ANNOUNCEMENT_CHANNEL_ID"))     # The channel ID for the #announcement channel

# --- Discord Role IDs ---
# These can be used for assigning roles to players, mods, etc. and can be referenced
# throughout the codebase when role checks or assignments are needed.
# -- Standard Game Roles --
LIVING_ROLE_ID                      = int(get_required_env("LIVING_PLAYER_ROLE_ID", 1322336366796996789, aliases=["LIVING_ROLE_ID"]))        # Role ID for the "Player" role
DEAD_ROLE_ID                        = int(get_required_env("DEADZOR_PLAYER_ROLE_ID", 1322336409926762586, aliases=["DEAD_PLAYER_ROLE_ID", "DEAD_ROLE_ID"]))          # Role ID for the "Dead" role
LIVING_PLAYER_ROLE_ID               = LIVING_ROLE_ID
DEAD_PLAYER_ROLE_ID                 = DEAD_ROLE_ID
SPECTATOR_ROLE_ID                   = int(get_required_env("SPECTATOR_ROLE_ID", 1322335985702277151))            # Role ID for the "Spectator" role
MOD_ROLE_ID                         = int(get_required_env("ADMIN_ROLE_ID", 1322336444366454895, aliases=["MOD_ROLE_ID"]))                  # Role ID for the "Moderator" role
# --- # Classic Award Roles
CLASSIC_TOP_SKILL_ROLE_ID           = int(get_required_env("CLASSIC_TOP_SKILL_ROLE_ID", 1482294174161305620, aliases=["CLASSIC_MVP_ROLE_ID"]))    # Role ID for the "Classic Top Skill" role
CLASSIC_TOP_SURVIVOR_ROLE_ID        = int(get_required_env("CLASSIC_TOP_SURVIVOR_ROLE_ID", 1482294180205301821, aliases=["CLASSIC_SURVIVOR_ROLE_ID"])) # Role ID for the "Classic Top Survivor" role
CLASSIC_RED_SHIRT_ROLE_ID           = int(get_required_env("CLASSIC_RED_SHIRT_ROLE_ID", 1482294728799162579))    # Role ID for the "Classic Red Shirt" role
CLASSIC_MVP_ROLE_ID                 = CLASSIC_TOP_SKILL_ROLE_ID
CLASSIC_SURVIVOR_ROLE_ID            = CLASSIC_TOP_SURVIVOR_ROLE_ID
# Battle Royale Award Roles
BR_TOP_WINS_ROLE_ID                 = int(get_required_env("BR_TOP_WINS_ROLE_ID", 1482320636234694679, aliases=["BR_CHAMPION_ROLE_ID"]))          # Role ID for the "BR Top Wins" role
BR_TOP_SURVIVOR_ROLE_ID             = int(get_required_env("BR_TOP_SURVIVOR_ROLE_ID", 1482320824777048094, aliases=["BR_SURVIVOR_ROLE_ID"]))      # Role ID for the "BR Top Survivor" role
BR_RED_SHIRT_ROLE_ID                = int(get_required_env("BR_RED_SHIRT_ROLE_ID", 1482320998920618075))         # Role ID for the "BR Red Shirt" role
BR_CHAMPION_ROLE_ID                 = BR_TOP_WINS_ROLE_ID
BR_SURVIVOR_ROLE_ID                 = BR_TOP_SURVIVOR_ROLE_ID

# --- GAME DATA PATHS AND SETTINGS ---
_raw_game_type = get_required_env("GAME_TYPE", "Alpha_Testing", aliases=["ENVIRONMENT"])
if _raw_game_type.strip().lower() in ("production", "prod"):
    game_type = "Production"
elif _raw_game_type.strip().lower() in ("alpha testing", "alpha_testing", "alpha", "test", "testing"):
    game_type = "Alpha_Testing"
else:
    game_type = _raw_game_type.strip()

_raw_save_path = get_required_env("DATA_SAVE_PATH", f"stats/{game_type}").replace("\\", "/").lstrip("./")
if _raw_save_path.startswith("Stats/"):
    _raw_save_path = "stats/" + _raw_save_path[6:]
elif _raw_save_path == "Stats":
    _raw_save_path = "stats"
data_save_path = _raw_save_path  # Path to save game data (always lowercase stats/)

# --- EXTERNAL API KEYS ---
MODEL_NAME = "gemini-2.5-flash-lite"
GOOGLE_AI_API_KEY = get_required_env("GOOGLE_AI_API_KEY")  # API key for Google AI services
GOOGLE_AI_TIMEOUT = 120.0  # Timeout for Google AI API calls in seconds
AI_MAX_RETRIES =  3  # Maximum number of retries for AI story generation
AI_RETRY_DELAY = 5 # Base delay in seconds for retries (will be multiplied by the retry count for exponential backoff)

# --- BOT SETTINGS ---
BOT_PREFIX = get_required_env("BOT_PREFIX","/")
OWNER_ID = int(get_required_env("OWNER_ID"))

# --- GAME TIMING CONFIGURATION PARAMETERS ---
JOIN_HOURS  = 24    # Duration of signup period in hours
PHASE_HOURS = 12   # Duration of day and night phases in hours
game_settings = {}  # Initialize game_settings here

# --- PLAYER SETUP CONFIGURATION PARAMETERS ---
min_players = 5                     # Minimum number of players to start the game
min_cop_players: int = 5            # Minimum players required to include a Cop
min_doctor_players: int = 5         # Minimum players required to include a Doctor
min_town_rb_players: int = 16        # Minimum players required to include a Town Role Blocker
min_mob_rb_mafia_count: int = 4     # Minimum Mafia count required to include a Mafia Role Blocker
min_sk_players: int = 4             # Minimum players required to include a Serial Killer
mob_ratio: float = 0.5              # Ratio of Mafia to total players


# --- GAME LOOP AND TIMEOUT SETTINGS ---
REMINDER_POINTS = {60: "1 hour", 30: "30 minutes", 10: "10 minutes"} # For testing, you could change it to: REMINDER_POINTS = {2: "2 minutes", 1: "1 minute"}
game_loop_interval_seconds = 15  # Interval for the game loop to check phase deadlines and send reminders
signup_loop_interval_seconds = 15  # Interval for the signup loop to check player count and send reminders

# --- VOTING SETTINGS ---
MAX_MISSED_VOTES = 1 # Player is killed after missing 1 vote

# --- Statistics Tracking Settings ---
GOOGLE_SHEET_ID = get_required_env("GOOGLE_SHEET_ID", aliases=["GOOGLE_SHEET_KEY"])
GOOGLE_CREDENTIALS_FILE = get_required_env("GOOGLE_CREDENTIALS_FILE", aliases=["GOOGLE_SERVICE_ACCOUNT_JSON"])
GOOGLE_SIMULATION_SHEET_ID = get_required_env("GOOGLE_SIMULATION_SHEET_ID", default="")  # Optional Simulation Sheet ID

GOOGLE_SHEET_GAMES_TAB = "Games"
GOOGLE_SHEET_PLAYERS_TAB = "Players"
GOOGLE_SHEET_VOTES_TAB = "Votes"
GOOGLE_SHEET_RULES_TAB = get_required_env("GOOGLE_SHEET_RULES_TAB", "Rules Setup")

# --- Skill Score Parameters ---
# Weights for the 3 sub-scores (default is 1:1:1)
SKILL_WEIGHT_PERSUASION = 1
SKILL_WEIGHT_ELUSIVENESS = 1
SKILL_WEIGHT_UNDERSTANDING = 1
# Percentage of the game considered "early game" for the Understanding score
# (e.g., 0.25 = first 25% of phases)
SKILL_EARLY_GAME_PERCENT = 0.25
SKILL_LATE_GAME_PERCENT = 0.75
# Weights for the "Understanding" score, based on faction
SKILL_WIN_WEIGHT_TOWN = 0.10
SKILL_WIN_WEIGHT_MAFIA = 0.35
SKILL_WIN_WEIGHT_NEUTRAL = 0.55

# --- MISC SETTINGS ---
DM_TIMEOUT = 20.0 # seconds
message_send_delay = 1 #delay in seconds before sending a message
start_message_send_delay = 1 # delay in minutes between sending status update messages during signup phase
