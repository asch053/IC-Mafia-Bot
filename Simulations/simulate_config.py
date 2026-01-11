# config.py

# --- GAME DATA PATHS AND SETTINGS ---
game_type = "Simulation_Testing"  # Game type for the bot
data_save_path = f"Stats/{game_type}"  # Path to save game data

# --- GAME TIMING CONFIGURATION PARAMETERS ---
JOIN_HOURS  = 24    # Duration of signup period in hours
PHASE_HOURS = 12   # Duration of day and night phases in hours
game_settings = {}  # Initialize game_settings here

# --- PLAYER SETUP CONFIGURATION PARAMETERS ---
min_players = 5                     # Minimum number of players to start the game
min_cop_players: int = 5            # Minimum players required to include a Cop
min_doctor_players: int = 5         # Minimum players required to include a Doctor
min_town_rb_players: int = 5        # Minimum players required to include a Town Role Blocker
min_mob_rb_mafia_count: int = 3     # Minimum Mafia count required to include a Mafia Role Blocker
min_sk_players: int = 8             # Minimum players required to include a Serial Killer


# --- VOTING SETTINGS ---
MAX_MISSED_VOTES = 1 # Player is killed after missing 1 vote

# --- Statistics Tracking Settings ---
TUNING_GOOGLE_SHEET_ID = "1P4TOTiU_EQHxYnKcuV9sGFddql1XWIiEaXCeZbE02DI"
SIMUALTION_GOOGLE_SHEET_ID = "1pKufBdummCZ53TLhizXnHSq6Tdzk3qpzlfkSXwCnhQk"

# --- Google Sheets Configuration ---
GOOGLE_CREDENTIALS_FILE = "ic-mafia-bot-41a41f61e757.json"
GOOGLE_SHEET_GAMES_TAB = "Games"
GOOGLE_SHEET_PLAYERS_TAB = "Players"
GOOGLE_SHEET_VOTES_TAB = "Votes"

GOOGLE_SIMULATION_SHEET_ID = "1y_Ik4Zh715ZvHHGtg4-m-7IazChfaVfxEN9ajrrmLTc"  # Replace with your Simulation Sheet ID

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

# --- Simulation Parameters ---
PLAYER_COUNTS_TO_SIMULATE = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]  # List of player counts to simulate

missed_vote_probability = 0.992  # target 4% of players die from inactivy over a whole game

PROBABILITY_MAFIA_SMART = 0.1           # Chance that Mafia can work out town network players based on chat and deduction
PROBABILITY_TOWN_SMART = 0.6            # Chance that Town will join Bandwagons
BASE_INTUITION= 0.8                     # Base Percentage chance that a plain town could work out a mafia member based on chat and deduction

PROBABILITY_HARD_BANDWAGON = 0.6        # Chance that Town will join the biggest bandwagon when no known Mafia members are available
PROBABILITY_SOFT_BANDWAGON = 0.6        # Chance that Town will join a soft bandwagon 
PROBABILITY_CURIOUS_BANDWAGON = 0.1     # Chance that Town will join a curious bandwagon 


LOGGING_ENABLED = False  # Enable verbose logging for simulations (slows down performance)
