import discord
import os
from discord.ext import commands, tasks
import asyncio
import json
from datetime import datetime, timedelta, timezone
import random
import config  
import logging
import logging.handlers
import logging.config
from logging.handlers import RotatingFileHandler 
import subprocess
import sys

# ----------test branch------------------------------- #

# --- Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=config.BOT_PREFIX, intents=intents)

def setup_logging():
    """Configures logging for the bot."""
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(".", "logs", datetime.now(timezone(timedelta(hours=12))).strftime("%Y-%m-%d")) # Use UTC+12
    os.makedirs(log_dir, exist_ok=True)
    # --- Create formatter ---
    dt_fmt = '%Y-%m-%d %H:%M:%S'
    formatter = logging.Formatter('[{asctime}] [{levelname:<8}] {name} - {funcName}:{lineno}: {message}', dt_fmt, style='{')

    # --- Create handlers ---

    # Debug log handler
    debug_log_file = os.path.join(log_dir, f"{datetime.now(timezone(timedelta(hours=12))).strftime('%Y-%m-%d')}_debug.log")
    debug_handler = RotatingFileHandler( #No longer need to specify the logging module
        debug_log_file,
        encoding='utf-8',
        maxBytes=10 * 1024 * 1024,  # 10 MiB
        backupCount=5,  # Rotate through 5 files
    )
    debug_handler.setFormatter(formatter)
    debug_handler.setLevel(logging.DEBUG)
    # Error log handler
    error_log_file = os.path.join(log_dir, f"{datetime.now(timezone(timedelta(hours=12))).strftime('%Y-%m-%d')}_error.log")
    error_handler = RotatingFileHandler( #No longer need to specify the logging module
        error_log_file,
        encoding='utf-8',
        maxBytes=10 * 1024 * 1024,  # 10 MiB
        backupCount=5,  # Rotate through 5 files
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.INFO) # Only INFO and above
    # Console handler (INFO and above)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO) # Only INFO and above to console
    # --- Get logger and add handlers ---
    logger = logging.getLogger('discord') # Get the discord logger
    logger.setLevel(logging.DEBUG)  # Set the ROOT logger level to DEBUG
    logger.addHandler(debug_handler)       # Everything to the debug log
    logger.addHandler(error_handler)      # Errors to the error log
    logger.addHandler(console_handler)   # Info and above to console
    return logger, debug_handler  # Return the logger and main filehandler

# --- Logging setup ---
logger, handler = setup_logging() # Set up logging at the very top

# Example logging calls
logger.debug("This is a debug message.")
logger.info("This is an info message.")
logger.warning("This is a warning message.")
logger.error("This is an error message.")
logger.critical("This is a critical message.")

# --- Game Variables ---
game_started = False
players = {}  # Dictionary to store player information
time_signup_ends = None
game_roles = []
current_phase = None
phase_number = 0
lynch_votes = {}
game_id = 0
game_data ={}
sk_target = None
mob_target = None
heal_target = None
investigate_target = None
town_block_target = None 
mob_block_target = None
message_send_delay = config.message_send_delay
story_text = None

# --- Load Roles ---
try:
    with open("Data/discord_roles.json", "r") as f:
        discord_role_data = json.load(f)
except FileNotFoundError:
    print("ERROR: discord_roles.json not found!")
    discord_role_data = {}  # Initialize as an empty dictionary to prevent further errors

# --- Load Bot Names ---
try:
    with open("Data/bot_names.txt", "r") as f:
        npc_names = [line.strip() for line in f]
except FileNotFoundError:
    npc_names = []

# --- Load Rules ---
try:
    with open("Data/rules.txt", "r") as f:
        rules_text = f.read()
except FileNotFoundError:
    rules_text = "Rules not found."

# --- Load Mafia Setups ---
try:
    with open("Data/mafia_setups.json", "r") as f:
        mafia_setups = json.load(f)
        print(f"Loading Discord Roles => {discord_role_data}")
except FileNotFoundError:
    print("ERROR: mafia_setups.json not found!")
    mafia_setups = {}

# --- Roles ---
class GameRole:
    def __init__(self, name, alignment, short_description ,description, action=None, uses=None):
        self.name = name
        self.alignment = alignment
        self.short_description = short_description
        self.description = description
        self.action = action
        self.uses = uses
    def __str__(self):
        return self.name
    def to_dict(self):
        """Converts the GameRole object to a dictionary."""
        return {
            "name": self.name,
            "alignment": self.alignment,
            "description": self.description,
            "short_description": self.short_description,
            "action": self.action,
            "uses": self.uses,
        }

# --- load data files ---
def save_json_data(data, filename, subdirectory="game_data"):
    """
    Saves data to a JSON file in the specified subdirectory.
    Creates the subdirectory if it doesn't exist.  Handles both
    initial file creation and appending to existing files.
    Args:
        data: The data to save (must be JSON serializable).
        filename: The name of the file (e.g., "game_1.json", "lynch_data.json").
                  Do *not* include the .json extension here.
        subdirectory: The subdirectory within the "stats" folder.  Defaults to "game_data".
                      Use "game_data/game_ID" for individual game files, and
                      "lynch_data" for lynch data.
    """
    filepath = os.path.join("stats", subdirectory, filename + ".json")
    os.makedirs(os.path.dirname(filepath), exist_ok=True)  # Ensure directory exists
    try:
        with open(filepath, "r") as f:
            try:
                existing_data = json.load(f)
            except json.JSONDecodeError:  # Handle empty or invalid JSON
                existing_data = []  # Initialize as list
    except FileNotFoundError:
        existing_data = []  # Initialize as list if file not found
    # If existing_data is a list, append.  Otherwise, overwrite.
    if isinstance(existing_data, list):
        existing_data.append(data)
        data_to_save = existing_data  # Save the *entire* list
    else:
        # If file existed but wasn't a list, overwrite it.
        # This handles the initial game data, and any case where we
        # don't want to append.
        data_to_save = data
    try:
        with open(filepath, "w") as f:
            json.dump(data_to_save, f, indent=4)
        logger.info(f"DEBUG: Data saved to {filepath}")
    except Exception as e:
        logger.error(f"ERROR: Could not save data to {filepath}. Error: {e}")

def load_data(filepath, error_msg):
    """Loads data from a JSON or TXT file, handling FileNotFoundError."""
    try:
        with open(filepath, "r") as f:
            if filepath.endswith(".json"):
                data = json.load(f)
            else:  # Assume it's a TXT file
                data = [line.strip() for line in f]
        return data
    except FileNotFoundError:
        print(error_msg)
        if filepath.endswith(".json"):
            # Create an empty JSON file if it doesn't exist
            if filepath == "data/game_data.json":
                with open(filepath, "w") as f:
                    json.dump([], f)
                return []
        return {} if filepath.endswith(".json") else []

# --- Data Retention ---
def save_game_data(data, filename, subdirectory="game_data"):
    """
    Saves data to a JSON file in the specified subdirectory.
    Creates the subdirectory if it doesn't exist.  Handles both
    initial file creation and appending to existing files.
    Args:
        data: The data to save (must be JSON serializable).
        filename: The name of the file (e.g., "game_1.json", "lynch_data.json").
                  Do *not* include the .json extension here.
        subdirectory: The subdirectory within the "stats" folder.  Defaults to "game_data".
                      Use "game_data/game_ID" for individual game files, and
                      "lynch_data" for lynch data.
    """
    filepath = os.path.join("stats", subdirectory, filename + ".json")
    os.makedirs(os.path.dirname(filepath), exist_ok=True)  # Ensure directory exists
    try:
        with open(filepath, "r") as f:
            try:
                existing_data = json.load(f)
            except json.JSONDecodeError:  # Handle empty or invalid JSON
                existing_data = []  # Initialize as list
    except FileNotFoundError:
        existing_data = []  # Initialize as list if file not found
    # If existing_data is a list, append.  Otherwise, overwrite.
    if isinstance(existing_data, list):
        existing_data.append(data)
        data_to_save = existing_data  # Save the *entire* list
    else:
        # If file existed but wasn't a list, overwrite it.
        # This handles the initial game data, and any case where we
        # don't want to append.
        data_to_save = data
    try:
        with open(filepath, "w") as f:
            json.dump(data_to_save, f, indent=4)
        logger.info(f"DEBUG: Data saved to {filepath}")
    except Exception as e:
        logger.error(f"ERROR: Could not save data to {filepath}. Error: {e}")

# --- Bot Functions ---
def is_owner_or_mod(bot, discord_role_data):
    """Custom check to allow command usage by owner or users with Mod role."""
    async def predicate(ctx):
        if ctx.author.id == bot.owner_id:  # Check if it's the bot owner
            return True
        # Check for Mod role in a guild context
        if ctx.guild:
            mod_role_id = discord_role_data.get("mod", {}).get("id")
            mod_role = discord.utils.get(ctx.guild.roles, id=mod_role_id)
            if mod_role and mod_role in ctx.author.roles:
                return True
        # Send DM if used in private message and not by owner or mod
        if isinstance(ctx.channel, discord.DMChannel):
            try:
                # Add a timeout to the DM sending
                await asyncio.wait_for(ctx.author.send("This command cannot be used in private messages. "
                                                        "Please use it in the designated server channel."), timeout=5.0)  # 5-second timeout
            except asyncio.TimeoutError:
                logger.error("DEBUG: Timeout while sending DM in is_owner_or_mod.")
                # Handle the timeout (e.g., log it, do nothing, etc.)
                pass  # In this case, we just log and continue.
            except discord.Forbidden:
                logger.error("DEBUG: Bot does not have permission to DM the user.")
                pass # Log this
            except Exception as e:
                logger.error("DEBUG: An unexpected error while sending a DM")

        return False
    return commands.check(predicate)

async def update_player_discord_roles(bot, guild, players, discord_role_data):
    """Updates player roles in Discord based on their status, efficiently."""

    living_role_id = discord_role_data.get("living", {}).get("id")
    dead_role_id = discord_role_data.get("dead", {}).get("id")
    spectator_role_id = discord_role_data.get("spectator", {}).get("id")
    logger.info(f"INFO: Living = {living_role_id}, dead = {dead_role_id}, spectator = {spectator_role_id}")
    living_role = discord.utils.get(guild.roles, id=living_role_id)
    dead_role = discord.utils.get(guild.roles, id=dead_role_id)
    spectator_role = discord.utils.get(guild.roles, id=spectator_role_id)

    if not living_role or not dead_role or not spectator_role:
        logger.error("ERROR: Could not find 'Living Players', 'Dead Players', or 'Spectator' role.")
        return
    # Efficiently update player roles
    for player_id, player_data in players.items():
        if player_id > 0:  # Check if it's not an NPC
            member = guild.get_member(player_id)
            if member:
                try:
                    if player_data["alive"]:
                        if dead_role in member.roles:  # Only remove if present
                            await member.remove_roles(dead_role)
                        if spectator_role in member.roles:
                            await member.remove_roles(spectator_role)
                        if living_role not in member.roles:  # Only add if not present
                            await member.add_roles(living_role)
                    else:
                        if living_role in member.roles:
                            await member.remove_roles(living_role)
                        if spectator_role in member.roles:
                            await member.remove_roles(spectator_role)
                        if dead_role not in member.roles:
                            await member.add_roles(dead_role)
                except discord.errors.HTTPException as e:  # More specific exception handling
                    if e.status == 429:
                        retry_after = e.retry_after
                        logger.warning(f"Rate limited adding/removing roles for {member.name}.  Retrying in {retry_after:.2f} seconds.")
                        await asyncio.sleep(retry_after)  # Wait before retrying
                    elif e.status == 403:
                        logger.error(f"Forbidden: Bot lacks permissions to manage roles for {member.name}.")
                        break # No point in trying for this player
                    else:
                        logger.exception(f"HTTPException updating roles for {member.name}: {e}")
                        break #Don't retry for unexpected HTTP errors
                except discord.Forbidden:
                    logger.error(f"ERROR: Bot lacks permissions to manage roles for {member.name}.")
                    break  # No point in retrying
                except Exception as e:
                    logger.exception(f"Unexpected error updating roles for {member.name}: {e}")
                    break  # Don't retry for unexpected errors
    # Efficiently update spectator roles.
    for member in guild.members:
        if member.id not in players and not member.bot:
            try:
                if spectator_role not in member.roles:
                    await member.add_roles(spectator_role)
                if living_role in member.roles:
                    await member.remove_roles(living_role)
                if dead_role in member.roles:
                    await member.remove_roles(dead_role)
            except discord.errors.HTTPException as e:  # More specific exception handling
                if e.status == 429:
                  retry_after = e.retry_after
                  logger.warning(f"Rate limited adding/removing roles for {member.name}.  Retrying in {retry_after:.2f} seconds.")
                  await asyncio.sleep(retry_after)  # Wait before retrying
                elif e.status == 403:
                    logger.error(f"Forbidden: Bot lacks permissions to manage roles for {member.name}.")
                    break # No point in trying for this player
                else:
                  logger.exception(f"HTTPException updating roles for {member.name}: {e}")
                  break  #Don't retry for unexpected HTTP errors
            except discord.Forbidden:
                logger.error(f"ERROR: Bot lacks permissions to manage roles for {member.name}.")
                break #No point in trying again
            except Exception as e:
                logger.exception(f"Unexpected error updating roles for {member.name}: {e}")
                break # Don't retry for unexpected errors

async def is_player_alive(player_id, players):
    """Checks if a player is alive and returns the player data if so."""
    if player_id in players:
        if players[player_id]["alive"]:
            return players[player_id]  # Return the player's data
        else:
            return "Dead"  # Player is dead
    else:
        return None  # Player not found
    
async def get_player_id_by_name(player_name, players):
    """
    Finds a player's ID based on their name (or nickname).
    Returns the player ID if found, otherwise returns None.
    """
    logger.info("DEBUG: get_player_id_by_name called")
    for player_id, player_data in players.items():
        if player_data["name"].lower() == player_name.lower() or \
           (player_data["display_name"] and player_data["display_name"].lower() == player_name.lower()):
            logger.debug(f"DEBUG: player_id returned = {player_id}")
            return player_id
    return None  # Player not found

