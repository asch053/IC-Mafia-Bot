# game/engine.py
import discord
import asyncio
import json
import logging
import io
import random
import os
import secrets

from discord.ext import tasks
from datetime import datetime, timedelta, timezone
from collections import (
    Counter,
    defaultdict
)

import config
import game.actions as actions
from utils.utilities import (
    load_data,
    save_json_data,
    update_player_discord_roles,
    format_time_remaining,
    send_role_dm,
    send_mafia_info_dm,
    send_chunked_message
    
)

from game.narration import NarrationManager # Import the NarrationManager
from utils.randomness_tester import test_role_distribution # Import the test function
from game.roles import GameRole, get_role_instance
from game.player import Player # Import the Player class
from game import setup_generator # Import the setup_generator function


# Get the same logger instance as in mafiabot.py
logger = logging.getLogger('discord')

class Game:
    """Manages the entire state and lifecycle of a single Mafia game."""
    def __init__(self, bot, guild, cleanup_callback=None, game_type="classic"):
        logger.info("Initializing new Game instance.")
        self.narration_manager = NarrationManager()
        self.bot = bot
        self.guild = guild  # The context from the '/startmafia' command
        self.last_reminder_time = None  # Track the last time a reminder was sent
        self.cleanup_callback = cleanup_callback
        # --- Game State Variables ---
        logger.debug("Setting up initial game settings and player data.")
        self.game_settings = {
            "game_id": None, #date-time string of time signups ended
            "game_type": game_type,
            "story_type": None,
            "game_started": False,
            "start_time": None,
            "end_time": None,
            "current_phase": "setup", # Phases: setup, signup, preparation, night, day, finished
            "phase_number": 0,
            "phase_end_time": None,
            "gf_investigate": True,  # Default
            "sk_investigate": False, # Default
            "gf_night_immune": True,  # Default
            "sk_night_immune": True, # Default
            "phase_hours": 12, # Default
        }
        self.chat_log = [] # To store chat messages during the game FR-5.4: Advanced Data Logging
        self.game_event_log = [] # To store game events during the game FR-5.4: Advanced Data Logging
        self.players = {} # This will now store Player objects: {player_id: Player_Object}
        self.lynch_votes = {} # This will store votes for lynching: {player_id: target_id}
        self.game_roles = [] # This will store GameRole objects assigned to players
        self.night_actions = {} # Stores night actions: {player_id: {"action": "type", "target": id}}
        self.protected_players_this_night = {} # Tracks players protected during the night & who protected them {player_id: protector_id}
        self.blocked_players_this_night = {} # Tracks players who were blocked this night
        self.vote_history = [] # NEW: To store every single vote
        self.player_lock = asyncio.Lock() # Create lock to ensure one person at a time for joining and exiting game
        self.vote_lock = asyncio.Lock() # Create lock to ensure one vote at a time 
        # --- Night Action Tracking ---
        self.night_outcomes = {}
        self.heals_on_players = {}
        self.kill_attempts_on = {}
        self.blocked_players_this_night = {}
        # --- Control Flags ---
        self.force_start_flag = False
        self.reminders_sent = set() # Tracks sent reminders for the current phase
        self.max_players = 19 # Default max players
        # --- Narration Markers ---
        self.is_prologue = None
        self.is_epilogue = None 
        # --- Data Loading ---
        logger.debug("Loading game data from JSON files.")
        try:
            self.discord_role_data = load_data("data/discord_roles.json") #loads discord roles data
        except Exception as e:
            logger.error(f"Error loading discord roles data: {e}")
        try:
            self.npc_names = load_data("data/bot_names.txt") #load NPC bot names
        except Exception as e:
            logger.error(f"Error loading NPC names: {e}")
        try:    
            self.rules_text = "\n".join(load_data("data/rules.txt"))
        except Exception as e:
            logger.error(f"Error loading rules text: {e}")
            self.rules_text = "No rules text found. Please check the rules.txt file."
        try:    
            self.mafia_setups = load_data("data/mafia_setups.json")
        except Exception as e:
            logger.error(f"Error loading mafia setups: {e}")
            logger.critical("No mafia setups loaded. The game cannot start.")
        logger.debug("Game instance initialized.")

    # --- 1. SIGN-UP PHASE ---
    async def start(self, game_type, start_datetime_obj, phase_hours, gf_investigate, sk_investigate, narration_type, max_players=21):
        """Announces the sign-up phase and starts the signup_loop."""
        logger.info("Starting the sign-up phase for the game.")
        logger.debug("Setting up game settings.")
        self.game_settings["game_id"] = start_datetime_obj.strftime("%Y%m%d-%H%M%S") #sets game_id to a unique string based on the start time
        self.game_settings["game_type"] = game_type # Set game type to the type of game being played
        self.game_settings["game_started"] = True # Set game_started to True
        self.game_settings["start_time"] = start_datetime_obj # Set start_time to the start time
        self.game_settings["current_phase"] = "signup" # Set current phase to signup
        self.game_settings["phase_end_time"] = start_datetime_obj # Set when the phase ends
        self.game_settings["phase_hours"] = phase_hours # Set phase hours as set within the game initialization
        self.game_settings["gf_investigate"] = gf_investigate # Set Godfather immunity as set within the game initialization
        self.game_settings["sk_investigate"] = sk_investigate # Set Serial Killer immunity as set within the game initialization
        self.game_settings["story_type"] = narration_type # Set narration type as set within the game initialization
        self.max_players = max_players #set max players as set within the game initialization
        self.is_prologue = True # Mark that the next story is the prologue
        self.is_epilogue = False # Not the epilogue yet
        # Set all players to spectators
        #logger.info("Setting all players to spectators.")
        #await update_player_discord_roles(self.bot, self.guild, self.players, self.discord_role_data)
        # Announce the game in multiple channels
        # Build the announcement message
        logger.debug("Building announcement message for the sign-up phase.")
        # Get spectator role mention
        # You need the role's ID from your config
        spectator_role_id = self.discord_role_data.get("spectator", {}).get("id", 0)
        logger.info(f"Spectator role ID: {spectator_role_id}")
        # Then, get the actual Role object from the server
        spectator_role = self.guild.get_role(spectator_role_id)
        logger.info(f"Spectator role object: {spectator_role}")
        signup_channel_mention = f"<#{config.SIGN_UP_HERE_CHANNEL_ID}>" 
        start_time_str = start_datetime_obj.strftime('%Y-%m-%d %H:%M:%S UTC') # Format the start time as a string
        time_left_str = format_time_remaining(start_datetime_obj) # Format the time remaining until the game starts
        announcement = (
            f"**A new game of {self.game_settings['game_type']} Mafia has been scheduled!**\n\n"
            f"Theme will be **{self.game_settings['story_type']}**.\n"
            f"Sign-ups are now open for **{time_left_str}**! {spectator_role.mention} Use `/mafiajoin` in {signup_channel_mention} to join.\n"
            f"The game will officially begin at: **{start_time_str}** (or when {self.max_players} players join)."
        )
        logger.info(f"Game announcement: {announcement}")
        # Send the announcement to the relevant channels
        await self.bot.get_channel(config.ANNOUNCEMENT_CHANNEL_ID).send(announcement) #send announcement to #announcement channel
        await self.bot.get_channel(config.SIGN_UP_HERE_CHANNEL_ID).send("## New Game ##\n--------------------------\n**Game Starting Soon!**\n\n\n") #send special text to #sign-up-here channel
        await self.bot.get_channel(config.STORIES_CHANNEL_ID).send("## New Game ##\n--------------------------\n**Game Starting Soon!**\n\n\n") #send special text to #sign-up-here channel
        # Create a different message for the rules and roles channel, including the standard rules text
        # Get the rules
        rules = self.rules_text
        # Add objective on win condition based on game type
        if self.game_settings["game_type"] == "battle_royale":
            rules += "11. **Objective:** Be the last player alive!"
            rules += "\n12. **Night Phase:** Each night, with night have either a kill action or a block action. There are no teams in Battle Royale; everyone is out for themselves!"
        else:
            rules += "11. **Objective:** The Town must eliminate all Mafia members and the Serial Killer. The Mafia must outnumber the Town. The Serial Killer must be the last player standing."
            rules += "\n12. **Night Phase:** Mafia members choose a player to kill. The Serial Killer also chooses a player to kill. Some Town roles may have night actions."
        # add in details on if SK or GF are investigation immune
        if not gf_investigate:
            rules += "\n**Note:** The Godfather is *immune* to investigations."
        else:
            rules += "\n**Note:** The Godfather can be investigated normally."
        if not sk_investigate:
            rules += "\n**Note:** The Serial Killer is *immune* to investigations."
        else:
            rules += "\n**Note:** The Serial Killer can be investigated normally."
        # Add details on SK and GF night death immunity
        if self.game_settings["gf_night_immune"]:
            rules += "\n**Note:** The Godfather is *immune* to night kills."
        else:
            rules += "\n**Note:** The Godfather can be killed at night."
        if self.game_settings["sk_night_immune"]:
            rules += "\n**Note:** The Serial Killer is *immune* to night kills."
        else:
            rules += "\n**Note:** The Serial Killer can be killed at night."
        # Send the rules to the rules channel
        await self.bot.get_channel(config.RULES_AND_ROLES_CHANNEL_ID).send(f" ## New Game ##\n--------------------------\n**Game Starting Soon!**\n\n{rules}\n")
        logger.debug("Sign-up phase announcement sent to all channels.")
        # Start the sign-up monitoring loop
        logger.info("Starting the sign-up loop to monitor player sign-ups and send reminders.")
        self.signup_loop.start()

    @tasks.loop(seconds=config.signup_loop_interval_seconds) # Loop periodically to send reminders
    async def signup_loop(self):
        """Monitors the sign-up phase, sends reminders, and checks for start conditions."""
        logger.info("Sign-up loop iteration started.")
        # --- Check for start conditions ---
        game_should_start = False
        reason = ""
        # Check if there is a valid reason for the game to start (i.e. if the sign-up phase has ended, max players reached, or force start flag is set)
        if datetime.now(timezone.utc) >= self.game_settings["phase_end_time"]: # Checking if the current time is past the scheduled start time
            game_should_start = True
            reason = "The scheduled start time has been reached."
            logger.info("Sign-up phase ended due to reaching the scheduled start time.")
        elif len(self.players) >= self.max_players: # Checking if the number of players has reached the maximum allowed
            game_should_start = True
            reason = f"The maximum number of players ({self.max_players}) has been reached."
            logger.info(f"Sign-up phase ended due to reaching the maximum player count: {self.max_players}.")
        elif self.force_start_flag: # Checking if the force start flag is set
            game_should_start = True
            reason = "The game has been force-started by an administrator."
            logger.info("Sign-up phase ended due to force start flag being set by Admin.")
        if game_should_start: # If any of the conditions are met, end the sign-up phase and send message stating signups have closed to the sign-up channel
            logger.info(f"Ending sign-up loop. Reason: {reason}")
            await self.bot.get_channel(config.SIGN_UP_HERE_CHANNEL_ID).send(f"**Sign-ups are now closed!** {reason} The game will now begin.")
            await self.bot.get_channel(config.ANNOUNCEMENT_CHANNEL_ID).send(f"**Sign-ups are now closed!** {reason} The game will now begin.")
            self.signup_loop.stop() # Stop the sign-up loop
            if self.game_settings["current_phase"] == "signup":
                await self.prepare_game() # Start preparing the game if the sign-up phase is still active
            return
        # --- If phase has NOT ended, check for reminders ---
        spectator_role = self.guild.get_role(self.discord_role_data.get("spectator", {}).get("id", 0))
        time_left = self.game_settings["phase_end_time"] - datetime.now(timezone.utc) #determine how much time is left in the current phase
        time_left_str = format_time_remaining(self.game_settings["phase_end_time"])
        total_minutes_left = time_left.total_seconds() / 60 # Convert to total minutes
        if not spectator_role: return # Can't send reminders without the spectator role
        reminder_points = config.REMINDER_POINTS # list of times to send reminders
        # Loop through the times to send reminders and send one if the time left is less than or equal to one of the reminder time and the reminder has not been sent yet
        logger.debug(f"Checking for reminders. Total minutes left: {total_minutes_left}")
        for minutes, text in reminder_points.items():
            if total_minutes_left <= minutes and minutes not in self.reminders_sent:
                await self.bot.get_channel(config.SIGN_UP_HERE_CHANNEL_ID).send(
                    f"**Reminder!** {spectator_role.mention}  There's still time to join! Sign-ups close in **{time_left_str}**.\n"
                    f"Use `/mafiajoin` to participate!\n"
            )
                self.reminders_sent.add(minutes) # Add this reminder to the set of sent reminders so can avoid sending it again
                logger.info(f"Sent reminder for {text} remaining in the phase.")
                break # Only send one reminder per loop iteration


    async def force_start(self, interaction: discord.Interaction):
        """Admin command to force the signup phase to end and the game to start."""
        if self.game_settings["current_phase"] != "signup":
            await interaction.response.send_message("This command can only be used during the sign-up phase.", ephemeral=True)
            return
        self.force_start_flag = True
        await interaction.response.send_message(
            f"Force start flag set. The game will begin on the next loop iteration (within {config.signup_loop_interval_seconds} seconds).",
            ephemeral=True
        )

    async def add_player(self, user, player_name, channel):
        """Adds a player to the game during the signup phase."""
        async with self.player_lock: # Add this lock
            if self.game_settings["current_phase"] != "signup": # Check if the game is currently in the sign-up phase
                await channel.send("Sorry, the game is not currently accepting new players.") # Can't join if not in signup phase
                logger.error(f"{user.name} tried to join the game outside of the sign-up phase.")
                return
            if user.id in self.players: # Check if the player is already in the game
                await channel.send("You have already joined the game!")
                logger.warning(f"{user.name} tried to join the game again with player name {player_name}.")
                return
            if len(self.players) >= self.max_players: # Check if the game is already full
                await channel.send(f"Sorry, the game is full with {self.max_players} players.")
                logger.warning(f"{user.name} tried to join the game but it is already full.")
                return
            # Create a Player object
            self.players[user.id] = Player(user_id=user.id, discord_name=user.name, display_name=player_name)
            # send a confirmation message
            await channel.send(f"Welcome to the game, **{player_name}**! You are player #{len(self.players)}.")
            logger.info(f"{user.name} ({player_name}) has joined the game.")
            await update_player_discord_roles(self.bot, self.guild, self.players, self.discord_role_data) # Update player roles in Discord
            status_message = self.get_status_message() # Generate a status message with players listed
            try:
                await self.bot.get_channel(config.SIGN_UP_HERE_CHANNEL_ID).send(status_message) # Send the status message to the sign-up channel
            except Exception as e:
                logger.error(f"Failed to send status message: {e}")
            return f"You have successfully signed up as **{player_name}**! You are player #{len(self.players)}."

    async def remove_player(self, user, channel):
        """Removes a player from the game during the signup phase."""
        async with self.player_lock: # Add this lock    
            # Check if the game is currently in the sign-up phase
            if self.game_settings["current_phase"] != "signup":
                await channel.send("You can only leave the game during the sign-up phase.")
                logger.error(f"{user.name} tried to leave the game outside of the sign-up phase.")
                return
            if user.id in self.players: # Check if the player is in the game
                player_name = self.players[user.id].display_name
                # Remove the player from the game
                del self.players[user.id]
                # send a confirmation message
                await channel.send(f"**{player_name}** has left the game.")
                logger.info(f"{user.name} ({player_name}) has left the game.")
                #update player roles in Discord
                await update_player_discord_roles(self.bot, self.guild, self.players, self.discord_role_data)
            else:
                await channel.send("You are not currently in the game.")
                logger.warning(f"{user.name} tried to leave the game but was not a participant.")

    # --- 2. GAME PREPARATION ---
    async def prepare_game(self):
        """Prepares the game by adding NPCs, assigning roles, and starting the main loop."""
        # Prepare game to start by ensuring all settings are correct for start of game
        logger.info("Sign-up phase ended. Preparing game...")
        self.game_settings["current_phase"] = "preparation" # Change the current phase to preparation to indicate the game is being prepared 
        # Add NPCs if player count is below minimum 
        min_players = config.min_players # Minimum players required to start the game as defined in config.py
        logger.info(f"Current player count: {len(self.players)}. Minimum required players: {min_players}.")
        while len(self.players) < min_players:
            self.add_npc() #add NPCs until the player count reaches the minimum required
        # Generate roles for the game
        logger.info(f"Generating game roles for {len(self.players)} players...")
        self.generate_game_roles()
        if not self.game_roles:
            # If cannot generate roles, abort the game preparation
            # Send the error to the public rules channel
            rules_channel = self.bot.get_channel(config.RULES_AND_ROLES_CHANNEL_ID)
            if rules_channel:
                await rules_channel.send("Error: Could not generate roles...")
                logger.error("No roles generated for the current player count. Aborting game preparation.") 
            await self.reset()
            return  
        logger.info(f"Generated {len(self.game_roles)} roles for the game.\n List of roles: {self.game_roles}")
        # --- SAFETY CHECK: Ensure no roles failed to load ---
        if any(role is None for role in self.game_roles):
            error_msg = "CRITICAL ERROR: One or more roles failed to generate. Check setup_generator.py names against role_definition.json."
            logger.critical(error_msg)
            await self.bot.get_channel(config.RULES_AND_ROLES_CHANNEL_ID).send(f"⚠️ **Game Error:** {error_msg}")
            await self.reset()
            return
        # ---------------------------------------------------
        # --- Run Randomness Test and Post Results ---
        logger.info("Running role assignment randomness test...")
        player_names = [p.display_name for p in self.players.values()]
        role_names = [r.name for r in self.game_roles]
        summary_string, detailed_string = test_role_distribution(player_names, role_names)
        rules_channel = self.bot.get_channel(config.RULES_AND_ROLES_CHANNEL_ID)
        if rules_channel:
            # Prepare the detailed breakdown as a text file to upload
            detailed_as_bytes = io.BytesIO(detailed_string.encode('utf-8'))
            text_file = discord.File(detailed_as_bytes, filename="randomness_test_results.txt")
            # Send the summary message and attach the file
            await rules_channel.send(summary_string, file=text_file)
        else:
            logger.warning("Could not find rules channel to post randomness test results.")
        # --- End of Test ---
        await self.assign_roles() #assign roles to players randomly
        logger.info(f"Assigned roles to {len(self.players)} players.")
        # Update player roles in Discord based on their game status (alive, dead, or spectator)
        await update_player_discord_roles(self.bot, self.guild, self.players, self.discord_role_data) 
        # Generate a status message with the roles being played
        status_message = await self.role_status_message() 
        # Send status message with roles to rules channel
        logger.info(f"Sending status message to rules channel: {status_message}")
        try:
            await rules_channel.send(status_message)
        except Exception as e:
            logger.error(f"Failed to send status message: {e}")
        # Start the main game loop
        self.game_loop.start()
        logger.info(f"Game prepared. Starting main game loop.")
        story_channel = self.bot.get_channel(config.STORIES_CHANNEL_ID)
        if story_channel:
            await story_channel.send("\n\n--- **GAME STARTED** ---\n\n")
        # Create narration event for game start with a list of active players
        game_state = {
            "phase": self.game_settings["current_phase"],
            "phase_number": self.game_settings['phase_number'],
            "living_players": [p for p in self.players.values() if p.is_alive],
            "is_prologue": self.is_prologue,
            "is_epilogue": self.is_epilogue,
            "game_type": self.game_settings["game_type"],
            "story_type": self.game_settings["story_type"]
        }
        self.narration_manager.add_event('game_start', game_state=game_state)
        self.is_prologue = False # The prologue has now been used, so set it to False

    def add_npc(self):
        """Adds a single NPC to the game."""
        # Load a list of NPC names from the text file that have not been used yet
        available_names = [name for name in self.npc_names if name not in [p.display_name for p in self.players.values()]]
        if not available_names:
            logger.error("Could not add NPC, no unique names available.")
            return     
        # Randomly select a name from the available names and create an id for the NPC   
        npc_name = random.choice(available_names)
        npc_id = -(len(self.players) + 1) # Ensure unique negative ID
        # Create a Player object for the NPC
        self.players[npc_id] = Player(user_id=npc_id, discord_name=npc_name, display_name=npc_name)
        logger.info(f"Added NPC: {npc_name}")

    def generate_game_roles(self):
        """Generates a list of GameRole objects based on player count."""
        # --- 4. Get Role List ---
        logger.info("Generating dynamic role list...")
        game_type = self.game_settings['game_type']

        player_count = len(self.players)
        if player_count < config.min_players:
            logger.warning(f"Cannot generate {game_type} roles for {player_count} players. Minimum is {config.min_players}.\n Converting to Battle Royale mode.")
            self.bot.get_channel(config.RULES_AND_ROLES_CHANNEL_ID).send(f"Error: Could not generate a 'Classic' game for {player_count} players. Minimum is {config.min_players}.\n Converting to Battle Royale mode.")
            self.bot.get_channel(config.TALKY_TALKY_CHANNEL_ID).send(f"Error: Could not generate a 'Classic' game for {player_count} players. Minimum is {config.min_players}.\n Converting to Battle Royale mode.")
            self.game_settings['game_type'] = "battle_royale"
        
        # New smart way!
        role_names = setup_generator.generate_roles(player_count, game_type)
        # We MUST check for an empty list, which our generator
        # returns if the player count is too low!
        if not role_names:
            self.bot.get_channel(config.RULES_AND_ROLES_CHANNEL_ID).send(
                f"Error: Could not generate a 'Classic' game for {player_count} players. "
                f"Minimum is {config.min_players}."
            )
            logger.critical(f"Could not generate roles for {player_count} players. Aborting game preparation.")
            self.reset()
            return
        logger.info(f"Generated role names: {role_names}")
        # Convert role names to GameRole objects
        self.game_roles = []
        self.game_roles = [get_role_instance(name) for name in role_names]
        # Overwrite investigation immunities based on game settings
        for role in self.game_roles:
            if role.name == "Godfather":
                role.investigation_immune = not self.game_settings["gf_investigate"]
                logger.info(f"Set Godfather investigation immunity to {role.investigation_immune} != {self.game_settings['gf_investigate']}")
            elif role.name == "Serial Killer":
                role.investigation_immune = not self.game_settings["sk_investigate"]
                logger.info(f"Set Serial Killer investigation immunity to {role.investigation_immune} != {self.game_settings['sk_investigate']}")
        logger.info("Game roles generated successfully.")
        

    async def assign_roles(self):
        """Assigns the generated roles to players randomly and sends DMs."""
        player_pool = list(self.players.values())
        role_pool = self.game_roles[:]  # Create a copy

        logger.info(f"Securely shuffling {len(role_pool)} roles for {len(player_pool)} players.")

        # Fisher-Yates shuffle using a cryptographically secure random number generator.
        # This is the most robust way to ensure a truly random permutation.
        for i in range(len(role_pool) - 1, 0, -1):
            # Pick an index j from 0 to i (inclusive).
            j = secrets.randbelow(i + 1)
            # Swap the elements at positions i and j.
            role_pool[i], role_pool[j] = role_pool[j], role_pool[i]

        # Pair the unshuffled list of players with the now-shuffled list of roles.
        for player_obj, role in zip(player_pool, role_pool):
            player_obj.assign_role(role)
            if not player_obj.is_npc:
                await send_role_dm(self.bot, player_obj.id, role, self.guild)

        logger.info("Roles assigned to players successfully.")
        
        # After assigning roles, send Mafia team information to Mafia players
        if self.game_settings["game_type"] == "classic":
            await send_mafia_info_dm(self.bot, self.players)
            logger.info("Mafia team information has been distributed.")

    # --- 3. MAIN GAME LOOP ---
    @tasks.loop(seconds=config.game_loop_interval_seconds) # Run every 15 seconds to check phase deadlines
    async def game_loop(self):
        """
        The main game loop. Runs every 15 seconds to check phase deadlines and send reminders. - To be updated in production to run every minute
        It handles the transition between phases, processes end-of-phase events, and checks for win conditions
        """
         
        living_role = self.guild.get_role(self.discord_role_data.get("living", {}).get("id", 0)) # Get the living role mention
        if not living_role:
            logger.critical("Could not find the living role in the guild. Check the discord_roles.json configuration.")
            return
        
        # --- If the phase has ended, process it and start the next one ---
        if datetime.now(timezone.utc) >= self.game_settings["phase_end_time"]:
            current_end_time = self.game_settings["phase_end_time"]
            logger.info(f"Phase {self.game_settings['current_phase']} {self.game_settings['phase_number']} ended at {current_end_time}.")
            # Process end-of-phase events and add them to the narration manager
            winner = None # Initialize winner
            # Process day or night phase end
            if self.game_settings["current_phase"].lower() == "day": # Check if current phase is day
                logger.debug("Day phase ended. Processing lynch votes...")
                await self.bot.get_channel(config.VOTING_CHANNEL_ID).send(f"**{self.game_settings['current_phase'].capitalize()} {self.game_settings['phase_number']} has ended!**\n\n{living_role.mention} the day has ended. Processing lynch votes...") # Notify players that the day has ended and votes are being processed
                self.game_settings["current_phase"] = "pre-night" # Pause to allow the Transition to night phase
                logger.info(f"Transistioned to pre-night so >> Current phase = {self.game_settings['current_phase']}, phase number = {self.game_settings['phase_number']}")
                winner = await self.tally_votes() # Capture winner from the lynch vote
                logger.debug("Day phase ended. Processing lynch votes...")
            elif self.game_settings["current_phase"].lower() == "night": # Else check if current phase is night
                logger.info("Night phase ended. Processing night actions...")
                logger.info(f"Current phase = {self.game_settings['current_phase']}, phase number = {self.game_settings['phase_number']}")
                await self.bot.get_channel(config.STORIES_CHANNEL_ID).send(f"{living_role.mention} the night has ended. Processing night actions...") # Notify players that the night has ended and actions are being processed
                self.game_settings["current_phase"] = "pre-day" # Pause to allow the Transition to day phase
                logger.info(f"Transistioned to pre-day so >> Current phase = {self.game_settings['current_phase']}, phase number = {self.game_settings['phase_number']}")
                await self.process_night_actions() # If night phase has ended, process all night actions
                await self._resolve_night_deaths() # Resolve deaths after processing actions
                # NEW: Update last_action_target for players who acted
                processed_actions = self.night_actions.copy()
                # First, reset the memory for players who didn't act this night
                for player in self.players.values():
                    if player.id not in processed_actions:
                        player.last_action_target_id = None
                # Then, set the new memory for players who did act
                for p_id, action_data in processed_actions.items():
                    if action_data['type'] in ['heal', 'block']:
                        acting_player = self.players.get(p_id)
                        if acting_player:
                            acting_player.last_action_target_id = action_data['target_id']
            logger.info(f"{self.game_settings['current_phase'].capitalize()} phase ended. Events processed, creating story...")
            # update discord roles
            await update_player_discord_roles(self.bot, self.guild, self.players, self.discord_role_data) 
            logger.info("Updated player roles in Discord based on current game state.")
            # Check for win conditions if win conditions not already met (i.e. Jester win)
            if not winner:
                logger.info("Checking win conditions after phase end.")
                winner = self.check_win_conditions()
                if winner:
                    logger.info(f"Win conditions met. Winner: {winner}")
            # Construct the story (the narrator function now adds the header)
            logger.info("Constructing story from narration manager events...")
            # Send previous game phase events to the narration manager to build the story
            # Determine if Day or Night phase just ended
            if self.game_settings['current_phase'] == "pre-day":
                phase_just_ended = "night"
            elif self.game_settings['current_phase'] == "pre-night":
                phase_just_ended = "day"
            else:
                phase_just_ended = self.game_settings['current_phase']
            # Prepare game state for story construction
            # Note: We want to capture the state of the game at the moment the phase ended, 
            # which is why we prepare this game_state before processing the events for the next phase
            game_state = {
                "phase": phase_just_ended,
                "number": self.game_settings['phase_number'],
                "living_players": [p for p in self.players.values() if p.is_alive],
                "game_type": self.game_settings.get("game_type", "classic"),
                "story_type": self.game_settings.get('story_type', 'Classic Mafia'),
                "is_prologue": self.is_prologue, # Important for setting the scene
                "is_game_over": False
            }
            logger.info(f"Preparing to construct story for phase: {phase_just_ended}, number: {self.game_settings['phase_number']} with {len(game_state['living_players'])} living players.\n{game_state}")
            # Construct the story
            story = await self.narration_manager.construct_story(game_state=game_state)
            if self.is_prologue:
                self.is_prologue = False  # The prologue has been told!
            if story:
                #send story to the stories channel
                logger.info("Story constructed from narration manager events.")
                logger.info(f"Story for phase {self.game_settings['current_phase']} {self.game_settings['phase_number']}:\n{story}")
                story_channel = self.bot.get_channel(config.STORIES_CHANNEL_ID)
                # Send the story in chunks if it's too long
                if story_channel:
                    await send_chunked_message(self, story_channel, story)
                    logger.info("Story sent to stories channel.")
            logger.info(f"Phase {self.game_settings['current_phase']} {self.game_settings['phase_number']} ended. Story constructed.")
            # Clear the narration manager for the next phase
            self.narration_manager.clear()
            if winner: #if there is a winner, announce them and stop the game loop
                await self.announce_winner(winner)
                logger.info(f"Game ended with winner: {winner}")
                await update_player_discord_roles(self.bot, self.guild, self.players, self.discord_role_data) # Update player roles based on their current state
                logger.info("Updated player roles in Discord based on current game state.")
                await self.reset() # Reset the game state 
                return
            # Generate a status message with players listed and send it to the Rules channel
            status_message = self.get_status_message() 
            try:
                await self.bot.get_channel(config.RULES_AND_ROLES_CHANNEL_ID).send(status_message)
            except Exception as e:
                logger.error(f"Error sending status message: {e}")
            # Transition to the new phase
            self.reminders_sent.clear() # Reset reminders for the new phase
            logger.info(f"Current phase before transition: {self.game_settings['current_phase']}, phase number: {self.game_settings['phase_number']}")
             # Set the end time for the new phase
            self.game_settings["phase_end_time"] = current_end_time + timedelta(hours=self.game_settings["phase_hours"])
            if self.game_settings["current_phase"].lower() == "pre-day": # If the current phase that was processed was 'night' (i.e. current phase is 'pre-day'), transition to 'day'
                self.game_settings["current_phase"] = "day"
                #announce the start of the new day phase
                announcement = f"## ☀️ Day {self.game_settings['phase_number']} has begun. You have {format_time_remaining(self.game_settings['phase_end_time'])}  to discuss and vote."
                logger.info("Transitioning to day phase.")
            else: # Was 'preparation' or 'pre-night' or 'day', so transition to 'night'
                self.game_settings["current_phase"] = "night" # Transition to 'night'
                self.game_settings["phase_number"] += 1 # Increment the phase number at each night phase transition
                # Reset night actions and lynch votes for the new night phase
                self.night_actions = {} 
                self.lynch_votes = {}
                announcement = f"## 🌙 Night {self.game_settings['phase_number']} has begun. You have {format_time_remaining(self.game_settings['phase_end_time'])} hours to use your night actions."
                logger.info("Transitioning to night phase.")
           
            await self.bot.get_channel(config.STORIES_CHANNEL_ID).send(announcement)
            return # End this loop iteration after phase transition
        
        # --- If phase has NOT ended, check for reminders ---
        time_left = self.game_settings["phase_end_time"] - datetime.now(timezone.utc) #determine how much time is left in the current phase
        total_minutes_left = time_left.total_seconds() / 60 # Convert to total minutes
        living_role = self.guild.get_role(self.discord_role_data.get("living", {}).get("id", 0)) # Get the living role mention
        if not living_role:
            logger.critical("Could not find the living role in the guild. Check the discord_roles.json configuration.")
            return
        reminder_points = config.REMINDER_POINTS # list of times to send reminders
        # Loop through the times to send reminders and send one if the time left is less than or equal to one of the reminder time and the reminder has not been sent yet
        logger.debug(f"Checking for reminders. Total minutes left: {total_minutes_left}")
        for minutes, text in reminder_points.items():
            if total_minutes_left <= minutes and minutes not in self.reminders_sent:
                await self.bot.get_channel(config.STORIES_CHANNEL_ID).send(
                    f"**Reminder:** There is **{text}** left in the phase! {living_role.mention}"
                )
                self.reminders_sent.add(minutes) # Add this reminder to the set of sent reminders so can avoid sending it again
                logger.info(f"Sent reminder for {text} remaining in the phase.")
                break # Only send one reminder per loop iteration
       
        
    @game_loop.before_loop
    async def before_game_loop(self):
        # Wait until the bot is ready before starting the game loop
        await self.bot.wait_until_ready()
        logger.info("Main game loop is starting.")
        # Trigger the first phase transition immediately
        self.game_settings["phase_end_time"] = datetime.now(timezone.utc)
        
    @signup_loop.before_loop
    async def before_signup_loop(self):
        # Wait until the bot is ready before starting the sign-up loop
        await self.bot.wait_until_ready()
        logger.info("Sign-up loop is starting.")
    
    @game_loop.after_loop
    async def after_game_loop(self):
        """Runs automatically when the game loop stops."""
        logger.info("Game loop has finished. Triggering cleanup.")
        if self.cleanup_callback:
            self.cleanup_callback()

    # --- 4. ACTION & VOTE PROCESSING ---    
    async def process_lynch_vote(self, interaction, voter_user, target_name):
        """Processes a single vote to lynch a player, sent from a cog."""
        async with self.vote_lock: # Add this lock
            logger.info(f"Processing lynch vote from {voter_user.name} for target '{target_name}'")
            # 1. Validation Checks
            if self.game_settings["current_phase"] != "day": # Check if the current phase is 'day'
                # If not, send a message and log the attempt
                logger.warning(f"{voter_user.name} tried to vote outside of the day phase.")
                return "You can only vote during the day phase."
            voter_obj = self.players.get(voter_user.id) # Get the Player object for the voter
            logger.debug(f"Got Voter object: {voter_obj}")
            if not voter_obj or not voter_obj.is_alive: # Check if the voter is a valid player and is alive
                # If not, send a message and log the attempt
                logger.warning(f"{voter_user.name} tried to vote but is not a valid player or is dead.")
                return "You are not currently able to vote in this game."
            target_obj = self.get_player_by_name(target_name) # Get the Player object for the target by name
            if not target_obj: # If the target is not found, send a message and log the attempt
                logger.warning(f"{voter_obj.display_name} tried to vote for a non-existent player: {target_name}.")
                return f"Could not find a player named '{target_name}'."
            if not target_obj.is_alive: # Check if the target is alive
                # If the target is dead, send a message and log the attempt
                logger.warning(f"{voter_obj.display_name} tried to vote for a dead player: {target_obj.display_name}.")
                return f"**{target_obj.display_name}** is already dead and cannot be voted for."
            logger.info(f"Vote from {voter_obj.display_name} for target {target_obj.display_name} is valid.")
            # 2. Handle vote changes (un-vote previous target)
            if voter_obj.action_target is not None: # First check if the voter has a previous target
                # If they do, remove their vote from the previous target
                logger.info(f"{voter_obj.display_name} is changing their vote from previous target ID {voter_obj.action_target} to new target ID {target_obj.id}.")
                previous_target_id = voter_obj.action_target
                if previous_target_id in self.lynch_votes and voter_obj.id in self.lynch_votes[previous_target_id]:
                    self.lynch_votes[previous_target_id].remove(voter_obj.id)
                    # If the list for the previous target is now empty, remove the key
                    if not self.lynch_votes[previous_target_id]:
                        del self.lynch_votes[previous_target_id]
            # 3. Record the new vote
            voter_obj.action_target = target_obj.id # Store the ID of the new target
            logger.info(f"Recording vote: {voter_obj.display_name} -> {target_obj.display_name}")
            if target_obj.id not in self.lynch_votes: # If the target does not have a vote list yet, create it
                self.lynch_votes[target_obj.id] = []
            # Add the voter's ID to the target's list of voters
            if voter_obj.id not in self.lynch_votes[target_obj.id]:
                self.lynch_votes[target_obj.id].append(voter_obj.id)
            # NEW: Log the vote to the history
            self.vote_history.append({
                "voter_id": voter_obj.id,
                "voter_name": voter_obj.display_name,
                "target_id": target_obj.id,
                "target_name": target_obj.display_name,
                "phase": f"Day {self.game_settings['phase_number']}",
                "timestamp_utc": datetime.now(timezone.utc).isoformat()
            })
            logger.info(f"Vote history updated: {self.vote_history[-1]}") # Log the latest vote
            # 4. Announce the vote in the voting channel
            voting_channel = self.bot.get_channel(config.VOTING_CHANNEL_ID)
            if voting_channel:
                target_obj = self.get_player_by_name(target_name)
                voter_obj = self.players.get(voter_user.id)
                await voting_channel.send(f"**{voter_obj.display_name}** has voted for **{target_obj.display_name}**.")
                await self.send_vote_count(voting_channel)
                logger.info(f"Vote recorded: {voter_obj.display_name} -> {target_obj.display_name}")
                return f"Your vote for **{self.get_player_by_name(target_name).display_name}** has been recorded."
            else:
                logger.warning(f"Could not find voting channel with ID: {config.VOTING_CHANNEL_ID}")
                return("Vote recorded, but could not find the voting channel to post an update.")


    async def send_vote_count(self, channel):
        """Constructs and Sends the current vote count to the specified channel."""
        if not self.lynch_votes: # If there are no votes, send a message indicating that
            logger.info("No votes have been cast yet.")
            await channel.send("No votes have been cast yet.")
            return
        # Construct the vote count message
        count_message = "**Current Vote Tally:**\n"
        # Sort by number of votes descending
        vote_data = sorted(self.lynch_votes.items(), key=lambda item: len(item[1]), reverse=True)
        for target_id, voter_ids in vote_data:
            target_obj = self.players.get(target_id)
            if target_obj:
                voter_names = [self.players.get(voter_id).display_name for voter_id in voter_ids if self.players.get(voter_id)]
                vote_count = len(voter_ids)
                count_message += f"- **{target_obj.display_name}** ({vote_count}): {', '.join(voter_names)}\n"
        # Also list players who haven't voted
        living_player_ids = {p.id for p in self.players.values() if p.is_alive}
        voted_player_ids = set() # To track who has voted
        # Collect all player IDs who have voted
        for ids in self.lynch_votes.values():
            voted_player_ids.update(ids)
        not_voted_ids = living_player_ids - voted_player_ids
        if not_voted_ids: # If there are players who haven't voted, list them
            not_voted_names = [self.players[p_id].display_name for p_id in not_voted_ids]
            count_message += f"\n**Yet to vote ({len(not_voted_names)}):** {', '.join(not_voted_names)}"
        await channel.send(count_message)

    async def tally_votes(self):
        """
        Determines the outcome of the day's vote, lynching all players
        tied for the most votes, and adds the result to the narration manager.
        """
        # NEW: Handle inactive players
        living_player_ids = {p.id for p in self.players.values() if p.is_alive}
        voted_player_ids = set()
        for ids in self.lynch_votes.values():
            voted_player_ids.update(ids)
        not_voted_ids = living_player_ids - voted_player_ids
        inactivity_deaths = []
        phase_str = f"Day {self.game_settings['phase_number']}"
        logger.info("Determining any inactive players...")
        for player_id in not_voted_ids:
            player_obj = self.players.get(player_id)
            if player_obj:
                player_obj.missed_votes += 1
                if player_obj.missed_votes >= config.MAX_MISSED_VOTES:
                    player_obj.kill(phase_str, "Inactivity")
                    inactivity_deaths.append(player_obj)
                    logger.info(f"Player {player_obj.display_name} has been killed for inactivity.")
        if inactivity_deaths:
            self.narration_manager.add_event('inactivity_kill', victims=inactivity_deaths)
            logger.info(f"Sent inactivity deaths for narration: {inactivity_deaths}")
            # check if any deaths require a godfather promotion
            for dead_player in inactivity_deaths:
                self._handle_promotions(dead_player)
        # Check if there are any votes at all
        # This single check handles both "no votes" and "all votes retracted".
        if not self.lynch_votes or not any(self.lynch_votes.values()):
            self.narration_manager.add_event('no_lynch')
            logger.info("No votes were cast or all were retracted, adding 'no_lynch' event.")
            return
        max_votes = len(max(self.lynch_votes.values(), key=len))
        # Get a list of all player IDs who are tied for the most votes.
        lynched_player_ids = [
            target_id for target_id, voter_ids in self.lynch_votes.items() 
            if len(voter_ids) == max_votes
        ]
        logger.info(f"Lynching players with IDs: {lynched_player_ids} (max votes: {max_votes})")
        # Get the full Player objects for the victims.
        lynched_players = [self.players.get(pid) for pid in lynched_player_ids if self.players.get(pid)] # Filter out any None values in case a player ID was not found.
        # If for some reason we have IDs but no player objects, stop.
        if not lynched_players:
            logger.warning("Could not find player objects for lynching, aborting tally.")
            self.narration_manager.add_event('no_lynch')
            return
        
        # Create a dictionary to hold the details for the narration manager.
        # Format: {victim_object: [voter_objects]}
        phase_str = f"Day {self.game_settings['phase_number']}"
        lynch_details = {}
        for victim in lynched_players:
            # Kill the player and record details FIRST
            victim.kill(phase_str, "Lynched by the town")
            victim.death_info['voters'] = [p.display_name for p in [self.players.get(v_id) for v_id in self.lynch_votes.get(victim.id, [])] if p]
            self._handle_promotions(victim)
            voters = [self.players.get(v_id) for v_id in self.lynch_votes.get(victim.id, [])]
            lynch_details[victim] = voters
        # Add the lynch event for the story
        self.narration_manager.add_event('lynch', victims=lynched_players, details=lynch_details)
        logger.info(f"Lynched players: {[p.display_name for p in lynched_players]} - {[p.role.name for p in lynched_players]} ")
        
        # NOW, check if the lynch resulted in a Jester win
        if len(lynched_players) == 1 and lynched_players[0].role and lynched_players[0].role.name == "Jester":
            self.narration_manager.add_event('jester_win', victim=lynched_players[0])
            logger.info(f"Jester {lynched_players[0].display_name} has won the game by being lynched.")
            self.game_settings['winning_team'] = "Jester" 
            return "Jester"  # Return the winner directly
        return None  # No special winner from this lynch
           
    async def record_night_action(self, interaction: discord.Interaction, action_type: str, target_name: str):
        """Validates and records a night action from a player's DM."""
        # Get the player ID directly from the interaction object
        player_id = interaction.user.id
        player_obj = self.players.get(player_id)
        logger.info(f"Recording night action from player {player_id} ({player_obj.display_name if player_obj else 'Unknown'}) for action '{action_type}' on target '{target_name}'")
        # --- Validation ---
        if self.game_settings["current_phase"] != "night":
            logger.info("Player tried to do night action outside of night phase")
            return "You can only perform actions during the night."
        if not player_obj or not player_obj.is_alive:
            logger.info("Player tried to do night action but is not a valid player or is dead.")
            return "You are not able to perform actions in the game."
        if not player_obj.can_perform_action(action_type):
            logger.info(f"The player's role does not have the '{action_type}' ability.")
            return f"Your role does not have the '{action_type}' ability."
        target_obj = self.get_player_by_name(target_name)
        if not target_obj:
            logger.info(f"Could not find a player named '{target_name}'.")
            return f"Could not find a player named '{target_name}'."
        if not target_obj.is_alive:
            logger.info(f"{target_obj.display_name} is already dead.")
            return f"{target_obj.display_name} is already dead."
        # Add the self-target check back in
        if action_type != 'heal' and target_obj and target_obj.id == player_obj.id:
            return "You cannot target yourself with this ability."
        # NEW: Check for repeat targeting        
        if action_type in ['heal', 'block'] and target_obj and target_obj.id == player_obj.last_action_target_id:
            logger.info("Player tried to target the same person two nights in a row with their heal or block ability.")
            return "You cannot target the same person two nights in a row with this ability."
        # --- Record Action ---
        self.night_actions[player_id] = {
            "type": action_type,
            "target_id": target_obj.id,
            'night_priority': player_obj.role.night_priority if hasattr(player_obj.role, 'night_priority') else 99, # Default to 99 if no priority set
        }
        logger.info(f"Recorded night action: {player_obj.display_name} -> {action_type} on {target_obj.display_name}")
        return f"Your action (**{action_type}** on **{self.get_player_by_name(target_name).display_name}**) has been recorded."

    async def process_night_actions(self):
        """Processes all recorded night actions in the correct priority order."""
        # If no actions were taken, add a 'no_actions' event and return
        if not self.night_actions:
            self.narration_manager.add_event('no_actions')
            return
        # Prepare a structure to hold the outcomes of actions for narration
        night_outcomes = {
            player_id: {'action': data['type'], 'target': data['target_id'], 'status': None}
            for player_id, data in self.night_actions.items()
        }
        self.heals_on_players.clear() # Reset heals and kills tracking
        logger.info("Processing night actions...")
        logger.info(f"Initial night actions: {self.night_actions}")
        logger.info(f"Initial night outcomes before processing: {night_outcomes}")

        # Group actions by their primary priority
        action_priority = {"block": 1, "heal": 2, "kill": 3, "investigate": 4}

        # Create a mapping of priority to list of player IDs
        actions_by_priority = defaultdict(list)
        for player_id, data in self.night_actions.items():
            priority = action_priority.get(data['type'], 99) # Default to 99 if action type is unknown
            actions_by_priority[priority].append(player_id) # Group player IDs by action priority
            logger.debug(f"Action '{data['type']}' from player {player_id} assigned to priority {priority}.")
        # Sort and flatten actions into a final processing order
        final_processing_order = []
        # Itterate over priority groups in ascending order
        for priority in sorted(actions_by_priority.keys()):
            priority_group = actions_by_priority[priority]
            logger.info(f"Processing priority group {priority} with players: {priority_group}")
        # Step 1: Shuffle the group to ensure fairness among roles with the same sub-priority.
            random.shuffle(priority_group)
        # Step 2: Sort the now-shuffled group by the role's specific night_priority using Python's built-in sort.
            # This allows for fine-grained control (e.g., Town Blocker before Mafia Blocker).
            # The sort is stable, maintaining the shuffled order for ties.
            sorted_group = sorted(priority_group, key=lambda pid: self.night_actions[pid].get('night_priority', 99))
        # Step 3: Append the sorted group to the final processing order.           
            final_processing_order.extend(sorted_group)

        logger.info(f"Final action processing order: {final_processing_order}")

        # Process each action in the final determined order
        for player_id in final_processing_order:
            action_data = self.night_actions[player_id] # Get the action data for this player
            logger.info(f"Processing action for player {player_id}: {action_data}")
            handler = actions.ACTION_HANDLERS.get(action_data['type']) # Get the handler function for this action type
            logger.info(f"Found handler for action '{action_data['type']}': {handler}")
            if handler:
                try:
                    handler(self, player_id, action_data['target_id'], night_outcomes) # Call the handler function
                except Exception as e:
                    logger.error(f"Error processing action for player {player_id}: {e}", exc_info=True)
        logger.info(f"Final night outcomes after handlers: {night_outcomes}")
    
    async def _resolve_night_deaths(self):
        """
        Final step of the night. Compares kill attempts against heals to determine
        who dies. Updated to handle multiple killers correctly.
        """
        logger.info("Resolving final night deaths...")
        phase_str = f"Night {self.game_settings['phase_number']}"
        for victim_id, killer_ids in list(self.kill_attempts_on.items()):
            victim_obj = self.players.get(victim_id)
            if not victim_obj or not victim_obj.is_alive:
                continue
            # --- Check for Saves FIRST ---
            # (Saves should still apply to the whole group of attackers)
            if victim_id in self.heals_on_players:
                healer_id = self.heals_on_players[victim_id][0]
                healer_obj = self.players.get(healer_id)
                # Use the first killer in the list for the narration "X saved Y from Z"
                primary_killer = self.players.get(killer_ids[0])
                event_type = 'save_battle_royale' if self.game_settings.get('game_type') == "battle_royale" else 'save'
                self.narration_manager.add_event(event_type, healer=healer_obj, victim=victim_obj, killer=primary_killer)
                continue
            # --- Process Kill: Find a living killer ---
            living_killer = None
            for k_id in killer_ids:
                potential_killer = self.players.get(k_id)
                if potential_killer and potential_killer.is_alive:
                    living_killer = potential_killer
                    break # We found one! That's all we need.
            if living_killer:
                # At least one attacker is alive, Ordos (the victim) dies!
                victim_obj.kill(phase_str, f"Killed by {living_killer.role.name if living_killer.role else 'Unknown'}")
                self._handle_promotions(victim_obj)
                event_type = 'kill_battle_royale' if self.game_settings.get('game_type') == "battle_royale" else 'kill'
                self.narration_manager.add_event(event_type, killer=living_killer, victim=victim_obj)
                logger.info(f"{victim_obj.display_name} was killed by {living_killer.display_name}.")
            else:
                # ALL killers died earlier in this resolution phase.
                primary_killer = self.players.get(killer_ids[0])
                event_type = 'kill_missed_battle_royale' if self.game_settings.get('game_type') == "battle_royale" else 'failed_kill_killer_dead'
                self.narration_manager.add_event(event_type, killer=primary_killer, victim=victim_obj)
                logger.info(f"All kill attempts on {victim_obj.display_name} failed because all attackers are dead.")
        self.kill_attempts_on.clear()
        logger.info("Night deaths resolved.")

    # --- 5. GAME END & UTILITIES ---
    def get_player_by_name(self, name):
        """Finds a Player object by their display name (case-insensitive)."""
        for player_obj in self.players.values():
            if player_obj.display_name.lower() == name.lower():
                return player_obj
        return None

    def _handle_promotions(self, dead_player):
        """
        Checks if the dead player was the Mafia's designated killer (Godfather or Promoted Goon)
        and promotes a new killer if necessary to keep the game going.
        """
        # Checks if player is Mafia AND had the kill ability (Godfather or Promoted Goon)
        # We use .get('kill') to safely handle Mafia roles that don't kill (like Role Blockers)
        # Access alignment from the ROLE, not the player
        if dead_player.role and dead_player.role.abilities.get('kill') and dead_player.role.alignment == "Mafia":
            logger.info(f"Processing promotion because {dead_player.display_name} died.")
            # Find a living Mafioso to promote
            mafioso_to_promote = None
            # Priority 1: Promote a "Mob Goon" first (Standard cannon fodder promotion)
            for player in self.players.values():
                if player.is_alive and player.role and player.role.name == "Mob Goon":
                    mafioso_to_promote = player
                    logger.info(f"Found Mob Goon to promote: {mafioso_to_promote.display_name}")
                    break
            # Priority 2: If no Goon, promote ANY Mafia member (e.g., Role Blocker, Framer)
            # This ensures the Mafia team isn't neutered just because the Goons are dead.
            if not mafioso_to_promote:
                logger.warning("No Mob Goon found to promote. Searching for any surviving Mafia member.")
                for player in self.players.values():
                    if player.is_alive and player.role and player.role.alignment == "Mafia":
                        mafioso_to_promote = player
                        logger.info(f"Found Mafia member to promote: {mafioso_to_promote.display_name} - {mafioso_to_promote.role.name}")
                        break
            # Perform the Promotion
            if mafioso_to_promote:
                # Only promote if they don't ALREADY have the kill ability
                if 'kill' not in mafioso_to_promote.role.abilities:
                    logger.info(f"Promoting {mafioso_to_promote.display_name} to Godfather status.")
                    # Grant the kill ability
                    mafioso_to_promote.role.abilities['kill'] = "Choose a player for the Mafia to kill."
                    # Add event for story narration
                    self.narration_manager.add_event('promotion', promoted_player=mafioso_to_promote)
                    # Notify the player
                    dm_message = (
                        "The Godfather is dead! You have been promoted to the head of the family.\n"
                        "You now have the ability to kill. Use `/kill player-name` in this DM."
                    )
                    asyncio.create_task(mafioso_to_promote.send_dm(self.bot, dm_message))
                    logger.info(f"PROMOTION: {mafioso_to_promote.display_name} now leads the Mafia.")
            else:
                logger.info("The Mafia has been wiped out. No one left to promote.")
                return

    async def save_story_log(self, alignments, end_time):
        """
        Saves the full narrative history, player manifest, and chat log 
        to a Markdown file. 
        Compatible with both v0.5 (Static) and v0.6 (AI).
        """
        logger.info("Saving story log...")
        try:
            # 1. Get the full story string from the manager
            full_story = self.narration_manager.get_full_story_log()
            # 2. Define the filename (e.g., Stats/game_type/game folder/game_12345_story.md)
            # 2.1 Get the game ID
            game_id = self.game_settings.get('game_id', 'unknown_game')
            # 2.2 Build the output directory path
            output_dir = f"{config.data_save_path}/{self.game_settings.get('game_type', 'classic')}/{self.game_settings.get('game_id')}".title().replace('_', ' ')
            # Create the directory if it doesn't exist
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
                logger.info(f"Created output directory: {output_dir}")
            else:
                logger.info(f"Output directory already exists: {output_dir}")
            # Set the filename
            game_id = self.game_settings.get('game_id', 'unknown_game')
            filename = f"{output_dir}/game_{game_id}_story.md"
            logger.info(f"Story log will be saved to: {filename}")
            # 3. Build the Player Manifest (Cast of Characters)
            # This helps the AI associate names with roles and outcomes.
            manifest_section = "## Cast of Characters\n\n| Player | Role | Status |\n| :--- | :--- | :--- |\n"
            for player_id, player in self.players.items():
                status = "Alive" if player.is_alive else f"Dead ({player.death_info.get('phase', 'Unknown')} - {player.death_info.get('how', 'Unknown')})"
                role_name = player.role.name if player.role else "Unknown"
                manifest_section += f"| **{player.display_name}** | {role_name} | {status} |\n"
            logger.info(f"Built player manifest section for story log.{output_dir}/{filename}")
            # 4. Build Chat Transcript (if self.chat_log exists)
            chat_section = ""
            logger.info("Building chat transcript section for story log.")
            if hasattr(self, 'chat_log') and self.chat_log:
                chat_section = "\n## Chat Transcript\n\nTimestamp| Channel | Phase | Player ID | Player Name | Message\n:--- | :--- | :--- | :--- | :---\n"
                for entry in self.chat_log:
                    # Assuming entry is a dict or string. Adjust based on your chat_log structure.
                    if isinstance(entry, dict):
                        timestamp = entry.get('timestamp_utc', '')
                        id = entry.get('user_id', '')
                        name = entry.get('username', 'Unknown')
                        channel = entry.get('channel_name', 'Unknown')
                        phase = entry.get('phase', 'N/A')
                        phase_number = entry.get('phase_number', 0)
                        msg = entry.get('content', '')
                        chat_section += f"**[{timestamp}], Channel: {channel}, Phase: {phase} - {phase_number}, Player ID: {id}, {name}:** {msg}\n\n"
                    else:
                        chat_section += f"{str(entry)}\n\n"
                logger.info("Chat log included in story log.")

            else:
                chat_section = "\n## Chat Transcript\n\n_No chat log available._\n"
                logger.info("No chat log available to include in story log.")
            # 5. Combine into the final file content
            file_content = (
                f"# Game Story Log\n"
                f"**Game ID:** {game_id}\n"
                f"**Start date (UTC):** {self.game_settings.get('start_time').isoformat() if self.game_settings.get('start_time') else 'N/A'}\n"
                f"**End date (UTC):** {end_time.isoformat()}\n"
                f"Game Type: {self.game_settings.get('game_type', 'classic')}\n"
                f"Number of players: {len(self.players)}\n"
                f"Player counts: Town={alignments.get('Town', 0)}, Mafia={alignments.get('Mafia', 0)}, Neutral={alignments.get('Neutral', 0)}\n"
                f"Total days: {self.game_settings.get('phase_number')}\n"
                f"Phase hours: {self.game_settings.get('phase_hours')}\n"
                f"**Winning Team:** {self.game_settings.get('winning_team', 'Unknown')}\n\n"
                f"**Winning Players:** {sorted([p.display_name for p in self.players.values() if p.is_winner])}\n\n"
                f"{manifest_section}\n"
                f"{full_story}"
                f"{chat_section}"
            )
            logger.info(f"Final file content for story log prepared. Saving to {filename}")
            # 6. Save the file
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(file_content)
            logger.info(f"Story log successfully saved to {filename}")
            return filename
        except Exception as e:
            logger.error(f"Failed to save story log: {e}")
            return None
    
    async def save_data_summary(self, game_data, final_summary):
        """Saves the game summary data to a JSON file in the appropriate stats directory."""
        logger.info("Saving game data summary...")
        # --- Save to File ---
        try:
            game_id = game_data.get('game_id')
            if not game_id:
                logger.error("Cannot save summary, game_id is missing.")
                return
            # Construct the new directory path: stats/<game_id>
            # Dynamically build the path based on the game type
            game_type_dir = self.game_settings.get('game_type', 'classic').replace('_', ' ').title() # E.g., "Battle Royale"
            base_dir = os.path.join(config.data_save_path, game_type_dir)
            game_log_dir = os.path.join(base_dir, game_id)
            # Create the directories
            os.makedirs(game_log_dir, exist_ok=True)
            file_path = os.path.join(game_log_dir, f"{game_id}_summary.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(final_summary, f, ensure_ascii=False, indent=4)
            logger.info(f"Game summary saved successfully to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save game summary: {e}")


    # Add this new method to the Game class, for example, before check_win_conditions
    async def _save_game_summary(self, winner):
        """Gathers all game data and saves it to a JSON file in the 'logs' directory."""
        logger.info(f"Saving game summary for game_id: {self.game_settings['game_id']}")
        end_time = datetime.now(timezone.utc)
        # 1. --- Game Overall Data ---
        alignments = Counter(p.role.alignment for p in self.players.values() if p.role)
        # Calulate number of phases
        phase_count = self.game_settings.get('phase_number', 0)
        last_phase = self.game_settings.get('current_phase', 'unknown').lower()
        if last_phase == 'day' or last_phase == 'pre-night':
            total_phases = (phase_count * 2)
        else:
            total_phases = (phase_count * 2) - 1
        game_data = {
            "game_id": self.game_settings.get('game_id'),
            "game_type": self.game_settings.get('game_type', 'classic'),
            "number_of_players": len(self.players),
            "player_counts": {
                "town": alignments.get("Town", 0),
                "mafia": alignments.get("Mafia", 0),
                "neutral": alignments.get("Neutral", 0)
            },
            "start_date_utc": self.game_settings.get('start_time').isoformat() if self.game_settings.get('start_time') else None,
            "end_date_utc": end_time.isoformat(),
            "total_days": self.game_settings.get('phase_number'),
            "phase_hours": self.game_settings.get('phase_hours'),
            "total_phases": total_phases,
            "last_phase": last_phase,
            "winning_faction": winner,
            "winning_players": sorted([p.display_name for p in self.players.values() if p.is_winner])
        }
        # 2. --- Player Data ---
        player_data = []
        for player in sorted(self.players.values(), key=lambda p: p.display_name):
            player_data.append({
                "player_id": player.id,
                "player_name": player.display_name,
                "alignment": player.role.alignment if player.role else "Unknown",
                "role": player.role.name if player.role else "Unknown",
                "status": "Dead" if not player.is_alive else "Alive",
                "is_winner": player.is_winner,
                "death_phase": player.death_info.get('phase'),
                "death_cause": player.death_info.get('how'),
                "death_phase_number": player.death_info.get('phase_number'),
                "lynched_by_voters": player.death_info.get('voters') # From step 4
            })
        # 3. --- Lynch Data ---
        # This comes from the vote_history we captured in step 3
        lynch_data = self.vote_history
        chat_activity_logs =  self.chat_log
        # --- Final Compilation ---
        final_summary = {
            "game_summary": game_data,
            "player_data": player_data,
            "lynch_vote_history": lynch_data,
            "chat_activity_logs": chat_activity_logs
        }
        # 4. --- Save to File ---
        await self.save_data_summary(game_data, final_summary)
        await self.save_story_log(alignments, end_time)
        await self.export_game_stats() 
    
    # In your Game Engine / Main Cog

    async def export_game_stats(self):
        """Handles exporting game stats to Google Sheets or other platforms."""
        logger.info("Exporting game stats...")       
        # --- 🐍 LYDIA'S INJECTION POINT ---
        # Trigger the export immediately after saving.
        # We use create_task so it runs in the background and doesn't freeze the bot.
        export_cog = self.bot.get_cog("ExportCog")
        channel = self.bot.get_channel(config.RULES_AND_ROLES_CHANNEL_ID) # You can specify a channel for the export cog to post in, or pass None if it handles its own channels.
        if export_cog:
            await export_cog.run_export_logic(channel=channel, game_mode=self.game_settings.get('game_type', 'classic'))
            logger.info("Game stats exported.")
        else:
            logger.warning("Export Cog not found. Stats were not uploaded.")
        
    def check_win_conditions(self):
        """Checks if any team has won. Returns the winning team or None."""
        living_players = [p for p in self.players.values() if p.is_alive]
        logger.info(f"Checking win conditions for {len(living_players)} living players.")
        # If there are no living players, it's a draw
        if not living_players:
            return "Draw" # Everyone is dead
        # Count living players by alignment
        counts = Counter(p.role.alignment for p in living_players if p.role)
        mafia_count = counts.get("Mafia", 0) # Count living mafia players
        town_count = counts.get("Town", 0) # Count living town players
        neutral_killer_count = sum(1 for p in living_players if p.role and p.role.alignment == "Serial Killer" and "kill" in p.role.abilities) # Count Neutral Killers specifically (e.g., Serial Killer)
        logger.info(f"Living counts - Mafia: {mafia_count}, Town: {town_count}, Neutral Killers: {neutral_killer_count}")
        # NEW: Add the "Last Person Standing" check here
        if len(living_players) == 1:
            last_player = living_players[0]
            # Return the player's specific role name as the winner
            if last_player.role:
                logger.info(f"Win Condition Met: {last_player.display_name} is the last one standing.")
                if self.game_settings['game_type'] == 'battle_royale':
                    return last_player.display_name
                else:
                    return last_player.role.alignment  # Return the alignment of the last player
        # If there are no living players, it's a draw
        if not living_players:
            return "Draw" # Everyone is dead
            # Other Draw conditions
        # If end of night phase has only 2 players, one for each alignment, it's a draw
        if self.game_settings["current_phase"].lower() == "pre-day" and len(living_players) == 2 and ((mafia_count == 1 and town_count == 1) or (neutral_killer_count == 1 and town_count == 1) or (mafia_count == 1 and neutral_killer_count == 1)):
            logger.info("Draw condition met: Only two players left, one from each alignment.")
            return "Draw"
        # --- Check Win Conditions ---
        if self.game_settings["game_type"] != "battle_royale":
            # Town Win: All Mafia and Neutral Killers are eliminated.
            if mafia_count == 0 and neutral_killer_count == 0:
                # Check if there are any other hostile neutrals left (e.g. Jester doesn't count)
                # This is a more advanced check for later. For now, this is sufficient.
                if town_count > 0:
                    logger.info("Win Condition Met: Town wins.")
                return "Town"    
            # Mafia Win: 
            # Mafia outnumber Town, and no Neutral Killers remain.
            if mafia_count >= town_count and neutral_killer_count == 0:
                if mafia_count > 0:
                    logger.info("Win Condition Met: Mafia wins.")
                    return "Mafia"
            # Mafia equal to Town and is end of day phase and no doc or or protective role exists
            if mafia_count == town_count and neutral_killer_count == 0 and self.game_settings["current_phase"].lower() == "pre-night" :
                # Check if there are no protective roles left (e.g., Doctor)
                protective_roles = [p for p in living_players if p.role and ("heal" in p.role.abilities or "block" in p.role.abilities)]
                if not protective_roles:
                    logger.info("Win Condition Met: Mafia wins.")
                    return "Mafia"
            # Serial Killer or other Neutral Win
            # Neutral Killer Win: Only the Neutral Killer(s) remain.
            if neutral_killer_count > 0 and town_count == 0 and mafia_count == 0:
                logger.info("Win Condition Met: Neutral Killer wins.")
                # You might want to return the specific role name, e.g., "Serial Killer"
                return "Serial Killer"  
            # Or SK wins if SK alive at end of day phase and no doc or protective role exists
            if neutral_killer_count == 1 and town_count == 1 and mafia_count == 0 and self.game_settings["current_phase"].lower() == "pre-night":
                # Check if there are no protective roles left (e.g., Doctor)
                protective_roles = [p for p in living_players if p.role and ("heal" in p.role.abilities or "block" in p.role.abilities)]
                if not protective_roles:
                    logger.info("Win Condition Met: Serial Killer wins.")
                    return "Serial Killer"
            # SK wins if SK alive at end of day phase and only 1 Mafia alive and not godfather
            if neutral_killer_count == 1 and mafia_count == 1 and town_count == 0 and self.game_settings["current_phase"].lower() == "pre-night":
                # Check if there is only one Mafia left and it's not the Godfather
                mafia_roles = [p.role for p in living_players if p.role and p.role.alignment == "Mafia"]
                if len(mafia_roles) == 1 and mafia_roles[0].name != "Godfather":
                    logger.info("Win Condition Met: Serial Killer wins.")
                    return "Serial Killer"
                if len(mafia_roles) == 1 and mafia_roles[0].name == "Godfather":
                    logger.info("Win Condition Met: Draw.")
                    return "Draw"
            # No winner yet return none
        logger.info("No win condition met yet.")
        return None

    async def announce_winner(self, winner):
        """Announces the winner and cleans up the game."""
        logger.info(f"Announcing winner: {winner}")
        # --- Step 1: Determine Winners ---
        winning_players = []
        for player_obj in self.players.values():
            player_obj.is_winner = False
            if player_obj.role:
                if winner in ["Town", "Mafia"] and player_obj.role.alignment == winner:
                    player_obj.is_winner = True
                elif player_obj.role.name == winner:
                    player_obj.is_winner = True
                elif player_obj.display_name == winner:
                    player_obj.is_winner = True     
            if player_obj.is_winner:
                winning_players.append(player_obj)
                logger.info(f"Marked {player_obj.display_name} as a winner.")
            # If player is NOT a winner AND is still alive, mark them as dead now.
            if not player_obj.is_winner and player_obj.is_alive:
                if self.game_settings['current_phase'] == 'pre-day':
                    current_phase = f"Night {self.game_settings['phase_number']}"
                elif self.game_settings['current_phase'] == 'pre-night':
                    current_phase = f"Day {self.game_settings['phase_number']}"
                else:
                    current_phase = f"{self.game_settings['current_phase'].capitalize()} {self.game_settings['phase_number']}"
                player_obj.kill(current_phase, "Game Over - Losing Player")
                logger.info(f"Marked losing player {player_obj.display_name} as dead.")
        # --- Step 2: Save the summary ---
        await self._save_game_summary(winner)
        # --- Step 3: Create display name ---
        winner_display_name = ""
        if winner in ["Town", "Mafia"]:
            winner_display_name = f"The {winner}"
        elif winner == "Draw":
            winner_display_name = "game has ended in a draw! No one"
        elif winning_players:
            winner_display_name = f"**{winning_players[0].display_name}**"
        else:
            winner_display_name = winner
        # --- Step 4: Announce the results ---
        self.narration_manager.add_event('game_over', winner=f"{winner_display_name}")      
        # FIX: Create the game_state dictionary expected by the new v0.6 NarrationManager
        game_state = {
                        "phase": self.game_settings['current_phase'],
                        "number": self.game_settings['phase_number'],
                        "living_players": [p for p in self.players.values() if p.is_alive],
                        "game_type": self.game_settings.get('game_type', 'classic'),
                        "story_type": self.game_settings.get('story_type', 'Classic Mafia'),
                        "is_prologue": False,
                        "is_game_over": True 
                    }
        # Use 'await' and pass the dictionary
        story = await self.narration_manager.construct_story(game_state=game_state)
        # --- Send Messages Separately and Chunked ---
        try:
            channel = self.bot.get_channel(config.STORIES_CHANNEL_ID)
            if not channel:
                logger.error(f"Could not find stories channel {config.STORIES_CHANNEL_ID}")
                return
            # 1. Send the Story First
            full_message = f"**Game Over!**\n{story}"
            # Discord has a 2000 character limit. We need to chunk the message.
            # We use 1900 to be safe and allow for markdown overhead.
            if len(full_message) <= 2000:
                await channel.send(full_message)
            else:
                # Split by lines to preserve formatting where possible
                lines = full_message.split('\n')
                chunk = ""
                for line in lines:
                    # If adding the next line exceeds the limit, send the current chunk
                    if len(chunk) + len(line) + 1 > 1900:
                        await channel.send(chunk)
                        chunk = "" # Reset chunk
                    chunk += line + "\n"
                # Send any remaining text in the buffer
                if chunk:
                    await channel.send(chunk)
            logger.info("Sent game over story to channel.")
            logger.debug(f"Full story content: {story}")
            # 2. Generate the Status Message
            status_message = self.get_status_message()
            if status_message:
                # 3. Check length. If > 1900 chars, chunk it!
                if len(status_message) > 1900:
                    logger.info("Status message is too long, splitting into chunks.")
                    chunks = []
                    current_chunk = ""
                    for line in status_message.split('\n'):
                        # Check if adding this line would exceed the limit
                        if len(current_chunk) + len(line) + 1 > 1900:
                            chunks.append(current_chunk)
                            current_chunk = line + "\n"
                        else:
                            current_chunk += line + "\n"
                    if current_chunk:
                        chunks.append(current_chunk)
                    # Send each chunk as a separate message
                    for chunk in chunks:
                        await channel.send(chunk)
                else:
                    # It fits! Send it normally.
                    await channel.send(status_message)
            logger.info(f"Announced winner: {winner_display_name}.")
        except Exception as e:
            logger.error(f"Error announcing winner: {e}", exc_info=True)

    async def reset(self):
        """
        Resets the game state to prepare for a new game.
        Removes 'Living'/'Dead' roles from all players and assigns 'Spectator'.
        """
        logger.info("Resetting the game state.")
        
        # 1. Update Discord Roles for ALL players
        logger.info("getting relevant discord roles.")
        spectator_role = self.guild.get_role(self.discord_role_data.get("spectator", {}).get("id", 0))
        living_role = self.guild.get_role(self.discord_role_data.get("living", {}).get("id", 0))
        dead_role = self.guild.get_role(self.discord_role_data.get("dead", {}).get("id", 0))
        # Proceed only if all roles are found
        if spectator_role and living_role and dead_role:
            logger.info(f"Updating Discord roles for all {len(self.players)} players to spectator.")
            # Iterate through all players to update roles
            for player_id, player in self.players.items():
                if player_id <=0:
                    continue  # Skip invalid player IDs
                try:
                    member = self.guild.get_member(player_id)
                    if not member:
                        # Fallback: try fetching if not in cache
                        logger.warning(f"Member {player_id} not found in cache, fetching from guild.")
                        try:
                            member = await self.guild.fetch_member(player_id)
                        except discord.NotFound:
                            logger.warning(f"Could not find member {player_id} to reset roles.")
                            continue
                    logger.info(f"Updating roles for player {player.display_name} (ID: {player_id})")
                    # Remove game roles
                    roles_to_remove = [r for r in member.roles if r.id in [living_role.id, dead_role.id]]
                    if roles_to_remove:
                        await member.remove_roles(*roles_to_remove)
                        logger.info(f"Removed roles {', '.join([r.name for r in roles_to_remove])} from {player.display_name}.")
                    # Add spectator role
                    if spectator_role not in member.roles:
                        await member.add_roles(spectator_role)
                        logger.info(f"Added role {spectator_role.name} to {player.display_name}.")
                except discord.Forbidden:
                    logger.error(f"Permission denied when resetting roles for user {player_id}.")
                except Exception as e:
                    logger.error(f"Error resetting roles for user {player_id}: {e}", exc_info=True)
        # 2. Clear Game State
        logger.info("Clearing game state.")
        self.players.clear()
        self.lynch_votes.clear()
        self.game_roles.clear()
        self.night_actions.clear()
        self.vote_history.clear()
        self.heals_on_players.clear()
        self.kill_attempts_on.clear()
        self.night_outcomes.clear()
        self.heals_on_players.clear()
        self.kill_attempts_on.clear()
        self.blocked_players_this_night.clear()
        self.chat_log.clear()
        self.game_settings["start_time"] = None
        self.game_settings["game_started"] = False
        self.game_settings["current_phase"] = "setup"
        self.game_settings["phase_number"] = 0
        self.game_settings["game_id"] = None
        self.force_start_flag = False
        self.reminders_sent.clear()
        self.narration_manager.clear()
        
        # 3. Stop Loops
        if self.game_loop.is_running():
            self.game_loop.cancel()
        if self.signup_loop.is_running():
            self.signup_loop.stop()
            
        logger.info("Game state reset complete.")

    def get_status_message(self):
        """Generates a formatted status message with the current game state."""
        # Construct the base status message
        logger.info("Generating status message.")
        if self.game_settings["current_phase"] == "pre-day":
            current_phase = "Night"
        elif self.game_settings["current_phase"] == "pre-night":
            current_phase = "Day"
        else:
            current_phase = self.game_settings["current_phase"].capitalize()
        status_message = f"**Game Status: {self.game_settings['game_id']}**\n"
        status_message += f"**Phase:** {current_phase.capitalize()} {self.game_settings['phase_number']}\n"
        # Add time remaining only for active phases
        if self.game_settings['current_phase'] in ['day', 'night', 'signup']:
            time_left = format_time_remaining(self.game_settings['phase_end_time'])
            status_message += f"**Time Remaining:** {time_left}\n"
        # --- Player Status Section ---
        # Get categorized player lists
        all_players = list(self.players.values())
        winning_players = sorted([p for p in all_players if p.is_winner], key=lambda p: p.display_name)
        dead_players = sorted([p for p in all_players if not p.is_alive], key=lambda p: p.display_name)
        # Check if the game has ended by seeing if there are any winners
        if winning_players:
            # Game Over: Display winners and their roles
            status_message += f"\n**🏆 Winners:** ({len(winning_players)})\n"
            for player_obj in winning_players:
                role_name = player_obj.role.name if player_obj.role else "Unknown Role"
                role_alignment = player_obj.role.alignment if player_obj.role else "Unknown Alignment"
                # Start the base string
                status_message += f"- {player_obj.display_name} ({role_alignment}: {role_name})"
                # Only add death info if the player is dead
                if not player_obj.is_alive:
                    death_phase = player_obj.death_info.get('phase', 'N/A')
                    death_cause = player_obj.death_info.get('how', 'N/A')
                    status_message += f" (Died on {death_phase} - {death_cause})"
                status_message += "\n" # Add the newline at the end
            # Optionally, list any living players who didn't win
            living_losers = sorted([p for p in all_players if p.is_alive and not p.is_winner], key=lambda p: p.display_name)
            if living_losers:
                status_message += f"\n**Other Living Players:** ({len(living_losers)})\n"
                for player_obj in living_losers:
                    # Reveal roles of living losers since the game is over
                    role_name = player_obj.role.name if player_obj.role else "Unknown Role"
                    role_alignment = player_obj.role.alignment if player_obj.role else "Unknown Alignment"
                    status_message += f"- {player_obj.display_name} ({role_alignment}: {role_name})\n"
        else:
            # Game Ongoing: Display living players without revealing roles
            living_players = sorted([p for p in all_players if p.is_alive], key=lambda p: p.display_name)
            status_message += f"\n**Living Players:** ({len(living_players)})\n"
            for player_obj in living_players:
                status_message += f"- {player_obj.display_name}\n"
        # Always display the list of dead players
        if dead_players:
            status_message += f"\n**Dead Players:** ({len(dead_players)})\n"
            for player_obj in dead_players:
                role_name = player_obj.role.name if player_obj.role else "Unknown Role"
                role_alignment = player_obj.role.alignment if player_obj.role else "Unknown Alignment"
                death_phase = player_obj.death_info.get('phase', 'N/A')
                death_cause = player_obj.death_info.get('how', 'N/A')
                status_message += f"- ~~{player_obj.display_name}~~ (Dead, {role_alignment}: {role_name}, Died on {death_phase} - {death_cause})\n"
        logger.info(f"Generated status message for game {self.game_settings['game_id']}.")
        return status_message
    
    async def role_status_message(self):
        """Generates a status message with the roles being played."""
        logger.debug("Generating role status message for the game.")
        role_counts = Counter(role.name for role in self.game_roles)
        status_message = "\n\n---------------------------------------\n"
        status_message += "\n## Current Roles in the Game: ##\n"
        for role_name, count in role_counts.items():
            status_message += f" - **{role_name}**: {count}\n"
        return status_message
    
    # Admin command to forcibly end the current phase
    async def force_end_phase(self, interaction: discord.Interaction):
        """[ADMIN ONLY] Forcibly ends the current day or night phase."""
        if self.game_settings["current_phase"] in ["day", "night"]:
            self.game_settings["phase_end_time"] = datetime.now(timezone.utc)
            logger.warning(f"Phase forcibly ended by admin: {interaction.user.name}")
            await interaction.response.send_message(
                "Phase end time has been set to now. The game will advance on the next loop. This will set the next phase end time from now.", 
                ephemeral=False
            )
        else:
            await interaction.response.send_message("A day or night phase is not currently active.", ephemeral=True)