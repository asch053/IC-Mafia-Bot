import discord
import asyncio
import json
import os
import io
from datetime import datetime, timezone, timedelta
import logging
import config
import random

# Get the same logger instance as in mafiabot.py
logger = logging.getLogger('discord')

# --- File I/O Functions ---
def load_data(filepath, error_default=None):
    """Loads data from a JSON or TXT file."""
    filepath = filepath.lower()
    try:
        with open(filepath, "r", encoding='utf-8') as f:
            if filepath.endswith(".json"):
                return json.load(f)
            else:
                return [line.strip() for line in f]
    except FileNotFoundError:
        logger.error(f"File not found: {filepath}. Returning empty default.")
        return error_default if error_default is not None else ({} if filepath.endswith(".json") else [])
    except Exception as e:
        logger.exception(f"An unexpected error occurred loading {filepath}: {e}")
        return error_default if error_default is not None else None

def save_json_data(filepath, data):
    """Saves a dictionary or list to a JSON file."""
    try:
        with open(filepath, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save data to {filepath}: {e}")

# --- Discord Role & Interaction Functions ---

async def update_player_discord_roles(bot, guild, user_input, action: str):
    """
    Updates Discord roles for one or many players.
    
    Args:
        bot: The bot instance.
        guild: The discord.Guild object.
        user_input: Can be a single user_id (int), a Player object, 
                   or a dictionary of {user_id: Player}.
        action: "alive", "dead", or "spectator".
    """
    # 1. Standardize input into a list of IDs
    user_ids = []
    
    if isinstance(user_input, dict):
        # engine.py sent the whole player dictionary!
        user_ids = list(user_input.keys())
    elif hasattr(user_input, 'id'):
        # engine.py sent a single Player object
        user_ids = [user_input.id]
    elif isinstance(user_input, (int, str)):
        # engine.py sent a single ID
        user_ids = [int(user_input)]
    elif isinstance(user_input, list):
        # engine.py sent a list of IDs or Objects
        user_ids = [u.id if hasattr(u, 'id') else int(u) for u in user_input]

    if not user_ids:
        logger.warning(f"update_player_discord_roles called with no valid users for action: {action}")
        return

    # 2. Get the role objects from config
    alive_role = guild.get_role(config.LIVING_ROLE_ID)
    dead_role = guild.get_role(config.DEAD_ROLE_ID)
    spectator_role = guild.get_role(config.SPECTATOR_ROLE_ID)
    managed_roles = [r for r in [alive_role, dead_role, spectator_role] if r is not None]

    # 3. Process each user in the collection
    for uid in user_ids:
        try:
            if uid < 0:
                logger.warning(f"Skipping role update for user ID {uid} because it's a bot.")
                continue
            member = await guild.fetch_member(uid)
            if not member:
                continue
            # Cleanup: Remove existing game roles
            roles_to_remove = [r for r in managed_roles if r in member.roles]
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason="Mafia Bot: Status Cleanup")
            # Add the new role
            role_to_add = None
            if action == "alive": role_to_add = alive_role
            elif action == "dead": role_to_add = dead_role
            elif action == "spectator": role_to_add = spectator_role

            if role_to_add:
                await member.add_roles(role_to_add, reason=f"Mafia Bot: Assigned {action}")
                logger.info(f"Updated role for {member.display_name}: {action}")

        except Exception as e:
            logger.error(f"Failed to update roles for user {uid}: {e}")

def get_role_hierarchy(roles: list, current_user_role: discord.Role) -> bool:
    """Checks if the current user's highest role is higher than all target roles."""
    for role in roles:
        if role and role.position >= current_user_role.position:
            return False
    return True

# --- Messaging & formatting functions ---

def format_time_remaining(target) -> str:
    """Formats the time remaining from now until target (datetime or timedelta)."""
    if isinstance(target, datetime):
        # Ensure UTC comparison
        now = datetime.now(timezone.utc)
        delta = target - now
    else:
        delta = target
    logger.critical(f"Calculating time remaining for target: {target}, current time: {datetime.now(timezone.utc)}, delta: {delta}")
    seconds = int(delta.total_seconds())
    if seconds < 0:
        return "Time is up!"
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h {minutes}m {seconds}s"

async def send_chunked_message(bot, channel, message: str, chunk_size: int = 1900):
    """Sends a long message in chunks."""
    for i in range(0, len(message), chunk_size):
        await channel.send(message[i:i+chunk_size])

async def send_role_dm(bot, player, role, guild):
    """Sends role information via DM."""
    try:
        if player.id < 0:
            logger.warning(f"Skipping DM for player {player.display_name} because it's a bot.")
            return
        user = await bot.fetch_user(player.id)
        await user.send(f"Your role is: **{role.name}**\n{role.description}")
    except Exception as e:
        logger.error(f"Failed to send role DM to {player.display_name}: {e}")

async def send_mafia_info_dm(bot, players):
    """Sends mafia members a list of their teammates."""
    mafia_players = [p for p in players.values() if p.role and p.role.alignment == "Mafia"]
    # If no Mafia players, we can skip sending DMs
    if not mafia_players:
        logger.error("No Mafia players found to send team information.")
        return
    for player in mafia_players:
        if player.role.alignment != "Mafia":
            continue  # Just a safety check, should not happen
        if player.id < 0:
            logger.warning(f"Skipping DM for player {player.display_name} because it's a bot.")
            continue
        try:
            user = await bot.fetch_user(player.id)
            mafia_names = ", ".join([p.display_name for p in mafia_players if p.id != player.id])
            msg = f"Your Mafia teammates are: **{mafia_names}**" if mafia_names else "You are the only Mafia member. Good luck!"
            await user.send(msg)
            logger.info(f"Sent Mafia team info DM to {player.display_name}.")
        except Exception as e:
            logger.error(f"Failed to send mafia DM to {player.display_name}: {e}")
    
    
# -- AI Functions ---
def log_prompt_to_json(phase_key, prompt):
    log_file = "Logs/prompts_archive.json"
    data = {}
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            data = json.load(f)   
    data[phase_key] = {
        "timestamp": str(datetime.now()),
        "prompt": prompt
    }
    with open(log_file, 'w') as f:
        json.dump(data, f, indent=4)

def archive_phase_data(phase_key: str, prompt: str, thoughts: str, result: str):
    """Stores the complete AI transaction for debugging and observability."""
    archive_path = os.path.join("Logs", "prompts_archive.json")
    os.makedirs("Logs", exist_ok=True)
    archive_data = {}
    if os.path.exists(archive_path):
        try:
            with open(archive_path, 'r', encoding='utf-8') as f:
                archive_data = json.load(f)
        except json.JSONDecodeError:
            archive_data = {}
    archive_data[phase_key] = {
        "timestamp": datetime.now().isoformat(),
        "prompt_sent": prompt,
        "ai_reasoning": thoughts if thoughts else "No thoughts recorded.",
        "final_story": result
    }
    with open(archive_path, 'w', encoding='utf-8') as f:
        json.dump(archive_data, f, indent=4)

# --- Stats Functions ---

def filter_games_by_time(games: list, days: int = None) -> list:
    """Filters a list of games, returning only those that ended within the last X days."""
    if not days:
        return games
        
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    filtered_games = []
    
    for game in games:
        end_str = game.get('game_summary', {}).get('end_date_utc')
        if end_str:
            try:
                # Parse the ISO format string stored by your bot
                end_date = datetime.fromisoformat(end_str)
                if end_date > cutoff_date:
                    filtered_games.append(game)
            except ValueError:
                logger.warning(f"Could not parse date string: {end_str}")
                
    return filtered_games