def get_specific_player_id(players,specific_role):
    """
    Finds the ID of player based on a given role

    Args:
        players (dict): The dictionary containing player information.

    Returns:
        int or None: The ID of the living Serial Killer player, or None if no such player is found.
    """
    logger.info(f"get_sepcific_player has been called for {specific_role}")
    for player_id, player_data in players.items():
        logger.debug(f"Player Name = {player_data['display_name']} returns role {player_data['role'].name}")
        if (player_data["role"] and player_data["role"].name == specific_role):
            return player_id
    return None

async def send_role_dm(bot, player_id, role, message_send_delay):
    """Sends a DM to the player with their role information, with a timeout."""
    logger.info(f"DEBUG: Player ID = {player_id} Ready to send role")
    print("-------------------------------")
    try:
        player = await bot.fetch_user(player_id)
        logger.debug(f"DEBUG: Player details: {player}... sending role")
        print("-------------------------------")
        await asyncio.sleep(message_send_delay)  # Consider if this delay is *really* needed
        await asyncio.wait_for(player.send(f"You are a **{role.name}**.\n{role.description}"), timeout=5.0)  # Timeout here
    except discord.Forbidden:
        logger.error(f"Could not send role information to {player.name} due to their privacy settings.")
    except asyncio.TimeoutError: # Handle timeout
        logger.error(f"Timeout sending role information to {player.name}.")
    except Exception as e:
        logger.error(f"An error occurred while sending role information to {player.name}: {e}")

async def send_mafia_info_dm(bot, players, message_send_delay):
    """Sends DMs to Mafia players with a list of other Mafia members."""
    logger.info("DEBUG: Calling send_mafia_info_dm")
    for player_id, player_data in players.items():
        if player_data["alive"] and player_data["role"].alignment == "Mafia":
            mafia_members = [
                p_data["display_name"]
                for p_id, p_data in players.items()
                if p_id != player_id and p_data["alive"] and p_data["role"].alignment == "Mafia"
            ]
            if mafia_members:
                mafia_list = ", ".join(mafia_members)
                message = f"The other living Mafia members are: {mafia_list}"
                logger.info("Sent mafia list to all mafia alligned players")
            else:
                message = "You are the only remaining Mafia member."
            if player_id > 0:
                try:
                    player = await bot.fetch_user(player_id)
                    await asyncio.sleep(message_send_delay) # Consider if this delay is really needed.
                    await asyncio.wait_for(player.send(message), timeout=5.0) # Add timeout
                except discord.Forbidden:
                    logger.error(f"Could not send info DM to {player_data['name']} due to their privacy settings.")
                except asyncio.TimeoutError:  # Handle the timeout.
                    logger.error(f"Timeout sending info DM to {player_data['name']}.")
                except Exception as e:
                    logger.error(f"An error occurred while sending info DM to {player_data['name']}: {e}")


async def test_randomness(bot, simulations: int = 10000):
    """
    (Admin/Mod only) Runs the role assignment randomness test script
    using the names of the players currently in the game.
    
    Args:
        simulations: (Optional) The number of iterations to run.
    """
    global players
    rules_channel = bot.get_channel(config.RULES_AND_ROLES_CHANNEL_ID)  # Get the channel to send messages
    if not players:
        await rules_channel.send("Error: There are no players currently in the game to test with.")
        return
    # Use the display names of current players for the test
    player_names = [data["display_name"] for data in players.values()]
    num_players = len(player_names)
    if num_players < 5: # Or whatever your minimum game size is
        await rules_channel.send(f"Error: Need at least 5 players to run a valid test, but there are only {num_players}.")
        return
    if simulations > 50000: # Add a safety limit
        await rules_channel.send("Please choose a number of simulations less than 50,000 to avoid long waits.")
        return
    await rules_channel.send(f"Running randomness test for the **{num_players} current players** over **{simulations} simulations**. This might take a moment...")
    # Construct the command to run the script. Player names go at the end.
    command_to_run = [
        sys.executable,
        'randomnumbertest.py', # The name of your script file
        '--simulations',
        str(simulations)
    ] + player_names # Add the list of names to the command
    try:
        # Run the script as a separate process in a thread to avoid blocking
        process = await asyncio.to_thread(
            subprocess.run,
            command_to_run,
            capture_output=True,
            text=True,
            check=True
        )
        # The output might be too long for a single Discord message, so send as a file
        results_output = process.stdout
        results_filename = "randomness_test_results.txt"
        with open(results_filename, "w", encoding="utf-8") as f:
            f.write(results_output)
        # Send the file to Discord
        await rules_channel.send("Test complete! Here are the results:", file=discord.File(results_filename))
        logger.info(f"Randomness test completed successfully. Results saved to {results_filename}.") 
        # Clean up the file
        os.remove(results_filename)
    except FileNotFoundError:
        await rules_channel.send("Error: `randonnumbertester.py` not found in the bot's directory.")
        logger.error("Could not find randonnumbertester.py to run the test.")
    except subprocess.CalledProcessError as e:
        await rules_channel.send("An error occurred while running the test script. The player count might be invalid for your setups. Check logs for details.")
        logger.error(f"Test script failed with exit code {e.returncode}:\nSTDOUT: {e.stdout}\nSTDERR: {e.stderr}")
    except Exception as e:
        await rules_channel.send("An unexpected error occurred. Please check the logs.")
        logger.exception(f"An unexpected error occurred in testrandom command: {e}")


async def assign_game_roles(bot, players, game_roles, message_send_delay):  # bot needed!
    """Assigns roles to players randomly based on the chosen setup."""
    global roles
    # Shuffle the player IDs and roles
    player_ids = list(players.keys())
    await test_randomness(bot,10000)
    random.shuffle(player_ids)  # Shuffle player IDs
    await asyncio.sleep(message_send_delay)  
    random.shuffle(player_ids)
    await asyncio.sleep(message_send_delay)  
    random.shuffle(game_roles)
    await asyncio.sleep(message_send_delay)  
    random.shuffle(game_roles)  # Shuffle roles to ensure randomness
    # Assign roles to players
    for i, player_id in enumerate(player_ids):
        if i < len(game_roles):
            role = game_roles[i]
            players[player_id]["role"] = role
            players[player_id]["alive"] = True
            players[player_id]["votes"] = 0
            # Send DM with role information *directly*, not as a task
            if player_id > 0:  # Check if it's not an NPC
                await send_role_dm(bot, player_id, role, message_send_delay)  # Await the DM!
        else:
            logger.critical(
                f"WARNING: More players than roles in setup. {players[player_id]['name']} will not be assigned a role."
            )

# --- Role Definitions ---
async def generate_game_roles(num_players):
    """Generates a role setup based on the number of players."""
    logger.debug("DEBUG: generate_game_roles called")
    global game_roles
    game_roles = []
    # Get the appropriate setup from mafia_setups.json
    setups = mafia_setups.get(str(num_players))
    if not setups:
        logger.error(f"ERROR: No setup found for {num_players} players.")
        return
    # Select a random setup (for now, just the first one)
    setup = setups[0]
    # Create Role objects based on the setup
    for role_data in setup["roles"]:
        for _ in range(role_data["quantity"]):
            game_role = GameRole(
                name=role_data["name"],
                alignment=role_data["alignment"],
                short_description=role_data["short_description"],
                description=role_data["description"],
                action=role_data.get("action", ""),
                uses=role_data.get("uses"),
            )
            game_roles.append(game_role)
    logger.info("Game Roles Created")

# --- Helper Functions ---
def get_time_left_string(end_time):
    """
    Calculates the time remaining until the given end_time.

    Args:
        end_time: A datetime object (timezone-aware, UTC) representing the future time.

    Returns:
        A formatted string representing the remaining time, or a status message.
    """
    logger.info(f"format_time_remaining has been called with end time = {end_time}")
    if end_time is None:
        return "Unknown"
    if not isinstance(end_time, datetime):  # Input validation!
        raise TypeError("end_time must be a datetime object")
    if end_time.tzinfo is None:
        raise ValueError("end_time must be a timezone-aware datetime object")
    now = datetime.now(timezone.utc)
    time_left = end_time - now
    if time_left.total_seconds() <= 0:
        logger.info("Time's up!")
        return "Time's up!"
    days = time_left.days
    hours = time_left.seconds // 3600
    minutes = (time_left.seconds % 3600) // 60
    seconds = time_left.seconds % 60
    # Build the output string dynamically
    logger.info(f"Build return based on time left ==> {days}, {hours}, {minutes}, {seconds}")
    parts = []
    if days > 0:
        parts.append(f"{days} day{'s' if days > 1 else ''}")  # Handle plural
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes > 1 else ''}")
    if seconds > 0 and days == 0 and hours == 0: # Only show if less than an hour left
       parts.append(f"{seconds} seconds")
    if len(parts) == 0:
        return "Less than a second"  # Handle very small time differences
    elif len(parts) == 1:
        return parts[0]  # "5 minutes"
    elif len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"  # "2 hours and 30 minutes"
    else:
        # "1 day, 2 hours, and 30 minutes"
        return ", ".join(parts[:-1]) + ", and " + parts[-1]

def generate_status_message(players):
    global current_phase, time_left, phase_number, time_day_ends, time_night_ends, time_signup_ends
    """Generates the game status message."""
    logger.info("DEBUG: generate_status_message called")
    logger.info(f"The current phase is {current_phase} - {phase_number}")
    status_message = "**Current Game Status:**\n"
    # Add phase information with countdown
    if current_phase == "":
        time_left = get_time_left_string(time_signup_ends)
        status_message += f"**Phase:** Signups - ends in {time_left}\n"
        status_message += (
            f"Use `/join [name]` in the <#{config.SIGN_UP_HERE_CHANNEL_ID}> channel to join the game.\n "
        )
        status_message += (
            f"Game will start at: {time_signup_ends.strftime('%Y-%m-%d %H:%M:%S UTC')}.\n"
        )
        logger.info(f"DEBUG: Status message generated during setup with {time_left}")
    else:
        if current_phase == "Day":
            time_left = get_time_left_string(time_day_ends)
        else:
            time_left = get_time_left_string(time_night_ends)
        status_message += (
            f"**Phase:** {current_phase} {phase_number} - ends in {time_left}\n"
        )
    status_message += f"**Players ({len(players)}):**\n"
    for player_id, player_data in players.items():
        player_name = player_data["display_name"]
        player_status = "Alive" if player_data["alive"] else "Dead"
        if player_data["alive"]:
            status_message += f"- {player_name}: Status = {player_status}\n"
        else:
            # Only show role/alignment for dead players
            player_role = (
                player_data["role"].name if player_data.get("role") else "No Role"
            )
            player_alignment = (
                player_data["role"].alignment if player_data.get("role") else "N/A"
            )
            death_info = player_data.get("death_info")
            death_phase = death_info.get("phase") if death_info else "N/A"
            death_how = death_info.get("how") if death_info else "N/A"
            status_message += (
                f"- ~~{player_name}~~: Status = {player_status}, "
                f"Role = {player_role}, Alignment = {player_alignment}, "
                f"Died in Phase: {death_phase}, Cause: {death_how}\n"
            )
    logger.debug(f"DEBUG: Status message generated: {status_message}")
    return status_message

def create_godfather_role(name):
    """Creates a new Godfather role object."""
    return GameRole(
        name= name,
        alignment="Mafia",
        short_description="A member of the Mafia. Can now choose the Mafia's target each night.",
        description="Your mob boss has died so you as a member of the Mafia will now be promoted to Mob Godfather.\nyou now choose the Mafia's target each night. \n Use _/kill player-name_ in this DM during the night phase with the bot to kill your chosen player. \n \nDuring the day you can still use _/vote player-name_ in the voting channel to cast your vote on who should be lynched for that day.\n You win when there are more mob than other factions",
        action="Kill",
    )

async def list_assigned_roles():
    """
    Lists all assigned roles with their counts, sorted alphabetically,
    and returns a formatted string.
    """
    logger.info("list_assigned_roles called to generate role list with counts.")
    global players

    if not players:
        return "No players in the game."
    # Step 1: Tally roles and store a representative object for each role type
    role_counts = {}
    role_details = {} # To store one instance of each role for its details
    for player_data in players.values():
        if player_data.get("role"):  # Safely check if a role is assigned
            role = player_data["role"]
            role_name = role.name
            # Increment count for this role name
            role_counts[role_name] = role_counts.get(role_name, 0) + 1
            # If we haven't seen this role before, store its full details
            if role_name not in role_details:
                role_details[role_name] = role
    if not role_counts:
        logger.error("No Roles have been assigned in list_assigned_roles.")
        return "No roles have been assigned yet."
    # Step 2: Build the formatted message parts from the tallied data
    message_parts = []
    # Sort role names alphabetically for a consistent order
    for role_name in sorted(role_counts.keys()):
        count = role_counts[role_name]
        role_obj = role_details[role_name] # Get the role object to access its alignment/desc
        # Format the line including the count, e.g., "(2x) Town - Plain Townie - ..."
        line = f"- **{role_obj.alignment}** - {role_name} ({count}) - _{role_obj.short_description}_"
        message_parts.append(line)
    # Step 3: Join parts into the final message
    role_list_message = "**\nAssigned Roles in this Game:**\n"
    role_list_message += "\n".join(message_parts)
    logger.debug(f"Generated role list: {role_list_message}")
    return role_list_message

# --- Game Functions ---
def reset_game():
    """Resets the game variables."""
    global game_started, players, game_settings, game_roles, current_phase, phase_number, time_signup_ends, time_day_ends, time_night_ends, lynch_votes, gameprocess
    logger.info("DEBUG: reset_game() called")
    game_started = False
    players = {}
    game_settings = {}
    game_roles = []
    current_phase = ""
    phase_number = 0
    time_signup_ends = None
    time_day_ends = None
    time_night_ends = None
    lynch_votes = {}
    logger.debug(f"DEBUG: gameprocess is running {gameprocess.is_running}")
    if gameprocess.is_running:
        gameprocess.stop
        gameprocess.cancel
 
