# game/engine.py
import discord
import asyncio
import json
import logging
from discord.ext import tasks
from datetime import datetime, timedelta, timezone
import random

import config
from utils.utilities import (
    load_data,
    save_json_data,
    update_player_discord_roles,
    format_time_remaining,
    send_role_dm,
)
from game.roles import GameRole, get_role_instance
from game.player import Player # Import the Player class

# Get the same logger instance as in mafiabot.py
logger = logging.getLogger('discord')

class Game:
    """Manages the entire state and lifecycle of a single Mafia game."""

    def __init__(self, bot, ctx):
        logger.info("Initializing new Game instance.")
        self.bot = bot
        self.ctx = ctx  # The context from the '/startmafia' command
        self.guild = ctx.guild
        self.last_reminder_time = None  # Track the last time a reminder was sent

        # --- Game State Variables ---
        self.game_settings = {
            "game_id": None,
            "game_started": False,
            "current_phase": "setup", # Phases: setup, signup, night, day, finished
            "phase_number": 0,
            "phase_end_time": None,
            "phase_hours": 12, # Default
        }
        self.players = {} # This will now store Player objects: {player_id: Player_Object}
        self.lynch_votes = {}
        self.game_roles = []
        self.night_actions = {} # Stores night actions: {player_id: {"action": "type", "target": id}}
        
        # --- Control Flags ---
        self.force_start_flag = False
        self.reminders_sent = set() # Tracks sent reminders for the current phase
        self.max_players = 25 # Default max players

        # --- Data Loading ---
        self.discord_role_data = load_data("data/discord_roles.json")
        self.npc_names = load_data("data/bot_names.txt")
        self.rules_text = "\n".join(load_data("data/rules.txt"))
        self.mafia_setups = load_data("data/mafia_setups.json")

        if not self.mafia_setups:
            logger.critical("No mafia setups loaded. The game cannot start.")
        
        logger.debug("Game instance initialized.")

    # --- 1. SIGN-UP PHASE ---

    async def start(self, start_datetime_obj, phase_hours, max_players=25):
        """Announces the sign-up phase and starts the signup_loop."""
        self.game_settings["game_id"] = start_datetime_obj.strftime("%Y%m%d-%H%M%S")
        self.game_settings["game_started"] = True
        self.game_settings["current_phase"] = "signup"
        self.game_settings["phase_end_time"] = start_datetime_obj
        self.game_settings["phase_hours"] = phase_hours
        self.max_players = max_players

        # Announce the game in multiple channels
        signup_channel_mention = f"<#{config.SIGN_UP_HERE_CHANNEL_ID}>"
        start_time_str = start_datetime_obj.strftime('%Y-%m-%d %H:%M:%S UTC')
        time_left_str = format_time_remaining(start_datetime_obj)

        announcement = (
            f"**A new game of Mafia has been scheduled!**\n\n"
            f"Sign-ups are now open for **{time_left_str}**! Use `/join <your_game_name>` in {signup_channel_mention} to join.\n"
            f"The game will officially begin at: **{start_time_str}** (or when {self.max_players} players join)."
        )
        await self.bot.get_channel(config.TALKY_TALKY_CHANNEL_ID).send(announcement)
        await self.bot.get_channel(config.SIGN_UP_HERE_CHANNEL_ID).send(announcement)
        await self.bot.get_channel(config.RULES_AND_ROLES_CHANNEL_ID).send(f"**Game Starting Soon!**\n\n{self.rules_text}")
        
        # Start the sign-up monitoring loop
        self.signup_loop.start()

    @tasks.loop(seconds=30) # Loop periodically to send reminders
    async def signup_loop(self):
        """Monitors the sign-up phase, sends reminders, and checks for start conditions."""
        
        # --- Check for start conditions ---
        game_should_start = False
        reason = ""

        if datetime.now(timezone.utc) >= self.game_settings["phase_end_time"]:
            game_should_start = True
            reason = "The scheduled start time has been reached."
        elif len(self.players) >= self.max_players:
            game_should_start = True
            reason = f"The maximum number of players ({self.max_players}) has been reached."
        elif self.force_start_flag:
            game_should_start = True
            reason = "The game has been force-started by an administrator."

        if game_should_start:
            logger.info(f"Ending sign-up loop. Reason: {reason}")
            await self.bot.get_channel(config.SIGN_UP_HERE_CHANNEL_ID).send(f"**Sign-ups are now closed!** {reason} The game will now begin.")
            self.signup_loop.stop()
            if self.game_settings["current_phase"] == "signup":
                await self.prepare_game()
            return

        # --- Send Reminder Message ---
        time_for_reminder = False
        if self.last_reminder_time is None:
            time_for_reminder = True
        elif (datetime.now(timezone.utc) - self.last_reminder_time).total_seconds() >= config.start_message_send_delay * 60:
            time_for_reminder = True
        if time_for_reminder:
            spectator_role = self.guild.get_role(self.discord_role_data.get("spectator", {}).get("id", 0))
            if not spectator_role:
                return # Can't send reminders without the role
            time_left_str = format_time_remaining(self.game_settings["phase_end_time"])
            await self.bot.get_channel(config.SIGN_UP_HERE_CHANNEL_ID).send(
                    f"**Reminder!** {spectator_role.mention}  There's still time to join! Sign-ups close in **{time_left_str}**.\n"
                    f"Use `/mafiajoin` to participate!\n"
            )

    async def force_start(self, ctx):
        """Admin command to force the signup phase to end and the game to start."""
        if self.game_settings["current_phase"] != "signup":
            await ctx.send("This command can only be used during the sign-up phase.")
            return
        
        self.force_start_flag = True
        await ctx.send(f"Force start flag has been set. The game will begin on the next loop iteration (within {config.start_message_send_delay} minutes).")
        logger.warning(f"Game force start initiated by {ctx.author.name}.")


    async def add_player(self, user, player_name):
        """Adds a player to the game during the signup phase."""
        if self.game_settings["current_phase"] != "signup":
            await self.ctx.send("Sorry, the game is not currently accepting new players.")
            return

        if user.id in self.players:
            await self.ctx.send("You have already joined the game!")
            return
            
        if len(self.players) >= self.max_players:
            await self.ctx.send(f"Sorry, the game is full with {self.max_players} players.")
            return

        # Create a Player object instead of a dictionary
        self.players[user.id] = Player(user_id=user.id, discord_name=user.name, display_name=player_name)
        
        await self.ctx.send(f"Welcome to the game, **{player_name}**! You are player #{len(self.players)}.")
        logger.info(f"{user.name} ({player_name}) has joined the game.")

    # --- 2. GAME PREPARATION ---

    async def prepare_game(self):
        """Prepares the game by adding NPCs, assigning roles, and starting the main loop."""
        logger.info("Sign-up phase ended. Preparing game...")
        self.game_settings["current_phase"] = "preparation"
        
        # Add NPCs if player count is below minimum (e.g., 5)
        min_players = config.min_players
        while len(self.players) < min_players:
            self.add_npc()

        # Generate and assign roles
        self.generate_game_roles()
        if not self.game_roles:
            await self.ctx.send("Error: Could not generate roles based on the number of players. Aborting game.")
            await self.reset()
            return

        await self.assign_roles()
        await update_player_discord_roles(self.bot, self.guild, self.players, self.discord_role_data)
        
        # Start the main game loop
        self.game_loop.start()
        logger.info(f"Game prepared. Starting main game loop.")

    def add_npc(self):
        """Adds a single NPC to the game."""
        # Use attribute access on Player objects now
        available_names = [name for name in self.npc_names if name not in [p.display_name for p in self.players.values()]]
        if not available_names:
            logger.error("Could not add NPC, no unique names available.")
            return
            
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
        player_ids = list(self.players.keys())
        random.shuffle(player_ids)
        random.shuffle(self.game_roles)

        for i, player_id in enumerate(player_ids):
            player_obj = self.players.get(player_id)
            if i < len(self.game_roles):
                role = self.game_roles[i]
                player_obj.assign_role(role) # Use the Player object's method
                
                if not player_obj.is_npc:
                    await send_role_dm(self.bot, player_id, role)
            else:
                logger.warning(f"More players than available roles. Player {player_obj.display_name} was not assigned a role.")

    # --- 3. MAIN GAME LOOP ---

    @tasks.loop(minutes=1)
    async def game_loop(self):
        """
        The main game loop. Runs every minute to check phase deadlines and send reminders.
        """
        # If the phase has ended, process it and start the next one
        if datetime.now(timezone.utc) >= self.game_settings["phase_end_time"]:
            story_parts = []
            if self.game_settings["current_phase"] == "day":
                lynch_story = await self.tally_votes()
                if lynch_story: story_parts.append(lynch_story)
            elif self.game_settings["current_phase"] == "night":
                night_story = await self.process_night_actions()
                if night_story: story_parts.append(night_story)

            if story_parts:
                full_story = "\n\n".join(story_parts)
                await self.bot.get_channel(config.STORIES_CHANNEL_ID).send(f"**--- End of {self.game_settings['current_phase'].capitalize()} {self.game_settings['phase_number']} ---**\n{full_story}")

            winner = self.check_win_conditions()
            if winner:
                await self.announce_winner(winner)
                self.game_loop.stop()
                return
            
            await update_player_discord_roles(self.bot, self.guild, self.players, self.discord_role_data)
            
            # Transition to the new phase
            self.reminders_sent.clear() # Reset reminders for the new phase
            if self.game_settings["current_phase"] == "night":
                self.game_settings["current_phase"] = "day"
                announcement = f"## ☀️ Day {self.game_settings['phase_number']} has begun. You have {self.game_settings['phase_hours']} hours to discuss and vote."
            else: # Was 'preparation' or 'day'
                self.game_settings["current_phase"] = "night"
                self.game_settings["phase_number"] += 1
                self.night_actions = {} 
                self.lynch_votes = {}
                announcement = f"## 🌙 Night {self.game_settings['phase_number']} has begun. You have {self.game_settings['phase_hours']} hours to use your night actions."

            self.game_settings["phase_end_time"] = datetime.now(timezone.utc) + timedelta(hours=self.game_settings["phase_hours"])
            await self.bot.get_channel(config.STORIES_CHANNEL_ID).send(announcement)
            return # End this loop iteration after phase transition

        # --- If phase has NOT ended, check for reminders ---
        time_left = self.game_settings["phase_end_time"] - datetime.now(timezone.utc)
        total_minutes_left = time_left.total_seconds() / 60
        
        living_role = self.guild.get_role(self.discord_role_data.get("living", {}).get("id", 0))
        if not living_role: return

        reminder_points = {60: "1 hour", 30: "30 minutes", 10: "10 minutes"}

        for minutes, text in reminder_points.items():
            if total_minutes_left <= minutes and minutes not in self.reminders_sent:
                await self.bot.get_channel(config.STORIES_CHANNEL_ID).send(
                    f"**Reminder:** There is **{text}** left in the phase! {living_role.mention}"
                )
                self.reminders_sent.add(minutes)
                break # Only send one reminder per loop iteration
        
    @game_loop.before_loop
    async def before_game_loop(self):
        await self.bot.wait_until_ready()
        logger.info("Main game loop is starting.")
        # Trigger the first phase transition immediately
        self.game_settings["phase_end_time"] = datetime.now(timezone.utc)
        
    @signup_loop.before_loop
    async def before_signup_loop(self):
        await self.bot.wait_until_ready()
        logger.info("Sign-up loop is starting.")

    # --- 4. ACTION & VOTE PROCESSING ---
    
    async def process_lynch_vote(self, ctx, voter, target_name):
        """Processes a single vote to lynch a player."""
        ### Vote validation ###
        # Phase validation
        if self.game_settings["current_phase"] != "day":
            await ctx.send("You can only vote during the day phase.")
            return
        voter_obj = self.players.get(voter.id)
        # Voter validation
        if not voter_obj or voter_obj.is_alive == False:
            await ctx.send("You are not able to currently vote in this game.")
            logger.warning(f"Player {voter.display_name} tried to vote but is not eligible.\nvoter_obj: {voter_obj}, voter.is_alive: {voter.is_alive}")
            return
        # Find the target player by name
        target_obj = self.get_player_by_display_name(target_name)
        # Target validation
        if not target_obj:
            await ctx.send(f"Could not find a player named '{target_name}'.")
            logger.warning(f"Vote from {voter.display_name} failed: target '{target_name}' not found.")
            return
        if not target_obj.is_alive:
            await ctx.send(f"**{target_obj.display_name}** is already dead and cannot be lynched.")
            logger.warning(f"Vote from {voter.display_name} failed: target '{target_obj.display_name}' is dead.")
            return
        if voter_obj.id == target_obj.id:
            await ctx.send("You cannot vote to lynch yourself.")
            logger.warning(f"Player {voter.display_name} tried to vote for themselves.")
            return
        ### Process Vote ###
        # Remove any previous vote from this voter
        if voter_obj.action_target is not None:
            # Find the previous target player
            previous_target = voter_obj.action_target
            if previous_target in self.lynch_votes and voter_obj.id in self.lynch_votes[previous_target.id]["voters"]:
                self.lynch_votes[previous_target.id]["votes"] -= 1
                self.lynch_votes[previous_target.id]["voters"].remove(voter_obj.id)
                voter_obj.action_target = None
                if not self.lynch_votes[previous_target.id]["votes"]:
                    del self.lynch_votes[previous_target.id]
        # Record the new vote
        voter_obj.action_target = target_obj.id
        if target_obj.id not in self.lynch_votes:
            self.lynch_votes[target_obj.id] = {"votes": 0, "voters": []}
        if voter_obj.id not in self.lynch_votes[target_obj.id]:
            self.lynch_votes[target_obj.id]["votes"] += 1
            self.lynch_votes[target_obj.id]["voters"].append(voter_obj.id)
        #Announce the vote in #voting-channel
        voting_channel = self.bot.get_channel(config.VOTING_CHANNEL_ID)
        if voting_channel:
            await voting_channel.send(f"**{voter.display_name}** has voted to lynch **@{target_obj.display_name}**. Total votes: {self.lynch_votes[target_obj.id]['votes']}")
            logger.info(f"Player {voter.display_name} voted to lynch {target_obj.display_name}. Total votes: {self.lynch_votes[target_obj.id]['votes']}")
            await self.send_vote_count(self, voting_channel) # Send updated vote count
        else:
            logger.error("Voting channel not found. Cannot announce vote.")
        return
    
    async def send_vote_count(self, channel):
        """Constructs and Sends the current vote count to the specified channel."""
        if not self.lynch_votes:
            logger.info("No votes have been cast yet.")
            await channel.send("No votes have been cast yet.")
            return
        # Construct the vote summary message
        logger.info("Sending current vote count.")
        count_message = "Current Vote Count:\n"
        vote_data = sorted(self.lynch_votes.items(), key=lambda item: len(item[1]), reverse=True)
        for target_id, voter_ids in vote_data:
            target_obj = self.players.get(target_id)
            if target_obj:
                voter_names = [self.players.get(voter_id).display_name for voter_id in voter_ids if self.players.get(voter_id)]
                vote_count = len(voter_ids)
                count_message += f"- **{target_obj.display_name}** ({vote_count}): {', '.join(voter_names)}\n"
        # Also list players who haven't voted
        living_player_ids = {p.id for p in self.players.values() if p.is_alive}
        voted_player_ids = set()
        for ids in self.lynch_votes.values():
            voted_player_ids.update(ids)
        not_voted_ids = living_player_ids - voted_player_ids
        if not_voted_ids:
            not_voted_names = [self.players[p_id].display_name for p_id in not_voted_ids]
            count_message += f"\n**Yet to vote ({len(not_voted_names)}):** {', '.join(not_voted_names)}"
        await channel.send(count_message)

    async def tally_votes(self):
        """Counts all votes at the end of the day and returns a story string."""
        if not self.lynch_votes:
            logger.info("No votes were cast during the day.")
            return "No votes were cast today."
        if self.current_phase != "day":
            logger.warning("Tallying votes outside of the day phase.")
            return "Votes can only be tallied during the day phase."
        lynched_players = []
        

        return 

    async def record_night_action(self, player_id, action_type, target_name):
        """Records a night action from a player's DM."""
        # ... logic to validate and store night actions ...
        await self.bot.get_user(player_id).send(f"Your action ({action_type} on {target_name}) has been recorded.") # Placeholder
        pass

    async def process_night_actions(self):
        """Processes all recorded night actions and returns a story string."""
        # ... logic to resolve kills, heals, investigations, etc. ...
        return "It was a quiet night. Nothing seemed to happen." # Placeholder

    # --- 5. GAME END & UTILITIES ---

    def check_win_conditions(self):
        """Checks if any team has won. Returns the winning team or None."""
        # ... win condition logic ...
        return None # Placeholder

    async def announce_winner(self, winner):
        """Announces the winner and cleans up the game."""
        await self.bot.get_channel(config.STORIES_CHANNEL_ID).send(f"## GAME OVER! The **{winner}** team has won!")
        # ... more detailed winner announcement ...
        await self.reset()

    async def reset(self):
        """Resets the game state and cancels any running tasks."""
        if self.signup_loop.is_running():
            self.signup_loop.cancel()
        if self.game_loop.is_running():
            self.game_loop.cancel()
        
        # Reset Discord roles for all players involved
        await update_player_discord_roles(self.bot, self.guild, {}, self.discord_role_data)
        
        self.game_settings["game_started"] = False
        self.game_settings["current_phase"] = "finished"
        logger.info(f"Game {self.game_settings['game_id']} has been reset.")

    def get_status_message(self):
        """Generates a formatted status message string."""
        # ... status message generation logic ...
        return "Game status is currently under construction." # Placeholder
