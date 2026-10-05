# game/engine/initialise.py
import os
import sys
import asyncio
import logging
import config
from game.narration import NarrationManager
from utils.loaddata import load_data

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def _get_config():
    engine_mod = sys.modules.get('game.engine')
    if engine_mod and hasattr(engine_mod, 'config'):
        return engine_mod.config
    return config


def initialize_game(self, bot, guild, cleanup_callback=None, game_type="classic"):
    """Sets up initial state variables, dictionaries, locks, and loads data files."""
    cfg = _get_config()
    logger.info("Initializing new Game instance.")
    self.narration_manager = NarrationManager()
    self.bot = bot
    self.guild = guild
    self.last_reminder_time = None
    self.cleanup_callback = cleanup_callback

    # --- Game State Variables ---
    logger.debug("Setting up initial game settings and player data.")
    self.game_settings = {
        "game_id": None,
        "game_type": game_type,
        "story_type": None,
        "game_started": False,
        "start_time": None,
        "end_time": None,
        "current_phase": "setup",
        "phase_number": 0,
        "phase_end_time": None,
        "gf_investigate": True,
        "sk_investigate": False,
        "gf_night_immune": True,
        "sk_night_immune": True,
        "br_skip_day": False,
        "phase_hours": 12,
        "mafia_ratio": getattr(cfg, 'mob_ratio', 0.25),
        "town_rb_req": getattr(cfg, 'min_town_rb_players', 10),
        "mafia_rb_req": getattr(cfg, 'min_mob_rb_mafia_count', 4),
        "sk_player_count": getattr(cfg, 'min_sk_players', 9),
        "town_cop_req": getattr(cfg, 'min_cop_players', 6),
        "town_doctor_req": getattr(cfg, 'min_doctor_players', 7),
    }
    self.chat_log = []
    self.game_event_log = []
    self.players = {}
    self.lynch_votes = {}
    self.game_roles = []
    self.night_actions = {}
    self.protected_players_this_night = {}
    self.blocked_players_this_night = {}
    self.vote_history = []
    self.player_lock = asyncio.Lock()
    self.vote_lock = asyncio.Lock()

    # --- Night Action Tracking ---
    self.night_outcomes = {}
    self.heals_on_players = {}
    self.kill_attempts_on = {}
    self.blocked_players_this_night = {}

    # --- Control Flags ---
    self.force_start_flag = False
    self.reminders_sent = set()
    self.max_players = 19

    # --- Narration Markers ---
    self.is_prologue = None
    self.is_epilogue = None

    # --- Data Loading ---
    logger.debug("Loading game data from data files.")
    bot_names_path = "data/game_setup/bot_names.txt"
    try:
        if not os.path.exists(bot_names_path):
            raise FileNotFoundError(f"Bot names file '{bot_names_path}' does not exist.")
        loaded_names = load_data(bot_names_path)
        if isinstance(loaded_names, list):
            self.npc_names = [name.strip() for name in loaded_names if name and name.strip()]
        else:
            self.npc_names = []
            
        if not self.npc_names:
            raise ValueError(f"Bot names file '{bot_names_path}' is empty or contains no valid names.")
    except Exception as e:
        logger.critical(
            f"CRITICAL ERROR: Failed to load NPC bot names from '{bot_names_path}': {e}. "
            "Gracefully falling back to generated bot names in 'Bot_##' format.",
            exc_info=True
        )
        fallback_count = max(50, getattr(self, "max_players", 19) * 2)
        self.npc_names = [f"Bot_{i:02d}" for i in range(1, fallback_count + 1)]
        logger.info(f"Generated {len(self.npc_names)} fallback NPC names in 'Bot_##' format.")

    try:
        rules_list = load_data("data/game_setup/rules.txt")
        self.rules_text = "\n".join(rules_list) if isinstance(rules_list, list) else str(rules_list)
    except Exception as e:
        logger.error(f"Error loading rules text: {e}")
        self.rules_text = "No rules text found. Please check the rules.txt file."

    try:
        self.theme_stories = load_data("data/narration/themes.json")
    except Exception as e:
        logger.error(f"Error loading theme stories: {e}")
        self.theme_stories = {}

    try:
        self.player_quirks = load_data("data/narration/player_concepts.json")
    except Exception as e:
        logger.error(f"Error loading player quirks: {e}")
        self.player_quirks = {}

    logger.debug("Game instance initialized.")