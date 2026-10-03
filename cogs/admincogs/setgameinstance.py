import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def set_game_instance(bot, game_instance):
    """
    Sets the game instance on bot.game_instance and synchronizes with GameCog.
    """
    bot.game_instance = game_instance
    game_cog = bot.get_cog('GameCog')
    if game_cog:
        game_cog.game = game_instance
    logger.info(f"Game instance set to: {game_instance}")
    logger.info(f"Game instance set to: {game_instance}")