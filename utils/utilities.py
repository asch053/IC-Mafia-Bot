# utils/utilities.py
import discord
import asyncio
import json
import os
import io
from datetime import datetime, timezone
import logging
import config

# Get the same logger instance as in mafiabot.py
logger = logging.getLogger('discord')

# --- File I/O Functions ---
def load_data(filepath,error_default=None):
    """
    Loads data from a JSON or TXT file.
    Args:
        filepath (str): The full path to the file.
    Returns:
        The loaded data (dict/list for JSON, list of strings for TXT), or an empty default.
    """
    try:
        with open(filepath, "r", encoding='utf-8') as f:
            
            if filepath.endswith(".json"):
                return json.load(f)
            else:  # Assume it's a TXT file
                return [line.strip() for line in f]
    except FileNotFoundError:
        logger.error(f"File not found: {filepath}. Returning empty default.")
        return {} if filepath.endswith(".json") else []
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in file: {filepath}. Returning empty default.")
        return {} # Return empty dict for malformed JSON
    except Exception as e:
        logger.exception(f"An unexpected error occurred loading {filepath}: {e}")
        return {} if filepath.endswith(".json") else []

def save_json_data(data, filename, subdirectory):
    """
    Saves data to a JSON file in a specified subdirectory of 'stats'. Overwrites the file.
    Args:
        data: The JSON-serializable data to save.
        filename (str): The name of the file without the .json extension.
        subdirectory (str): The subdirectory within the "stats" folder.
    """
    try:
        # Create the full directory path
        full_dir_path = os.path.join("stats", subdirectory)
        os.makedirs(full_dir_path, exist_ok=True)
        # Construct the full file path
        filepath = os.path.join(full_dir_path, f"{filename}.json")
        with open(filepath, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        logger.info(f"Data successfully saved to {filepath}")
    except TypeError as e:
        logger.error(f"Data for {filename} was not JSON serializable: {e}")
    except Exception as e:
        logger.exception(f"Failed to save data to {filename}: {e}")

# --- Player & Role Functions ---
async def update_player_discord_roles(bot, guild, players, discord_role_data):
    """Updates player roles in Discord based on their game status (alive/dead)."""
    logger.debug("Updating player Discord roles based on game status.")
    if not guild:
        logger.critical("update_player_discord_roles called without a valid guild.")
        return
    living_role = guild.get_role(discord_role_data.get("living", {}).get("id", 0))
    dead_role = guild.get_role(discord_role_data.get("dead", {}).get("id", 0))
    spectator_role = guild.get_role(discord_role_data.get("spectator", {}).get("id", 0))
    if not all((living_role, dead_role, spectator_role)):
        logger.critical("Could not find one or more required roles (Living, Dead, Spectator) in the server.")
        return
    # Update roles for players in the game
    for player_id, player_obj in players.items():
        if player_obj.is_npc: continue # Skip NPCs
        # Fetch the member object from the guild
        logger.debug(f"Updating roles for player {player_obj.display_name} (ID: {player_id})")
        member = guild.get_member(player_id)
        if not member:
            logger.warning(f"Could not find player with ID {player_id} in the server.")
            continue
        user_roles = [role.id for role in member.roles]
        logger.warning(f"User roles for {member.name} (ID: {member.id}): {user_roles}")
        try:
            if player_obj.is_alive:
                await member.add_roles(living_role)
                await member.remove_roles(dead_role, spectator_role)
            else:
                await member.add_roles(dead_role)
                await member.remove_roles(living_role, spectator_role)
        except discord.HTTPException as e:
            logger.error(f"Failed to update roles for {member.name}: {e}")
        logger.debug(f"Updated roles for {member.name} (ID: {member.id}) - Alive: {player_obj.is_alive}")
        user_roles = [role.id for role in member.roles]
        logger.warning(f"User roles for {member.name} (ID: {member.id}): {user_roles}")
    # Ensure non-players are spectators
    player_ids = {pid for pid, p_obj in players.items() if not p_obj.is_npc}
    async for member in guild.fetch_members(limit=None):
        logger.debug(f"Checking non-player roles for {member.name} (ID: {member.id})")
        # Skip bots and already known players
        if member.bot or member.id in player_ids:
            continue
        user_roles = [role.id for role in member.roles]
        logger.warning(f"User roles for {member.name} (ID: {member.id}): {user_roles}")
        try:
            if living_role in member.roles or dead_role in member.roles:
                await member.remove_roles(living_role, dead_role)
                logger.debug(f"Removed player roles from {member.name} (ID: {member.id})")
            # Ensure they have the spectator role
            if spectator_role not in member.roles:
                await member.add_roles(spectator_role)
            user_roles = [role.id for role in member.roles]
            logger.warning(f"User roles for {member.name} (ID: {member.id}): {user_roles}")
        except discord.HTTPException as e:
            logger.error(f"Failed to update non-player roles for {member.name}: {e}")

async def send_role_dm(bot, player_id, role, guild):
    """
    Sends a DM to the player with their role information, with a timeout and fallback channel.
    Returns True on direct DM success, False on failure or fallback.
    """
    try:
        player = await bot.fetch_user(player_id)
        message = f"**Your Role: {role.name}**\n\n**Alignment:** {role.alignment}\n\n**Description:** {role.description}"
        logger.debug(f"Attempting to send role DM to {player.name} ({player_id})")
        # Use asyncio.wait_for to add a timeout
        await asyncio.wait_for(player.send(message), timeout=config.DM_TIMEOUT)
        logger.info(f"Successfully sent role DM to {player.name} ({player_id}).")
        return True
    except (discord.Forbidden, discord.HTTPException):
        logger.error(f"Could not send role DM to player {player_id} due to privacy settings.")
        # Fallthrough to alert moderators
    except asyncio.TimeoutError:
        logger.error(f"Timed out while trying to send role DM to player {player_id}.")
        # Fallthrough to alert moderators
    except Exception as e:
        logger.exception(f"An unexpected error occurred sending role DM to {player_id}: {e}")
        # Fallthrough to alert moderators

    # --- MODERATOR ALERT & FALLBACK ---
    logger.warning(f"Initiating moderator alert and fallback for player {player_id}.")
    mod_channel = bot.get_channel(config.MOD_CHANNEL_ID)
    member = guild.get_member(player_id) # It's okay if member is None
    if mod_channel:
        await mod_channel.send(
            f"⚠️ **DM Failed:** Could not send role information to {member.mention if member else f'user ID `{player_id}`'}. "
            f"Their DMs may be closed. Please contact them or check the private fallback channel."
        )
    return False # Indicate DM failed

async def send_mafia_info_dm(bot, players):
    """Sends DMs to Mafia players with a list of their teammates."""
    logger.info("Sending Mafia team information via DM to all Mafia players.")
    # Filter players to find those with Mafia roles
    mafia_team = [p for p in players.values() if p.role and p.role.alignment == "Mafia"]
    # If no Mafia players, we can skip sending DMs
    if not mafia_team:
        logger.error("No Mafia players found to send team information.")
        return
    for member in mafia_team:
        # Create a list of teammates, excluding the current member
        teammates = [p.display_name for p in mafia_team if p.id != member.id]
        # If there are teammates, format the message to include them
        if teammates:
            message = f"You are on the Mafia team. Your teammates are: **{', '.join(teammates)}**."
        else:
            # If no teammates, just inform them they are alone
            message = "You are the sole member of the Mafia."
        # Use the send_dm method on the Player object
        await member.send_dm(bot, message)
        logger.debug(f"Sent Mafia team DM to {member.display_name} ({member.id}).")

# --- Time & Formatting ---

def format_time_remaining(end_time):
    """Formats the time remaining until a future datetime object."""
    if not isinstance(end_time, datetime) or end_time.tzinfo is None:
        return "Invalid time"
    now = datetime.now(timezone.utc)
    time_left = end_time - now
    if time_left.total_seconds() <= 0:
        return "Time's up!"
    days = time_left.days
    hours, remainder = divmod(time_left.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if days > 0: parts.append(f"{days} day{'s' if days > 1 else ''}")
    if hours > 0: parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
    if minutes > 0: parts.append(f"{minutes} minute{'s' if minutes > 1 else ''}")
    if not parts: # If less than a minute left
        return f"{seconds} second{'s' if seconds != 1 else ''}"
    return " and ".join(parts)

# --- Game Functions ---


