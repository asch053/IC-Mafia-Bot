import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def get_game_instance(bot):
    """
    Retrieves the current game instance from the bot's attributes.
    Returns None if no game instance is found.
    """
    try:
        return getattr(bot, 'game_instance', None)
    except Exception as e:
        logger.error(f"Error retrieving game instance: {e}")
        return None