async def prepare_game_start(ctx, bot, npc_names, phase_hours):
    """Prepares the game to start by adding NPCs and assigning roles."""
    global players, current_phase, game_id, game_data, time_signup_ends, game_roles, message_send_delay
    logger.info("prepare_game_start called")
    game_id = time_signup_ends.strftime("%Y%m%d-%H%M%S")  # Unique ID based on time game starts
    logger.info(f"Game ID generated = {game_id}")
    # Fill in any missing players with NPCs
    while len(players) < config.min_players:  # Minimum number of players
        npc_name = random.choice(npc_names)
        npc_id = -(npc_names.index(npc_name) + 1)
        players[npc_id] = {
            "name": npc_name,
            "display_name": npc_name,
            "role": None,
            "alive": True,
            "votes": 0,
            "action_target": None,
            "previous_target": None,
            "missed_votes": 0,
            "death_info":    {
                    "phase": None,
                    "phase_num": None,
                    "total_phases": None,
                    "how": None
                }
        }
        logger.debug(f"NPC {npc_name} added")
    game_data = {
            "game_id": game_id,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "players": players,  # You'll add player data here later
            "phases": [],  # You can store phase data here
            "winner": None,  # Update this when the game ends
            }
    # Save initial game data
    logger.info(f"DEBUG: Game created with game_id = {game_id}")
    # Save initial game data
    name = f"game_{game_id}"
    subdir = f"{config.game_type}/{game_id}"
    save_json_data(game_data, name, subdir)
    logger.info(f"DEBUG: Stat files created... assigning {len(players)} roles...")
    # Generate and assign roles
    await generate_game_roles(len(players))
    if game_roles:
        await assign_game_roles(bot, players, game_roles, message_send_delay)
        logger.info("DEBUG: Roles assigned")
        role_list_message = await list_assigned_roles()
        ruleschannel = bot.get_channel(config.RULES_AND_ROLES_CHANNEL_ID)
        storychannel = bot.get_channel(config.STORIES_CHANNEL_ID)
        await ruleschannel.send("\n \n -------- **NEW GAME STARTING** -------- \n"
                           f"Each phase will be {phase_hours} hours long. \n\n" 
                           "**Roles have been assigned, starting game!**\n\n")
        await ruleschannel.send("\n\n------ **Role List** ---------\n\n"
                                f"{role_list_message}\n\n"
                                )
        await storychannel.send("\n \n -------- **NEW GAME STARTING** -------- \n \n")
        logger.info("DEBUG: Sending DM to all mafia players")
        await send_mafia_info_dm(bot,players, message_send_delay)
        # await start_game_night(bot, role_data, injokes, no_injoke) #Removed until game logic added
        # Create initial game data
        logger.debug(f"Ready to start, gameprocess.is_running = {gameprocess.is_running}")
        if not gameprocess.is_running:
            current_phase = "Night"
            logger.info(f"Starting game process in {current_phase}")
            await gameprocess.start(ctx,bot,players)
        else:
            logger.error("gameprocess was running... now stopping")
            gameprocess.stop()
            current_phase = "Night"
            logger.error(f"After stopping, starting game process in {current_phase}")
            await gameprocess.start(ctx,bot,players)
    else:
        await ctx.send("Failed to generate roles.")
    logger.info("DEBUG: prepare_game_start finished")  # Add this print statement

async def process_lynch_vote(voter_id, lynch_target):
    global lynch_votes, players
    logger.info("DEBUG: process_lynch_vote called")
    # Check if the voter is alive
    lynch_target_id = await get_player_id_by_name(lynch_target, players)
    target_alive = await is_player_alive(lynch_target_id,players)
    logger.debug(f"DEBUG: Target is {lynch_target} with Lynch Target ID => {lynch_target_id} and status {target_alive}")
    # Check if the voter has already voted
    for target_id, vote_data in lynch_votes.items():
        if voter_id in vote_data["voters"]:
            # Remove the previous vote
            vote_data["voters"].remove(voter_id)
            vote_data["total_votes"] -= 1
            # If there are no more votes for the previous target, remove the entry
            if vote_data["total_votes"] == 0:
                del lynch_votes[target_id]
            break
    # Add target player to the lynch
    # Record the new vote
    players[voter_id]["action_target"] = lynch_target_id
    players[lynch_target_id]["votes"] += 1
    # Add the new vote
    if lynch_target_id not in lynch_votes:
        lynch_votes[lynch_target_id] = {"total_votes": 0, "voters": []}
    lynch_votes[lynch_target_id]["total_votes"] += 1
    lynch_votes[lynch_target_id]["voters"].append(voter_id)
    channel = bot.get_channel(config.VOTING_CHANNEL_ID)
    await channel.send(f"<@{voter_id}> voted for <@{lynch_target}> who now has {lynch_votes[lynch_target_id]["total_votes"]}")
    logger.debug(f"DEBUG: Lynch votes after /vote -> {lynch_votes}")

async def countlynchvotes(bot, players):
    global lynch_votes, current_phase, phase_number, game_id, story_text
    lynched_players = []
    story_parts = []
    max_votes = 0
    total_phases = (phase_number * 2) - (1 if current_phase == "night" else 0)
    if current_phase != "Day":
        logger.error("DEBUG: tally_votes called outside of day phase. Skipping.")
        logger.error(f"DEBUG: Current phase is {current_phase} - {phase_number}")
        return
    else:
        logger.debug(f"DEBUG: Current Lynch list: {lynch_votes}")
        for player_id, vote_data in lynch_votes.items():
            if vote_data["total_votes"] > max_votes:
                max_votes = vote_data["total_votes"]
                lynched_players = [player_id]
            elif vote_data["total_votes"] == max_votes:
                lynched_players.append(player_id)
            logger.info(f"Debug: Lynched Players => {lynched_players}")
         # Announce the voting results
    voting_channel = bot.get_channel(config.VOTING_CHANNEL_ID)
    story_channel = bot.get_channel(config.STORIES_CHANNEL_ID)
    if max_votes == 0:
        story_parts.append("No votes were cast.")
        story_parts.append("Everyone stood around and looked at each other. Shrugging they went back to their houses.\n **No one was lynched**")
    else:
        status_message = "**Voting Results:**\n"
        for player_id, vote_data in lynch_votes.items():
            player_name = players[player_id]["display_name"]
            voters = vote_data["voters"]
            voter_list = ", ".join([players[voter_id]["display_name"] for voter_id in voters])
            status_message += f"- {player_name}: {vote_data['total_votes']} votes ({voter_list})\n"
        await voting_channel.send(status_message)

    # Process lynchings
    if lynched_players:
        for lynched_player_id in lynched_players:
            lynched_player_data = players[lynched_player_id]
            lynched_player_name = lynched_player_data["display_name"]
            lynched_player_role = lynched_player_data["role"].name
            lynched_player_faction = lynched_player_data["role"].alignment
            story_parts.append(f"The town gathered as the sun went down to lynch **{lynched_player_name}, the {lynched_player_role} from {lynched_player_faction}!**")
            # Mark the player as dead
            players[lynched_player_id]["alive"] = False
            logger.debug(f"DEBUG: Marked lynched player {lynched_player_name} as dead")
            # Mark the player as dead and record how
            players[lynched_player_id]["alive"] = False
            players[lynched_player_id]["death_info"] = {
            "phase": f"{current_phase} {phase_number}",
            "phase num": phase_number,
            "total phases": total_phases,
            "how": "Lynched",
            "voters": [voter for voter in lynch_votes[lynched_player_id]['voters']] # correctly create voters
                }
            
            # Announce the player's role
            if lynched_player_id is not None and lynched_player_data["role"]:  # only show role for actual player and they have a role
                lynched_player_role = lynched_player_data["role"].name
                story_parts.append(f"{lynched_player_name}'s role was: {lynched_player_role}")
    else:
        story_parts.append("No one was lynched.")
    lynch_data = {
    "game_id": game_id,
        "phase": current_phase,
        "phase_num": phase_number,
        "lynch votes": lynch_votes  
    }
    subdir = f"{config.game_type}/{game_id}"
    filename = f"{game_id}_Lynch_Data"
    save_json_data(lynch_data,filename,subdir)
    story_text = "\n".join(story_parts)
    logger.debug(story_text)
    return (story_text)

async def send_vote_update(bot,players):
    """
    Creates and sends a message to the voting channel with the current lynch vote status.
    """
    global current_phase, phase_number
    voting_channel = bot.get_channel(config.VOTING_CHANNEL_ID)
    logger.debug(f"DEBUG: Current phase is {current_phase}- {phase_number}")
    logger.info("DEBUG: Send_vote_update called...")
    if current_phase != "Day":
        await voting_channel.send("Vote counting is only available during the day phase.")
        return
    # Tally votes (ensure lynch_votes is updated before calling this function)
    vote_counts = {}
    voters = {}  # Dictionary to track who voted for whom
    for player_id, player_data in players.items():
        target_id = player_data["action_target"]
        logger.debug(f"DEBUG: {player_id} -> target_id: {target_id}")
        if target_id is not None and player_data["alive"]:
            if target_id not in vote_counts:
                vote_counts[target_id] = 0
            vote_counts[target_id] += 1
            # Add voter to the list of voters for the target
            if target_id not in voters:
                voters[target_id] = []
            voters[target_id].append(player_data["display_name"])
    # Prepare the message content
    message_content = "**Current Lynch Vote:**\n"
    logger.debug(f"DEBUG: Current message content == {message_content}")
    logger.debug(f"DEBUG: vote counts: {vote_counts}")
    if not vote_counts:
        message_content += "No votes yet.\n"
        logger.error(f"DEBUG: Current message content == {message_content}")
    else:
        logger.debug(f"DEBUG: {vote_counts}")
        for player_id, vote_count in vote_counts.items():
            if player_id is None or player_id == "":
                logger.error("No id")
            else:
                player_data = players[player_id]
                player_name = player_data["display_name"]
                voter_list = ", ".join(voters[player_id])
                message_content += f"- {player_name}: {vote_count} vote(s) - {voter_list}\n"
    # Find players who haven't voted
    not_voted = [
        player_data["display_name"]
        for player_id, player_data in players.items()
        if player_data["alive"] and player_data["action_target"] is None
    ]
    if not_voted:
        message_content += "\n**Players who haven't voted yet:**\n"
        message_content += ", ".join(not_voted) + "\n"
    else:
        message_content += "\nAll players have voted.\n"
    await voting_channel.send(message_content) 

def check_win_conditions():
    """
    Checks if any team has won the game.

    Returns:
        str: The name of the winning team ("Mafia", "Town", "Neutral") or None if no team has won yet.
    """
    global players, current_phase, phase_number
    living_mafia = 0
    living_town = 0
    living_neutral = 0
    for player_id, player_data in players.items():
        if player_data["alive"]:
            if player_data["role"].alignment == "Mafia":
                living_mafia += 1
            elif player_data["role"].alignment == "Town":
                living_town += 1
            elif player_data["role"].alignment == "Neutral":
                living_neutral += 1
    
    if living_mafia == 0 and living_neutral == 0 and living_town == 0:
        logger.info("The game was a draw after everyone died")
        return "Draw"       # if everyone is dead, then the game ended in a draw  
    
    elif living_neutral == 1 and living_mafia == 0 and living_town == 0:
        logger.info("The game was Won by the SK after Killing everyone")
        return "Serial Killer"    # Neutral wins if they are the only one alive
    
    elif living_mafia > living_town and living_neutral == 0:
        for player_id, player_data in players.items():
            if player_data["role"].alignment == "Town" and player_data["alive"] == True:
                total_phases = ((phase_number * 2) - (1 if current_phase == "Night" else 0) - 1)
                players[player_id]["alive"] = False
                players[player_id]["death_info"] = {
                    "phase": f"{current_phase} {phase_number}",
                    "phase num": phase_number,
                    "total phases": total_phases,
                    "how": "Killed by Mob",
                    }
        logger.info("The game was won by the Mafia after the SK died and Mafia outnumbered Town")
        return "Mafia"      # Mafia wins if they equal or outnumber Town and SK is dead
    
    elif living_mafia == 0 and living_neutral == 0 and living_town > 0:
        logger.info("The game was Won by the Town as they were the only people left")
        return "Town"       # Town wins if no Mafia or Neutral players are alive
    
    elif current_phase == "Night" and living_mafia == 1 and living_town == 1 and living_neutral == 0:
        for player_id, player_data in players.items():
            if player_data["alive"] == True:
                total_phases = ((phase_number * 2) - (1 if current_phase == "Night" else 0) - 1)
                players[player_id]["alive"] = False
                players[player_id]["death_info"] = {
                    "phase": f"{current_phase} {phase_number}",
                    "phase num": phase_number,
                    "total phases": total_phases,
                    "how": "Lynched",
                    } 
        logger.info("The game was a draw as only 2 people left at start of day from mafia and town")
        return "Draw"
    
    elif current_phase == "Night" and living_mafia == 1 and living_neutral == 1 and living_town == 0:
        for player_id, player_data in players.items():
            if player_data["alive"] == True:
                total_phases = ((phase_number * 2) - (1 if current_phase == "Night" else 0) - 1)
                players[player_id]["alive"] = False
                players[player_id]["death_info"] = {
                    "phase": f"{current_phase} {phase_number}",
                    "phase num": phase_number,
                    "total phases": total_phases,
                    "how": "Lynched",
                    } 
        logger.info("The game was a draw as only 2 people left at start of day from SK and town")
        return "Draw"
    
    elif current_phase == "Day" and living_neutral == 1 and living_town == 1 and living_mafia == 0:
        for player_id, player_data in players.items():
            if player_data["alive"] == True and player_data["role"].alignment == "Town":
                total_phases = ((phase_number * 2) - (1 if current_phase == "Night" else 0) - 1)
                players[player_id]["alive"] = False
                players[player_id]["death_info"] = {
                    "phase": f"{current_phase} {phase_number}",
                    "phase num": phase_number,
                    "total phases": total_phases,
                    "how": "Killed by SK",
                    }
        logger.info("The game was won by SK as only SK and 1 town alive at start of night - SK will kill last town overnight")
        return "Serial Killer"    # Neutral wins if they are the only one alive
    
    elif current_phase == "Day" and living_mafia == 1 and living_neutral == 1 and living_mafia == 0:
        for player_id, player_data in players.items():
            if player_data["alive"] == True:
                total_phases = ((phase_number * 2) - (1 if current_phase == "Night" else 0) - 1)
                players[player_id]["alive"] = False
                players[player_id]["death_info"] = {
                    "phase": f"{current_phase} {phase_number}",
                    "phase num": phase_number,
                    "total phases": total_phases,
                    "how": "Lynched",
                    } 
        logger.info("The game was a draw as only 2 people left at start of day from mafia and SK")
        return "Draw"
    
    elif current_phase == "Day" and living_mafia == 1 and living_town == 1 and living_neutral == 0:
        for player_id, player_data in players.items():
            if player_data["alive"] == True and player_data["role"].alignment == "Town":
                total_phases = ((phase_number * 2) - (1 if current_phase == "Night" else 0) - 1)
                players[player_id]["alive"] = False
                players[player_id]["death_info"] = {
                    "phase": f"{current_phase} {phase_number}",
                    "phase num": phase_number,
                    "total phases": total_phases,
                    "how": "Killed by Mafia",
                    } 
        logger.info("The game was won by Mob as only mob and 1 town alive at start of night - Mob will kill last town overnight")
        return "Mafia"
    
    elif current_phase == "Day" and living_mafia == 1 and living_neutral == 1 and living_town ==0:
        for player_id, player_data in players.items():
            if player_data["alive"] == True and player_data["role"].alignment == "Mafia":
                total_phases = ((phase_number * 2) - (1 if current_phase == "Night" else 0) - 1)
                players[player_id]["alive"] = False
                players[player_id]["death_info"] = {
                    "phase": f"{current_phase} {phase_number}",
                    "phase num": phase_number,
                    "total phases": total_phases,
                    "how": "Killed by SK",
                    } 
        logger.info("SK wins if they and 1 mob left at start of night as they kill first")
        return "Serial Killer" #SK wins if they and 1 mob left at start of night as they kill first
    else:
        logger.info("No winner found")
        return None  # No winner yet 
 
