# game/engine/reset.py
import sys
import logging
from utils.updatediscordroles import update_player_discord_roles

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def _get_update_roles_fn():
    engine_mod = sys.modules.get('game.engine')
    if engine_mod and hasattr(engine_mod, 'update_player_discord_roles'):
        return engine_mod.update_player_discord_roles
    return update_player_discord_roles


async def reset(game):
    """
    Resets the game state to prepare for a new game.
    Removes 'Living'/'Dead' roles from all players and assigns 'Spectator'.
    """
    logger.info("Resetting the game state.")

    # 1. Update Discord Roles for ALL players
    logger.info("getting relevant discord roles.")
    logger.info("Resetting player roles to spectators.")
    await _get_update_roles_fn()(game.bot, game.guild, game.players, action="spectator")

    # 2. Clear Game State
    logger.info("Clearing game state.")
    game.players.clear()
    game.lynch_votes.clear()
    game.game_roles.clear()
    game.night_actions.clear()
    game.vote_history.clear()
    game.heals_on_players.clear()
    game.kill_attempts_on.clear()
    game.night_outcomes.clear()
    game.blocked_players_this_night.clear()
    game.chat_log.clear()
    game.game_settings["start_time"] = None
    game.game_settings["game_started"] = False
    game.game_settings["current_phase"] = "setup"
    game.game_settings["phase_number"] = 0
    game.game_settings["game_id"] = None
    game.force_start_flag = False
    game.reminders_sent.clear()
    if hasattr(game, 'narration_manager') and game.narration_manager:
        game.narration_manager.clear()

    # 3. Stop Loops
    if hasattr(game, 'game_loop') and game.game_loop.is_running():
        game.game_loop.cancel()
    if hasattr(game, 'signup_loop') and game.signup_loop.is_running():
        game.signup_loop.stop()

    logger.info("Game state reset complete.")
