# config_template.py
# This is a template file. 
# Rename this file to config.py and fill in your actual bot token and other values.
# DO NOT commit your config.py file to GitHub!

# --- Bot Essentials ---
# Get your Bot Token from the Discord Developer Portal
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
# Get your User ID by right-clicking your name in Discord (with Developer Mode on)
OWNER_ID = 123456789012345678
# The prefix for text-based commands (if you still use them)
BOT_PREFIX = "/"

# --- Channel IDs ---
# Right-click the channel in Discord and select "Copy Channel ID"
ANNOUNCEMENT_CHANNEL_ID = 12345
SIGN_UP_HERE_CHANNEL_ID = 12345
RULES_AND_ROLES_CHANNEL_ID = 12345
VOTING_CHANNEL_ID = 12345
STORIES_CHANNEL_ID = 12345
TALKY_TALKY_CHANNEL_ID = 12345

# --- Game Loop Timings (in seconds) ---
# How often the main game loop checks for phase end
game_loop_interval_seconds = 15
# How often the sign-up loop checks for start time/reminders
signup_loop_interval_seconds = 30 

# --- Game Rules & Balance ---
# Minimum players required to start a "Classic" game
min_players = 5
# Maximum number of missed votes before a player is auto-killed for inactivity
MAX_MISSED_VOTES = 3

# --- Dynamic Role Generator Settings (for Classic) ---
min_sk_players = 9          # Min players to add a Serial Killer
min_cop_players = 6         # Min players to add a Town Cop
min_doctor_players = 7      # Min players to add a Town Doctor
min_town_rb_players = 8     # Min players to add a Town Role Blocker
min_mob_rb_mafia_count = 4  # Min *Mafia* players to upgrade one to a Mafia Role Blocker

# --- Sign-up Reminder Times (in minutes before start) ---
# (Dictionary format: {minutes: "display_text"})
REMINDER_POINTS = {
    60: "1 hour",
    30: "30 minutes",
    15: "15 minutes",
    5: "5 minutes",
    1: "1 minute"
}

# ---------------------------------------------------------------------
# --- NEW: AI Narration (v0.6+) ---
# ---------------------------------------------------------------------
# Get your API key from Google AI Studio (formerly MakerSuite)
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY_HERE"


# ---------------------------------------------------------------------
# --- NEW: Google Sheets Export ---
# ---------------------------------------------------------------------
# The ID of the Google Sheet (from the URL: .../d/THIS_IS_THE_ID/edit)
GOOGLE_SHEET_ID = "YOUR_SHEET_ID_GOES_HERE"

# The filename of your Google Cloud credentials JSON file
# (This file MUST be in the same folder as bot.py!)
GOOGLE_CREDENTIALS_FILE = "google_credentials.json"

# The EXACT names of the tabs (worksheets) in your Google Sheet
GOOGLE_SHEET_GAMES_TAB = "Games"
GOOGLE_SHEET_PLAYERS_TAB = "Players"
GOOGLE_SHEET_VOTES_TAB = "Votes"


# ---------------------------------------------------------------------
# --- NEW: Skill Score Parameters ---
# ---------------------------------------------------------------------
# Weights for the 3 sub-scores (default is 1:1:1)
SKILL_WEIGHT_PERSUASION = 1
SKILL_WEIGHT_ELUSIVENESS = 1
SKILL_WEIGHT_UNDERSTANDING = 1

# Percentage of the game considered "early game" for the Understanding score
# (e.g., 0.25 = first 25% of phases)
SKILL_EARLY_GAME_PERCENT = 0.25

# Weights for the "Understanding" score, based on faction difficulty
# (Hardest to win = highest weight!)
SKILL_WIN_WEIGHT_TOWN = 0.15      # Easiest to win, lowest skill points
SKILL_WIN_WEIGHT_MAFIA = 0.35     # Medium difficulty
SKILL_WIN_WEIGHT_NEUTRAL = 0.50   # Hardest to win, highest skill points