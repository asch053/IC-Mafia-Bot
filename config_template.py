# config_template.py
# This is a template for the configuration file.
# In a real deployment, you would copy this to config.py and fill in the secrets.
# For GitHub Actions, the secrets are injected from the environment.

import os

# --- Core Bot Settings ---
# The BOT_TOKEN is the most sensitive value.
# We will get it from GitHub secrets (environment variables) if it's available.
BOT_TOKEN = os.environ.get('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')

# --- Channel IDs (These are not secret, just configuration) ---
ANNOUNCEMENT_CHANNEL_ID = 123456789012345678
SIGN_UP_HERE_CHANNEL_ID = 123456789012345678
RULES_AND_ROLES_CHANNEL_ID = 123456789012345678
STORIES_CHANNEL_ID = 123456789012345678
VOTING_CHANNEL_ID = 123456789012345678
TALKY_TALKY_CHANNEL_ID = 123456789012345678
MOD_CHANNEL_ID = 123456789012345678

# --- Game Settings ---
min_players = 6
signup_loop_interval_seconds = 15
signup_loop_interval_seconds = 15
game_loop_interval_seconds = 15
MAX_MISSED_VOTES = 2

# A list of tuples for reminder points (minutes, text)
REMINDER_POINTS = {
    60: "1 hour",
    30: "30 minutes",
    15: "15 minutes",
    5: "5 minutes"
}