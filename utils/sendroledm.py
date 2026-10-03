# utils/sendroledm.py
"""
Utility module for securely dispatching private role information to players.

Key Features:
- Transparent display of themed skins: `**{role_display}** ({role_name})`
- NPC / bot user identification: Skips DM dispatch for virtual NPC players (ID < 0)
- Graceful exception logging: Catches and logs privacy / closed DM errors without halting game setup
"""

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def send_role_dm(bot, player, role, guild):
    """
    Sends a private direct message (DM) to a player with their assigned role and ability instructions.

    Args:
        bot (discord.Client): The Discord bot client instance.
        player (Player): The player receiving the role assignment.
        role (GameRole): The GameRole object containing mechanical and themed data.
        guild (discord.Guild): The Discord server running the game.

    Returns:
        bool: True if the DM was successfully delivered or safely skipped for an NPC; False on error.
    """
    # 1. Resolve player identifiers and display names safely
    player_id = player.id if hasattr(player, 'id') else int(player)
    player_name = getattr(player, 'display_name', str(player_id))
    guild_name = getattr(guild, 'name', 'Mafia Game')
    role_name = getattr(role, 'name', 'Unknown')
    role_display = getattr(role, 'display_name', role_name)
    role_desc = getattr(role, 'description', '')

    logger.debug(
        f"Attempting to send role DM to player {player_name} for role {role_name} "
        f"(Display: {role_display}) in guild {guild_name}."
    )

    try:
        # 2. Virtual NPCs use negative IDs; skip DM delivery safely
        if player_id < 0:
            logger.warning(f"Skipping DM for player {player_name} because it's an automated NPC bot.")
            return True

        # 3. Retrieve the Discord User object
        user = await bot.fetch_user(player_id)
        logger.debug(f"Fetched user object for {player_name}: {user}.")

        # 4. Format role header: Show themed display name alongside canonical mechanical name
        if role_display and role_display != role_name:
            role_header = f"**{role_display}** ({role_name})"
        else:
            role_header = f"**{role_name}**"

        # 5. Dispatch the private direct message
        await user.send(f"Your role is: {role_header}\n{role_desc}")
        logger.info(f"Successfully sent role DM to {player_name} for role {role_name} ({role_display}).")
        return True

    except Exception as e:
        # User may have DMs closed or blocked the bot; log the error gracefully without breaking startup
        logger.error(f"Failed to send role DM to {player_name}: {e}")
        return False