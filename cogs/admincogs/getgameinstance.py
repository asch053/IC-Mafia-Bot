import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def get_game_instance(bot):
    """
    Retrieves the current game instance from bot.game_instance with fallback to GameCog.
    Returns None if no game instance is found.
    """
    try:
        inst = getattr(bot, 'game_instance', None)
        if inst is not None:
            return inst
        game_cog = bot.get_cog('GameCog')
        if game_cog and hasattr(game_cog, 'game'):
            return game_cog.game
        return None
    except Exception as e:
        logger.error(f"Error retrieving game instance: {e}")
        return None
        return None