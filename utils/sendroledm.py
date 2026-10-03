import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

async def send_role_dm(bot, player, role, guild):
    """Sends role information via DM."""
    logger.debug(f"Attempting to send role DM to player {player.display_name} for role {role.name} in guild {guild.name}.")
    try:
        if player.id < 0:
            logger.warning(f"Skipping DM for player {player.display_name} because it's a bot.")
            return
        user = await bot.fetch_user(player.id)
        logger.debug(f"Fetched user object for {player.display_name}: {user}.")
        await user.send(f"Your role is: **{role.name}**\n{role.description}")
        logger.info(f"Successfully sent role DM to {player.display_name} for role {role.name}.")
    except Exception as e:
        logger.error(f"Failed to send role DM to {player.display_name}: {e}")