async def announce_winner(bot, winner):
    """Announces the winner and resets the game."""
    global game_started, phase_number, current_phase, discord_role_data, players,game_id, time_signup_ends, gameprocess
    # Send announcement to the stories channel
    #await generate_narration(bot, f"Game Over! The **{winner}** team wins!")
    logger.info(f"Winning team = {winner}")
    channel = bot.get_channel(config.STORIES_CHANNEL_ID)
    if winner != "Draw":
        winning_players = []
        for player_id, player_data in players.items():
            if player_data["role"].alignment == winner:
                winning_players.append(f"<@{player_id}>")
                logger.debug(f"DEBUG: {player_data['display_name']} is a winner")
        if winning_players:
            winners = ", ".join(winning_players)
            logger.debug(f"DEBUG: Winners = {winners}")
            await channel.send(f"GAME ENDED - Congratulations to {winner} - {winners}!")
    else:
        await channel.send(f"GAME ENDED - Game was a draw!")
    # Update roles to remove all players from Living/Dead Players
    guild = bot.get_guild(config.SERVER_ID)
    living_role = discord.utils.get(guild.roles, id=discord_role_data.get("living", {}).get("id"))
    dead_role = discord.utils.get(guild.roles, id=discord_role_data.get("dead", {}).get("id"))
    spectator_role = discord.utils.get(guild.roles, id=discord_role_data.get("spectator", {}).get("id"))
    for member in guild.members:
        await member.remove_roles(living_role, dead_role)
        if not member.bot:
            await member.add_roles(spectator_role)  # Add Spectator to non-bots
    # Save game data before resetting
    if current_phase != "signup":
        game_data = {
            "game_id": game_id,
            "total_phases": (phase_number * 2) - (1 if current_phase == "night" else 0),
            "winner": winner,
            "players": [
                {
                    "player_id": player_id,
                    "name": player_data["display_name"],
                    "role": player_data["role"].name if player_data["role"] else "None",
                    "alignment": player_data["role"].alignment if player_data["role"] else "N/A",
                    "status": "Alive" if player_data["alive"] else "Dead",
                    "won": winner == "Town" if player_data["role"].alignment == "Town"
                            else winner == "Mafia" if player_data["role"].alignment == "Mafia"
                            else winner == "Neutral" if player_data["role"].alignment == "Neutral"
                            else "Draw",
                    "death_phase": player_data.get("death_info", {}).get("phase"),
                    "death_cause": player_data.get("death_info", {}).get("how"),
                    "phases_lasted": player_data.get("death_info", (phase_number * 2) - (1 if current_phase == "night" else 0)),
                    #"votes": game_votes.get(player_id, {}).get("votes", []),
                }
                for player_id, player_data in players.items()
            ],
        }
        if game_data:
            logger.debug(f"DEBUG: {game_data}")
            filename = f"{game_id}_Game_Data"
            subdir = f"{config.game_type}/{game_id}"
            save_json_data(game_data,filename,subdir)  # Save to JSON file

    # --- Construct the final game_data ---
    game_data["winner"] = winner
    game_data["end_time"] = datetime.now(timezone.utc).isoformat()  # Add end time
    game_data["total_phases"] = (phase_number * 2) - (1 if current_phase == "night" else 0)

     # Build the player list, converting GameRole objects to dictionaries
    game_data["players"] = [
         {
             "player_id": player_id,
             "name": player_data["name"],
             "display_name": player_data["display_name"],
             "role": player_data["role"].to_dict() if player_data["role"] else None,  # to_dict()!
             "alignment": player_data["role"].alignment if player_data.get("role") else "N/A", #Safely get alignment
             "alive": player_data["alive"],
             "death_phase": player_data.get("death_info", {}).get("phase"),
             "death_cause": player_data.get("death_info", {}).get("how"),
             "phases_lasted": player_data.get("death_info", {}).get("total phases", phase_number), #handle if dead or not
             "votes": [],  # Store vote history here later
         }
         for player_id, player_data in players.items()
     ]
    if game_data:
        save_json_data(game_data, f"game_{game_data['game_id']}", f"{config.game_type}/{game_id}") 
        logger.debug(f"Saved game data to file: {game_data}")  
    # Reset game variables
    game_started = False  # Allow new games to be started
    gameprocess.stop()

async def process_role_block(bot):
    """
    Resolves role blocker actions for the night. It first determines all outcomes
    (mutual blocks, single blocks) and then applies them to avoid logic errors.
    """
    global players, story_text, town_block_target, mob_block_target
    logger.info("process_role_block called")
    story_parts = []
    # Get player ID for town and mob Role Blockers 
    town_rb_id = get_specific_player_id(players, "Town Role Blocker")
    mob_rb_id = get_specific_player_id(players, "Mob Role Blocker")
    # --- Step 1: Read all initial targets BEFORE making any changes ---
    town_target = None
    if town_rb_id and players[town_rb_id]["alive"]:
        town_target = players[town_rb_id]["action_target"]
        logger.info("Town Roleblock target found")
    mob_target = None
    if mob_rb_id and players[mob_rb_id]["alive"]:
        mob_target = players[mob_rb_id]["action_target"]
        logger.info("Mob Roleblock target found")
    # --- Step 2: Determine the outcomes based on initial targets ---
    # These variables track if a blocker's action was successful
    town_block_succeeds = town_target is not None
    mob_block_succeeds = mob_target is not None
    # Check for mutual blocks, which nullify the actions
    if town_target == mob_rb_id and mob_target == town_rb_id:
        logger.info("Mutual block between Town RB and Mob RB. Both actions are nullified.")
        story_parts.append("Two shadowy figures spent the entire night chasing each other in circles, accomplishing nothing.")
        town_block_succeeds = False
        mob_block_succeeds = False
    elif town_target == mob_rb_id:
        logger.info("Town RB blocked Mob RB.")
        story_parts.append("One of the mob went out to see if they could cause some trouble.\nHowever, as they drove across town, they could see a set of headlights in their mirrors.\nThey decided to head back home, unable to fulfill their mission.")
        mob_block_succeeds = False
    elif mob_target == town_rb_id:
        logger.info("Mob RB blocked Town RB.")
        story_parts.append("One of the townsfolk went out to see if they could help their besieged town.\nHowever, as they drove across town, they could see a set of headlights in their mirrors.\nThey decided to head back home, unable to fulfill their mission.")
        town_block_succeeds = False
    # --- Step 3: Apply the final, determined outcomes ---
    # Apply Town RB's block if it was successful
    if town_block_succeeds:
        # Safety check to ensure the target is a valid player ID
        if isinstance(town_target, int) and town_target in players:
            players[town_target]["action_target"] = None # Nullify the target's action
            town_block_target = town_target # Set global for other actions to check
            logger.debug(f"Town RB successfully blocked {players[town_target]['display_name']} (ID: {town_target})")
        else:
            logger.warning(f"Town RB had an invalid target: {town_target}")
    # Apply Mob RB's block if it was successful
    if mob_block_succeeds:
        # Safety check to ensure the target is a valid player ID
        if isinstance(mob_target, int) and mob_target in players:
            players[mob_target]["action_target"] = None # Nullify the target's action
            mob_block_target = mob_target # Set global for other actions to check
            logger.debug(f"Mob RB successfully blocked {players[mob_target]['display_name']} (ID: {mob_target})")
        else:
            logger.warning(f"Mob RB had an invalid target: {mob_target}")
    story_text = "\n".join(story_parts)
    logger.info("process_role_block completed")
    return story_text

async def process_sk_night_kill(bot):
    global current_phase, phase_number, players, town_block_target, mob_block_target, story_text
    story_parts = []
    total_phases = (phase_number * 2) - (1 if current_phase == "night" else 0)
    sk_player_id = get_specific_player_id(players, "Serial Killer")
    if sk_player_id is None:
        logger.error("DEBUG: No living Serial Killer found. Skipping SK night kill process.")
        return
    if sk_player_id == town_block_target:
        logger.info("SK was blocked by town RB")
        story_parts.append("The SK went out looking for someone to kill, but there was a shadowy figure following them.\n The SK decided it was to risky to kill tonight and went home.")
        story_text = "\n".join(story_parts)
        logger.debug(f"DEBUG: {story_text}")
        return story_text
    if sk_player_id == mob_block_target:
        logger.info("SK was blocked by mob RB")
        story_parts.append("The SK went out looking for someone to kill, but there was a shadowy figure following them.\n The SK decided it was to risky to kill tonight and went home.")
        story_text = "\n".join(story_parts)
        logger.debug(f"DEBUG: {story_text}")
        return story_text
    target_id = players[sk_player_id]["action_target"]
    # Check if a Serial Killer was found before proceeding
    if sk_player_id > 0:
        sk_player = await bot.fetch_user(sk_player_id)
        try:
            if players[sk_player_id]["alive"] == False:
                logger.error("DEBUG: SK Player is Dead")
                story_parts.append("")
                story_text = "\n".join(story_parts)
                logger.debug(f"DEBUG: {story_text}")
                return story_text
            if target_id is None:
                logger.error("DEBUG: No target selected for SK. Skipping kill process.")
                await sk_player.send("You did not select a target for the night kill.")
                story_parts.append("The Serial Killer found some childrens paint and started to lick it.... they never left their house all night")
                story_text = "\n".join(story_parts)
                logger.debug(f"DEBUG: {story_text}")
                return(story_text)
            if target_id not in players:
                logger.error(f"DEBUG: Invalid target ID {target_id} for SK. Skipping kill process.")
                await sk_player.send(f"Invalid target for the night kill. Target player is not in the game.")
                story_parts.append("The Serial Killer found some childrens paint and started to lick it.... they never left their house all night")
                story_text = "\n".join(story_parts)
                logger.debug(f"DEBUG: {story_text}")
                return story_text
            if not players[target_id]["alive"]:
                logger.error("DEBUG: Target player for SK is already dead. Skipping kill process.")
                await sk_player.send("Target player for the night kill is already dead.")
                story_parts.append("The Serial Killer found some childrens paint and started to lick it.... they never left their house all night")
                story_text = "\n".join(story_parts)
                logger.debug(f"DEBUG: {story_text}")
                return story_text
            # Target is valid, proceed with the kill process
            logger.debug(f"DEBUG: SK killed {target_id}")
            # If target is not the godfather then mark the player as dead and record how
            if players[target_id]["role"].name != "Godfather" and players[target_id]["role"].name != "Serial Killer":
                logger.critical("DEBUG: SK Kill process correct")
                players[target_id]["alive"] = False
                players[target_id]["death_info"] = {
                    "phase": f"{current_phase} {phase_number}",
                    "phase_num": phase_number,
                    "total_phases": total_phases,
                    "how": "Killed by SK"
                }
                # Announce the player's death
                target_name = players[target_id]["display_name"]
                target_role = players[target_id]["role"].name
                target_faction = players[target_id]["role"].alignment
                story_parts.append(f"The deranged person that was the serial killer went out into the town at night.\nThey saw {target_name} walking alone and couldn't resist...\n")
                story_parts.append(f"**{target_name} was killed by the SK!**\n\n")
                logger.critical(story_parts)
                logger.debug(f"DEBUG: SK action_target = {players[sk_player_id]["action_target"]}")
            else:
                if players[target_id]["role"].name == "Godfather" or players[target_id]["role"].name == "Serial Killer":
                    story_parts.append(f"The crazy serial killer went after the {players[target_id]["role"].name} but their nemsis was too hard to kill")
            #clear SK player action target
            players[sk_player_id]["action_target"] = None
            logger.debug(f"DEBUG: SK action_target = {players[sk_player_id]["action_target"]}")
            logger.debug(f"{story_parts}")
        except discord.Forbidden:
            logger.error(f"Could not send DM to Serial Killer due to their privacy settings.")
        except Exception as e:
            logger.error(f"An error occurred while sending DM to Serial Killer: {e}")
    else:
        logger.error("DEBUG: No living Serial Killer found.")
    logger.debug("--- WE ARE HERE!! ---")
    if sk_player_id < 0:
        story_parts.append("The Serial Killer found some childrens paint and started to lick it.... they never left their house all night")
    story_text = "\n".join(story_parts)
    logger.debug(f"DEBUG: {story_text}")
    return(story_text)

