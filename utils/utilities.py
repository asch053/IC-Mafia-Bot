# utils/utilities.py
import discord
import asyncio
import json
import os
from datetime import datetime, timezone
import logging
import mafiaconfig as config

logger = logging.getLogger('discord')  # Get the SAME logger as in bot.py

def load_data(filepath, error_msg):
    """Loads data from a JSON or TXT file, handling FileNotFoundError."""
    # Try to open and load the data, return appropriate defaults on failure.
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

async def send_story(bot, message: str, image_url: str = None, video_url: str = None):
    """This function sends a message to the designated #stories channel in your Discord server. 
    It can optionally include an image or a video along with the text message, and it includes error 
    handling for common issues like missing permissions or network problems
    Args:
        bot: The Discord bot instance.
        message: The text message to send.
        image_url: (Optional) URL of an image to include.
        video_url: (Optional) URL of a video to include.
    Raises:
        TypeError: if bot is not a discord.ext.commands.Bot instance.
        ValueError: If both image_url and video_url are provided.
        discord.errors.HTTPException: If sending the message fails (caught and logged).
        discord.errors.Forbidden: If the bot does not have permission (caught and logged).
    """
    # Get the channel object and send the message
    if not isinstance(bot, discord.ext.commands.Bot):
        raise TypeError("bot must be an instance of discord.ext.commands.Bot")
    if image_url and video_url:
        raise ValueError("Cannot send both an image and a video.")
    story_channel = bot.get_channel(config.STORIES_CHANNEL_ID)
    if not story_channel:
        logger.error("Story channel not found (ID: %s)", config.STORIES_CHANNEL_ID)
        return
    embed = discord.Embed(description=message, color=0x00FF00)
    try:
        if image_url:
            embed.set_image(url=image_url)
            await story_channel.send(embed=embed)
        elif video_url:
            # For videos, you generally just send the URL directly.  Discord embeds them.
            await story_channel.send(message)
            await story_channel.send(video_url) #separate messages for text and video
        else:
            await story_channel.send(embed=embed) # Embed method.
    except discord.errors.HTTPException as e:
        logger.exception("HTTPException while sending story message: %s", e)
    except discord.errors.Forbidden as e:
        logger.error("Forbidden error while sending story message. Check bot permissions: %s", e)
    except Exception as e:  # Catch-all for unexpected errors
        logger.exception("Unexpected error sending story message: %s", e)

async def generate_narration(bot, event, players, player=None):
    """Generates narration based on game events."""
    #  Construct narration text, incorporating in-jokes, and send via send_story.
    if event == "night_start":
        phase_number = players.get("phase_number", 1) if isinstance(players, dict) else 1
        if player: # If targeting a player
            narration = f"Night {phase_number} has fallen. {player.display_name} is doing something suspicious..."
        else:
            narration = f"Night {phase_number} has fallen. The town goes to sleep..."
    elif event == "day_start":
        narration = "The sun rises. Time to discuss and vote!"
    elif event == "player_lynched":
      if player:
        narration = f"{player.display_name} was lynched by the town!"
      else:
        narration = "A player was lynched!" # Fallback, should not happen
    elif event == "player_killed_mafia":
      if player:
        narration = f"{player.display_name} was killed by the Mafia!"
      else:
        narration = "Someone was killed by the Mafia!"
    elif event == "player_killed_sk":
      if player:
        narration = f"{player.display_name} was killed by the Serial Killer!"
      else:
        narration = "Someone was killed by the Serial Killer!"
    elif event == "doctor_healed":
      if player:
        narration = f"The Doctor successfully protected {player.display_name}!"
      else:
        narration = "The Doctor protected someone."
    elif event == "cop_investigated":
        # In a real game, you WOULD NOT reveal this publicly!  This is
        # just an example.  You'd DM this to the Cop.
        if player:
          narration = f"The Cop investigated {player.display_name}."
        else:
          narration = "The cop investigated someone."
    elif event == "game_over":
        narration = f"Game Over! The {player} team wins!" #player acts as winner
    else:
        narration = f"An unknown event occurred: {event}"
    await send_story(bot, narration) # bot may need to be passed in

