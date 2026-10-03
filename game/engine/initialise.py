import asyncio
import logging
import config
from game.narration import NarrationManager
from utils.loaddata import load_data


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

async def initialize_game(self, bot, guild, game_type, phase_hours, start_datetime, narration_type,
                          gf_investigate_choice, sk_investigate_choice, mafia_ratio, town_rb_req,
                          mafia_rb_req, sk_player_count, town_cop_req, town_doctor_req, cleanup_callback):
    self.narration_manager = NarrationManager()
    self.bot = bot
    self.guild = guild  # The context from the '/startmafia' command
    self.last_reminder_time = None  # Track the last time a reminder was sent
    self.cleanup_callback = cleanup_callback
    # --- Game State Variables ---
    logger.debug("Setting up initial game settings and player data.")
    self.game_settings = {
            "game_id": None, #date-time string of time signups ended
            "game_type": game_type,
            "story_type": None,
            "game_started": False,
            "start_time": None,
            "end_time": None,
            "current_phase": "setup", # Phases: setup, signup, preparation, night, day, finished
            "phase_number": 0,
            "phase_end_time": None,
            "gf_investigate": True,  # Default
            "sk_investigate": False, # Default
            "gf_night_immune": True,  # Default
            "sk_night_immune": True, # Default
            "phase_hours": 12, # Default
            "mafia_ratio": config.mob_ratio, # Default
            "town_rb_req": config.min_town_rb_players, # Default
            "mafia_rb_req": config.min_mob_rb_mafia_count, # Default
            "sk_player_count": config.min_sk_players, # Default
            "town_cop_req": config.min_cop_players, # Default
            "town_doctor_req": config.min_doctor_players # Default
        }
    self.chat_log = [] # To store chat messages during the game FR-5.4: Advanced Data Logging
    self.game_event_log = [] # To store game events during the game FR-5.4: Advanced Data Logging
    self.players = {} # This will now store Player objects: {player_id: Player_Object}
    self.lynch_votes = {} # This will store votes for lynching: {player_id: target_id}
    self.game_roles = [] # This will store GameRole objects assigned to players
    self.night_actions = {} # Stores night actions: {player_id: {"action": "type", "target": id}}
    self.protected_players_this_night = {} # Tracks players protected during the night & who protected them {player_id: protector_id}
    self.blocked_players_this_night = {} # Tracks players who were blocked this night
    self.vote_history = [] # NEW: To store every single vote
    self.player_lock = asyncio.Lock() # Create lock to ensure one person at a time for joining and exiting game
    self.vote_lock = asyncio.Lock() # Create lock to ensure one vote at a time 
    # --- Night Action Tracking ---
    self.night_outcomes = {}
    self.heals_on_players = {}
    self.kill_attempts_on = {}
    self.blocked_players_this_night = {}
    # --- Control Flags ---
    self.force_start_flag = False
    self.reminders_sent = set() # Tracks sent reminders for the current phase
    self.max_players = 19 # Default max players
    # --- Narration Markers ---
    self.is_prologue = None
    self.is_epilogue = None 
    # --- Data Loading ---
    logger.debug("Loading game data from data files.")
    try:
        self.npc_names = load_data("data/game_setup/bot_names.txt") #load NPC bot names
    except Exception as e:
        logger.error(f"Error loading NPC names: {e}")
    try:    
        self.rules_text = "\n".join(load_data("data/game_setup/rules.txt"))
    except Exception as e:
        logger.error(f"Error loading rules text: {e}")
        self.rules_text = "No rules text found. Please check the rules.txt file."
    try:
        self.theme_stories = load_data("data/narration/themes.json")
    except Exception as e:
        logger.error(f"Error loading theme stories: {e}")
        logger.critical("No theme stories loaded. The game cannot use AI narration.")
    try:
        self.player_quirks= load_data("data/narration/player_concepts.json")
    except Exception as e:
        logger.error(f"Error loading player quirks: {e}")
        logger.critical("No player quirks loaded. The game cannot use AI narration.")