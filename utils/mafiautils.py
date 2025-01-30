import discord
import json
import asyncio
from discord.ext import commands
from datetime import datetime, timedelta, timezone


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

#--- Roles ---
class GameRole:
    def __init__(self, name, alignment, description, night_action=None, uses=None):
        self.name = name
        self.alignment = alignment
        self.description = description
        self.night_action = night_action
        self.uses = uses

    def __str__(self):
        return self.name
    
# --- Bot Functions ---
def is_owner_or_mod(bot):
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

#--- Game Functions ---
def get_time_left_string(end_time):
    """
    Calculates the time remaining until the given end_time.
    Returns a formatted string of the remaining time or "Time's up!".
    """
    if end_time is None:
        return "Unknown"

    now = datetime.now(timezone.utc)
    time_left = end_time - now

    if time_left.total_seconds() <= 0:
        return "Time's up!"

    minutes = int(time_left.total_seconds() // 60)
    return f"{minutes} minutes"
 
async def is_player_alive(players, player_id):
    """Checks if a player is alive and returns the player data if so."""
    if player_id in players:
        if players[player_id]["alive"]:
            return players[player_id]  # Return the player's data
        else:
            return "Dead"  # Player is dead
    else:
        return None  # Player not found
    
async def get_player_id_by_name(players, player_name):
    """
    Finds a player's ID based on their name (or nickname).
    Returns the player ID if found, otherwise returns None.
    """
    print(f"DEBUG: target Player name = {player_name}")
    for player_id, player_data in players.items():
        if player_data["name"].lower() == player_name.lower() or \
           (player_data["display_name"] and player_data["display_name"].lower() == player_name.lower()):
            return player_id

    return None  # Player not found


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

async def send_role_dm(bot, player_id, role):
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