async def process_mafia_night_kill(bot):
    global current_phase, phase_number, players, town_block_target, mob_block_target, story_text

    story_parts = []
    total_phases = (phase_number * 2) - (1 if current_phase == "night" else 0)
    mob_gf_id = get_specific_player_id(players,"Godfather")
    if mob_gf_id:
        mob_gf_alive = players[mob_gf_id]["alive"]
    if mob_gf_id is None or mob_gf_alive == False :
        mob_goon_id = get_specific_player_id(players,"Mob Goon")
        name = "Mob Goon"
        logger.error("DEBUG: No living Godfather found.")
        logger.info(f"DEBUG: Promoting Mob to Godfather")
        if mob_goon_id is None or players[mob_goon_id]["alive"] == False:
            mob_goon_id = get_specific_player_id(players,"Mob Role Blocker")
            name = "Mob Role Blocker"
            if mob_goon_id is None or players[mob_goon_id]["alive"] == False:
                logger.error("Debug: All mob are dead")
                return ()
        if mob_goon_id > 0 and players[mob_goon_id]["alive"] == True and players[mob_goon_id]["role"].action != "Kill":
            mob_goon_player = await bot.fetch_user(mob_goon_id)
            logger.info("Promoted Mob Good to Mob Godfather")
            try:
                await mob_goon_player.send(f"Your Godfather has been killed, you are the Godfather Now\n\n {players[mob_goon_id]["role"].description}\nAny previous ight actions you may have had no longer work.\nYou are now the Godfather and can choose a target to kill.\nPlease use the /kill command to select a target.\n")
            except discord.Forbidden:
                logger.error(f"Could not send DM to promoted Godfather.  User has DMs disabled.")
            except discord.HTTPException as e:
                logger.error(f"HTTP Error sending DM to promoted Godfather: {e}")
            except Exception as e:
                logger.exception(f"Unexpected error promoting Godfather: {e}")

        players[mob_goon_id]["role"] = create_godfather_role(name)
        mob_gf_id = mob_goon_id
        logger.debug(f"DEBUG: Mob Goon or RB now has GF powers, and mob_gf_id is equal to mob_good_id or mob_rb_id")
    target_id = players[mob_gf_id]["action_target"]
    if mob_gf_id == town_block_target:
        logger.info("Godfather was blocked by town RB")
        story_parts.append("The Mafia talked and decided on a target. They sent out their killer to do the job for them, but there was a shadowy figure following them.\n The mob hired killer decided it was to risky to kill tonight and went home.\n")
        story_text = "\n".join(story_parts)
        return (story_text)
    if mob_gf_id == mob_block_target:
        logger.info("Godfather was blocked by mob RB")
        story_parts.append("The Mafia talked and decided on a target. They sent out their killer to do the job for them, but there was a shadowy figure following them.\n The mob hired killer decided it was to risky to kill tonight and went home.\n")
        story_text = "\n".join(story_parts)
        return (story_text)

    # Check if a Godfather was found before proceeding
    if mob_gf_id > 0:
        if bot:
            mob_gf_player = await bot.fetch_user(mob_gf_id)
            try:
                if target_id is None:
                    logger.error("DEBUG: No target selected for Mob. Skipping kill process.")
                    await mob_gf_player.send("You did not select a target for the night kill.")
                    story_parts.append("The Godfather stayed in and thought about who they should kill... but they thought for so long the sun came up and they had not left the house")
                    story_text = "\n".join(story_parts)
                    logger.debug(f"DEBUG: {story_text}")
                    return(story_text)
                if target_id not in players:
                    logger.error(f"DEBUG: Invalid target ID {target_id} for Mob kill. Skipping kill process.")
                    story_parts.append("The Godfather stayed in and thought about who they should kill... but they thought for so long the sun came up and they had not left the house")
                    await mob_gf_player.send(f"Invalid target for the night kill. Target player is not in the game.")
                    story_text = "\n".join(story_parts)
                    logger.debug(f"DEBUG: {story_text}")
                    return(story_text)
                if not players[target_id]["alive"]:
                    logger.error("DEBUG: Target player for Mob is already dead. Skipping kill process.")
                    await mob_gf_player.send("Target player for the night kill is already dead.")
                    story_parts.append("The Godfather decided on who to kill, but the target was already dead.\n They thought about who they should kill next time.\n")
                    story_text = "\n".join(story_parts)
                    logger.debug(story_text)
                    return (story_text)
            except discord.Forbidden:
                logger.error(f"Could not send DM to mob GF due to their privacy settings.")
            except Exception as e:
                logger.error(f"An error occurred while sending DM to mob GF: {e}")
    else:
        logger.error("DEBUG: No living Godfather found.")
    if target_id is None or target_id == "":  
        logger.error("DEBUG: No target")
        story_parts.append("The Godfather stayed in and thought about who they should kill... but they thought for so long the sun came up and they had not left the house")
    else:    # only show role for non-npc
            logger.debug(f"DEBUG: Mob killed {target_id}")
            # Mark the player as dead and record how
            if players[target_id]["role"].name != "Godfather" and players[target_id]["role"].name != "Serial Killer" :
                players[target_id]["alive"] = False
                players[target_id]["death_info"] = {
                        "phase": f"{current_phase} {phase_number}",
                        "phase_num": phase_number,
                        "total_phases": total_phases,
                        "how": "Killed by Mob"
                    }    
                # Announce the player's role
                target_name = players[target_id]["display_name"]
                story_parts.append(f"The mob godfather was looking over the town at night. They saw {target_name} nearby and decided to feed them to the fishes\n")
                story_parts.append(f"**{target_name} was killed by the Mob!**\n\n")
            else:
                if players[target_id]["role"].name == "Godfather" or players[target_id]["role"].name == "Serial Killer":
                    story_parts.append(f"The Godfather went after the {players[target_id]["role"].name} but their nemsis was too hard to kill")
    players[mob_gf_id]["action_target"] = None
    logger.debug(f"DEBUG: Mob GF action_target = {players[mob_gf_id]["action_target"]}")
    story_text = "\n".join(story_parts)
    logger.debug(story_text)
    return (story_text)

async def process_doc_night_heal(bot): #pass in bot and target_id variables
    """Processes the Doctor's night heal action."""
    # Declare global variables so can determine current phase (day/night), phase number (to determine ifa dead player should be healed) and the players dictonary 
    global current_phase, phase_number, players, heal_target, town_block_target, mob_block_target, story_text

    story_parts = []
    if current_phase != "Night":
        logger.warning("process_doc_night_heal called outside Night phase")
        return (story_text)
    town_rb_id = get_specific_player_id(players, "Town Role Blocker")
    mob_rb_id = get_specific_player_id(players, "Mob Role Blocker")
    town_doc_id = get_specific_player_id(players, "Town Doctor")
    if town_doc_id is None: 
        logger.debug("No Town Doc found. Skipping investigation.")
        return
    if players[town_doc_id]["alive"] == False and players[town_doc_id]["action_target"] == None:
        logger.debug("Town doc is dead already")
        return
    if town_rb_id and town_rb_id > 0:
        town_block_target = players[town_rb_id]["action_target"]
    if mob_rb_id and mob_rb_id > 0:
        mob_block_target = players[mob_rb_id]["action_target"]
    if town_doc_id > 0:
        heal_target = players[town_doc_id]["action_target"]
    if town_doc_id is not None:
        town_doc_alive = players[town_doc_id]["alive"]
        logger.debug(f"Town doc status = {town_doc_alive}")
    else:
        logger.debug("No town doc")
    if heal_target is None:
        story_parts.append("The town doctor was at home watching some TV. They thought about going out and trying to help their fellow towns people, but wanted to watch one more episode. Before they knew it the sun was rising and they had missed their change to help.\n")
        logger.debug("Town doctor did not enter a heal target")
        story_text = "\n".join(story_parts)
        logger.debug(story_text)
        return (story_text)  
    elif town_doc_id == town_block_target or town_doc_id == mob_block_target:
        story_parts.append("Once the sun went down, the town doctor headed out into the cold night with a determination to help. However, where ever they went there was always a shadowy figure somewhere behind them. They spent all night avoiding this mysterious figure that they did not find anyone to help.\n")
        logger.debug("Town doctor was blocked")
        story_text = "\n".join(story_parts)
        logger.debug(story_text)
        return (story_text)  
    elif players[heal_target]["alive"] == False:
        logger.debug(f"DEBUG: Town Doctor heals {heal_target}") #log who the doctor is healing
        # If target was previously dead, revive them
        players[heal_target]["alive"] = True
        players[heal_target]["death_info"] = {
            "phase": None,
            "phase_num": None,
            "total_phases": None,
            "how": None
            }    
        if town_doc_id == heal_target:
            logger.debug("Doctor saved themselves")
            story_parts.append(f"As the doctor waled through town they found {players[heal_target]["display_name"]} bloodied and dying. The town doctor pulled out their emergency first aid kit and set about saving {players[heal_target]["display_name"]} from certain death")
            story_parts.append(f"**{players[heal_target]["display_name"]} was healed by the Town Doctor!**\n\n")
        else:
            logger.debug(f"Doctor saved {heal_target}")
            story_parts.append(f"As the doctor waled through town they found {players[heal_target]["display_name"]} bloodied and dying. The town doctor pulled out their emergency first aid kit and set about saving {players[heal_target]["display_name"]} from certain death")
            story_parts.append(f"**{players[heal_target]["display_name"]} was healed by the Town Doctor!**\n\n")
        story_text = "\n".join(story_parts)
        logger.debug(story_text)
        return (story_text)  
                       
async def process_cop_night_investigate(bot):
    """Processes the Cop's night investigation action."""
    global current_phase, phase_number, players, town_block_target, mob_block_target, story_text

    if current_phase != "Night":
        logger.warning("Cop investigation attempted outside of night phase.")
        return
    town_cop_id = get_specific_player_id(players, "Town Cop")
    town_rb_id = get_specific_player_id(players, "Town Role Blocker")
    mob_rb_id = get_specific_player_id(players, "Mob Role Blocker")
    if town_cop_id is None or players[town_cop_id]["alive"] == False:
        logger.debug("No Town Cop found. Skipping investigation.")
        return story_text
    if town_rb_id is None:
        logger.debug("No Town RB found. Skipping Blocks.")
    if mob_rb_id is None:
        logger.debug("No Mob RB found. Skipping Blocks.")
    if town_rb_id and town_rb_id > 0:
        town_block_target = players[town_rb_id]["action_target"]
    if mob_rb_id and mob_rb_id > 0:
        mob_block_target = players[mob_rb_id]["action_target"]
    story_parts = []
    if town_cop_id == town_block_target:
        story_parts.append("Once the sun went down, the town cop headed out into the cold night with a determination to find out what was happening. However, where ever they went there was always a shadowy figure somewhere behind them. They spent all night avoiding this mysterious figure.\n")
        logger.debug("Town RB blocks town cop")
        story_text = "\n".join(story_parts)
        logger.debug(story_text)
        return (story_text)  
    if town_cop_id == mob_block_target:
        story_parts.append("Once the sun went down, the town cop headed out into the cold night with a determination to find out what was happening. However, where ever they went there was always a shadowy figure somewhere behind them. They spent all night avoiding this mysterious figure.\n")
        logger.debug("Mob RB blocks town cop")
        story_text = "\n".join(story_parts)
        logger.debug(story_text)
        return (story_text)  
    target_id = players[town_cop_id]["action_target"]
    if town_cop_id > 0: #do not send messages to NPC bots
        town_cop_player = await bot.fetch_user(town_cop_id)
        if target_id not in players:
            logger.debug(f"Invalid target ID {target_id} for Cop investigation. Skipping.")
            try:
                await town_cop_player.send(f"Invalid target. That player is not in the game.")
            except discord.Forbidden:
                logger.error(f"Could not send DM to Town Cop due to their privacy settings.")
            except Exception as e:
                logger.error(f"An error occurred while sending DM to Town Cop: {e}")
            return
        if not players[target_id]["alive"]:
            logger.debug("Target player for Cop investigation is already dead. Skipping.")
            try:
                await town_cop_player.send("You cannot investigate dead players.")
            except discord.Forbidden:
                logger.error(f"Could not send DM to Town Cop due to their privacy settings.")
            except Exception as e:
                logger.error(f"An error occurred while sending DM to Town Cop: {e}")
            return
        if target_id is None:
            logger.debug("No target selected for Cop investigation. Skipping.")
            try:
                await town_cop_player.send("You did not select a target for the investigation.")
            except discord.Forbidden:
                logger.error(f"Could not send DM to Town Cop due to their privacy settings.")
            except Exception as e:
                logger.error(f"An error occurred while sending DM to Town Cop: {e}")
            return
        # Target is valid, proceed with investigation.
        target_name = players[target_id]["display_name"]  # Use display_name
        target_role = players[target_id]["role"].name
        target_alignment = players[target_id]["role"].alignment # Get alignment
        target_short_desc = players[target_id]["role"].short_description
        if target_role == "Godfather" or target_role == "Serial Killer":
            target_role = "Plain Townie"
            target_alignment = "Town"
            target_short_desc = "Normal member of town"
        try:
            await town_cop_player.send(f"You investigated {target_name}.  Their role is: {target_role} ({target_short_desc}).  Their alignment is: {target_alignment}.")
        except discord.Forbidden:
            logger.error(f"Could not send investigation result to Town Cop ({town_cop_player.name}) due to their privacy settings.")
        except Exception as e:
            logger.error(f"An error occurred while sending investigation result to Town Cop ({town_cop_player.name}): {e}")
    return

