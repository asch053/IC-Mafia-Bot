import discord
import json
import random
from Testing.config import STORIES_CHANNEL_ID, SERVER_ID, game_settings
from game_engine import game_settings, datetime, timezone

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
        return {} if filepath.endswith(".json") else []

async def send_story(bot, message, stories_channel_id):
    """Sends a message to the #stories channel."""
    stories_channel = bot.get_channel(stories_channel_id)
    await stories_channel.send(message)

async def generate_narration(bot, event, players, no_injoke, injokes, player=None):
    """Generates narration based on game events."""
    personality = game_settings.get("personality", "Standard")
    gore_level = game_settings.get("gore_level", "Low")

    narration = f"[{personality}/{gore_level}] Event: {event}"

    if player:
        player_name = player.nick if player.nick else player.name
        player_info = next((p for p in no_injoke if p["id"] == player.id), None)
        if not player_info:
            for injoke_player, data in injokes.items():
                if injoke_player.lower() in player_name.lower():
                    if data["jokes"]:
                        narration += " " + random.choice(data["jokes"]).format(player=player_name)

    for p_id, p_data in players.items():
        if (player is None or p_id != player.id):
            p_name = p_data["name"]
            narration = narration.replace(f"<@{p_id}>", p_name)

    await send_story(bot, narration, STORIES_CHANNEL_ID)

async def update_player_roles(bot, guild, players, role_data):
    """Updates player roles in Discord based on their status."""
    living_role_id = role_data.get("living", {}).get("id")
    dead_role_id = role_data.get("dead", {}).get("id")
    spectator_role_id = role_data.get("spectator", {}).get("id")

    living_role = discord.utils.get(guild.roles, id=living_role_id)
    dead_role = discord.utils.get(guild.roles, id=dead_role_id)
    spectator_role = discord.utils.get(guild.roles, id=spectator_role_id)

    if not living_role or not dead_role or not spectator_role:
        print("ERROR: Could not find 'Living Players', 'Dead Players', or 'Spectator' role.")
        return

    for player_id, player_data in players.items():
        if player_id > 0:
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

def get_time_left_string(end_time):
    """Calculates the time remaining until the given end_time and returns a formatted string."""
    if end_time is None:
        return "Unknown"

    time_left = end_time - datetime.now(timezone.utc)
    if time_left.total_seconds() < 0:
        return "Ended"

    minutes = int(time_left.total_seconds() // 60)

    return f"{minutes} minutes"