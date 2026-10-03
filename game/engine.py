import discord
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class Game:
    """Manages the entire state and lifecycle of a single Mafia game."""
    def __init__(self, game_type: str, phase_hours: float, start_datetime: str, narration_type: str = "Classic Mafia",
                 gf_investigate_choice: str = "No", sk_investigate_choice: str = "No", 
                 mafia_ratio: float = 0.25, town_rb_req: int = 1, mafia_rb_req: int = 1, 
                 sk_player_count: int = 1, town_cop_req: int = 1, town_doctor_req: int = 1):
        
        logger.debug("Game instance initialized.")