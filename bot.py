import discord
import os
from discord.ext import commands, tasks
import asyncio
import json
from datetime import datetime, timedelta, timezone
import random
import config  # Assuming you have a config.py file with necessary settings
import logging

# --- Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=config.BOT_PREFIX, intents=intents)

#--- Log Setup ---
handler = logging.FileHandler(filename='.\Logs\discord.log', encoding='utf-8', mode='w')

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
    data_dir = os.path.join("stats", subdirectory)
    os.makedirs(data_dir, exist_ok=True)
    # Construct the full file path
    filepath = os.path.join(data_dir, filename)
    # Save the data to the JSON file
    with open(filepath, "w") as f:
           json.dump(data, f, indent=4)
    print(f"DEBUG: Data saved to {filepath}")

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

# --- Roles ---
class GameRole:
    def __init__(self, name, alignment, description, night_action=None, uses=None):
        self.name = name
        self.alignment = alignment
        self.description = description
        self.night_action = night_action
        self.uses = uses
    def __str__(self):
        return self.name

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
def is_owner_or_mod():
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
            await ctx.author.send("This command cannot be used in private messages. Please use it in the designated server channel.")
        return False
    return commands.check(predicate)

# --- Role Definitions ---
def generate_game_roles(num_players):
    """Generates a role setup based on the number of players."""
    global game_roles
    game_roles = []
    # Get the appropriate setup from mafia_setups.json
    setups = mafia_setups.get(str(num_players))
    if not setups:
        print(f"ERROR: No setup found for {num_players} players.")
        return
    # Select a random setup (for now, just the first one)
    setup = setups[0]
    # Create Role objects based on the setup
    for role_data in setup["roles"]:
        for _ in range(role_data["quantity"]):
            game_role = GameRole(
                name=role_data["name"],
                alignment=role_data["alignment"],
                description=role_data["description"],
                uses=role_data.get("uses"),
            )
            game_roles.append(game_role)

# --- Helper Functions ---
async def update_player_discord_roles(bot, guild, players, discord_role_data):
    """Updates player roles in Discord based on their status."""
    living_role_id = discord_role_data.get("living", {}).get("id")
    dead_role_id = discord_role_data.get("dead", {}).get("id")
    spectator_role_id = discord_role_data.get("spectator", {}).get("id")
    living_role = discord.utils.get(guild.roles, id=living_role_id)
    dead_role = discord.utils.get(guild.roles, id=dead_role_id)
    spectator_role = discord.utils.get(guild.roles, id=spectator_role_id)
    if not living_role or not dead_role or not spectator_role:
        print("ERROR: Could not find 'Living Players', 'Dead Players', or 'Spectator' role.")
        return
    for player_id, player_data in players.items():
        if player_id > 0:  # Check if it's not an NPC
            member = guild.get_member(player_id)
            if member:
                if player_data["alive"]:
                    await member.add_roles(living_role)
                    await member.remove_roles(dead_role, spectator_role)
                else:
                    await member.add_roles(dead_role)
                    await member.remove_roles(living_role, spectator_role)
    for member in guild.members:
        if member.id not in players and not member.bot:
            await member.add_roles(spectator_role)
            await member.remove_roles(living_role, dead_role)

