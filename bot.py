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

# ----------------------------------------- #

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
current_phase = ""
phase_number = 0
lynch_votes = {}
game_id = 0
game_data ={}
sk_target = ""
mob_target = ""
heal_target = ""
investigate_target =""
message_send_delay = config.message_send_delay

# --- Load Roles ---
try:
    with open("data/discord_roles.json", "r") as f:
        discord_role_data = json.load(f)
except FileNotFoundError:
    print("ERROR: discord_roles.json not found!")
    discord_role_data = {}  # Initialize as an empty dictionary to prevent further errors

# --- Load Bot Names ---
try:
    with open("data/bot_names.txt", "r") as f:
        npc_names = [line.strip() for line in f]
except FileNotFoundError:
    npc_names = []

# --- Load Rules ---
try:
    with open("data/rules.txt", "r") as f:
        rules_text = f.read()
except FileNotFoundError:
    rules_text = "Rules not found."

# --- Load Mafia Setups ---
try:
    with open("data/mafia_setups.json", "r") as f:
        mafia_setups = json.load(f)
        print(f"Discord Roles => {discord_role_data}")
except FileNotFoundError:
    print("ERROR: mafia_setups.json not found!")
    mafia_setups = {}

# --- Roles ---
class GameRole:
    def __init__(self, name, alignment, short_description ,description, uses=None):
        self.name = name
        self.alignment = alignment
        self.short_description = short_description
        self.description = description
        self.uses = uses
    def __str__(self):
        return self.name
    def to_dict(self):
        """Converts the GameRole object to a dictionary."""
        return {
            "name": self.name,
            "alignment": self.alignment,
            "description": self.description,
            "day_action": self.day_action,
            "day_uses": self.day_uses,
            "lynch_vote": self.lynch_vote,
            "night_action": self.night_action,
            "night_uses": self.night_uses,
        }

# --- load data files ---
def save_json_data(data, name, sub="game_data"):
    """
    Saves data to a JSON file in the specified subdirectory.
    Creates the subdirectory if it doesn't exist.

    Args:
        data: The data to save (must be JSON serializable, like a dictionary or list).
        filename: The name of the file (e.g., "game_1.json").
        subdirectory: The subdirectory within the "data" folder where the file should be saved.
    """
    filename = f"{name}.json"
    subdirectory = f"{sub}/{name}"
    # Create the subdirectory if it doesn't exist
    data_dir = os.path.join("stats", subdirectory, name)
    os.makedirs(data_dir, exist_ok=True)
    # Construct the full file path
    filepath = os.path.join(data_dir, filename)
    # Save the data to the JSON file
    with open(filepath, "w") as f:
           json.dump(data, f, indent=4)
    logger.debug(f"DEBUG: Data saved to {filepath}")

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
def save_game_data(game_data):
    """Saves the game data to a JSON file."""
    try:
        with open("stats/testgames/game_data.json", "r") as f:
            all_games = json.load(f)
    except FileNotFoundError:
        all_games = []
    all_games.append(game_data)
    with open("stats/testgames/game_data.json", "w") as f:
        json.dump(all_games, f, indent=4)

def save_lynch_data(lynch_data):
    """Saves the game data to a JSON file."""
    try:
        with open("stats/testgames/lynch_data.json", "r") as f:
            all_games = json.load(f)
    except FileNotFoundError:
        all_games = []
    all_games.append(lynch_data)
    with open("stats/testgames/lynch_data.json", "w") as f:
        json.dump(all_games, f, indent=4)

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
    for player_id, player_data in players.items():
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

async def assign_game_roles(bot, players, game_roles, message_send_delay):  # bot needed!
    """Assigns roles to players randomly based on the chosen setup."""
    global roles
    # Shuffle the player IDs and roles
    player_ids = list(players.keys())
    random.shuffle(player_ids)
    random.shuffle(game_roles)
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
            logger.warning(
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
                uses=role_data.get("uses"),
            )
            game_roles.append(game_role)
    logger.info("Game Roles Created")

