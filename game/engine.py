# game/engine.py
import discord
import asyncio
import json
import logging
import io
import random
import os

from discord.ext import tasks
from datetime import datetime, timedelta, timezone
from collections import Counter

import config
import game.actions as actions
from utils.utilities import (
    load_data,
    save_json_data,
    update_player_discord_roles,
    format_time_remaining,
    send_role_dm,
    send_mafia_info_dm,
)

from game.narration import NarrationManager # Import the NarrationManager
from utils.randomness_tester import test_role_distribution # Import the test function
from game.roles import GameRole, get_role_instance
from game.player import Player # Import the Player class

# Get the same logger instance as in mafiabot.py
logger = logging.getLogger('discord')

class Game:
    """Manages the entire state and lifecycle of a single Mafia game."""
    def __init__(self, bot, guild, cleanup_callback=None):
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
            "game_started": False,
            "start_time": None,
            "end_time": None,
            "current_phase": "setup", # Phases: setup, signup, preparation, night, day, finished
            "phase_number": 0,
            "phase_end_time": None,
            "phase_hours": 12, # Default
        }
        self.players = {} # This will now store Player objects: {player_id: Player_Object}
        self.lynch_votes = {} # This will store votes for lynching: {player_id: target_id}
        self.game_roles = [] # This will store GameRole objects assigned to players
        self.night_actions = {} # Stores night actions: {player_id: {"action": "type", "target": id}}
        self.vote_history = [] # NEW: To store every single vote
        self.player_lock = asyncio.Lock() # Create lock to ensure one person at a time for joining and exiting game
        self.vote_lock = asyncio.Lock() # Create lock to ensure one vote at a time 
        # --- Control Flags ---
        self.force_start_flag = False
        self.reminders_sent = set() # Tracks sent reminders for the current phase
        self.max_players = 19 # Default max players
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
    async def start(self, start_datetime_obj, phase_hours, max_players=19):
        """Announces the sign-up phase and starts the signup_loop."""
        self.game_settings["game_id"] = start_datetime_obj.strftime("%Y%m%d-%H%M%S") #sets game_id to a unique string based on the start time
        self.game_settings["game_started"] = True #set game_started to True
        self.game_settings["start_time"] = start_datetime_obj #set start_time to the start time
        self.game_settings["current_phase"] = "signup" #set current phase to signup
        self.game_settings["phase_end_time"] = start_datetime_obj #set when the phase ends
        self.game_settings["phase_hours"] = phase_hours #set phase hours as set within the game initialization
        self.max_players = max_players #set max players as set within the game initialization
        # Announce the game in multiple channels
        # Build the announcement message
        logger.debug("Building announcement message for the sign-up phase.")
        # Get spectator role mention
        # You need the role's ID from your config
        spectator_role_id = self.discord_role_data.get("spectator", {}).get("id", 0)
        # Then, get the actual Role object from the server
        spectator_role = self.guild.get_role(spectator_role_id)
        signup_channel_mention = f"<#{config.SIGN_UP_HERE_CHANNEL_ID}>" 
        start_time_str = start_datetime_obj.strftime('%Y-%m-%d %H:%M:%S UTC') # Format the start time as a string
        time_left_str = format_time_remaining(start_datetime_obj) # Format the time remaining until the game starts
        announcement = (
            f"**A new game of Mafia has been scheduled!**\n\n"
            f"Sign-ups are now open for **{time_left_str}**! {spectator_role.mention} Use `/mafiajoin` in {signup_channel_mention} to join.\n"
            f"The game will officially begin at: **{start_time_str}** (or when {self.max_players} players join)."
        )
        logger.info(f"Game announcement: {announcement}")
        # Send the announcement to the relevant channels
        await self.bot.get_channel(config.TALKY_TALKY_CHANNEL_ID).send(announcement) #send announcement to #talky-talky channel
        await self.bot.get_channel(config.SIGN_UP_HERE_CHANNEL_ID).send(announcement) #send announcement to #sign-up-here channel
        # Create a different message for the rules and roles channel, including the standard rules text
        await self.bot.get_channel(config.RULES_AND_ROLES_CHANNEL_ID).send(f"##New Game##\n--------------------------\n**Game Starting Soon!**\n\n{self.rules_text}\n")
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
            self.signup_loop.stop() # Stop the sign-up loop
            if self.game_settings["current_phase"] == "signup":
                await self.prepare_game() # Start preparing the game if the sign-up phase is still active
            return
        # --- Send Reminder Message if game shouldn't start ---
        time_for_reminder = False
        # Check if it's time to send a reminder message
        if self.last_reminder_time is None: # If no reminders have been sent yet, send the first one
            time_for_reminder = True
        elif (datetime.now(timezone.utc) - self.last_reminder_time).total_seconds() >= config.start_message_send_delay * 60:
            # If enough time has passed (parameter is start_message_send_delay in config.py) since the last reminder, send another one
            time_for_reminder = True
        if time_for_reminder: # If it's time to send a reminder then send it to sign-up channel and @spectator role
            spectator_role = self.guild.get_role(self.discord_role_data.get("spectator", {}).get("id", 0))
            if not spectator_role:
                return # Can't send reminders without the role
            time_left_str = format_time_remaining(self.game_settings["phase_end_time"])
            await self.bot.get_channel(config.SIGN_UP_HERE_CHANNEL_ID).send(
                    f"**Reminder!** {spectator_role.mention}  There's still time to join! Sign-ups close in **{time_left_str}**.\n"
                    f"Use `/mafiajoin` to participate!\n"
            )

    # In game/engine.py

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
            await channel.send(f"Welcome to the game, **{player_name}**! You are player #{len(self.players)}.")
            logger.info(f"{user.name} ({player_name}) has joined the game.")
            await update_player_discord_roles(self.bot, self.guild, self.players, self.discord_role_data) # Update player roles in Discord
            status_message = self.get_status_message() # Generate a status message with players listed
            try:
                await channel.send(status_message) # Send the status message to the sign-up channel
            except Exception as e:
                logger.error(f"Failed to send status message: {e}")
    
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
            logger.error("Could not find rules channel to post randomness test results.")
        # --- End of Test ---
        await self.assign_roles() #assign roles to players randomly
        logger.info(f"Assigned roles to {len(self.players)} players.")
        # Update player roles in Discord based on their game status (alive, dead, or spectator)
        await update_player_discord_roles(self.bot, self.guild, self.players, self.discord_role_data) 
        status_message = self.get_status_message() # Generate a status message with players listed
        try:
            await rules_channel.send(status_message)
        except Exception as e:
            logger.error(f"Failed to send status message: {e}")
        # Start the main game loop
        self.game_loop.start()
        logger.info(f"Game prepared. Starting main game loop.")

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
        num_players = len(self.players)
        setup_key = str(num_players)
        # Check if we have a setup for this number of players
        if setup_key not in self.mafia_setups:
            logger.error(f"No setup found for {num_players} players in mafia_setups.json.")
            return
        # Randomly select a setup for this player count
        setup = random.choice(self.mafia_setups[setup_key])
        logger.info(f"Using setup for {num_players} players: {setup['id']}")
        # Generate a list of roles based on the setup
        self.game_roles = []
        for role_data in setup["roles"]:
            for _ in range(role_data["quantity"]):
                role_instance = get_role_instance(role_data["name"])
                if role_instance:
                    self.game_roles.append(role_instance)
                else:
                    logger.warning(f"Could not find or create an instance for role: {role_data['name']}")    
        logger.info(f"Generated {len(self.game_roles)} roles for {num_players} players.")

    async def assign_roles(self):
        """Assigns the generated roles to players randomly and sends DMs."""
        player_ids = list(self.players.keys()) # Get a list of player IDs
        random.shuffle(player_ids) # Shuffle the player IDs to randomize role assignment
        random.shuffle(self.game_roles) # Shuffle the roles to randomize assignment
        # Assign a role from game_roles to each player in player_ids
        logger.info(f"Assigning {len(self.game_roles)} roles to {len(player_ids)} players.")
        for i, player_id in enumerate(player_ids):
            player_obj = self.players.get(player_id)
            if i < len(self.game_roles):
                role = self.game_roles[i]
                player_obj.assign_role(role) # Use the Player object's method
                if not player_obj.is_npc:
                    await send_role_dm(self.bot, player_id, role)
            else:
                logger.warning(f"More players than available roles. Player {player_obj.display_name} was not assigned a role.")
        logger.info("Roles assigned to players successfully.")
        # After assigning roles, send Mafia team information to Mafia players
        await send_mafia_info_dm(self.bot, self.players)
        logger.info("Mafia team information has been distributed.")

    # --- 3. MAIN GAME LOOP ---
    @tasks.loop(seconds=config.game_loop_interval_seconds) # Run every 15 seconds to check phase deadlines
    async def game_loop(self):
        """
        The main game loop. Runs every 15 seconds to check phase deadlines and send reminders. - To be updated in production to run every minute
        It handles the transition between phases, processes end-of-phase events, and checks for win conditions
        """
        # If the phase has ended, process it and start the next one
        if datetime.now(timezone.utc) >= self.game_settings["phase_end_time"]:
            # Process end-of-phase events and add them to the narration manager
            winner = None # Initialize winner
            if self.game_settings["current_phase"].lower() == "day":
                winner = await self.tally_votes() # Capture winner from the lynch vote
                logger.debug("Day phase ended. Processing lynch votes...")
            elif self.game_settings["current_phase"].lower() == "night":
                logger.debug("Night phase ended. Processing night actions...")
                await self.process_night_actions() # If night phase has ended, process all night actions
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
            # Check for win conditions if win conditions not already met (i.e. Jester win)
            if not winner:
                logger.debug("Checking win conditions after phase end.")
                winner = self.check_win_conditions()
            # Construct the story (the narrator function now adds the header)
            story = self.narration_manager.construct_story(
                self.game_settings['current_phase'],
                self.game_settings['phase_number']
            )
            if story:
                #send story to the stories channel
                logger.debug("Story constructed from narration manager events.")
                await self.bot.get_channel(config.STORIES_CHANNEL_ID).send(story)
            logger.info(f"Phase {self.game_settings['current_phase']} {self.game_settings['phase_number']} ended. Story constructed.")
            # Clear the narration manager for the next phase
            self.narration_manager.clear()
            if winner: #if there is a winner, announce them and stop the game loop
                await self.announce_winner(winner)
                self.game_loop.stop()
                logger.info(f"Game ended with winner: {winner}")
                 
                return
            await update_player_discord_roles(self.bot, self.guild, self.players, self.discord_role_data) # Update player roles based on their current state
            logger.info("Updated player roles in Discord based on current game state.")
            # Generate a status message with players listed and send it to the Rules channel
            status_message = self.get_status_message() 
            try:
                await self.bot.get_channel(config.RULES_AND_ROLES_CHANNEL_ID).send(status_message)
            except Exception as e:
                logger.error(f"Error sending status message: {e}")
            # Transition to the new phase
            self.reminders_sent.clear() # Reset reminders for the new phase
            self.game_settings["phase_end_time"] = datetime.now(timezone.utc) + timedelta(hours=self.game_settings["phase_hours"])
            if self.game_settings["current_phase"] == "night": # If the current phase was 'night', transition to 'day'
                self.game_settings["current_phase"] = "day"
                #announce the start of the new day phase
                announcement = f"## ☀️ Day {self.game_settings['phase_number']} has begun. You have {format_time_remaining(self.game_settings['phase_end_time'])}  to discuss and vote."
                logger.info("Transitioning to day phase.")
            else: # Was 'preparation' or 'day'
                self.game_settings["current_phase"] = "night" # Transition to 'night'
                self.game_settings["phase_number"] += 1 # Increment the phase number at each night phase transition
                # Reset night actions and lynch votes for the new night phase
                self.night_actions = {} 
                self.lynch_votes = {}
                announcement = f"## 🌙 Night {self.game_settings['phase_number']} has begun. You have {format_time_remaining(self.game_settings['phase_end_time'])} hours to use your night actions."
                logger.info("Transitioning to night phase.")
            # Set the end time for the new phase
            
            await self.bot.get_channel(config.STORIES_CHANNEL_ID).send(announcement)
            return # End this loop iteration after phase transition
        # --- If phase has NOT ended, check for reminders ---
        time_left = self.game_settings["phase_end_time"] - datetime.now(timezone.utc) #determine how much time is left in the current phase
        total_minutes_left = time_left.total_seconds() / 60 # Convert to total minutes
        living_role = self.guild.get_role(self.discord_role_data.get("living", {}).get("id", 0)) # Get the living role mention
        if not living_role: return # Can't send reminders without the living role
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
            if voter_obj.id == target_obj.id: # Check if the voter is trying to vote for themselves
                # If so, send a message and log the attempt
                logger.warning(f"{voter_obj.display_name} tried to vote for themselves.")
                return "You cannot vote for yourself."
            logger.info(f"Vote from {voter_obj.display_name} for target {target_obj.display_name} is valid.")
            # 2. Handle vote changes (un-vote previous target)
            if voter_obj.action_target is not None: # First check if the voter has a previous target
                # If they do, remove their vote from the previous target
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
                logger.error(f"Could not find voting channel with ID: {config.VOTING_CHANNEL_ID}")
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
        # If no votes were cast, add the 'no_lynch' event and stop.
        if not self.lynch_votes:
            self.narration_manager.add_event('no_lynch')
            logger.info("No votes were cast, adding 'no_lynch' event.")
            return
        # Find the maximum number of votes any player received.
        max_votes = len(max(self.lynch_votes.values(), key=len))
        # If the highest vote count is 0 (e.g., votes were cast and then retracted), treat as no lynch.
        if max_votes == 0:
            self.narration_manager.add_event('no_lynch')
            logger.info("No votes received, adding 'no_lynch' event.")
            return
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
            logger.error("Could not find player objects for lynching, aborting tally.")
            self.narration_manager.add_event('no_lynch')
            return
        # Inside tally_votes, after identifying the lynched player(s)
        if len(lynched_players) == 1:
            lynched_player = lynched_players[0]
            logger.info(f"Lynched_player = {lynched_player.display_name}")
            # NEW: Check for Jester win condition
            if lynched_player.role.name == "Jester":
                self.narration_manager.add_event('jester_win', victim=lynched_player)
                # The game ends immediately in a Jester victory
                self.game_settings['winning_team'] = "Jester" 
                logger.info(f"Jester {lynched_player.display_name} has won the game by being lynched.")
                return # End the tallying process
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

        # NOW, check if the lynch resulted in a Jester win
        if len(lynched_players) == 1 and lynched_players[0].role and lynched_players[0].role.name == "Jester":
            self.narration_manager.add_event('jester_win', victim=lynched_players[0])
            logger.info(f"Jester {lynched_players[0].display_name} has won.")
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
            "target_id": target_obj.id
        }
        #await interaction.response.send_message(f"Your action (**{action_type}** on **{target_obj.display_name}**) has been recorded for the night.")
        logger.info(f"Recorded night action: {player_obj.display_name} -> {action_type} on {target_obj.display_name}")
        return f"Your action (**{action_type}** on **{self.get_player_by_name(target_name).display_name}**) has been recorded."

    async def process_night_actions(self):
        """Processes all recorded night actions using the ACTION_HANDLERS dictionary."""
        if not self.night_actions:
            self.narration_manager.add_event('no_actions')
            return
        # 1. Initialize outcomes for all submitted actions
        night_outcomes = {
            player_id: {'action': data['type'], 'target': data['target_id'], 'status': 'success'}
            for player_id, data in self.night_actions.items()
        }
        logger.info(f"Processing night actions: {night_outcomes}")
        self.protected_players_this_night = set()
        self.blocked_players_this_night = set() # NEW: Track blocked players
        # 2. Process actions by priority to determine final outcomes
        action_priority = {"block": 1, "heal": 2, "kill": 3, "investigate": 4}
        sorted_player_ids = sorted(
            self.night_actions.keys(),
            key=lambda pid: action_priority.get(self.night_actions[pid]['type'], 99)
        )        
        for player_id in sorted_player_ids:
            action = self.night_actions[player_id]
            handler = actions.ACTION_HANDLERS.get(action['type'])
            if handler:
                # Pass the night_outcomes dict to the handlers
                handler(self, player_id, action['target_id'], night_outcomes)
        logger.info(f"Processed night actions: {night_outcomes}\nReady to send to be prepped for narration")
        # 3. Generate the story based on the final outcomes
        self._generate_narration_from_outcomes(night_outcomes)

    # --- 5. GAME END & UTILITIES ---
    def get_player_by_name(self, name):
        """Finds a Player object by their display name (case-insensitive)."""
        for player_obj in self.players.values():
            if player_obj.display_name.lower() == name.lower():
                return player_obj
        return None
    
    # In the Game class, you can add this method after process_night_actions

    def _generate_narration_from_outcomes(self, night_outcomes):
        """
        Looks at the final outcomes and generates stories ONLY for actions
        that were successful, as blocked/saved/immune stories are handled elsewhere.
        """
        for player_id, outcome in night_outcomes.items():
            if outcome['status'] != 'success':
                continue

            actor = self.players.get(player_id)
            target = self.players.get(outcome['target'])
            
            if outcome['action'] == 'kill':
                self.narration_manager.add_event('kill', killer=actor, victim=target)
            elif outcome['action'] == 'investigate':
                self.narration_manager.add_event('investigate', investigator=actor, target=target)

    def _handle_promotions(self, dead_player):
        """Checks for and handles promotions (e.g., Mafioso to Godfather)."""
        logger.info(f"Checking for promotion of {dead_player.display_name}.")
        if dead_player.role and dead_player.role.name == "Godfather":
            logger.info(f"{dead_player.display_name} is the {dead_player.role.name}.")
            # Find a living Mafioso to promote
            mafioso_to_promote = None
            for player in self.players.values():
                if player.is_alive and player.role and player.role.name == "Mob Goon":
                    mafioso_to_promote = player
                    break
            if not mafioso_to_promote:
                logger.warning("No Mob Goon found to promote to Godfather, trying to find other mob.")
                # If no Mob Goon found, try to find any Mafia member to promote
                for player in self.players.values():
                    if player.is_alive and player.role and player.role.alignment == "Mafia":
                        mafioso_to_promote = player
                        break
            # If a Mafioso was found, promote them to Godfather
            if mafioso_to_promote and 'kill' not in mafioso_to_promote.role.abilities:
                logger.info(f"Promoting {mafioso_to_promote.display_name} to Godfather.")
                # Assign the Godfather role to the Mafioso
                mafioso_to_promote.role.abilities['kill'] = "Choose a player for the Mafia to kill."
                self.narration_manager.add_event('promotion', promoted_player=mafioso_to_promote)
                # Send a DM to the newly promoted Godfather
                dm_message = "The Godfather is dead! You have been promoted and now have the ability to kill."
                self.bot.loop.create_task(mafioso_to_promote.send_dm(self.bot, dm_message))
                logger.info(f"Promoted {mafioso_to_promote.display_name} to have kill ability.")
    
    # Add this new method to the Game class, for example, before check_win_conditions
    async def _save_game_summary(self, winner):
        """Gathers all game data and saves it to a JSON file in the 'logs' directory."""
        logger.info(f"Saving game summary for game_id: {self.game_settings['game_id']}")
        end_time = datetime.now(timezone.utc)
        # 1. --- Game Overall Data ---
        alignments = Counter(p.role.alignment for p in self.players.values() if p.role)
        game_data = {
            "game_id": self.game_settings.get('game_id'),
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
                "lynched_by_voters": player.death_info.get('voters') # From step 4
            })
        # 3. --- Lynch Data ---
        # This comes from the vote_history we captured in step 3
        lynch_data = self.vote_history
        # --- Final Compilation ---
        final_summary = {
            "game_summary": game_data,
            "player_data": player_data,
            "lynch_vote_history": lynch_data
        }
        # --- Save to File ---
        try:
            game_id = game_data.get('game_id')
            if not game_id:
                logger.error("Cannot save summary, game_id is missing.")
                return
            # Construct the new directory path: Stats/<game_id>
            game_log_dir = os.path.join("Stats/alpha_testing", game_id)
            # Create the directory (and the parent 'Stats' dir if it doesn't exist)
            os.makedirs(game_log_dir, exist_ok=True)
            # Define the file path inside the new directory
            file_path = os.path.join(game_log_dir, f"{game_id}_summary.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(final_summary, f, ensure_ascii=False, indent=4)
            logger.info(f"Game summary saved successfully to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save game summary: {e}")

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
        neutral_killer_count = sum(1 for p in living_players if p.role and p.role.alignment == "Neutral" and "kill" in p.role.abilities) # Count Neutral Killers specifically (e.g., Serial Killer)
        logger.info(f"Living counts - Mafia: {mafia_count}, Town: {town_count}, Neutral Killers: {neutral_killer_count}")
        
        # Other Draw conditions
        # If end of night phase has only 2 players, one for each alignment, it's a draw
        if self.game_settings["current_phase"].lower() == "night" and len(living_players) == 2 and ((mafia_count == 1 and town_count == 1) or (neutral_killer_count == 1 and town_count == 1) or (mafia_count == 1 and neutral_killer_count == 1)):
            logger.info("Draw condition met: Only two players left, one from each alignment.")
            return "Draw"
        
        # --- Check Win Conditions ---
        # Town Win: All Mafia and Neutral Killers are eliminated.
        if mafia_count == 0 and neutral_killer_count == 0:
            # Check if there are any other hostile neutrals left (e.g. Jester doesn't count)
            # This is a more advanced check for later. For now, this is sufficient.
            if town_count > 0:
                logger.info("Win Condition Met: Town wins.")
                return "Town"
            
        # Mafia Win: 
        # Mafia outnumber Town, and no Neutral Killers remain.
        if mafia_count > town_count and neutral_killer_count == 0:
            if mafia_count > 0:
                logger.info("Win Condition Met: Mafia wins.")
                return "Mafia"
        # Mafia equal to Town and is end of day phase and no doc or or protective role exists
        if mafia_count == town_count and neutral_killer_count == 0 and self.game_settings["current_phase"].lower() == "day" :
            # Check if there are no protective roles left (e.g., Doctor)
            protective_roles = [p for p in living_players if p.role and ("heal" in p.role.abilities or "block" in p.role.abilities)]
            if not protective_roles:
                logger.info("Win Condition Met: Mafia wins.")
                return "Mafia"
            
        # Neutral Killer Win: Only the Neutral Killer(s) remain.
        if neutral_killer_count > 0 and town_count == 0 and mafia_count == 0:
            logger.info("Win Condition Met: Neutral Killer wins.")
            # You might want to return the specific role name, e.g., "Serial Killer"
            return "Serial Killer"  
        # Or SK wins if SK alive at end of day phase and no doc or protective role exists
        if neutral_killer_count == 1 and town_count == 1 and mafia_count == 0 and self.game_settings["current_phase"].lower() == "day":
            # Check if there are no protective roles left (e.g., Doctor)
            protective_roles = [p for p in living_players if p.role and ("heal" in p.role.abilities or "block" in p.role.abilities)]
            if not protective_roles:
                logger.info("Win Condition Met: Serial Killer wins.")
                return "Serial Killer"
        # SK wins if SK alive at end of day phase and only 1 Mafia alive and not godfather
        if neutral_killer_count == 1 and mafia_count == 1 and town_count == 0 and self.game_settings["current_phase"].lower() == "day":
            # Check if there is only one Mafia left and it's not the Godfather
            mafia_roles = [p.role for p in living_players if p.role and p.role.alignment == "Mafia"]
            if len(mafia_roles) == 1 and mafia_roles[0].name != "Godfather":
                logger.info("Win Condition Met: Serial Killer wins.")
                return "Serial Killer"

        # No winner yet return none
        logger.info("No win condition met yet.")
        return None

    async def announce_winner(self, winner):
        """Announces the winner and cleans up the game."""
        logger.info(f"Announcing winner: {winner}")
        # Set 'is_winner' flag on player objects
        for player_obj in self.players.values():
            player_obj.is_winner = False # Default to not a winner
            if not player_obj.role:
                continue
            # Check for faction wins (e.g., winner="Town")
            if winner in ["Town", "Mafia"] and player_obj.role.alignment == winner:
                player_obj.is_winner = True
            # Check for specific role wins (e.g., winner="Jester")
            elif player_obj.role.name == winner:
                player_obj.is_winner = True

            if player_obj.is_winner:
                logger.info(f"Marked {player_obj.display_name} as a winner.")
        # Generate a status message
        status_message = self.get_status_message() # Generate a final status message
        self.narration_manager.add_event('game_over', winner=winner) # Add game end event to the narration manager
        story = self.narration_manager.construct_story(self.game_settings['current_phase'], self.game_settings['phase_number']) # Construct the final story
        # NEW: Call the summary function here
        await self._save_game_summary(winner)
        if story:
              story += f"\n\n{status_message}" # Add the status message to the story
        try:
            await self.bot.get_channel(config.STORIES_CHANNEL_ID).send(f"**Game Over!**\n{story}")
            logger.info(f"Announced winner: {winner}.")
        except Exception as e:
            logger.error(f"Error announcing winner: {e}")

    async def reset(self):
        """Resets the game state and cancels any running tasks."""
        logger.info("Resetting the game state.")
        # Cancel any running loops
        if self.signup_loop.is_running():
            self.signup_loop.cancel()
        if self.game_loop.is_running():
            self.game_loop.cancel()
        # Reset Discord roles for all players involved
        logger.info(f"Resetting player roles in Discord.")
        await update_player_discord_roles(self.bot, self.guild, self.players, self.discord_role_data)
        # Clear game state
        logger.info("Clearing game state variables.")
        self.players.clear()
        self.game_settings["game_started"] = False
        self.game_settings["current_phase"] = "finished"
        logger.info(f"Game {self.game_settings['game_id']} has been reset.")

    def get_status_message(self):
        """Generates a formatted status message with the current game state."""
        # Construct the base status message
        logger.info("Generating status message.")
        status_message = f"**Game Status: {self.game_settings['game_id']}**\n"
        status_message += f"**Phase:** {self.game_settings['current_phase'].capitalize()} {self.game_settings['phase_number']}\n"
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