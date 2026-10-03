import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def send_role_dm(bot, player, role, guild):
    """Sends role information via DM. Returns True on success, False on failure."""
    player_id = player.id if hasattr(player, 'id') else int(player)
    player_name = getattr(player, 'display_name', str(player_id))
    guild_name = getattr(guild, 'name', 'Mafia Game')
    role_name = getattr(role, 'name', 'Unknown')
    role_desc = getattr(role, 'description', '')

    logger.debug(f"Attempting to send role DM to player {player_name} for role {role_name} in guild {guild_name}.")
    try:
        if player_id < 0:
            logger.warning(f"Skipping DM for player {player_name} because it's a bot.")
            return True
        user = await bot.fetch_user(player_id)
        logger.debug(f"Fetched user object for {player_name}: {user}.")
        await user.send(f"Your role is: **{role_name}**\n{role_desc}")
        logger.info(f"Successfully sent role DM to {player_name} for role {role_name}.")
        return True
    except Exception as e:
        logger.error(f"Failed to send role DM to {player_name}: {e}")
        return False