def set_previous_actions(players):
    """Sets the current action_target to previous_target"""
    for player_id, player_data in players.items(): #iterate through items()
        player_data["previous_target"] = player_data["action_target"] 

def clear_actions(players):
    """Clears the 'action_target' for all players in the game."""
    for player_id, player_data in players.items():  # Iterate through items()
        player_data["action_target"] = None  # Set to None, not an empty string

async def check_gf_status(bot, players):
    mob_gf_id = get_specific_player_id(players,"Godfather")
    if mob_gf_id:
        mob_gf_alive = players[mob_gf_id]["alive"]
    if mob_gf_id is None or mob_gf_alive == False :
        mob_goon_id = get_specific_player_id(players,"Mob Goon")
        name = "Mob Goon"
        logger.error("DEBUG: No living Godfather found. Skipping Mafia night kill process.")
        logger.info(f"DEBUG: Promoting Mob to Godfather")
        if mob_goon_id is None or players[mob_goon_id]["alive"] == False:
            name = "Mob Role Blocker"
            mob_goon_id = get_specific_player_id(players,"Mob Role Blocker")
            if mob_goon_id is None or players[mob_goon_id]["alive"] == False:
                logger.error("Debug: All mob are dead")
                return
        players[mob_goon_id]["role"] = create_godfather_role(name)
        if mob_goon_id > 0:
            mob_goon_player = await bot.fetch_user(mob_goon_id)
            logger.info("Promoted Mob to Mob Godfather")
            try:
               await mob_goon_player.send(f"Your Godfather has been killed, you are the Godfather Now\n\n {players[mob_goon_id]["role"].description}")
            except discord.Forbidden:
                logger.error(f"Could not send DM to promoted Godfather.  User has DMs disabled.")
            except discord.HTTPException as e:
                logger.error(f"HTTP Error sending DM to promoted Godfather: {e}")
            except Exception as e:
                logger.exception(f"Unexpected error promoting Godfather: {e}")
        return
async def kill_inactive_player():
    global bot, players, current_phase, phase_number, story_text
    logger.info("Checking for inactive voters...")
    players_to_remove = []
    story_parts = []
    # --- Increment Missed Vote Counters ---
    for p_id, p_data in players.items():
        if p_data["alive"] and p_data["action_target"] is None:
            p_data["missed_votes"] += 1
            logger.info(f"Player {p_data['display_name']} missed vote {p_data['missed_votes']} time(s).")
    # --- End Increment ---
    # --- Identify Inactive Players ---
    for player_id, player_data in players.items():
        if player_data["alive"]: # Only check living players
            # Check for missed votes
            if player_data["missed_votes"] >= 1: # Check if they missed >= 1 vote
                logger.warning(f"Player {player_data['display_name']} (ID: {player_id}) marked inactive for missing vote.")
                players_to_remove.append((player_id, "Inactive - Missed Vote"))
    # --- Process Removals ---
    if players_to_remove:
        for player_id, reason in players_to_remove:
            if player_id in players: # Double-check player still exists
                player_data = players[player_id]
                if player_data["alive"]: # Make sure they weren't killed/lynched already
                    player_data["alive"] = False
                    total_phases_calculation = (phase_number * 2) - (1 if current_phase == "night" else 0) # Calculate here
                    player_data["death_info"] = {
                        "phase": f"{current_phase} {phase_number}",
                        "phase_num": phase_number,
                        "total_phases": total_phases_calculation,
                        "how": reason
                    }
                    logger.info(f"Removed inactive player: {player_data['display_name']} (ID: {player_id}), Reason: {reason}")
                    story_parts.append(f"**{player_data['display_name']}** was removed from the game due to inactivity (Missed Vote).")
                    # Announce role 
                    if player_data["role"]:
                         story_parts.append(f"Their role was: {player_data['role'].name}")
        # Send combined story message if there were removals
        if story_parts:
                story_text = "\n".join(story_parts)
                logger.debug(story_text)
    else:
        logger.info("No inactive voters found.")
    return (story_text)  

# --- Bot Event ---
@bot.event
async def on_ready():
    logger.critical(f"Logged in as {bot.user.name}")