# --- Helper Functions ---
def get_time_left_string(end_time):
    """
    Calculates the time remaining until the given end_time.
    Returns a formatted string of the remaining time in hours and minutes, or "Time's up!".
    """
    logger.debug("DEBUG: get_time_left_string has been called")
    if end_time is None:
        logger.error("Get_time_left_string has no end time given")
        return "Unknown"
    now = datetime.now(timezone.utc)
    time_left = end_time - now
    logger.info(f"time_left = {time_left}")
    if time_left.total_seconds() <= 0:
        return "Time's up!"
    hours = int(time_left.total_seconds() // 3600)
    minutes = int((time_left.total_seconds() % 3600) // 60)
    logger.info(f"DEBUG: hours left = {hours} and minutes {minutes}")
    if hours > 0:
        return f"{hours} hours {minutes} minutes"
    else:
        return f"{minutes} minutes"

def generate_status_message(players):
    global current_phase, time_left, phase_number, time_day_ends, time_night_ends, time_signup_ends
    """Generates the game status message."""
    logger.info(
        f"DEBUG: generate_status_message called\n"
        f"The current phase is {current_phase} - {phase_number}"
    )
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
    status_message += f"**Players:**\n"
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
    logger.info(f"DEBUG: Status message generated: {status_message}")
    return status_message

def create_godfather_role():
    """Creates a new Godfather role object."""
    return GameRole(
        name="Godfather",
        alignment="Mafia",
        short_description="Chooses the Mafia's target each night.",
        description="Chooses the Mafia's target each night. \n Use _/kill player-name_ in this DM with the bot to kill your chosen player. \n",
        night_action=None,
    )

async def list_assigned_roles():
    """
    Lists all assigned roles in the game and sends the list to a specified channel.

    Args:
        bot: The discord.ext.commands.Bot instance.
        channel_id: The ID of the channel to send the list to.
    """
    logger.info("list_assinged_roles called")
    global players
    # Build a set of unique role and alignment combinations
    assigned_roles = set()
    for player_data in players.values():
        if player_data.get("role"):  # Safely check if role is assigned
            role = player_data["role"]
            assigned_roles.add(f"**{role.alignment}** - {role.name} - _{role.short_description}_")  # Combine alignment and name
    if not assigned_roles:
        role_list_message = "No roles have been assigned yet."  # Should not happen, but good to check
        logger.error("No Roles have been assigned")
        return role_list_message
    # Sort list alphabetically
    logger.info(f"Role list: {assigned_roles}")
    # Create a formatted string of the assigned roles
    role_list_message = "**\nAssigned Roles in this Game:**\n"
    role_list_message += "\n".join(f"- {role_name}" for role_name in sorted(assigned_roles))
    logger.info(f"Role list: {role_list_message}")
    return(role_list_message)

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
    logger.info(f"DEBUG: gameprocess is running {gameprocess.is_running}")
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
    while len(players) < 7:
        npc_name = random.choice(npc_names)
        npc_id = -(npc_names.index(npc_name) + 1)
        players[npc_id] = {
            "name": npc_name,
            "display_name": npc_name,
            "role": None,
            "alive": True,
            "votes": 0,
            "action_target": None,
        }
        logger.info(f"NPC {npc_name} added")
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
    save_json_data(game_data, f"game_{game_id}")
    logger.info(f"DEBUG: Stat files created... assigning {len(players)} roles...")
    # Generate and assign roles
    await generate_game_roles(len(players))
    if game_roles:
        await assign_game_roles(bot, players, game_roles, message_send_delay)
        logger.info("DEBUG: Roles assigned")
        role_list_message = await list_assigned_roles()
        ruleschannel = bot.get_channel(config.RULES_AND_ROLES_CHANNEL_ID)
        storychannel = bot.get_channel(config.STORIES_CHANNEL_ID)
        await ruleschannel.send("\n \n -------- **NEW GAME STARTING** -------- \n \n"
                           f"Each phase will be {phase_hours} hours long. \n\n" 
                           "**Roles have been assigned, starting game!**\n\n")
        await ruleschannel.send("------ **Role List** ---------\n\n"
                                f"{role_list_message}\n\n"
                                )
        await storychannel.send("\n \n -------- **NEW GAME STARTING** -------- \n \n")
        logger.info("DEBUG: Sending DM to all mafia players")
        await send_mafia_info_dm(bot,players, message_send_delay)
        # await start_game_night(bot, role_data, injokes, no_injoke) #Removed until game logic added
        # Create initial game data
        logger.info(f"Ready to start, gameprocess.is_running = {gameprocess.is_running}")
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
    logger.info(f"DEBUG: Target is {lynch_target}")
    lynch_target_id = await get_player_id_by_name(lynch_target, players)
    target_alive = await is_player_alive(lynch_target_id,players)
    logger.info(f"DEBUG: target {lynch_target_id} alive => {target_alive}")
    logger.info(f"DEBUG: Lynch Target ID => {lynch_target_id}")
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
    logger.info(f"DEBUG: Lynch votes after /vote -> {lynch_votes}")

async def countlynchvotes(bot, players):
    global lynch_votes, current_phase, phase_number, game_id
    lynched_players = []
    max_votes = 0
    total_phases = (phase_number * 2) - (1 if current_phase == "night" else 0)
    if current_phase != "Day":
        logger.error("DEBUG: tally_votes called outside of day phase. Skipping.")
        logger.error(f"DEBUG: Current phase is {current_phase} - {phase_number}")
        return
    else:
        logger.info(f"DEBUG: Current Lynch list: {lynch_votes}")
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
        await voting_channel.send("No votes were cast.")
        await story_channel.send("Everyone stood around and looked at each other. Shrugging they went back to their houses.\n **No one was lynched**")
    else:
        status_message = "**Voting Results:**\n"
        for player_id, vote_data in lynch_votes.items():
            player_name = players[player_id]["name"]
            voters = vote_data["voters"]
            voter_list = ", ".join([players[voter_id]["name"] for voter_id in voters])
            status_message += f"- {player_name}: {vote_data['total_votes']} votes ({voter_list})\n"
        await voting_channel.send(status_message)

    # Process lynchings
    if lynched_players:
        for lynched_player_id in lynched_players:
            lynched_player_data = players[lynched_player_id]
            lynched_player_name = lynched_player_data["name"]
            lynched_player_role = lynched_player_data["role"].name
            lynched_player_faction = lynched_player_data["role"].alignment
            await story_channel.send(f"The town gathered as the sun went down to lynch **{lynched_player_name}, the {lynched_player_role} from {lynched_player_faction}!**")
            # Mark the player as dead
            players[lynched_player_id]["alive"] = False
            logger.info(f"DEBUG: Marked lynched player as dead")
            # Mark the player as dead and record how
            players[lynched_player_id]["alive"] = False
            players[lynched_player_id]["death_info"] = {
            "phase": f"{current_phase} {phase_number}",
            "phase num": f"{phase_number}",
            "total phases": f"{total_phases}",
            "how": "Lynched",
            "voters": f"{voter_list}"
                }
            # Announce the player's role
            if lynched_player_id > 0 and lynched_player_data["role"]:  # only show role for non-npc and they have a role
                lynched_player_role = lynched_player_data["role"].name
                await voting_channel.send(f"{lynched_player_name}'s role was: {lynched_player_role}")
    else:
        await voting_channel.send("No one was lynched.")
    lynch_data = {
    "game_id": game_id,
        "phase": current_phase,
        "phase_num": phase_number,
        "lynch votes": lynch_votes  
    }
    save_lynch_data(lynch_data)

async def send_vote_update(bot,players):
    """
    Creates and sends a message to the voting channel with the current lynch vote status.
    """
    global current_phase, phase_number
    voting_channel = bot.get_channel(config.VOTING_CHANNEL_ID)
    logger.info(f"DEBUG: Current phase is {current_phase}- {phase_number}")
    logger.info("DEBUG: Send_vote_update called...")
    if current_phase != "Day":
        await voting_channel.send("Vote counting is only available during the day phase.")
        logger.info(f"DEBUG: Current phase is {current_phase}")
        return
    # Tally votes (ensure lynch_votes is updated before calling this function)
    vote_counts = {}
    voters = {}  # Dictionary to track who voted for whom
    for player_id, player_data in players.items():
        target_id = player_data["action_target"]
        logger.info(f"DEBUG: {player_id} -> target_id: {target_id}")
        if target_id is not None and player_data["alive"]:
            if target_id not in vote_counts:
                vote_counts[target_id] = 0
            vote_counts[target_id] += 1
            # Add voter to the list of voters for the target
            if target_id not in voters:
                voters[target_id] = []
            voters[target_id].append(player_data["name"])
    # Prepare the message content
    message_content = "**Current Lynch Vote:**\n"
    logger.info(f"DEBUG: Current message content == {message_content}")
    logger.info(f"DEBUG: vote counts: {vote_counts}")
    if not vote_counts:
        message_content += "No votes yet.\n"
        logger.error(f"DEBUG: Current message content == {message_content}")
    else:
        logger.info(f"DEBUG: {vote_counts}")
        for player_id, vote_count in vote_counts.items():
            logger.info(f"DEBUG: PlayerID: {player_id}")
            if player_id is None or player_id == "":
                logger.error("No id")
            else:
                player_data = players[player_id]
                player_name = player_data["name"]
                voter_list = ", ".join(voters[player_id])
                message_content += f"- {player_name}: {vote_count} vote(s) - {voter_list}\n"
                logger.info(f"DEBUG: Current message content == {message_content}")
    # Find players who haven't voted
    not_voted = [
        player_data["name"]
        for player_id, player_data in players.items()
        if player_data["alive"] and player_data["action_target"] is None
    ]
    if not_voted:
        message_content += "\n**Players who haven't voted yet:**\n"
        message_content += ", ".join(not_voted) + "\n"
        logger.error(f"DEBUG: Current message content == {message_content}")
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
                    "phase num": f"{phase_number}",
                    "total phases": f"{total_phases}",
                    "how": "Killed by Mob",
                    }
        logger.info("The game was won by the Mafia after the SK died and Mafia outnumbered Town")
        return "Mafia"      # Mafia wins if they equal or outnumber Town and SK is dead
    
    elif living_mafia == 0 and living_neutral == 0 and living_town > 0:
        logger.info("The game was Won by the Town as they were the only people left")
        return "Town"       # Town wins if no Mafia or Neutral players are alive
    
    elif current_phase == "Day" and living_mafia == 1 and living_town == 1 and living_neutral == 0:
        for player_id, player_data in players.items():
            if player_data["alive"] == True:
                total_phases = ((phase_number * 2) - (1 if current_phase == "Night" else 0) - 1)
                players[player_id]["alive"] = False
                players[player_id]["death_info"] = {
                    "phase": f"{current_phase} {phase_number}",
                    "phase num": f"{phase_number}",
                    "total phases": f"{total_phases}",
                    "how": "Lynched",
                    } 
        logger.info("The game was a draw as only 2 people left at start of day from mafia and town")
        return "Draw"
    
    elif current_phase == "Day" and living_mafia == 1 and living_neutral == 1 and living_town == 0:
        for player_id, player_data in players.items():
            if player_data["alive"] == True:
                total_phases = ((phase_number * 2) - (1 if current_phase == "Night" else 0) - 1)
                players[player_id]["alive"] = False
                players[player_id]["death_info"] = {
                    "phase": f"{current_phase} {phase_number}",
                    "phase num": f"{phase_number}",
                    "total phases": f"{total_phases}",
                    "how": "Lynched",
                    } 
        logger.info("The game was a draw as only 2 people left at start of day from SK and town")
        return "Draw"
    
    elif current_phase == "Night" and living_neutral == 1 and living_town == 1 and living_mafia == 0:
        for player_id, player_data in players.items():
            if player_data["alive"] == True and player_data["role"].alignment == "Town":
                total_phases = ((phase_number * 2) - (1 if current_phase == "Night" else 0) - 1)
                players[player_id]["alive"] = False
                players[player_id]["death_info"] = {
                    "phase": f"{current_phase} {phase_number}",
                    "phase num": f"{phase_number}",
                    "total phases": f"{total_phases}",
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
                    "phase num": f"{phase_number}",
                    "total phases": f"{total_phases}",
                    "how": "Lynched",
                    } 
        logger.info("The game was a draw as only 2 people left at start of day from mafia and SK")
        return "Draw"
    
    elif current_phase == "Night" and living_mafia == 1 and living_town == 1 and living_neutral == 0:
        for player_id, player_data in players.items():
            if player_data["alive"] == True and player_data["role"].alignment == "Town":
                total_phases = ((phase_number * 2) - (1 if current_phase == "Night" else 0) - 1)
                players[player_id]["alive"] = False
                players[player_id]["death_info"] = {
                    "phase": f"{current_phase} {phase_number}",
                    "phase num": f"{phase_number}",
                    "total phases": f"{total_phases}",
                    "how": "Killed by Mafia",
                    } 
        logger.info("The game was won by Mob as only mob and 1 town alive at start of night - SK will kill last town overnight")
        return "Mafia"
    
    elif current_phase == "Night" and living_mafia == 1 and living_neutral == 1 and living_town ==0:
        for player_id, player_data in players.items():
            if player_data["alive"] == True and player_data["role"].alignment == "Mafia":
                total_phases = ((phase_number * 2) - (1 if current_phase == "Night" else 0) - 1)
                players[player_id]["alive"] = False
                players[player_id]["death_info"] = {
                    "phase": f"{current_phase} {phase_number}",
                    "phase num": f"{phase_number}",
                    "total phases": f"{total_phases}",
                    "how": "Killed by SK",
                    } 
        logger.info("SK wins if they and 1 mob left at start of night as they kill first")
        return "Serial Killer" #SK wins if they and 1 mob left at start of night as they kill first
    else:
        logger.info("No winner found")
        return None  # No winner yet 
 
async def announce_winner(bot, winner):
    """Announces the winner and resets the game."""
    global game_started, phase_number, current_phase, discord_role_data, players,game_id, gameprocess
    # Send announcement to the stories channel
    #await generate_narration(bot, f"Game Over! The **{winner}** team wins!")
    channel = bot.get_channel(config.STORIES_CHANNEL_ID)
    if winner != "Draw":
        winning_players = []
        for player_id, player_data in players.items():
            if player_data["role"].alignment == winner:
                winning_players.append(f"<@{player_id}>")
        if winning_players:
            winners = ", ".join(winning_players)
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
    game_data = {
        "game_id": game_id,
        "total_phases": (phase_number * 2) - (1 if current_phase == "night" else 0),
        "winner": winner,
        "players": [
            {
                "player_id": player_id,
                "name": player_data["name"],
                "role": player_data["role"].name if player_data["role"] else "None",
                "alignment": player_data["role"].alignment
                if player_data["role"]
                else "N/A",
                "status": "Alive" if player_data["alive"] else "Dead",
                "won": winner == "Town"
                if player_data["role"].alignment == "Town"
                else winner == "Mafia"
                if player_data["role"].alignment == "Mafia"
                else winner == "Neutral"
                if player_data["role"].alignment == "Neutral"
                else "Draw",
                "death_phase": player_data.get("death_info", {}).get("phase"),
                "death_cause": player_data.get("death_info", {}).get("how"),
                "phases_lasted": player_data.get("death_info", (phase_number * 2) - (1 if current_phase == "night" else 0)),
                #"votes": game_votes.get(player_id, {}).get("votes", []),
            }
            for player_id, player_data in players.items()
        ],
    }
    save_game_data(game_data)  # Save to JSON file
    # Reset game variables
    game_started = False  # Allow new games to be started
    gameprocess.stop()

async def process_sk_night_kill(bot, target_id):
    global current_phase, phase_number, players
    total_phases = (phase_number * 2) - (1 if current_phase == "night" else 0)
    sk_player_id = get_specific_player_id(players, "Serial Killer")
    if sk_player_id is None:
        logger.error("DEBUG: No living Serial Killer found. Skipping SK night kill process.")
        return
    sk_player_action_target = players[sk_player_id]["action_target"]
    # Check if a Serial Killer was found before proceeding
    if sk_player_id > 0:
        sk_player = await bot.fetch_user(sk_player_id)
        try:
            if target_id is None:
                logger.error("DEBUG: No target selected for SK. Skipping kill process.")
                await sk_player.send("You did not select a target for the night kill.")
                return
            if target_id not in players:
                logger.error(f"DEBUG: Invalid target ID {target_id} for SK. Skipping kill process.")
                await sk_player.send(f"Invalid target for the night kill. Target player is not in the game.")
                return
            if not players[target_id]["alive"]:
                logger.error("DEBUG: Target player for SK is already dead. Skipping kill process.")
                await sk_player.send("Target player for the night kill is already dead.")
                return
            # Target is valid, proceed with the kill process
            story_channel = bot.get_channel(config.STORIES_CHANNEL_ID)
            logger.info(f"DEBUG: SK killed {target_id}")

            # If target is not the godfather then mark the player as dead and record how
            if players[target_id]["role"].name != "Godfather" and players[target_id]["role"].name != "Serial Killer" :
                players[target_id]["alive"] = False
                players[target_id]["death_info"] = {
                    "phase": f"{current_phase} {phase_number}",
                    "phase_num": f"{phase_number}",
                    "total_phases": f"{total_phases}",
                    "how": "Killed by SK"
                }
                # Announce the player's death
                target_name = players[target_id]["name"]
                target_role = players[target_id]["role"].name
                target_faction = players[target_id]["role"].alignment
                await story_channel.send(f"**{target_name} was killed by the SK!**")
            #clear SK player action target
            players[sk_player_id]["action_target"] = ""
            logger.debug(f"DEBUG: SK action_target = {players[sk_player_id]["action_target"]}")
        except discord.Forbidden:
            logger.error(f"Could not send DM to Serial Killer due to their privacy settings.")
        except Exception as e:
            logger.error(f"An error occurred while sending DM to Serial Killer: {e}")
    else:
        logger.error("DEBUG: No living Serial Killer found.")

async def process_mafia_night_kill(bot,target_id):
    global current_phase, phase_number, players
    total_phases = (phase_number * 2) - (1 if current_phase == "night" else 0)
    mob_gf_id = get_specific_player_id(players,"Godfather")
    if mob_gf_id is None:
        mob_goon_id = get_specific_player_id(players,"Mob Goon")
        logger.error("DEBUG: No living Godfather found. Skipping Mafia night kill process.")
        logger.info(f"DEBUG: Promoting Mob Goon to Godfather")
        if mob_goon_id is None:
            logger.error("Debug: All mob are dead")
            return
        players[mob_goon_id]["role"] = create_godfather_role()
        if mob_goon_id > 0:
            mob_goon_player = await bot.fetch_user(mob_goon_id)
            logger.info("Promoted Mob Good to Mob Godfather")
            try:
                await mob_goon_player.send(f"Your Godfather has been killed, you are the Godfather Now\n\n {players[mob_goon_id]["role"].description}")
            except discord.Forbidden:
                logger.error(f"Could not send DM to promoted Godfather.  User has DMs disabled.")
            except discord.HTTPException as e:
                logger.error(f"HTTP Error sending DM to promoted Godfather: {e}")
            except Exception as e:
                logger.exception(f"Unexpected error promoting Godfather: {e}")
        return
    gf_player_action_target = players[mob_gf_id]["action_target"]
    logger.info(f"Players == {players}")
    # Check if a Godfather was found before proceeding
    if mob_gf_id > 0:
        if bot:
            mob_gf_player = await bot.fetch_user(mob_gf_id)
            try:
                if target_id is None:
                    logger.error("DEBUG: No target selected for Mob. Skipping kill process.")
                    await mob_gf_player.send("You did not select a target for the night kill.")
                    return
                if target_id not in players:
                    logger.error(f"DEBUG: Invalid target ID {target_id} for Mob kill. Skipping kill process.")
                    return
                if not players[target_id]["alive"]:
                    logger.error("DEBUG: Target player for Mob is already dead. Skipping kill process.")
                    await mob_gf_player.send("Target player for the night kill is already dead.")
                    return
            except discord.Forbidden:
                logger.error(f"Could not send DM to mob GF due to their privacy settings.")
            except Exception as e:
                logger.error(f"An error occurred while sending DM to mob GF: {e}")
    else:
        logger.error("DEBUG: No living Godfather found.")
    if target_id is None or target_id == "":  
        logger.error("DEBUG: No target")
    else:    # only show role for non-npc
            story_channel = bot.get_channel(config.STORIES_CHANNEL_ID)
            logger.debug(f"DEBUG: Mob killed {target_id}")
            # Mark the player as dead and record how
            if players[target_id]["role"].name != "Godfather" and players[target_id]["role"].name != "Serial Killer" :
                players[target_id]["alive"] = False
                players[target_id]["death_info"] = {
                        "phase": f"{current_phase} {phase_number}",
                        "phase num": f"{phase_number}",
                        "total phases": f"{total_phases}",
                        "how": "Killed by Mob"
                    }    
                # Announce the player's role
                target_name = players[target_id]["name"]
                await story_channel.send(f"**{target_name} was killed by the Mob!**")
    players[mob_gf_id]["action_target"] = ""
    logger.debug(f"DEBUG: Mob GF action_target = {players[mob_gf_id]["action_target"]}")
    return 

async def process_doc_night_heal(bot, target_id): #pass in bot and target_id variables
    """Processes the Doctor's night heal action."""
    # Declare global variables so can determine current phase (day/night), phase number (to determine ifa dead player should be healed) and the players dictonary 
    global current_phase, phase_number, players

    #Check if /heal is used during night phase
    if current_phase != "Night":
        logger.error("DEBUG: Doctor heal action attempted outside of night phase.")
        #if the current phase is not night then log the error and exit the function
        return
    # Check if the target is already dead from a previous phase
    if players[target_id]["alive"] == False:
        # If the target player has been set to dead
        death_info = players[target_id].get("death_info")
        # Then first get the death_info dictonary attached to that target player
        if death_info:
            # If there is some death info attached
            death_phase_num = death_info.get("phase_num")
            # Determine what phase the player died
            if death_phase_num < phase_number:
                # If the death phasenumber stored in the death info is less than the current phase then the target cannot be revived
                logger.info(
                    "DEBUG: Target player for Doctor heal is already dead from a previous phase. Skipping action."
                )
                await town_doc_player.send(
                    "Target player for the night heal is already dead."
                )
                # Log error and inform player before exiting function
                return
        # However, if Target is valid, proceed with heal
        story_channel = bot.get_channel(config.STORIES_CHANNEL_ID) # Get story channel id
        target_name = players[target_id]["name"] # get the name of the player being revived
        logger.info(f"DEBUG: Town Doctor heals {target_name}") #log who the doctor is healing
        # If target was previously dead, revive them
        players[target_id]["alive"] = True
        players[target_id]["death_info"] = {
                    "phase": None,
                    "phase num": None,
                    "total phases": None,
                    "how": None
                }    
        # Send info to story channel
        await story_channel.send(f"**Town Doctor found {target_name} and revived them!**")
    else:
        #if the player wasn't dead then just log the fact that the doctor tried to heal them
        logger.debug(f"**Town Doctor protected {target_name} from harm.**")
    #
    town_doc_id = get_specific_player_id(players, "Doctor")
    if town_doc_id is None:
        logger.error("DEBUG: No living doctor found. Skipping doc night heal process.")
        return
    # Fetch the Doctor's user object for sending DMs
    town_doc_player = await bot.fetch_user(town_doc_id)
    if target_id is None:
        logger.error("DEBUG: No target selected for Doctor heal. Skipping action.")
        await town_doc_player.send("You did not select a target to heal.")
        return
    if target_id not in players:
        logger.error(f"DEBUG: Invalid target ID {target_id} for Doctor heal. Skipping action.")
        await town_doc_player.send(f"Invalid target for the night heal. Target player is not in the game.")
        return
    # --- Doctor Self-Revive Logic ---
    # Check if the *doctor* is dead, AND the target is the doctor:
    if not players[town_doc_id]["alive"] and target_id == town_doc_id:
        logger.info("DEBUG: Doctor is dead and targeted themselves. Reviving Doctor.")
        players[town_doc_id]["alive"] = True  # Revive the doctor
        story_channel = bot.get_channel(config.STORIES_CHANNEL_ID)
        await story_channel.send("**Town Doctor managed to revive themselves....**")
        return # VERY important, stop the rest of the logic.
                       
async def process_cop_night_investigate(bot, target_id):
    """Processes the Cop's night investigation action."""
    global current_phase, phase_number, players

    if current_phase != "night":
        logger.warning("Cop investigation attempted outside of night phase.")
        return
    town_cop_id = get_specific_player_id(players, "Town Cop")
    if town_cop_id is None:
        logger.debug("No living Town Cop found. Skipping investigation.")
        return
    town_cop_player = await bot.fetch_user(town_cop_id)
    if target_id is None:
        logger.debug("No target selected for Cop investigation. Skipping.")
        try:
            await town_cop_player.send("You did not select a target for the investigation.")
        except discord.Forbidden:
            logger.error(f"Could not send DM to Town Cop due to their privacy settings.")
        except Exception as e:
            logger.error(f"An error occurred while sending DM to Town Cop: {e}")
        return
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
    # Target is valid, proceed with investigation.
    target_name = players[target_id]["display_name"]  # Use display_name
    target_role = players[target_id]["role"].name
    target_alignment = players[target_id]["role"].alignment # Get alignment
    target_short_desc = players[target_id]["role"].short_description
    logger.debug(f"Town Cop investigates {target_name} (ID: {target_id}), Role: {target_role}, Alignment: {target_alignment}")
    try:
        await town_cop_player.send(f"You investigated {target_name}.  Their role is: {target_role} ({target_short_desc}).  Their alignment is: {target_alignment}.")
    except discord.Forbidden:
        logger.error(f"Could not send investigation result to Town Cop ({town_cop_player.name}) due to their privacy settings.")
    except Exception as e:
        logger.error(f"An error occurred while sending investigation result to Town Cop ({town_cop_player.name}): {e}")

def clear_actions(players):
    """Clears the 'action_target' for all players in the game."""
    for player_id, player_data in players.items():  # Iterate through items()
        player_data["action_target"] = None  # Set to None, not an empty string

# --- Bot Event ---
@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user.name}")

