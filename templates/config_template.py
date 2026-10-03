"""TEMPLATE Configuration file for the IC Mafia Bot. This file contains all the constants and settings used throughout the bot's codebase. 
It is designed to be easily editable for different environments (development, testing, production) and can be overridden by environment variables 
for secure deployment."""

import os

# --- Helper Function for Strict Loading ---
def get_required_env(var_name: str, default: str = None) -> str:
    """
    Must Fix: Fetches an environment variable and fails gracefully if missing.
    This prevents the bot from starting with missing configuration data.
    """
    value = os.getenv(var_name)
    if not value:
        if default is not None:
            return default
        raise ValueError(
            f"CRITICAL STARTUP ERROR: '{var_name}' environment variable is missing! "
            f"Please ensure your .env file is correctly configured and loaded by Docker."
        )
    return value

# --- BOT AUTHENTICATION TOKENS ---
BOT_TOKEN = get_required_env("BOT_TOKEN")  # Put Your Testing Bot Token Here

# --- DISCORD SERVER AND CHANNEL IDS ---
SERVER_ID                   =   get_required_env("SERVER_ID", 123456789012345678)                   # Replace with your server's ID
TALKY_TALKY_CHANNEL_ID      =   get_required_env("TALKY_TALKY_CHANNEL_ID", 123456789012345678)      # Replace with #talky-talky channel ID
STORIES_CHANNEL_ID          =   get_required_env("STORIES_CHANNEL_ID", 123456789012345678)          # Replace with #stories channel ID
VOTING_CHANNEL_ID           =   get_required_env("VOTING_CHANNEL_ID", 123456789012345678)           # Replace with #voting-channel channel ID
RULES_AND_ROLES_CHANNEL_ID  =   get_required_env("RULES_AND_ROLES_CHANNEL_ID", 123456789012345678)  # Replace with #rules-and-roles channel ID
DEADZOR_CHANNEL_ID          =   get_required_env("DEADZOR_CHANNEL_ID", 123456789012345678)          # Replace with #deadzor channel ID
SIGN_UP_HERE_CHANNEL_ID     =   get_required_env("SIGN_UP_HERE_CHANNEL_ID", 123456789012345678)     # Replace with #sign-up-here channel ID
MOD_CHANNEL_ID              =   get_required_env("MOD_CHANNEL_ID", 123456789012345678)              # Replace with #mod channel ID
ANNOUNCEMENT_CHANNEL_ID     =   get_required_env("ANNOUNCEMENT_CHANNEL_ID", 123456789012345678)     # Replace with #announcement channel ID

# --- Discord Role IDs ---
# These can be used for assigning roles to players, mods, etc. and can be referenced
# throughout the codebase when role checks or assignments are needed.
# -- Standard Game Roles --
LIVING_PLAYER_ROLE_ID           = int(get_required_env("LIVING_PLAYER_ROLE_ID", 123456789012345678))        # Role ID for the "Player" role
DEAD_PLAYER_ROLE_ID             = int(get_required_env("DEAD_PLAYER_ROLE_ID", 123456789012345678))          # Role ID for the "Dead" role
SPECTATOR_ROLE_ID               = int(get_required_env("SPECTATOR_ROLE_ID", 123456789012345678))            # Role ID for the "Spectator" role
MOD_ROLE_ID                     = int(get_required_env("MOD_ROLE_ID", 123456789012345678))                  # Role ID for the "Moderator" role
# --- # Classic Award Roles
CLASSIC_TOP_SKILL_ROLE_ID       = int(get_required_env("CLASSIC_TOP_SKILL_ROLE_ID", 123456789012345678))    # Role ID for the "Classic Top Skill" role
CLASSIC_TOP_SURVIVOR_ROLE_ID    = int(get_required_env("CLASSIC_TOP_SURVIVOR_ROLE_ID", 123456789012345678)) # Role ID for the "Classic Top Survivor" role
CLASSIC_RED_SHIRT_ROLE_ID       = int(get_required_env("CLASSIC_RED_SHIRT_ROLE_ID", 123456789012345678))    # Role ID for the "Classic Red Shirt" role
# Battle Royale Award Roles
BR_TOP_WINS_ROLE_ID             = int(get_required_env("BR_TOP_WINS_ROLE_ID", 123456789012345678))          # Role ID for the "BR Top Wins" role
BR_TOP_SURVIVOR_ROLE_ID         = int(get_required_env("BR_TOP_SURVIVOR_ROLE_ID", 123456789012345678))      # Role ID for the "BR Top Survivor" role
BR_RED_SHIRT_ROLE_ID            = int(get_required_env("BR_RED_SHIRT_ROLE_ID", 123456789012345678))         # Role ID for the "BR Red Shirt" role

# --- GAME DATA PATHS AND SETTINGS ---
game_type = get_required_env("GAME_TYPE", "Alpha Testing")  # Game type for the bot
data_save_path = f"Stats/{game_type}"  # Path to save game data

# --- EXTERNAL API KEYS ---
GOOGLE_AI_API_KEY = get_required_env("GOOGLE_AI_API_KEY")  # Your API key for Google AI services here
GOOGLE_AI_TIMEOUT = 120.0  # Timeout for Google AI API calls in seconds
AI_MAX_RETRIES = 3  # Maximum number of retries for AI story generation
AI_RETRY_DELAY = 5  # Base delay in seconds for retries (will be multiplied by the retry count for exponential backoff)

# --- BOT SETTINGS ---
BOT_PREFIX = get_required_env("BOT_PREFIX", "/")  # Replace with your desired prefix
OWNER_ID = int(get_required_env("OWNER_ID"))  # Replace with your Discord user ID 

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
min_sk_players: int = 8             # Minimum players required to include a Serial Killer
mob_ratio: float = 0.5              # Ratio of Mafia to total players


# --- GAME LOOP AND TIMEOUT SETTINGS ---
REMINDER_POINTS = {60: "1 hour", 30: "30 minutes", 10: "10 minutes"} # For testing, you could change it to: REMINDER_POINTS = {2: "2 minutes", 1: "1 minute"}
game_loop_interval_seconds = 15  # Interval for the game loop to check phase deadlines and send reminders
signup_loop_interval_seconds = 15  # Interval for the signup loop to check player count and send reminders

# --- VOTING SETTINGS ---
MAX_MISSED_VOTES = 1 # Player is killed after missing 1 vote

# --- Statistics Tracking Settings ---
GOOGLE_SHEET_ID = get_required_env("GOOGLE_SHEET_ID")  # Replace with your Google Sheet ID
GOOGLE_CREDENTIALS_FILE = get_required_env("GOOGLE_CREDENTIALS_FILE") # Replace with your Google API credentials file
GOOGLE_SHEET_GAMES_TAB = "Games"
GOOGLE_SHEET_PLAYERS_TAB = "Players"
GOOGLE_SHEET_VOTES_TAB = "Votes"

GOOGLE_SIMULATION_SHEET_ID = get_required_env("GOOGLE_SIMULATION_SHEET_ID")  # Replace with your Simulation Sheet ID

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