# --- Bot Commands ---
@bot.command(name="mafiastart")
#@commands.has_role(discord_role_data.get("mod", {}).get("id"))
@commands.check(is_owner_or_mod(bot, discord_role_data))
async def start_game(ctx, phase_hours: float = config.PHASE_HOURS, *, start_datetime: str):
    # ""Args:""
    #    ctx: The command context.
    #    start_datetime: The datetime string for when the game should start, in the format YYYY-MM-DD HH:MM.
    #    phase_hours: The number of hours each phase (day/night) will last.
    #"""
    """Starts the Mafia game sign-up process."""
    global game_started, time_signup_ends, current_phase, phase_number, LOOP_HOURS
    LOOP_HOURS = phase_hours
    logger.debug(f"DEBUG: Phase Hours = {phase_hours} // {LOOP_HOURS} ")
    # Check if a game is already running
    if game_started:
        await ctx.send("A game is already in progress!")
        logger.error("A game is already in progress!")
        return
    # Reset game variables
    reset_game()
    game_started = True
    # Parse the start_datetime string into a datetime object
    try:
        time_signup_ends = datetime.strptime(start_datetime, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        logger.info(f"DEBUG: Time signups end => {time_signup_ends}")
    except ValueError:
        await ctx.send("Invalid date/time format. Please use '%Y-%m-%d %H:%M' format in UTC.")
        logger.error("Invalid date/time format. Please use '%Y-%m-%d %H:%M' format in UTC.")
        reset_game()
        game_started = False
        return
    # Check if the provided start_datetime is in the future
    if time_signup_ends < datetime.now(timezone.utc):
        await ctx.send("The provided start time is in the past. Please provide a future date and time.")
        logger.error("The provided start time is in the past. Please provide a future date and time.")
        reset_game()
        game_started = False
        return
    # Calculate join_hours based on the difference between now and start_datetime
    join_hours = round((time_signup_ends - datetime.now(timezone.utc)).total_seconds() / 3600, 2)
    logger.info(f"DEBUG: New game started with join hours {join_hours}")
    channel = bot.get_channel(config.TALKY_TALKY_CHANNEL_ID)
    await channel.send( f"Sign-ups are now open for {join_hours} hours! Use `/mafiajoin` in the <#{config.SIGN_UP_HERE_CHANNEL_ID}> channel to join the game.\n "
                        f"Game will start at: {time_signup_ends.strftime('%Y-%m-%d %H:%M:%S UTC')}.\n\n"
                        )
    channel = bot.get_channel(config.SIGN_UP_HERE_CHANNEL_ID)
    await channel.send( f"Sign-ups are now open for {join_hours} hours! Use `/mafiajoin` in the <#{config.SIGN_UP_HERE_CHANNEL_ID}> channel to join the game.\n"
                        f"Game will start at: {time_signup_ends.strftime('%Y-%m-%d %H:%M:%S UTC')}.\n\n"
                        )
    channel = bot.get_channel(config.RULES_AND_ROLES_CHANNEL_ID)
    await channel.send( "--- ** New Basic Bitch Game open for signups ** ---\n"
                        f"Sign-ups are now open for {join_hours} hours! Use `/mafiajoin` in the <#{config.SIGN_UP_HERE_CHANNEL_ID}> channel to join the game.\n"
                        f"**Game will start at: {time_signup_ends.strftime('%Y-%m-%d %H:%M:%S UTC')}.**\n\n"
                        f"{rules_text}\n"
                        "\n--- **No story generated** ---\n\n"
                        )
    # Wait for signups to end (until start_datetime)
    delay = (time_signup_ends - datetime.now(timezone.utc)).total_seconds()
    logger.debug(f"DEBUG: Delay =  {delay} // {(time_signup_ends - datetime.now(timezone.utc)).total_seconds()}")
    logger.info(f"DEBUG: Timestamp: {datetime.now(timezone.utc)} -  Game Started == {game_started}")
    await asyncio.sleep(delay)
    if game_started:
        logger.info(f"DEBUG: Timestamp: {datetime.now(timezone.utc)} - game started = {game_started} so prepare game start")
        await prepare_game_start(ctx, bot, npc_names, phase_hours)
    else:
        logger.error("DEBUG: Sign-ups ended, but the game was stopped.")
        logger.error(f"DEBUG: Timestamp: {datetime.now(timezone.utc)} - game started = {game_started}")

@bot.command(name="mafiajoin")
@commands.check(is_owner_or_mod(bot, discord_role_data))
#async def join_game(ctx,*,game_name: str):
async def join_game(ctx):
    """Joins the Mafia game."""
    global players
    if not game_started:
        await ctx.send("No game is currently running.")
        logger.error("No game is currently running.")
        return
    if ctx.channel.id != config.SIGN_UP_HERE_CHANNEL_ID:
        await ctx.send(f"Please use this command in the <#{config.SIGN_UP_HERE_CHANNEL_ID}> channel.")
        logger.error(f"Please use this command in the <#{config.SIGN_UP_HERE_CHANNEL_ID}> channel.")
        return
    player_id = ctx.author.id
    if player_id in players:
        await ctx.send("You have already joined the game!")
        logger.error(f"Player {player_id} have already joined the game!")
        return
    # Add player to the game
    if current_phase == "" or current_phase == "Signup": #check that the game is in signup phase
        # Add player to the players dictionary
        players[player_id] = {
            "name": ctx.author.name,
            "display_name": ctx.author.display_name,
            "role": None,
            "alive": True,
            "votes": 0,
            "action_target": None,
            "previous_target": None,
            "missed_votes": 0,
            "death_info":    {
                    "phase": None,
                    "phase_num": None,
                    "total_phases": None,
                    "how": None
                }
        }
        # Update discord roles
        guild = ctx.guild
        await update_player_discord_roles(bot,guild, players, discord_role_data)
        logger.info(f"DEBUG: Player joined: {ctx.author.name} (ID: {player_id}).") 
        await ctx.send(
            f"{ctx.author.mention} has joined the game!"
        )
    else:
       await ctx.author.send("You cannot join an active game, please wait for the game to finish and join the next game!")  
       logger.error(f"{player_id} tried to join an active game")  
@join_game.error
async def join_game_error(ctx, error):
    if isinstance(error, commands.PrivateMessageOnly):
        await ctx.author.send("This command can only be used in private messages.")
        logger.error(f"{ctx.author.name} tried to send command /join in private channel")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.author.send(  "You are missing a required argument. Use `/help join` to see required arguments.\n"
                                "Please provide a game name after the /join command\n"
                                "i.e. `/join PlayerOne`\n"
                                )
        logger.error(f"{ctx.author.name} missed an argument in /join")
    elif isinstance(error, commands.BadArgument):
        await ctx.author.send("Invalid argument provided, please check and try again. Use `/help join` to see required arguments.\n"
                                "Please provide a game name after the /join command\n"
                                "i.e. `/join PlayerOne`\n"
                                )
        logger.error(f"{ctx.author.name} used an incorrect argument in /join")
    else:
        await ctx.author.send("An error occurred during processing of this command.")
        logger.critical(f"An error occurred during processing of this command. {error}")

@bot.command(name="mafiastop")
@commands.check(is_owner_or_mod(bot, discord_role_data))
@commands.has_role(discord_role_data.get("mod", {}).get("id"))
async def stop_game(ctx):
    """Stops the current game."""
    global game_started, time_signup_ends, players, gameprocess
    if not game_started:
        await ctx.send("No game is currently running.")
        logger.error("No game is currently running.")
        return
    if time_signup_ends > datetime.now(timezone.utc):
        await ctx.send("Cannot end game during signup phase")
        logger.critical("Cannot end game during sign up phase")
        return
    game_started = False
    time_signup_ends = None  # Reset the signup end time
     # Stop the game loop task if it's running
    if gameprocess is not None:
        gameprocess.stop()
        logger.info(f"DEBUG: Gameprocess stopped.")
    else:
        logger.error("Game process not running")
    guild = ctx.guild
    await announce_winner(bot,"Draw")
    reset_game()
    await update_player_discord_roles(bot, guild, players, discord_role_data)
    await ctx.send("The current game has been stopped.")
    logger.info(f"DEBUG: Game stopped.")

@bot.command(name="mafiastatus")
@commands.check(is_owner_or_mod(bot, discord_role_data))
async def status(ctx):
    """Displays the current game status."""
    if not game_started:
        await ctx.send("No game is currently running.")
        logger.error("No game is running and /status called")
        return
    status_message = generate_status_message(players)
    try:
     await asyncio.wait_for(ctx.send(status_message), timeout=5.0)
     logger.info(f"/Status called and info sent to channel")
    except asyncio.TimeoutError:
     logger.error("Timeout while sending status message.")
    
@bot.command(name = "vote")
@commands.check(is_owner_or_mod(bot, discord_role_data))
@commands.has_role(discord_role_data.get("living", {}).get("id"))
async def vote(ctx, *, lynch_target):
    """Allows playes to vote."""
    global game_started, current_phase, phase_number, players
    if ctx.channel.id != config.VOTING_CHANNEL_ID:
        await ctx.send(f"Please use this command in the <#{config.VOTING_CHANNEL_ID}> channel.")
        return
    if not game_started:
        await ctx.send("No game is currently running.")
        return
    if not current_phase == "Day":
        await ctx.send("Not currently Day Phase")
        return
    player_id = ctx.author.id
    target_id = await get_player_id_by_name(lynch_target, players)
    logger.debug(f"DEBUG: Target for lynch = {target_id}")
    if player_id not in players:
        channel = bot.get_channel(config.VOTING_CHANNEL_ID)
        await channel.send("You are not in this game")
        return 
    if target_id not in players:
        channel = bot.get_channel(config.VOTING_CHANNEL_ID)
        logger.error(f"DEBUG {player_id}")
        logger.error(f"DEBUG: Target for lynch = {target_id}")
        await channel.send("Lynch target is not in this game")
        logger.error("Lynch target is not in this game")
        return
    if players[target_id]["alive"] == True: 
        logger.debug(f"DEBUG: Sending data to process_lynch_vote: {ctx}, {player_id}, {lynch_target}")
        await process_lynch_vote(player_id, lynch_target)
        await send_vote_update(bot, players)  # Send vote update after each vote
        # --- Reset Missed Votes ---
        players[player_id]["missed_votes"] = 0
        logger.debug(f"Reset missed_votes for {players[player_id]['display_name']}")
        # --- End Reset ---
    else:
        logger.error(f"Player {player_id} tried to vote for dead player {target_id}")
        await ctx.send("You can not vote for a dead player") 

@bot.command(name = "mafiacount")
@commands.has_role(discord_role_data.get("living", {}).get("id"))
async def count(ctx):
    await send_vote_update(bot, players) #manually send vote count with /count
    logger.info("/count has been called")
@count.error
async def count_error(ctx, error):
    if isinstance(error, commands.MissingRole):
        # Send a message to the voting channel.
        voting_channel = bot.get_channel(config.VOTING_CHANNEL_ID)
        await voting_channel.send(f"{ctx.author.mention}, you must be a living player to use the `/count` command.")
    elif isinstance(error, commands.NoPrivateMessage):
        await ctx.author.send("This command cannot be used in private messages.")
    else:
        # Handle other errors as needed.  Always log the full exception.
        await ctx.send("An error occurred while processing the `/count` command.")
        logger.exception(f"Error in /count command: {error}")

@bot.command(name="kill")
@commands.dm_only()
async def kill_command(ctx, *, kill_target: str):
    global sk_target, mob_target, players
    player_id = ctx.author.id
    if not game_started:
        await ctx.author.send("No game is currently running.")
        logger.error("No game is currently running.")
        return
    if player_id not in players:
        await ctx.author.send("You are not part of the current game.")
        logger.error(f"Player {player_id} is not part of the current game.")
        return
    if current_phase != "Night":
        await ctx.author.send("You can only use this command during the night phase.")
        logger.error(f"Player {player_id} can only use this command during the night phase.")
        return
    player_data = players[player_id]
    # Check if the player is alive
    if not player_data["alive"]:
        await ctx.author.send("Dead players cannot use this command.")
        logger.error(f"Dead player {player_id} cannot use this command.")
        return
    # Check for allowed roles
    #allowed_roles = ["Godfather", "Serial Killer"]
    if player_data["role"].action != "Kill":
        await ctx.author.send("You do not have the required role to use this command.")
        logger.error(f"Player {player_id} does not have the required role (kill) to use this command.")
        return
    if not kill_target:  # Check if target_name is empty
        await ctx.author.send("You must specify a target to kill.")
        logger.error(f"Player {player_id} used /kill with no target")
        return
    target_id = await get_player_id_by_name(kill_target, players)
    logger.debug("DEBUG: target input has been converted to ID")
    if target_id is None:
        await ctx.author.send(f"Could not find a player named '{kill_target}'.")
        logger.error(f"Player {player_id} used /kill but target_id could not be found")
        return
    # Ensure the target is not the player themselves
    if target_id == player_id:
        await ctx.author.send("You cannot target yourself.")
        logger.error(f"Player {player_id} used /kill on themselves")
        return
    # Ensure the target is alive
    if not players[target_id]["alive"]:
        await ctx.author.send("You cannot target dead players.")
        logger.error(f"Player {player_id} used /kill on a dead player")
        return
    # Rest of the command logic for players with the correct role
    logger.debug(f"SK used /kill on {target_id}")
    await ctx.author.send(f"You have chosen to kill {players[target_id]['display_name']}.")
    players[player_id]["action_target"]=target_id
    logger.debug(f"Player action target: {players[player_id]["action_target"]}")
@kill_command.error
async def kill_command_error(ctx, error):
    if isinstance(error, commands.PrivateMessageOnly):
        await ctx.author.send("This command can only be used in private messages.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.author.send("You are missing a required argument. Use `/help kill` to see required arguments.")
    elif isinstance(error, commands.BadArgument):
        await ctx.author.send("Invalid argument provided, please check and try again. Use `/help kill` to see required arguments.")
    else:
        await ctx.author.send("An error occurred during processing of this command.")

@bot.command(name="heal")
@commands.dm_only()
async def heal_command(ctx, *, target_name: str):  # Changed target to target_name
    """Allows the Doctor to select a player to heal during the night phase."""
    global heal_target, players
    player_id = ctx.author.id
    if not game_started:
        await ctx.author.send("No game is currently running.")
        logger.error("No game is currently running.")
        return
    if player_id not in players:
        await ctx.author.send("You are not part of the current game.")
        logger.error(f"Player {player_id} is not part of the current game")
        return
    if current_phase != "Night":
        await ctx.author.send("You can only use this command during the night phase.")
        logger.error(f"Player {player_id} used command /heal in {current_phase}")
        return
    player_data = players[player_id]
    # Check if the player is alive
    if not player_data["alive"]:
        await ctx.author.send("Dead players cannot use this command.")
        logger.error(f"Player {player_id} used /heal when dead")
        return
    # Check for allowed roles
    #allowed_roles = ["Town Doctor"]  # Add other roles if needed
    if player_data["role"].action != "Heal":
        await ctx.author.send("You do not have the required role to use this command.")
        logger.error(f"Player {player_id} does not have the required role (Heal) to use this command.")
        return
    target_id = await get_player_id_by_name(target_name, players)
    if target_id is None:
        await ctx.author.send(f"Could not find a player named '{target_name}'.")
        logger.error(f"Could not find the target {target_name}")
        return
    # Ensure the target is alive
    if not players[target_id]["alive"]:
        await ctx.author.send("You cannot target dead players.")
        logger.error(f"Player {player_id} targeted a dead player {target_id}")
        return
    if target_id == player_data["previous_target"]:
        await ctx.author.send("You cannot target the same player two nights in a row")
        logger.debug(f"Town Doc attempted to target {target_id} two nights in a row")
        return
    # Rest of the command logic for players with the correct role
    players[player_id]["action_target"] = target_id
    await ctx.author.send(f"You have chosen to heal {players[target_id]['display_name']}.")
    logger.debug(f"Player action target: {players[player_id]["action_target"]}")
@heal_command.error
async def heal_command_error(ctx, error):
    if isinstance(error, commands.PrivateMessageOnly):
        await ctx.author.send("This command can only be used in private messages.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.author.send("You are missing a required argument. Use `/help heal` to see required arguments.")
    elif isinstance(error, commands.BadArgument):
        await ctx.author.send("Invalid argument provided, please check and try again. Use `/help heal` to see required arguments.")
    else:
        await ctx.author.send("An error occurred during processing of this command.")

@bot.command(name="investigate")
@commands.dm_only()
async def investigate_command(ctx, *, target_name: str):
    """Allows the Town Cop to investigate a player during the night phase."""
    global investigate_target, players
    player_id = ctx.author.id
    if not game_started:
        await ctx.author.send("No game is currently running.")
        logger.error("No game is currently running.")
        return
    if player_id not in players:
        await ctx.author.send("You are not part of the current game.")
        logger.error(f"Player {player_id} is not part of the current game")
        return
    if current_phase != "Night":
        await ctx.author.send("You can only use this command during the night phase.")
        logger.error(f"Player {player_id} tried to use /investigate during the {current_phase} phase.")
        return
    player_data = players[player_id]
    # Check if the player is alive
    if not player_data["alive"]:
        await ctx.author.send("Dead players cannot use this command.")
        logger.error(f"Player {player_id} tried to use this whilst dead")
        return
    # Check for allowed roles
    #allowed_roles = ["Town Cop"]
    if player_data["role"].action != "Investigate":
        await ctx.author.send("You do not have the required role to use this command.")
        logger.error(f"Player {player_id} does not have the required role (Investigate) to use this command.")
        return
    target_id = await get_player_id_by_name(target_name, players)
    if target_id is None:
        await ctx.author.send(f"Could not find a player named '{target_name}'.")
        logger.error(f"Could not find {target_name}")
        return
    # Ensure the target is not the player themselves
    if target_id == player_id:
        await ctx.author.send("You cannot target yourself.")
        logger.error(f"player {player_id} tried to target themselves")
        return
    # Ensure the target is alive
    if not players[target_id]["alive"]:
        await ctx.send("You cannot target dead players.")
        logger.error(f"Player {player_id} tried to target a dead player")
        return
    # Rest of the command logic for players with the correct role
    players[player_id]["action_target"] = target_id
    await ctx.author.send(f"You have chosen to investigate {players[target_id]['display_name']}.")
    logger.debug(f"Player action target: {players[player_id]["action_target"]}")
@investigate_command.error
async def investigate_command_error(ctx, error):
    if isinstance(error, commands.PrivateMessageOnly):
        await ctx.author.send("This command can only be used in private messages.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.author.send("You are missing a required argument. Use `/help investigate` to see required arguments.")
    elif isinstance(error, commands.BadArgument):
        await ctx.author.send("Invalid argument provided, please check and try again. Use `/help investigate` to see required arguments.")
    else:
        await ctx.author.send("An error occurred during processing of this command.")

@bot.command(name="block")
@commands.dm_only()  # Must be used in DMs
async def roleblock_command(ctx, *, target_name: str):
    """Allows a Role Blocker to block a player's action during the night."""
    global players, current_phase, town_block_target, mob_block_target

    blocker_id = ctx.author.id
    # --- Basic Validation ---
    if not game_started:
        await ctx.author.send("No game is currently running.")
        logger.error("No game is currently running.")
        return
    if blocker_id not in players:
        await ctx.author.send("You are not part of the current game.")
        logger.error(f"Player {blocker_id} is not part of the current game")
        return
    if current_phase != "Night":
        await ctx.author.send("You can only use this command during the night phase.")
        logger.error(f"Player {blocker_id} tried to use /investigate during the {current_phase} phase.")
        return
    player_data = players[blocker_id]
    # Check if the player is alive
    if not player_data["alive"]:
        await ctx.author.send("Dead players cannot use this command.")
        logger.error(f"Player {blocker_id} tried to use this whilst dead")
        return
    # --- Role Check ---
    if player_data["role"].action != "Block":
        await ctx.author.send("You do not have the required role to use this command.")
        logger.error(f"Player {blocker_id} does not have the required role (block) to use this command.")
        return
    # --- Target Resolution and Validation ---
    target_id = await get_player_id_by_name(target_name,players)
    if target_id is None:
        await ctx.author.send(f"Could not find a player named '{target_name}'.")
        return
    if target_id == blocker_id:
        await ctx.author.send("You cannot block yourself.")
        return
    if target_id < 0:  # Prevent blocking NPCs
        await ctx.author.send("You cannot block NPCs.")
        return
    target_data = players.get(target_id)  # Use .get()
    if not target_data:
       await ctx.author.send("Invalid target")
       return
    if not target_data["alive"]:
        await ctx.author.send("You cannot block dead players.")
        return 
    # --- Check for previous blocks (two nights in a row) ---
    if target_id == player_data["previous_target"]:
        await ctx.author.send("You cannot target the same player two nights in a row")
        logger.debug(f"Roleblock {players[blocker_id]["role"].alignment} attempted to target {target_id} two nights in a row")
        return 
    # --- Process the Block ---
    await ctx.author.send(f"You have blocked {target_data['display_name']}.")
    players[blocker_id]["action_target"] = target_id
    logger.debug(f"The {player_data["role"].name} has blocked {target_data['display_name']}.")
    logger.debug(f"Player action target: {players[blocker_id]["action_target"]}")

@roleblock_command.error
async def roleblock_command_error(ctx, error):
    if isinstance(error, commands.PrivateMessageOnly):
        await ctx.author.send("This command can only be used in private messages.")
        logger.error("/block command can only be used in private messages.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.author.send("You are missing a required argument. Use `/help roleblock` to see required arguments.")
        logger.error("/block was not used correctly -> need to use `/help roleblock` to see required arguments.")
    elif isinstance(error, commands.BadArgument):
        await ctx.author.send("Invalid argument provided, please check and try again. Use `/help roleblock` to see required arguments.")
        logger.error("Invalid argument provided, please check and try again. Use `/help roleblock` to see required arguments.")
    else:
        await ctx.author.send("An error occurred during processing of this command.")
        logger.exception(f"Error in roleblock command: {error}")

@bot.command(name="mafiainfo")
async def show_info(ctx):
    """Shows the list of available commands."""
    info_text = (
        "**Available Commands:**\n\n"
        "**Player Commands:**\n"
        "- `/mafiajoin <name>` : Joins the upcoming game. Enter your game name as a parameter, which can be used during the game\n"
        "- `/mafiastatus`: Displays the current game status. Will show game names of all signed up players\n"
        "- `/vote <@player>`: Casts a vote during the day phase. Use either the players game name or discord ID (@name) to target\n"
        "- `/mafiacount`: Displays the current vote count.\n"
        "- `/mafiarules`: Displays the rules of the game.\n"
        "- `/mafiainfo`: Shows this help message.\n"
        "- `/mafialeave : Allows you to leave a game during setup phase only - Once a game starts you cannot use this function\n"
        " \n\n**Player Actions**\n"
        "- `/kill <@player>` (Godfather & Serial Killer only, DM only): Selects a player to be killed by the Mafia.\n"
        "- `/heal <@player>` (Doctor only, DM only): Selects a player to be healed.\n"
        "- `/investigate <@player>` (Town Cop only, DM only): Investigates a player's role.\n"
        "\n\n**Moderator Commands:**\n"
        "- `/mafiastart <start_datetime>  [phase_hours]`:  Starts a new game at the specified time. Date/time format: `YYYY-MM-DD HH:MM` (UTC).\n"
        "- `/mafiastop`: Stops the current game.\n"
    )
    await ctx.send(info_text)
    logger.info("/info was called")

@bot.command(name="mafiarules")
async def show_rules(ctx):
    """Displays the rules of the game."""
    global current_phase, phase_number, time_signup_ends, time_day_ends, time_night_ends
    ruleschannel = bot.get_channel(config.RULES_AND_ROLES_CHANNEL_ID)
    if current_phase == "Day":
        next_deadline = time_day_ends
    elif current_phase == "night":
        next_deadline = time_night_ends
    else:
        next_deadline = time_signup_ends
    if next_deadline:
        await ruleschannel.send(f"{rules_text}\n\n Current {current_phase} phase ends at {next_deadline}\n")
    else:
        await ctx.send(f"\nNo current game running. \nStandard game rules: {rules_text} \n")
    logger.info("/rules was called")

@bot.command(name="mafialeave")
async def leave_game(ctx):
    """Allows a player to leave the game during the sign-up phase."""
    global players

    player_id = ctx.author.id
    if not game_started:
        await ctx.send("No game is currently running.")
        return
    if current_phase != "":  # Use empty string for signup phase
        await ctx.send("You cannot leave a game that has already started.")
        return
    if player_id not in players:
        await ctx.send("You are not currently signed up for the game.")
        return
    # Remove the player from the players dictionary
    del players[player_id]
    # Remove the "Living Players" role (if they have it)
    guild = ctx.guild
    member = guild.get_member(player_id)
    if member:
        living_role_id = discord_role_data.get("living", {}).get("id")
        living_role = discord.utils.get(guild.roles, id=living_role_id)
        if living_role:
            try:
                await member.remove_roles(living_role)
            except discord.HTTPException as e:
                print(f"ERROR: Could not remove role from {member.name}: {e}")
        # Add Spectator Role
        spectator_role_id = discord_role_data.get("spectator", {}).get("id")
        spectator_role = discord.utils.get(guild.roles, id=spectator_role_id)
        if spectator_role:
            try:
                await member.add_roles(spectator_role)
            except discord.HTTPException as e:
                 print(f"ERROR: Could not remove role from {member.name}: {e}")
    await ctx.send(f"{ctx.author.mention} has left the game.")
    print(f"DEBUG: Player left: {ctx.author.name} (ID: {player_id}). Players: {players}")

@bot.command(name="mafiareinit") # Renamed command for clarity
@commands.check(is_owner_or_mod(bot, discord_role_data)) # Use custom check
async def reinitialize_players(ctx):
    """(Admin/Mod only) Re-initializes the player dictionary based on current roles.

    If in signup phase: Clears players and re-adds based on 'Living Players' role.
    If in game phase: Updates player status based on 'Living/Dead Players' roles,
                      preserving existing role/target/death data.
    """
    global players, game_started, current_phase # Ensure all needed globals are declared

    logger.info(f"Reinitialize players command called by {ctx.author.name}")

    if not game_started:
        await ctx.send("No game is currently running.")
        logger.warning("Attempted to reinitialize players when no game was started.")
        return

    guild = ctx.guild
    if not guild:
        await ctx.send("This command must be used in a server.")
        logger.warning("Reinitialize players command used outside of a server.")
        return

    # Get Discord Role Objects
    living_role_id = discord_role_data.get("living", {}).get("id")
    dead_role_id = discord_role_data.get("dead", {}).get("id")
    spectator_role_id = discord_role_data.get("spectator", {}).get("id") # Get spectator role too

    living_role = discord.utils.get(guild.roles, id=living_role_id)
    dead_role = discord.utils.get(guild.roles, id=dead_role_id)
    spectator_role = discord.utils.get(guild.roles, id=spectator_role_id)

    if not living_role or not dead_role or not spectator_role:
        await ctx.send("Error: Could not find 'Living Players', 'Dead Players', or 'Spectator' role in the server config.")
        logger.error("Could not find essential game roles in discord_roles.json or server.")
        return

    logger.info(f"Current game phase for reinitialization: '{current_phase or 'Signup'}'")

    new_players = {}

    if current_phase == "" or current_phase == "signup": # --- SIGNUP PHASE ---
        logger.info("Reinitializing players during signup phase.")
        players = {} # Clear the existing player dictionary

        for member in guild.members:
            if living_role in member.roles: # Only add members with the living role
                if not member.bot: # Exclude bots
                    logger.debug(f"Adding player {member.display_name} (ID: {member.id}) during signup reinit.")
                    new_players[member.id] = {
                        "name": member.name,
                        "display_name": member.display_name,
                        "role": None,
                        "alive": True, # Must be alive if they have living role
                        "votes": 0,
                        "action_target": None,
                        "previous_target": None,
                        "missed_votes": 0,
                        "death_info": {} # Initialize as empty
                    }
            # Ensure non-players have spectator role during signup phase reset
            elif not member.bot and spectator_role not in member.roles:
                 try:
                    await member.add_roles(spectator_role)
                    await member.remove_roles(living_role, dead_role) # Clean up other roles
                 except discord.HTTPException as e:
                     logger.error(f"HTTPException setting spectator role for {member.name}: {e}")
                 except discord.Forbidden:
                     logger.error(f"Bot lacks permissions to set spectator role for {member.name}.")

    else: # --- GAME PHASE (Day or Night) ---
        logger.info("Reinitializing players during active game phase (Day/Night).")
        for member in guild.members:
            if living_role in member.roles or dead_role in member.roles:
                if not member.bot: # Exclude bots
                    # Get existing player data safely
                    existing_player_data = players.get(member.id, {})
                    logger.debug(f"Processing player {member.display_name} (ID: {member.id}) during game phase reinit.")

                    # Add player to the new dictionary, preserving/resetting data
                    new_players[member.id] = {
                        "name": member.name,
                        "display_name": member.display_name,
                        "role": existing_player_data.get("role", None),  # Preserve role
                        "alive": living_role in member.roles,            # Update based on current role
                        "votes": 0,  # Reset votes for the new phase
                        "action_target": existing_player_data.get("action_target", None),  # Preserve target
                        "previous_target": existing_player_data.get("previous_target", None), # Preserve previous target
                        "missed_votes": existing_player_data.get("missed_votes", None), # Preserve previous missed votes
                        "death_info": existing_player_data.get("death_info", {}) if dead_role in member.roles else {} # Keep if dead
                    }
            # Ensure non-players have spectator role
            elif not member.bot and spectator_role not in member.roles:
                try:
                    await member.add_roles(spectator_role)
                    await member.remove_roles(living_role, dead_role) # Clean up other roles
                except discord.HTTPException as e:
                    logger.error(f"HTTPException setting spectator role for {member.name}: {e}")
                except discord.Forbidden:
                    logger.error(f"Bot lacks permissions to set spectator role for {member.name}.")

    players = new_players  # Replace the old dictionary with the new one.
    await ctx.send("Player dictionary reinitialized based on current roles.")
    logger.info("Player dictionary reinitialized by %s", ctx.author.name)
    logger.info(f"New Player dictionary: {players}")
    @reinitialize_players.error # Added specific error handler
    async def reinitialize_players_error(ctx, error):
        if isinstance(error, commands.CheckFailure): # Handles custom check failure
            # The is_owner_or_mod check already sends a DM if needed
            logger.warning(f"{ctx.author.name} lacked permission for /reset_players.")
        elif isinstance(error, commands.MissingRole): # Handles has_role failure
            await ctx.send(f"{ctx.author.mention}, you need the 'Mod' role to use this command.")
            logger.warning(f"{ctx.author.name} lacked 'Mod' role for /reset_players.")
        else:
            # Handle other errors as needed. Always log the full exception.
            await ctx.send("An unexpected error occurred during player reinitialization.")
            logger.exception(f"Error in /reset_players command: {error}")

@bot.command(name="testrandom")
@commands.check(is_owner_or_mod(bot, discord_role_data))
async def random_test(ctx, simulations: int = 10000):
    """
    (Admin/Mod only) Runs the role assignment randomness test script
    using the names of the players currently in the game.
    
    Args:
        simulations: (Optional) The number of iterations to run.
    """
    global players

    if not players:
        await ctx.send("Error: There are no players currently in the game to test with.")
        return

    await test_randomness(bot,simulations)

# --- Game Loop ---
@tasks.loop(seconds = 1)
async def gameprocess(ctx,bot,players):
    global phase_number, current_phase, lynch_votes, sk_target, mob_target, heal_target, investigate_target, time_night_ends, time_day_ends, message_send_delay, town_block_target, mob_block_target, story_text
    if current_phase == "Night":
        #night phase
        if phase_number == 0:
            time_night_ends = time_signup_ends + timedelta(hours=LOOP_HOURS)
        else:
            time_night_ends = time_day_ends + timedelta(hours=LOOP_HOURS)
        phase_number += 1 
        logger.info(f"DEBUG: Starting {current_phase} - {phase_number} which will last {LOOP_HOURS} hours")
        logger.info("The town goes to sleep....")
        storychannel = bot.get_channel(config.STORIES_CHANNEL_ID)
        ruleschannel = bot.get_channel(config.RULES_AND_ROLES_CHANNEL_ID)
        await storychannel.send(f"Night {phase_number} has fallen. The town goes to sleep...")
        logger.info(f"DEBUG: Current time night ends = {time_night_ends}")
        status_message = generate_status_message(players)
        await ruleschannel.send(status_message)
        await check_gf_status(bot, players)
        #future night time actions logic
        story_text = None
        logger.info("Sleeping....")
        await asyncio.sleep(LOOP_HOURS*60*60)
        await asyncio.sleep(message_send_delay)
        logger.info("DEBUG: Roleblockers")
        await process_role_block(bot)
        logger.debug(f"DEBUG: Story text to send => \n{story_text}")
        if story_text:
            await storychannel.send(story_text)
            story_text = None
        logger.info("DEBUG: SK Kill")
        await process_sk_night_kill(bot)
        logger.debug(f"DEBUG: Story text to send => \n{story_text}")
        if story_text:
            await storychannel.send(story_text)
            story_text = None
        await asyncio.sleep(message_send_delay)
        logger.info("DEBUG: Mob Kill")
        await process_mafia_night_kill(bot)
        logger.debug(f"DEBUG: Story text to send => \n{story_text}")
        if story_text:
            await storychannel.send(story_text)
            story_text = None
        await asyncio.sleep(message_send_delay)
        logger.info("DEBUG: Town Doc Heal")
        await process_doc_night_heal(bot)
        logger.debug(f"DEBUG: Story text to send => \n{story_text}")
        if story_text:
            await storychannel.send(story_text)
            story_text = None
        await asyncio.sleep(message_send_delay)
        logger.info("DEBUG: Town Cop Investigate")
        await process_cop_night_investigate(bot)
        logger.debug(f"DEBUG: Story text to send => \n{story_text}")
        if story_text:
            await storychannel.send(story_text)
            story_text = None
        await asyncio.sleep(message_send_delay)
        logger.info("DEBUG: All night actions done")
        guild = bot.get_guild(config.SERVER_ID)
        await update_player_discord_roles(bot, guild, players, discord_role_data)
        logger.info("DEBUG: Discord roles now updated")
        await asyncio.sleep(message_send_delay)
        logger.info("DEBUG: Checking winner")
        winner = check_win_conditions()
        logger.info(f"Winner is {winner}")
        if winner:
            logger.info("We have a winner!")
            await announce_winner(bot, winner)  # You'll need to implement announce_winner
            current_phase = None
            status_message = generate_status_message(players)
            await ruleschannel.send(status_message)
            reset_game()
            return  # End the game loop if there's a winner
        #recordphaseactions()
        set_previous_actions(players)
        clear_actions(players)
        logger.info(f"DEBUG: End of night phase, about to switch to day phase")
        current_phase = "Day"
        sk_target = None
        mob_target = None
        heal_target = None
        investigate_target = None
        town_block_target = None
        mob_block_target = None
        story_text = None
    else:
        #day phase
        logger.info(f"DEBUG: {current_phase} - {phase_number} has dawned which will last {LOOP_HOURS} hours.\n" 
              "The town awakens...")
        storychannel = bot.get_channel(config.STORIES_CHANNEL_ID)
        ruleschannel = bot.get_channel(config.RULES_AND_ROLES_CHANNEL_ID)
        votingchannel = bot.get_channel(config.VOTING_CHANNEL_ID)
        await storychannel.send(f"Day {phase_number} has dawned. The town awakens...")
        story_text = None
        logger.info(f"The current UTC time is {datetime.now(timezone.utc)}")
        time_day_ends = time_night_ends + timedelta(hours=LOOP_HOURS)
        logger.info(f"DEBUG: Current time day ends = {time_day_ends}")
        await asyncio.sleep(message_send_delay)
        logger.info("DEBUG: Generate and send status message")
        status_message = generate_status_message(players)
        await ruleschannel.send(status_message)
        #future day actions logic
        logger.info("working....")
        await asyncio.sleep(LOOP_HOURS*60*60)
        await votingchannel.send("Voting ended!")
        if config.game_type == "Production":
            await kill_inactive_player() #checks for inactive players and kills them
        if story_text:
            logger.debug(f"DEBUG: Story text to send => \n{story_text}")
            await storychannel.send(story_text)
        await asyncio.sleep(message_send_delay)
        logger.info("DEBUG: Counting votes...")
        await countlynchvotes(bot,players)
        logger.debug(f"DEBUG: The lynch results -> {lynch_votes} for {current_phase} - {phase_number}")
        logger.debug(f"DEBUG: Story text to send => \n{story_text}")
        if story_text:
            await storychannel.send(story_text)
        await asyncio.sleep(message_send_delay)
        guild = bot.get_guild(config.SERVER_ID)
        await update_player_discord_roles(bot, guild, players, discord_role_data)
        await asyncio.sleep(message_send_delay)
        logger.info("DEBUG: Checking win conditions")
        winner = check_win_conditions()
        if winner:
            logger.info("We have a winner!")
            await announce_winner(bot, winner)  # You'll need to implement announce_winner
            status_message = generate_status_message(players)
            await ruleschannel.send(status_message)
            reset_game()
            return  # End the game loop if there's a winner
        clear_actions(players)
        lynch_votes = {}
        current_phase = "Night"
        logger.info("DEBUG: Changed to night phase")

# --- Start the Bot ---
bot.run(config.BOT_TOKEN, log_handler=logger.handlers[0], log_level=logging.DEBUG) # Use new handler
