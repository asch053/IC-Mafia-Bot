import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def set_game_instance(bot, game_instance):
    """
    Sets the game instance for the bot.

    Args:
        bot (commands.Bot): The bot instance.
        game_instance (str): The game instance to set.
    """
    bot.game_instance = game_instance
    logger.info(f"Game instance set to: {game_instance}")