# --- Bot Commands ---
@bot.command(name="startmafia")
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
        return
    # Check if the provided start_datetime is in the future
    if time_signup_ends < datetime.now(timezone.utc):
        await ctx.send("The provided start time is in the past. Please provide a future date and time.")
        logger.error("The provided start time is in the past. Please provide a future date and time.")
        return
    # Calculate join_hours based on the difference between now and start_datetime
    join_hours = round((time_signup_ends - datetime.now(timezone.utc)).total_seconds() / 3600, 2)
    logger.info(f"DEBUG: New game started with join hours {join_hours}")
    channel = bot.get_channel(config.TALKY_TALKY_CHANNEL_ID)
    await channel.send( f"Sign-ups are now open for {join_hours} hours! Use `/join [name]` in the <#{config.SIGN_UP_HERE_CHANNEL_ID}> channel to join the game.\n "
                        f"Game will start at: {time_signup_ends.strftime('%Y-%m-%d %H:%M:%S UTC')}.\n\n"
                        )
    channel = bot.get_channel(config.SIGN_UP_HERE_CHANNEL_ID)
    await channel.send( f"Sign-ups are now open for {join_hours} hours! Use `/join [name]` in the <#{config.SIGN_UP_HERE_CHANNEL_ID}> channel to join the game.\n"
                        f"Game will start at: {time_signup_ends.strftime('%Y-%m-%d %H:%M:%S UTC')}.\n\n"
                        )
    channel = bot.get_channel(config.RULES_AND_ROLES_CHANNEL_ID)
    await channel.send( "--- ** New Basic Bitch Game open for signups ** ---\n"
                        f"Sign-ups are now open for {join_hours} hours! Use `/join [name]` in the <#{config.SIGN_UP_HERE_CHANNEL_ID}> channel to join the game.\n"
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

@bot.command(name="join")
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
    if current_phase == "":
        players[player_id] = {
            "name": ctx.author.name,
            "display_name": ctx.author.display_name,
            "role": None,
            "alive": True,
            "votes": 0,
            "action_target": None,
        }
        # Update discord roles
        guild = ctx.guild
        await update_player_discord_roles(bot,guild, players, discord_role_data)
        logger.info(f"DEBUG: Player joined: {ctx.author.name} (ID: {player_id}). Players: {players}")
        await ctx.send(
            f"{ctx.author.mention} has joined the game!"
        )
        # If we have reached 7 players, start the game
        if len(players) >= 7:
            await ctx.send("We have reached 7 players! The game will start in advance to the end of the signup phase.")
            logger.critical("We have reached 7 players! The game will start in advance to the end of the signup phase.")
            await prepare_game_start(ctx, bot, npc_names)
    else:
       await ctx.author.send("You cannot join an active game, please wait for the game to finish and join the next game!")  
       logger.info(f"{player_id} tried to join an active game")  
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

@bot.command(name="stop")
@commands.check(is_owner_or_mod(bot, discord_role_data))
@commands.has_role(discord_role_data.get("mod", {}).get("id"))
async def stop_game(ctx):
    """Stops the current game."""
    global game_started, time_signup_ends, players, gameprocess
    if not game_started:
        await ctx.send("No game is currently running.")
        logger.error("No game is currently running.")
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
    await update_player_discord_roles(bot, guild, players, discord_role_data)
    reset_game()
    await ctx.send("The current game has been stopped.")
    logger.info(f"DEBUG: Game stopped.")

@bot.command(name="status")
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
    logger.info(f"DEBUG: Target for lynch = {target_id}")
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
        logger.info(f"DEBUG: Sending data to process_lynch_vote: {ctx}, {player_id}, {lynch_target}")
        await process_lynch_vote(player_id, lynch_target)
        await send_vote_update(bot, players)  # Send vote update after each vote
    else:
        logger.error(f"Player {player_id} tried to vote for dead player {target_id}")
        ctx.send("You can not vote for a dead player") 

@bot.command(name = "count")
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
    allowed_roles = ["Godfather", "Serial Killer"]
    if player_data["role"].name not in allowed_roles:
        await ctx.author.send("You do not have the required role to use this command.")
        logger.error(f"Player {player_id} does not have the required role to use this command.")
        return
    if not kill_target:  # Check if target_name is empty
        await ctx.author.send("You must specify a target to kill.")
        logger.error(f"Player {player_id} used /kill with no target")
        return
    target_id = await get_player_id_by_name(kill_target, players)
    logger.info("DEBUG: target input has been converted to ID")
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
    if player_data["role"].name == "Godfather":
        mob_target = target_id
        await ctx.author.send(f"Godfather has selected {players[target_id]['name']} as the target.")
        logger.info(f"Godfather used /kill on {target_id}")
    elif player_data["role"].name == "Serial Killer":
        sk_target = target_id
        await ctx.author.send(f"Serial Killer has selected {players[target_id]['name']} as the target.")
        logger.info(f"SK used /kill on {target_id}")
    await ctx.author.send(f"You have chosen to kill {players[target_id]['display_name']}.")
    players[player_id]["action_target"]=target_id
    logger.info(f"Players: {players}")
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
    allowed_roles = ["Town Doctor"]  # Add other roles if needed
    if player_data["role"].name not in allowed_roles:
        await ctx.author.send("You do not have the required role to use this command.")
        logger.error(f"Player {player_id} does not have the required role")
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
    # Rest of the command logic for players with the correct role
    heal_target = target_id
    players[player_id]["action_target"] = target_id
    await ctx.author.send(f"You have chosen to heal {players[target_id]['name']}.")
    logger.info(f"Doctor healed {heal_target}")
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
    allowed_roles = ["Town Cop"]
    if player_data["role"].name not in allowed_roles:
        await ctx.author.send("You do not have the required role to use this command.")
        logger.error(f"Player {player_id} tried to use /investigate when not the cop role")
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
    investigate_target = target_id
    players[player_id]["action_target"] = target_id
    await ctx.author.send(f"You have chosen to investigate {players[target_id]['name']}.")
    logger.info(f"Player {player_id} targeted {target_id}")
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

@bot.command(name="info")
async def show_info(ctx):
    """Shows the list of available commands."""
    info_text = (
        "**Available Commands:**\n\n"
        "**Player Commands:**\n"
        "- `/join <name>` : Joins the upcoming game. Enter your game name as a parameter, which can be used during the game\n"
        "- `/status`: Displays the current game status. Will show game names of all signed up players\n"
        "- `/vote <@player>`: Casts a vote during the day phase. Use either the players game name or discord ID (@name) to target\n"
        "- `/count`: Displays the current vote count.\n"
        "- `/rules`: Displays the rules of the game.\n"
        "- `/info`: Shows this help message.\n"
        "- `/leave : Allows you to leave a game during setup phase only - Once a game starts you cannot use this function\n"
        " \n\n**Player Actions**\n"
        "- `/kill <@player>` (Godfather & Serial Killer only, DM only): Selects a player to be killed by the Mafia.\n"
        "- `/heal <@player>` (Doctor only, DM only): Selects a player to be healed.\n"
        "- `/investigate <@player>` (Town Cop only, DM only): Investigates a player's role.\n"
        "\n\n**Moderator Commands:**\n"
        "- `/startmafia <start_datetime>  [phase_hours]`:  Starts a new game at the specified time. Date/time format: `YYYY-MM-DD HH:MM` (UTC).\n"
        "- `/stop`: Stops the current game.\n"
    )
    await ctx.send(info_text)
    logger.info("/info was called")

@bot.command(name="rules")
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

@bot.command(name="leave")
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

@bot.command(name="remove")
@commands.check(is_owner_or_mod(bot, discord_role_data))  # Use your custom check
@commands.has_role(discord_role_data.get("mod", {}).get("id"))
async def kick_player(ctx, *, player_name: str):
    """Kicks a player from the game (Mod Only).

    Args:
        ctx: The command context.
        player_name: The name or mention of the player to kick.
    """
    global players, current_phase

    logger.info("Remove command called")
    target_id = await get_player_id_by_name(player_name)
    logger.info(f"Target for removal is {target_id}")
    if target_id is None:
        await ctx.send(f"Could not find a player named '{player_name}'.")
        logger.error(f"Could not find a player named '{player_name}'.")
        return
    if target_id not in players:
        await ctx.send(f"Player '{player_name}' is not in the current game.")
        logger.error(f"Player '{player_name}' is not in the current game.")
        return
    target_data = players[target_id]
    target_name = target_data["name"]
    logger.info(f"Target for removal is {target_name} in current phase {current_phase}")
    if current_phase == "":  # Sign-up phase
        # Remove the player from the game
        del players[target_id]
        logger.info(f"Deleting player {target_id}")
        # Remove roles
        if target_id > 0:
            guild = ctx.guild
            member = guild.get_member(target_id)
            if member:
                living_role_id = discord_role_data.get("living", {}).get("id")
                dead_role_id = discord_role_data.get("dead", {}).get("id")
                spectator_role_id = discord_role_data.get("spectator", {}).get("id")
                living_role = discord.utils.get(guild.roles, id=living_role_id)
                dead_role = discord.utils.get(guild.roles, id=dead_role_id)
                spectator_role = discord.utils.get(guild.roles, id=spectator_role_id)
                await member.remove_roles(living_role, dead_role)  # Remove both, just in case
                await member.add_roles(spectator_role)  # Add back spectator
            await ctx.send(f"{target_name} has been removed from the game.")
        logger.info(f"DEBUG: Player {target_name} (ID: {target_id}) removed during sign-up.")
    else:  # Game is in progress (Day or Night)
        if not target_data["alive"]:
            await ctx.send(f"{target_name} is already dead.")
            logger.error(f"{target_name} is already dead.")
            return
        # Mark the player as dead
        target_data["alive"] = False
        target_data["death_info"] = {
            "phase": f"{current_phase} {phase_number}",
            "phase_num": phase_number,
            "how": "Mod Kill",
        }
        # Update roles
        if target_id >0 :
            guild = ctx.guild
            await update_player_discord_roles(bot, guild, players, discord_role_data)
            # Send message to stories channel
            story_channel = bot.get_channel(config.STORIES_CHANNEL_ID)
            await story_channel.send(f"**{target_name} has been mod-killed!**")
            await ctx.send(f"{target_name} has been mod-killed.")
        logger.info(f"DEBUG: Player {target_name} (ID: {target_id}) mod-killed during {current_phase} phase.")
@kick_player.error
async def kick_player_error(ctx, error):
  if isinstance(error, commands.MissingRequiredArgument):
    await ctx.send("You need to provide a player's name to use the `/kick` command.")

# --- Game Loop ---
@tasks.loop(seconds = 1)
async def gameprocess(ctx,bot,players):
    global phase_number, current_phase, lynch_votes, sk_target, mob_target, heal_target, investigate_target, time_night_ends, time_day_ends, message_send_delay
    if current_phase == "Night":
        #night phase
        if phase_number == 0:
            time_night_ends = time_signup_ends + timedelta(hours=LOOP_HOURS)
        else:
            time_night_ends = time_day_ends + timedelta(hours=LOOP_HOURS)
        phase_number += 1 
        logger.info(f"DEBUG: Starting {current_phase} - {phase_number} which will last {LOOP_HOURS} hours\n"
              "The town goes to sleep....\n")
        storychannel = bot.get_channel(config.STORIES_CHANNEL_ID)
        ruleschannel = bot.get_channel(config.RULES_AND_ROLES_CHANNEL_ID)
        await storychannel.send(f"Night {phase_number} has fallen. The town goes to sleep...")
        logger.info(f"DEBUG: Current time night ends = {time_night_ends}")
        status_message = generate_status_message(players)
        await ruleschannel.send(status_message)
        #future night time actions logic
        logger.info("Sleeping....")
        await asyncio.sleep(LOOP_HOURS*60*60)
        logger.debug(f"DEBUG: Targets... Sk target = {sk_target}, mob target = {mob_target}, doc target = {heal_target}, cop target = {investigate_target}")
        await asyncio.sleep(message_send_delay)
        logger.debug(f"DEBUG: SK Kill {sk_target}")
        logger.info("DEBUG: SK Kill")
        await process_sk_night_kill(bot, sk_target)
        await asyncio.sleep(message_send_delay)
        logger.debug(f"DEBUG: Mob Kill {mob_target}")
        logger.info("DEBUG: Mob Kill")
        await process_mafia_night_kill(bot, mob_target)
        await asyncio.sleep(message_send_delay)
        logger.debug(f"DEBUG: Doc Heal {heal_target}")
        logger.info("DEBUG: Town Doc Heal")
        await process_doc_night_heal(bot, heal_target)
        await asyncio.sleep(message_send_delay)
        logger.debug(f"DEBUG - Cop investigate {investigate_target}")
        logger.info("DEBUG: Town Cop Investigate")
        await process_cop_night_investigate(bot, investigate_target)
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
            current_phase = ""
            status_message = generate_status_message(players)
            await ruleschannel.send(status_message)
            reset_game()
            return  # End the game loop if there's a winner
        #recordphaseactions()
        clear_actions(players)
        logger.info(f"DEBUG: End of night phase, about to switch to day phase")
        current_phase = "Day"
        sk_target = None
        mob_target = None
        heal_target = None
        investigate_target = None
    else:
        #day phase
        logger.info(f"DEBUG: {current_phase} - {phase_number} has dawned which will last {LOOP_HOURS} hours.\n" 
              "The town awakens...")
        storychannel = bot.get_channel(config.STORIES_CHANNEL_ID)
        ruleschannel = bot.get_channel(config.RULES_AND_ROLES_CHANNEL_ID)
        votingchannel = bot.get_channel(config.VOTING_CHANNEL_ID)
        await storychannel.send(f"Day {phase_number} has dawned. The town awakens...")
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
        logger.info("DEBUG: Counting votes...")
        await countlynchvotes(bot,players)
        logger.info(f"DEBUG: The lynch results -> {lynch_votes} for {current_phase} - {phase_number}")
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
        #recordphaseactions()
        clear_actions(players)
        lynch_votes = {}
        current_phase = "Night"
        logger.info("DEBUG: Changed to night phase")

# --- Start the Bot ---
bot.run(config.BOT_TOKEN, log_handler=logger.handlers[0], log_level=logging.DEBUG) # Use new handler