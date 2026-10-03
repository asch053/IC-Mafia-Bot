import discord
import logging
import config

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

async def update_player_discord_roles(bot, guild, game_players: dict, action: str = None):
    """
    Synchronizes roles for the entire server. 
    - Players in game_players get Alive/Dead roles.
    - Everyone else (non-bots) gets the Spectator role.
    """
    # 1. Fetch the actual role objects from IDs
    alive_role = guild.get_role(getattr(config, 'LIVING_ROLE_ID', 0))
    dead_role = guild.get_role(getattr(config, 'DEAD_ROLE_ID', 0))
    spec_role = guild.get_role(getattr(config, 'SPECTATOR_ROLE_ID', 0))
    logger.debug(f"Fetched roles - Alive: {alive_role}, Dead: {dead_role}, Spectator: {spec_role}")
    if not all([alive_role, dead_role, spec_role]):
        logger.error("Role synchronization failed: One or more role IDs are missing in config.")
        return

    logger.info(f"Starting server-wide role synchronization for {len(guild.members)} guild members.")

    # 2. Iterate through ALL members in the guild
    # Note: Use chunking or fetch if the server is large
    for member in guild.members:
        if member.id < 0:
            logger.debug(f"Skipping role sync for bot user: {member.display_name} (ID: {member.id})")
            continue  # Leave our fellow bots alone!
        logger.debug(f"Processing member: {member.display_name} (ID: {member.id})")
        # get player object for specific user id
        user_id = member.id
        player_obj = game_players.get(user_id)
        logger.debug(f"Player object for {member.display_name}: {player_obj}")
        # Determine target role based on game state and action
        if hasattr(player_obj, 'is_alive'):
            player_alive = player_obj.is_alive
        else:
            player_alive = None
        try:
            target_role = None
            # 3. Logic for Players IN the game
            target_role = None
            if action == "alive" or (action is None and player_alive is True):
                target_role = alive_role
            elif action == "dead" or (action is None and player_alive is False):
                target_role = dead_role
            elif action == "spectator" or (action is None and player_alive is None):
                target_role = spec_role            
            # 4. Logic for everyone NOT in the game
            else:
                target_role = spec_role
            logger.debug(f"Determined target role for {member.display_name}: {target_role}")
            if not target_role: continue  # Just a safety check, should not happen
            # 5. Apply changes only if necessary (to avoid rate limits)
            current_managed_roles = {r for r in [alive_role, dead_role, spec_role] if r in member.roles}
            logger.debug(f"Current managed roles for {member.display_name}: {current_managed_roles}")
            if target_role not in member.roles:
                # Remove any of the other two managed roles the user might have
                roles_to_remove = current_managed_roles - {target_role}
                if roles_to_remove:
                    await member.remove_roles(*roles_to_remove)
                    logger.debug(f"Synchronized roles for {member.display_name}: Removed {[r.name for r in roles_to_remove]}")
                # Add the target role if not already present
                await member.add_roles(target_role)
                logger.debug(f"Synchronized roles for {member.display_name}: Added {target_role.name}")
        # Handle specific exceptions for better logging and debugging
        except discord.Forbidden:
            logger.error(f"Missing permissions to manage roles for {member.display_name}")
        except Exception as e:
            logger.exception(f"Error syncing roles for {member.display_name}: {e}")

    logger.info(f"Server-wide role synchronization completed for {len(guild.members)} guild members.")