def get_time_left_string(end_time):
    """
    Calculates the time remaining until the given end_time.
    Returns a formatted string of the remaining time or "Time's up!".
    """
    print(f"get_time_left_string called with end_time = {end_time}")
    if end_time is None:
        return "Unknown"
    now = datetime.now(timezone.utc)
    time_left = end_time - now
    if time_left.total_seconds() <= 0:
        return "Time's up!"
    minutes = int(time_left.total_seconds() // 60)
    return f"{minutes} minutes"

async def is_player_alive(player_id):
    """Checks if a player is alive and returns the player data if so."""
    global players
    if player_id in players:
        if players[player_id]["alive"]:
            return players[player_id]  # Return the player's data
        else:
            return "Dead"  # Player is dead
    else:
        return None  # Player not found
    
async def get_player_id_by_name(player_name):
    """
    Finds a player's ID based on their name (or nickname).
    Returns the player ID if found, otherwise returns None.
    """
    global players
    print("DEBUG: get_player_id_by_name called")
    for player_id, player_data in players.items():
        if player_data["name"].lower() == player_name.lower() or \
           (player_data["display_name"] and player_data["display_name"].lower() == player_name.lower()):
            return player_id
    return None  # Player not found

def generate_status_message(players):
    global current_phase, time_left, phase_number, time_day_ends, time_night_ends, time_signup_ends
    """Generates the game status message."""
    print(f"DEBUG: generate_status_message called\n"
          f"The current phase is {current_phase} - {phase_number}")
    status_message = "**Current Game Status:**\n"
    # Add phase information with countdown
    if current_phase == "":
        time_left = get_time_left_string(time_signup_ends)
        status_message += f"**Phase:** Signups - ends in {time_left}\n"
        status_message += f"Use `/join [name]` in the <#{config.SIGN_UP_HERE_CHANNEL_ID}> channel to join the game.\n "
        status_message += f"Game will start at: {time_signup_ends.strftime('%Y-%m-%d %H:%M:%S UTC')}.\n"
    else:
        if current_phase == "Day":
            time_left = get_time_left_string(time_day_ends)
        else:
            time_left = get_time_left_string(time_night_ends)
        status_message += f"**Phase:** {current_phase} {phase_number} - ends in {time_left}\n"
    status_message += f"**Players:**\n"
    for player_id, player_data in players.items():
        player_name = player_data["display_name"]
        # Check if role is assigned before accessing its attributes
        player_role = ""
        player_alignment = ""
        if player_data["alive"]:
            status_message += f"- {player_name}: Status = Alive, Role = {player_role}, Alignment = {player_alignment}\n"
        else:
            player_role = player_data["role"].name if player_data.get("role") else "No Role"
            player_alignment = player_data["role"].alignment if player_data.get("role") else "N/A"
            death_info = player_data.get("death_info")
            death_phase = death_info.get("phase") if death_info else "N/A"
            death_how = death_info.get("how") if death_info else "N/A"
            status_message += f"- ~~{player_name}~~: Status = Dead, Role = {player_role}, Alignment = {player_alignment}, Died in Phase: {death_phase}, Cause: {death_how}\n"
    print("DEBUG: Status message generated")
    return status_message

def get_specific_player_id(players,specific_role):
    """
    Finds the ID of the living Serial Killer player, if any.

    Args:
        players (dict): The dictionary containing player information.

    Returns:
        int or None: The ID of the living Serial Killer player, or None if no such player is found.
    """
    for player_id, player_data in players.items():
        if (
            player_data["alive"]
            and player_data["role"]
            and player_data["role"].name == specific_role
        ):
            return player_id
    return None

def create_godfather_role():
    """Creates a new Godfather role object."""
    return GameRole(
        name="Godfather",
        alignment="Mafia",
        description="Chooses the Mafia's target each night.",
        night_action="Choose a target to kill. Use `/kill @player` in the Mafia chat.",
    )

# --- Game Functions ---
def reset_game():
    """Resets the game variables."""
    global game_started, players, game_settings, game_roles, current_phase, phase_number, time_signup_ends, time_day_ends, time_night_ends, lynch_votes, gameprocess
    print("DEBUG: reset_game() called")
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
    if gameprocess.is_running:
        gameprocess.stop

async def send_role_dm(player_id, role):
    """Sends a DM to the player with their role information."""
    print(f"DEBUG: PLayer ID = {player_id} Ready to send role")
    print("-------------------------------")
    try:
        player = await bot.fetch_user(player_id)
        await asyncio.sleep(30)
        print("DEBUG: sent role")
        print("-------------------------------")
        await player.send(f"You are a {role.name}. {role.description}")
    except discord.Forbidden:
        print(f"Could not send role information to {player.name} due to their privacy settings.")
    except Exception as e:
        print(f"An error occurred while sending role information to {player.name}: {e}")

async def send_mafia_info_dm(bot, players):
    """Sends DMs to Mafia players with a list of other Mafia members."""
    print("DEBUG: Calling send_mafia_info_dm")
    for player_id, player_data in players.items():
        if player_data["alive"] and player_data["role"].alignment == "Mafia":
            mafia_members = [
                p_data["name"]
                for p_id, p_data in players.items()
                if p_id != player_id and p_data["alive"] and p_data["role"].alignment == "Mafia"
            ]
            if mafia_members:
                mafia_list = ", ".join(mafia_members)
                message = f"The other living Mafia members are: {mafia_list}"
                print("Sent mafia list to all mafia alligned players")
            else:
                message = "You are the only remaining Mafia member."
            try:
                player = await bot.fetch_user(player_id)
                await asyncio.sleep(30)
                await player.send(message)
            except discord.Forbidden:
                print(f"Could not send Mafia info DM to {player_data['name']} due to their privacy settings.")
            except Exception as e:
                print(f"An error occurred while sending Mafia info DM to {player_data['name']}: {e}")

def assign_game_roles(players):
    """Assigns roles to players randomly based on the chosen setup."""
    global game_roles
    # Shuffle the player IDs 
    player_ids = list(players.keys())
    random.shuffle(player_ids)
    # Assign roles to players
    for i, player_id in enumerate(player_ids):
        if i < len(game_roles):
            role = game_roles[i]
            players[player_id]["role"] = role
            players[player_id]["alive"] = True
            players[player_id]["votes"] = 0
            # Send DM with role information
            if player_id > 0:  # Check if it's not an NPC
                asyncio.create_task(send_role_dm(player_id, role))
        else:
            print(
                f"WARNING: More players than roles in setup. {players[player_id]['name']} will not be assigned a role."
            )
    
async def prepare_game_start(ctx, bot, npc_names):
    """Prepares the game to start by adding NPCs and assigning roles."""
    global players, current_phase, game_id, game_data, time_signup_ends
    print("prepare_game_start called")
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
        print(f"NPC {npc_name} added")
    game_id = time_signup_ends.strftime("%Y%m%d-%H%M%S")  # Unique ID based on time game starts
    game_data = {
            "game_id": game_id,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "players": players,  # You'll add player data here later
            "phases": [],  # You can store phase data here
            "winner": None,  # Update this when the game ends
            }
    # Save initial game data
    print(f"DEBUG: Game created with game_id = {game_id}")
    # Save initial game data
    save_json_data(game_data, f"game_{game_id}")
    print(f"DEBUG: Stat files created... assigning {len(players)} roles...")
    # Generate and assign roles
    generate_game_roles(len(players))
    if game_roles:
        assign_game_roles(players)
        print("DEBUG: Roles assigned")
        channel = bot.get_channel(config.STORIES_CHANNEL_ID)
        await channel.send("\n \n -------------------- **NEW GAME STARTING** -------------------------- \n \n"
                           "**Roles have been assigned, starting game!**\n")
        print("DEBUG: Sending DM to all mafia players")
        await send_mafia_info_dm(bot,players)
        # await start_game_night(bot, role_data, injokes, no_injoke) #Removed until game logic added
        # Create initial game data
        print(f"Ready to start, gameprocess.is_running = {gameprocess.is_running}")
        if not gameprocess.is_running:
            current_phase = "Night"
            print(f"Starting game process in {current_phase}")
            await gameprocess.start(ctx,bot,players)
        else:
            print("gameprocess was running... now stopping")
            gameprocess.stop()
            current_phase = "Night"
            print(f"After stopping, starting game process in {current_phase}")
            await gameprocess.start(ctx,bot,players)
    else:
        await ctx.send("Failed to generate roles.")
    print("DEBUG: prepare_game_start finished")  # Add this print statement

async def process_lynch_vote(ctx, voter_id, lynch_target):
    global lynch_votes
    print(f"DEBUG: Target is {lynch_target}")
    lynch_target_id = await get_player_id_by_name(lynch_target)
    target_alive = await is_player_alive(lynch_target_id)
    print(f"DEBUG: target {lynch_target_id} alive => {target_alive}")
    if not target_alive:
        await ctx.send(f"Player {lynch_target} is not alive")
        return
    print(f"DEBUG: Lynch Tarrget ID => {lynch_target_id}")
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
    await channel.send(f"{ctx.author.mention} voted for {lynch_target} who now has {lynch_votes[lynch_target_id]["total_votes"]}")
    print(f"DEBUG: Lynch votes after /vote -> {lynch_votes}")

async def countlynchvotes(bot, ctx, players, game_roles):
    global lynch_votes, current_phase, phase_number
    lynched_players = []
    max_votes = 0
    total_phases = (phase_number * 2) - (1 if current_phase == "night" else 0)
    if current_phase != "Day":
        print("DEBUG: tally_votes called outside of day phase. Skipping.")
        print(f"DEBUG: Current phase is {current_phase} - {phase_number}")
        return
    else:
        print(f"DEBUG: Current Lynch list: {lynch_votes}")
        for player_id, vote_data in lynch_votes.items():
            if vote_data["total_votes"] > max_votes:
                max_votes = vote_data["total_votes"]
                lynched_players = [player_id]
            elif vote_data["total_votes"] == max_votes:
                lynched_players.append(player_id)
            print(f"Debug: Lynched Players => {lynched_players}")
         # Announce the voting results
    voting_channel = bot.get_channel(config.VOTING_CHANNEL_ID)
    story_channel = bot.get_channel(config.STORIES_CHANNEL_ID)
    if max_votes == 0:
        await voting_channel.send("No votes were cast.")
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
            await story_channel.send(f"**{lynched_player_name} was lynched!**")
            # Mark the player as dead
            players[lynched_player_id]["alive"] = False
            print(f"DEBUG: Marked lynched player as dead")
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
            if lynched_player_id > 0:  # only show role for non-npc
                lynched_player_role = lynched_player_data["role"].name
                await voting_channel.send(f"{lynched_player_name}'s role was: {lynched_player_role}")
    else:
        await voting_channel.send("No one was lynched.")
    lynch_data = {
    "game_id": datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"),
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
    print(f"DEBUG: Current phase is {current_phase}- {phase_number}")
    if current_phase != "Day":
        await voting_channel.send("Vote counting is only available during the day phase.")
        print(f"DEBUG: Current phase is {current_phase}")
        return
    # Tally votes (ensure lynch_votes is updated before calling this function)
    vote_counts = {}
    voters = {}  # Dictionary to track who voted for whom
    for player_id, player_data in players.items():
        target_id = player_data["action_target"]
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
    if not vote_counts:
        message_content += "No votes yet.\n"
    else:
        for player_id, vote_count in vote_counts.items():
            player_data = players[player_id]
            player_name = player_data["name"]
            voter_list = ", ".join(voters[player_id])
            message_content += f"- {player_name}: {vote_count} vote(s) - {voter_list}\n"
    # Find players who haven't voted
    not_voted = [
        player_data["name"]
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
        return "Draw"       # if everyone is dead, then the game ended in a draw  
    elif living_neutral == 1 and living_mafia == 0 and living_town == 0:
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

        return "Mafia"      # Mafia wins if they equal or outnumber Town and SK is dead
    elif living_mafia == 0 and living_neutral == 0 and living_town > 0:
        return "Town"       # Town wins if no Mafia or Neutral players are alive
    else:
        return None  # No winner yet 
 
async def announce_winner(bot, winner):
    """Announces the winner and resets the game."""
    global game_started, phase_number, current_phase, discord_role_data, players, gameprocess
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
        "game_id": datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"),
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
    reset_game()
    game_started = False  # Allow new games to be started
    gameprocess.stop()

async def process_sk_night_kill(bot,target_id):
    global current_phase, phase_number, players
    total_phases = (phase_number * 2) - (1 if current_phase == "night" else 0)
    sk_player_id = get_specific_player_id(players,"Serial Killer")
    print(f"DEBUG: mob_gf_id => {sk_player_id}")
    # Check if a Godfather was found before proceeding
    if sk_player_id is None:
        print("DEBUG: No living Godfather found. Skipping Mafia night kill process.")
        print(f"Players = {players}")
        return
    if sk_player_id > 0:
        if bot:  # Check if ctx is available
            sk_player = await bot.fetch_user(sk_player_id)
            try:
                if target_id is None:
                    print("DEBUG: No target selected for SK. Skipping kill process.")
                    await sk_player.send("You did not select a target for the night kill.")
                    return
                if target_id not in players:
                    print(f"DEBUG: Invalid target ID {target_id} for SK. Skipping kill process.")
                    await sk_player.send(f"Invalid target for the night kill. Target player is not in the game.")
                    return
                if not players[target_id]["alive"]:
                    print("DEBUG: Target player for SK is already dead. Skipping kill process.")
                    await sk_player.send("Target player for the night kill is already dead.") 
                    return
            except discord.Forbidden:
                print(f"Could not send DM to Serial Killer due to their privacy settings.")
            except Exception as e:
                print(f"An error occurred while sending DM to Serial Killer: {e}")
        else:
            print("DEBUG: No living Serial Killer found.")
    if target_id is not None:
        story_channel = bot.get_channel(config.STORIES_CHANNEL_ID)
        print(f"DEBUG: SK killed {target_id}")
        # Mark the player as dead and record how
        players[target_id]["alive"] = False
        players[target_id]["death_info"] = {
                "phase": f"{current_phase} {phase_number}",
                "phase num": f"{phase_number}",
                "total phases": f"{total_phases}",
                "how": "Killed by SK"
            }    
        # Announce the player's role
        target_name = players[target_id]["name"] 
        await story_channel.send(f"**{target_name} was killed by the SK!**")

async def process_mafia_night_kill(bot,target_id):
    global current_phase, phase_number, players
    total_phases = (phase_number * 2) - (1 if current_phase == "night" else 0)
    mob_gf_id = get_specific_player_id(players,"Godfather")
    print(f"DEBUG: mob_gf_id => {mob_gf_id}")
    # Check if a Godfather was found before proceeding
    if mob_gf_id is None:
        mob_goon_id = get_specific_player_id(players,"Mob Goon")
        print("DEBUG: No living Godfather found. Skipping Mafia night kill process.")
        print(f"DEBUG: Promoting Mob Goon to Godfather")
        if mob_goon_id is None:
            print("Debug: All mob are dead")
            return
        players[mob_goon_id]["role"] = create_godfather_role()
        if mob_goon_id > 0:
            mob_goon_player = await bot.fetch_user(mob_goon_id)
            await mob_goon_player.send("Your Godfather has been killed, you are the Godfather Now")
        return
    if mob_gf_id > 0:
        if bot:
            mob_gf_player = await bot.fetch_user(mob_gf_id)
            try:
                if target_id is None:
                    print("DEBUG: No target selected for Mob. Skipping kill process.")
                    await mob_gf_player.send("You did not select a target for the night kill.")
                    return
                if target_id not in players:
                    print(f"DEBUG: Invalid target ID {target_id} for Mob kill. Skipping kill process.")
                    return
                if not players[target_id]["alive"]:
                    print("DEBUG: Target player for Mob is already dead. Skipping kill process.")
                    await mob_gf_player.send("Target player for the night kill is already dead.")
                    return
            except discord.Forbidden:
                print(f"Could not send DM to mob GF due to their privacy settings.")
            except Exception as e:
                print(f"An error occurred while sending DM to mob GF: {e}")
    else:
        print("DEBUG: No living Godfather found.")
    if target_id is not None:  # only show role for non-npc
            story_channel = bot.get_channel(config.STORIES_CHANNEL_ID)
            print(f"DEBUG: Mob killed {target_id}")
            # Mark the player as dead and record how
            players[target_id]["alive"] = False
            players[target_id]["death_info"] = {
                    "phase": f"{current_phase} {phase_number}",
                    "phase num": f"{phase_number}",
                    "total phases": f"{total_phases}",
                    "how": "Killed by Mob"
                }    
            # Announce the player's role
            target_name = players[target_id]["name"] 
            await story_channel.send(f"**{target_name} was killed by the mob!**")

async def process_doc_night_heal(bot,target_id):
    global current_phase, phase_number, players
    if current_phase == "Day":
        return
    town_doc_id = get_specific_player_id(players,"Doctor")
    if town_doc_id > 0:
        if bot:
            town_doc_player = await bot.fetch_user(town_doc_id)
            try:
                if target_id is None or target_id == "":
                    print("DEBUG: No target selected for Doc. Skipping heal process.")
                    await town_doc_player.send("You did not select a target for the night heal.")
                    return
                if target_id not in players:
                    print(f"DEBUG: Invalid target ID {target_id} for Doc. Skipping heal process.")
                    await town_doc_player.send(f"Invalid target for the night heal. Target player is not in the game.")
                    return
                # Check if the target is already dead from a previous phase
                if not players[target_id]["alive"]:
                    death_info = players[target_id].get("death_info")
                    if death_info:
                        death_phase_num = death_info.get("phase_num")
                        if death_phase_num is not None and death_phase_num < phase_number:
                            print("DEBUG: Target player for Doctor heal is already dead from a previous phase. Skipping action.")
                            await town_doc_player.send("Target player for the night heal is already dead.")
                            return
            except discord.Forbidden:
                print(f"Could not send DM to town doc due to their privacy settings.")
            except Exception as e:
                print(f"An error occurred while sending DM to town doc: {e}")
    story_channel = bot.get_channel(config.STORIES_CHANNEL_ID)
    previous_target = False
    if target_id is not None:
        target_name = players[target_id]["name"]
        print(f"DEBUG: Town Doc heals {target_id}")
        if players[target_id]["alive"] == False:
            previous_target = True
        players[target_id]["alive"] = True
        if previous_target == True:
            await story_channel.send(f"**Town Doc found {target_name} and revived them....")

async def process_cop_night_investigate(bot,target_id):
    global current_phase, phase_number,players
    town_cop_id = get_specific_player_id(players,"Town Cop")
    if town_cop_id > 0:
        if bot:
            town_cop_player = await bot.fetch_user(town_cop_id)
            try:
                if target_id is None:
                    print("DEBUG: No target selected for cop. Skipping investigate process.")
                    await town_cop_player.send("You did not select a target for the investigation.")
                    return
                if target_id not in players:
                    print(f"DEBUG: Invalid target ID {target_id} for cop. Skipping investigation process.")
                    await town_cop_player.send(f"Invalid target for the investigation. Target player is not in the game.")
                    return
                if not players[target_id]["alive"]:
                    print("DEBUG: Target player for cop is already dead. Skipping investigation process.")
                    await town_cop_player.send("Target player for the investigation is already dead.")
                    return
                if target_id is not None:
                    target_role = players[target_id]["role"].name
                    target_description = players[target_id]["role"].description
                    await town_cop_player.send(f"{target_id} is {target_role}. {target_description}")
            except discord.Forbidden:
                print(f"Could not send role information to town cop due to their privacy settings.")
            except Exception as e:
                print(f"An error occurred while sending role information to town cop: {e}")

# --- Bot Event ---
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")

# --- Bot Commands ---
@bot.command(name="startmafia")
#@commands.has_role(discord_role_data.get("mod", {}).get("id"))
@commands.check(is_owner_or_mod())
async def start_game(ctx, phase_hours: float = config.PHASE_HOURS, *, start_datetime: str):
    # ""Args:""
    #    ctx: The command context.
    #    start_datetime: The datetime string for when the game should start, in the format YYYY-MM-DD HH:MM.
    #    phase_hours: The number of hours each phase (day/night) will last.
    #"""
    """Starts the Mafia game sign-up process."""
    global game_started, time_signup_ends, current_phase, phase_number, LOOP_HOURS
    LOOP_HOURS = phase_hours
    print(f"DEBUG: Phase Hours = {phase_hours} // {LOOP_HOURS} ")
    # Check if a game is already running
    if game_started:
        await ctx.send("A game is already in progress!")
        return
    # Reset game variables
    reset_game()
    game_started = True
    # Parse the start_datetime string into a datetime object
    try:
        time_signup_ends = datetime.strptime(start_datetime, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        await ctx.send("Invalid date/time format. Please use '%Y-%m-%d %H:%M' format in UTC.")
        return
    # Check if the provided start_datetime is in the future
    if time_signup_ends < datetime.now(timezone.utc):
        await ctx.send("The provided start time is in the past. Please provide a future date and time.")
        return
    # Calculate join_hours based on the difference between now and start_datetime
    join_hours = round((time_signup_ends - datetime.now(timezone.utc)).total_seconds() / 3600, 2)
    print(f"DEBUG: New game started.")
    channel = bot.get_channel(config.TALKY_TALKY_CHANNEL_ID)
    await channel.send( f"Sign-ups are now open for {join_hours} hours! Use `/join [name]` in the <#{config.SIGN_UP_HERE_CHANNEL_ID}> channel to join the game.\n "
                        f"Game will start at: {time_signup_ends.strftime('%Y-%m-%d %H:%M:%S UTC')}.\n"
                        )
    channel = bot.get_channel(config.SIGN_UP_HERE_CHANNEL_ID)
    await channel.send( f"Sign-ups are now open for {join_hours} hours! Use `/join [name]` in the <#{config.SIGN_UP_HERE_CHANNEL_ID}> channel to join the game.\n"
                        f"Game will start at: {time_signup_ends.strftime('%Y-%m-%d %H:%M:%S UTC')}.\n"
                        )
    channel = bot.get_channel(config.RULES_AND_ROLES_CHANNEL_ID)
    await channel.send( "------- ** New Basic Bitch Game open for signups ** -----------\n"
                        f"Sign-ups are now open for {join_hours} hours! Use `/join [name]` in the <#{config.SIGN_UP_HERE_CHANNEL_ID}> channel to join the game.\n"
                        f"Game will start at: {time_signup_ends.strftime('%Y-%m-%d %H:%M:%S UTC')}.\n"
                        f"{rules_text}\n"
                        "------- **No story generated** ------"
                        )
    # Wait for signups to end (until start_datetime)
    delay = (time_signup_ends - datetime.now(timezone.utc)).total_seconds()
    print(f"DEBUG: Delay =  {delay} // {(time_signup_ends - datetime.now(timezone.utc)).total_seconds()}")
    print(f"DEBUG: Game Started == {game_started}")
    await asyncio.sleep(delay)
    if game_started:
        print(f"game started = {game_started} so prepare game start")
        await prepare_game_start(ctx, bot, npc_names)
    else:
        print("DEBUG: Sign-ups ended, but the game was stopped.")

@bot.command(name="join")
@commands.check(is_owner_or_mod())
async def join_game(ctx,*,game_name: str):
    """Joins the Mafia game."""
    global players
    if not game_started:
        await ctx.send("No game is currently running.")
        return
    if ctx.channel.id != config.SIGN_UP_HERE_CHANNEL_ID:
        await ctx.send(f"Please use this command in the <#{config.SIGN_UP_HERE_CHANNEL_ID}> channel.")
        return
    player_id = ctx.author.id
    if player_id in players:
        await ctx.send("You have already joined the game!")
        return
    # Add player to the game
    players[player_id] = {
        "name": ctx.author.name,
        "display_name": game_name,
        "role": None,
        "alive": True,
        "votes": 0,
        "action_target": None,
    }
    # Update discord roles
    guild = ctx.guild
    await update_player_discord_roles(bot, guild, players, discord_role_data)
    print(f"DEBUG: Player joined: {ctx.author.name} (ID: {player_id}). Players: {players}")
    await ctx.send(
        f"{ctx.author.mention} has joined the game!"
    )
    # If we have reached 7 players, start the game
    if len(players) >= 7:
        await ctx.send("We have reached 7 players! The game will start in advance to the end of the signup phase.")
        await prepare_game_start(ctx, bot, npc_names, mafia_setups)
@join_game.error
async def join_game_error(ctx, error):
    if isinstance(error, commands.PrivateMessageOnly):
        await ctx.author.send("This command can only be used in private messages.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.author.send(  "You are missing a required argument. Use `/help join` to see required arguments.\n"
                                "Please provide a game name after the /join command\n"
                                "i.e. `/join PlayerOne`\n"
                                )
    elif isinstance(error, commands.BadArgument):
        await ctx.author.send("Invalid argument provided, please check and try again. Use `/help join` to see required arguments.\n"
                                "Please provide a game name after the /join command\n"
                                "i.e. `/join PlayerOne`\n"
                                )
    else:
        await ctx.author.send("An error occurred during processing of this command.")

@bot.command(name="stop")
@commands.check(is_owner_or_mod())
#@commands.has_role(discord_role_data.get("mod", {}).get("id"))
async def stop_game(ctx):
    """Stops the current game."""
    global game_started, time_signup_ends, gameprocess
    if not game_started:
        await ctx.send("No game is currently running.")
        return
    game_started = False
    time_signup_ends = None  # Reset the signup end time
    gameprocess.stop()
    reset_game()
    print("DEBUG: Game stopped. Players:", players)
    await ctx.send("The current game has been stopped.")
    guild = ctx.guild
    await update_player_discord_roles(bot, guild, players, discord_role_data)

@bot.command(name="status")
@commands.check(is_owner_or_mod())
#@commands.has_role(discord_role_data.get("mod", {}).get("id"))
async def status(ctx):
    """Displays the current game status."""
    if not game_started:
        await ctx.send("No game is currently running.")
        return
    status_message = generate_status_message(players)
    await ctx.send(status_message)
    print(f"/Status called and info sent to channel")

@bot.command(name = "vote")
@commands.check(is_owner_or_mod())
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
    if player_id not in players:
        channel = bot.get_channel(config.VOTING_CHANNEL_ID)
        await channel.send("You are not in this game")
        return  
    await process_lynch_vote(ctx, player_id, lynch_target)
    await send_vote_update(bot, players)  # Send vote update after each vote

@bot.command(name = "count")
@commands.check(is_owner_or_mod())
@commands.has_role(discord_role_data.get("living", {}).get("id"))
async def count(ctx):
    await send_vote_update(bot, players) #manually send vote count with /count

@bot.command(name="kill")
@commands.dm_only()
async def kill_command(ctx, *, kill_target: str):
    global sk_target, mob_target
    player_id = ctx.author.id
    if not game_started:
        await ctx.author.send("No game is currently running.")
        return
    if player_id not in players:
        await ctx.author.send("You are not part of the current game.")
        return
    if current_phase != "Night":
        await ctx.author.send("You can only use this command during the night phase.")
        return
    player_data = players[player_id]
    # Check if the player is alive
    if not player_data["alive"]:
        await ctx.author.send("Dead players cannot use this command.")
        return
    # Check for allowed roles
    allowed_roles = ["Godfather", "Serial Killer"]
    if player_data["role"].name not in allowed_roles:
        await ctx.author.send("You do not have the required role to use this command.")
        return
    if not kill_target:  # Check if target_name is empty
        await ctx.author.send("You must specify a target to kill.")
        return
    target_id = await get_player_id_by_name(kill_target)
    print("DEBUG: target input has been converted to ID")
    if target_id is None:
        await ctx.author.send(f"Could not find a player named '{kill_target}'.")
        return
    # Ensure the target is not the player themselves
    if target_id == player_id:
        await ctx.author.send("You cannot target yourself.")
        return
    # Ensure the target is alive
    if not players[target_id]["alive"]:
        await ctx.author.send("You cannot target dead players.")
        return
    # Rest of the command logic for players with the correct role
    if player_data["role"].name == "Godfather":
        mob_target = target_id
        await ctx.author.send(f"Godfather has selected {players[target_id]['name']} as the target.")
    elif player_data["role"].name == "Serial Killer":
        sk_target = target_id
        await ctx.author.send(f"Serial Killer has selected {players[target_id]['name']} as the target.")
    await ctx.author.send(f"You have chosen to kill {players[target_id]['name']}.")
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
    global heal_target
    player_id = ctx.author.id
    if not game_started:
        await ctx.author.send("No game is currently running.")
        return
    if player_id not in players:
        await ctx.author.send("You are not part of the current game.")
        return
    if current_phase != "Night":
        await ctx.author.send("You can only use this command during the night phase.")
        return
    player_data = players[player_id]
    # Check if the player is alive
    if not player_data["alive"]:
        await ctx.author.send("Dead players cannot use this command.")
        return
    # Check for allowed roles
    allowed_roles = ["Doctor"]  # Add other roles if needed
    if player_data["role"].name not in allowed_roles:
        await ctx.author.send("You do not have the required role to use this command.")
        return
    target_id = await get_player_id_by_name(target_name)
    if target_id is None:
        await ctx.author.send(f"Could not find a player named '{target_name}'.")
        return
    # Ensure the target is not the player themselves
    if target_id == player_id:
        await ctx.author.send("You cannot target yourself.")
        return
    # Ensure the target is alive
    if not players[target_id]["alive"]:
        await ctx.author.send("You cannot target dead players.")
        return
    # Rest of the command logic for players with the correct role
    heal_target = target_id
    await ctx.author.send(f"You have chosen to heal {players[target_id]['name']}.")
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
    global investigate_target
    player_id = ctx.author.id
    if not game_started:
        await ctx.author.send("No game is currently running.")
        return
    if player_id not in players:
        await ctx.author.send("You are not part of the current game.")
        return
    if current_phase != "Night":
        await ctx.author.send("You can only use this command during the night phase.")
        return
    player_data = players[player_id]
    # Check if the player is alive
    if not player_data["alive"]:
        await ctx.author.send("Dead players cannot use this command.")
        return
    # Check for allowed roles
    allowed_roles = ["Town Cop"]
    if player_data["role"].name not in allowed_roles:
        await ctx.author.send("You do not have the required role to use this command.")
        return
    target_id = await get_player_id_by_name(target_name)
    if target_id is None:
        await ctx.author.send(f"Could not find a player named '{target_name}'.")
        return
    # Ensure the target is not the player themselves
    if target_id == player_id:
        await ctx.author.send("You cannot target yourself.")
        return
    # Ensure the target is alive
    if not players[target_id]["alive"]:
        await ctx.send("You cannot target dead players.")
        return
    # Rest of the command logic for players with the correct role
    investigate_target = target_id
    await ctx.author.send(f"You have chosen to investigate {players[target_id]['name']}.")
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
        "**Available Commands:**\n"
        "`/startmafia <start_datetime>  [phase_hours]`:  Starts a new game at the specified time. Date/time format: `YYYY-MM-DD HH:MM` (UTC).\n"
        "`/stop`: Stops the current game.\n"
        "`/join <name>` : Joins the upcoming game. Enter your game name as a parameter, which can be used during the game\n"
        "`/status`: Displays the current game status. Will show game names of all signed up players\n"
        "`/vote <@player>`: Casts a vote during the day phase. Use either the players game name or discord ID (@name) to target\n"
        "`/count`: Displays the current vote count.\n"
        "`/rules`: Displays the rules of the game.\n"
        "`/info`: Shows this help message.\n"
        "`/kill <@player>` (Godfather & Serial Killer only, DM only): Selects a player to be killed by the Mafia.\n"
        "`/heal <@player>` (Doctor only, DM only): Selects a player to be healed.\n"
        "`/investigate <@player>` (Town Cop only, DM only): Investigates a player's role.\n"
    )
    await ctx.send(info_text)

@bot.command(name="rules")
async def show_rules(ctx):
    """Displays the rules of the game."""
    await ctx.send(rules_text)

# --- Game Loop ---
@tasks.loop(seconds = 1)
async def gameprocess(ctx,bot,players):
    global phase_number, current_phase, lynch_votes, sk_target, mob_target, heal_target, investigate_target, time_night_ends, time_day_ends
    if current_phase == "Night":
        #night phase
        phase_number += 1 
        print(f"DEBUG: Starting {current_phase} - {phase_number} which will last {LOOP_HOURS} hours\n"
              "The town goes to sleep....\n")
        channel = bot.get_channel(config.STORIES_CHANNEL_ID)
        await channel.send(f"Night {phase_number} has fallen. The town goes to sleep...")
        time_night_ends = datetime.now(timezone.utc) + timedelta(hours=LOOP_HOURS)
        print(f"DEBUG: Current time night ends = {time_night_ends}")
        status_message = generate_status_message(players)
        await channel.send(status_message)
        #future night time actions logic
        print("Sleeping....")
        await asyncio.sleep(LOOP_HOURS*60*60)
        print(f"DEBUG: Targets... Sk target = {sk_target}, mob target = {mob_target}, doc target = {heal_target}, cop target = {investigate_target}")
        await process_sk_night_kill(bot, sk_target)
        await asyncio.sleep(10)
        await process_mafia_night_kill(bot, mob_target)
        await asyncio.sleep(10)
        await process_doc_night_heal(bot, heal_target)
        await asyncio.sleep(10)
        await process_cop_night_investigate(bot, investigate_target)
        await asyncio.sleep(10)
        guild = bot.get_guild(config.SERVER_ID)
        await update_player_discord_roles(bot, guild, players, discord_role_data)
        await asyncio.sleep(10)
        winner = check_win_conditions()
        if winner:
            await announce_winner(bot, winner)  # You'll need to implement announce_winner
            return  # End the game loop if there's a winner
        #recordphaseactions()
        print(f"DEBUG: End of night phase, about to switch to day phase")
        current_phase = "Day"
        sk_target = ""
        mob_target = ""
        heal_target = ""
        investigate_target = ""
    else:
        #day phase
        print(f"DEBUG: {current_phase} - {phase_number} has dawned which will last {LOOP_HOURS} hours.\n" 
              "The town awakens...")
        channel = bot.get_channel(config.STORIES_CHANNEL_ID)
        await channel.send(f"Day {phase_number} has dawned. The town awakens...")
        print(f"The current UTC time is {datetime.now(timezone.utc)}")
        time_day_ends = datetime.now(timezone.utc) + timedelta(hours=LOOP_HOURS)
        print(f"DEBUG: Current time day ends = {time_day_ends}")
        await asyncio.sleep(10)
        status_message = generate_status_message(players)
        await channel.send(status_message)
        #future day actions logic
        print("working....")
        await asyncio.sleep(LOOP_HOURS*60*60)
        await channel.send("Voting ended!")
        await countlynchvotes(bot,ctx,players,game_roles)
        print(f"DEBUG: The lynch results -> {lynch_votes} for {current_phase} - {phase_number}")
        await asyncio.sleep(10)
        guild = bot.get_guild(config.SERVER_ID)
        await update_player_discord_roles(bot, guild, players, discord_role_data)
        await asyncio.sleep(10)
        winner = check_win_conditions()
        if winner:
            await announce_winner(bot, winner)  # You'll need to implement announce_winner
            return  # End the game loop if there's a winner
        #recordphaseactions()
        lynch_votes = {}
        current_phase = "Night"

# --- Start the Bot ---
bot.run(config.BOT_TOKEN,log_handler=handler, log_level=logging.DEBUG)