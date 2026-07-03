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
    logger.debug(f"Calculating time remaining for target: {target}, current time: {datetime.now(timezone.utc)}, delta: {delta}")
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

def add_chunked_field(embed, name, text, chunk_size=1000):
        """
        Helper: Splits long text into multiple fields to avoid Discord API errors.
        """
        if not text:
            logger.warning(f"No text provided for embed field '{name}'. Skipping.")
            return
        # Split content into a list of strings
        logger.info(f"Adding chunked field '{name}' to embed. Total length: {len(text)} characters.")
        chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
        for i, chunk in enumerate(chunks):
            # If there's only one chunk, just use the name; otherwise, add (Part X)
            field_name = name if len(chunks) == 1 else f"{name} (Part {i + 1})"
            embed.add_field(name=field_name, value=chunk, inline=False)
            logger.info(f"Added field '{field_name}' with {len(chunk)} characters to embed.")

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
            logger.debug(f"Sent Mafia team info DM to {player.display_name}.")
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