async def update_player_discord_roles(bot, ctx, players, discord_role_data):
    """Updates player roles in Discord based on their status, with retries and logging."""
    guild = ctx.guild
    living_role_id = discord_role_data.get("living", {}).get("id")
    dead_role_id = discord_role_data.get("dead", {}).get("id")
    spectator_role_id = discord_role_data.get("spectator", {}).get("id")
    living_role = discord.utils.get(guild.roles, id=living_role_id)
    dead_role = discord.utils.get(guild.roles, id=dead_role_id)
    spectator_role = discord.utils.get(guild.roles, id=spectator_role_id)
    if not living_role or not dead_role or not spectator_role:
        logger.error("Could not find 'Living Players', 'Dead Players', or 'Spectator' role.")
        return
    for player_id, player_data in players.items():
        if player_id > 0:  # Check if it's not an NPC
            member = guild.get_member(player_id)
            if member:
                for attempt in range(3):  # Retry up to 3 times
                    try:
                        if player_data["alive"]:
                            if living_role not in member.roles:
                                await member.add_roles(living_role)
                            if dead_role in member.roles:
                                await member.remove_roles(dead_role)
                            if spectator_role in member.roles:
                                await member.remove_roles(spectator_role)
                        else:
                            if dead_role not in member.roles:
                                await member.add_roles(dead_role)
                            if living_role in member.roles:
                                await member.remove_roles(living_role)
                            if spectator_role in member.roles:
                                await member.remove_roles(spectator_role)
                        break  # Success, exit the retry loop
                    except discord.errors.HTTPException as e:
                        if e.status == 429:
                            retry_after = e.retry_after
                            logger.warning(f"Rate limited adding/removing roles for {member.name}.  Retrying in {retry_after:.2f} seconds.")
                            await asyncio.sleep(retry_after)  # Wait before retrying
                        elif e.status == 403:
                            logger.error(f"Forbidden: Bot lacks permissions to manage roles for {member.name}.")
                            break # No point in trying for this player
                        else:
                            logger.exception(f"HTTPException updating roles for {member.name}: {e}")
                            break # Don't retry for other HTTP errors
                    except discord.Forbidden:
                        logger.error(f"Bot lacks permissions to manage roles for {member.name}.")
                        break
                    except Exception as e:
                        logger.exception(f"Unexpected error updating roles for {member.name}: {e}")
                        break  # Don't retry for unexpected errors
    for member in guild.members:
        if member.id not in players and not member.bot:
            for attempt in range(3):
                try:
                    if spectator_role not in member.roles:
                        await member.add_roles(spectator_role)
                    if living_role in member.roles:
                        await member.remove_roles(living_role)
                    if dead_role in member.roles:
                         await member.remove_roles(dead_role)
                    break #success
                except discord.errors.HTTPException as e:
                    if e.status == 429:
                        retry_after = e.retry_after
                        logger.warning(f"Rate limited adding/removing roles for {member.name}.  Retrying in {retry_after:.2f} seconds.")
                        await asyncio.sleep(retry_after)  # Wait before retrying
                    elif e.status == 403:
                        logger.error(f"Forbidden: Bot lacks permissions to manage roles for {member.name}.")
                        break # No point in trying for this player
                    else:
                        logger.exception(f"HTTPException updating roles for {member.name}: {e}")
                        break
                except discord.Forbidden:
                    logger.error(f"ERROR: Bot lacks permissions to manage roles for {member.name}.")
                    break #No point in trying again
                except Exception as e:
                    logger.exception(f"Unexpected error updating roles for {member.name}: {e}")
                    break # Don't retry for unexpected errors

def format_time_remaining(end_time):
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

async def is_player_alive(players, player_id):
    """Checks if a player is alive and returns the player data if so."""
    # Check if player exists and is alive, return data or False
    if player_id in players:
        if players[player_id]["alive"] == True:
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
    logger.info("DEBUG: get_player_id_by_name called")
    for player_id, player_data in players.items():
        if player_data["name"].lower() == player_name.lower() or \
           (player_data["display_name"] and player_data["display_name"].lower() == player_name.lower()):
            logger.debug(f"DEBUG: player_id returned = {player_id}")
            return player_id
    return None  # Player not found

async def is_player_alive(player_id, players):
    """Checks if a player is alive and returns the player data if so."""
    if player_id in players:
        if players[player_id]["alive"]:
            return players[player_id]  # Return the player's data
        else:
            return "Dead"  # Player is dead
    else:
        return None  # Player not found

def get_specific_player_id(players, specific_role):
    """
    Finds the ID of player based on a given role
    Args:
        players (dict): The dictionary containing player information.
    Returns:
        int or None: The ID of the living Serial Killer player, or None if no such player is found.
    """
  #used to find player based on assigned role
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

def get_status_message(players, game_settings, time_signup_ends=None):
    """Generates a formatted status message string."""
    # Format a string with current phase, players, roles, status, etc.
    """Generates the game status message."""
    logger.info("DEBUG: generate_status_message called")
    current_phase = game_settings["current_phase"]
    phase_number = game_settings["phase_number"]
    logger.info(f"The current phase is {current_phase} - {phase_number}")
    status_message = "**Current Game Status:**\n"
    # Add phase information with countdown
    if current_phase == "" or current_phase == None or current_phase == "signup":
        time_left = format_time_remaining(time_signup_ends)
        status_message += f"**Phase:** Signups - ends in {time_left}\n"
        status_message += (
            f"Use `/join [name]` in the <#{config.SIGN_UP_HERE_CHANNEL_ID}> channel to join the game.\n "
        )
        status_message += (
            f"Game will start at: {time_signup_ends.strftime('%Y-%m-%d %H:%M:%S UTC')}.\n"
        )
        logger.info(f"DEBUG: Status message generated during setup with {time_left}")
    elif current_phase == "Day":
        time_left = format_time_remaining(game_settings["time_day_ends"])
    elif current_phase == "Night":
        time_left = format_time_remaining(game_settings["time_night_ends"])
    else:
        time_left = None
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
    logger.debug(f"DEBUG: Status message generated: {status_message}")
    return status_message



