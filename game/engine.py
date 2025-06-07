# game/engine.py
import discord
import os
from discord.ext import commands, tasks
import asyncio
import json
from datetime import datetime, timedelta, timezone
import random
import mafiaconfig as config  # Assuming config.py is in the root directory
from utils.utilities import (
    load_data,
    save_json_data,
    update_player_discord_roles,
    format_time_remaining,
    send_role_dm,
    get_status_message,
    get_player_id_by_name,
    is_player_alive,
    get_specific_player_id,
)
from game.roles import GameRole
import logging

# --- Logging Setup ---
logger = logging.getLogger("discord")

# --- Game Class ---
class Game:
    def __init__(self, bot, ctx):
        """
        Initializes a new Game instance.
        Args:
            bot: The discord.ext.commands.Bot instance.
            ctx: The discord.ext.commands.Context instance representing the command invocation.
        """
        logger.info("Initializing new Game instance.")
        self.bot = bot  # Store the bot instance for later use (sending messages, etc.)
        self.ctx = ctx  # Store the context.  IMPORTANT:  Be very careful with this.
        # --- Game Variables ---
        # Initialize game_settings with its structure
        self.game_settings = {
            "game_id": None,  # Will be set when the game starts
            "game_started": False, # This is a boolean, no changes needed
            "start_time": None,  # Will be set when the game starts
            "current_phase": None,  # Start with an empty string, meaning sign-up phase
            "phase_number": 0,
            "total_phases": 0,
            "time_day_ends": None,
            "time_night_ends": None,
            "winning_team": None,  # Will be set when a team wins
        }
        # Initialize players with an empty dictionary
        self.players = {}
        # Initialize lynch_votes as an empty dictionary
        self.lynch_votes = {}
        # Other game variables (these are fine as they are)
        self.game_roles = []
        self.game_loop_task = None  # For managing the game loop task
        # Load data from files, handling potential errors.
        try:
            with open("data/discord_roles.json", "r") as f:
                self.discord_role_data = json.load(f)
        except FileNotFoundError:
            logger.error("discord_roles.json not found!")
            self.discord_role_data = (
                {}
            )  # Initialize as an empty dictionary to prevent further errors
        self.npc_names = load_data("data/bot_names.txt", "ERROR: bot_names.txt not found!")
        if not self.npc_names: # Handle loading failure
            self.npc_names = ["Bot1", "Bot2", "Bot3", "Bot4", "Bot5", "Bot6", "Bot7", "Bot8", "Bot9", "Bot 10", "Bot11"]  # Default list
            logger.warning("Using default NPC names.")
        try:
            with open("data/rules.txt", "r") as f:
                self.rules_text = f.read()
        except FileNotFoundError:
            self.rules_text = "Rules not found.\n"
            logger.error = "Riles not found..."
        self.mafia_setups = load_data(
            "data/mafia_setups.json", "ERROR: mafia_setups.json not found!"
        )
        if not self.mafia_setups:
            logger.critical("No mafia setups loaded. The game cannot start.") #Don't start without setups
            #  Handle the lack of setups more gracefully later.
        logger.debug("Game instance initialized.")

    async def start(self, start_datetime_obj, phase_hours):
        """Starts the game, sets up the sign-up phase."""
        self.game_settings["game_id"] = start_datetime_obj.strftime("%Y%m%d-%H%M%S") # Set Game ID
        self.game_settings["game_started"] = True
        self.game_settings["start_time"] = start_datetime_obj
        self.game_settings["current_phase"] = "signup"  # Set to "signup"
        # Calculate delay
        delay = (start_datetime_obj - datetime.now(timezone.utc)).total_seconds()
        join_hours = format_time_remaining(start_datetime_obj)
        channel = self.bot.get_channel(config.TALKY_TALKY_CHANNEL_ID)
        await channel.send( f"Sign-ups are now open for {join_hours}! Use `/join` in the <#{config.SIGN_UP_HERE_CHANNEL_ID}> channel to join the game.\n "
                        f"Game will start at: {self.game_settings["start_time"].strftime('%Y-%m-%d %H:%M:%S UTC')}.\n\n"
                        )
        channel = self.bot.get_channel(config.SIGN_UP_HERE_CHANNEL_ID)
        await channel.send( f"Sign-ups are now open for {join_hours}! Use `/join` in the <#{config.SIGN_UP_HERE_CHANNEL_ID}> channel to join the game.\n"
                        f"Game will start at: {self.game_settings["start_time"].strftime('%Y-%m-%d %H:%M:%S UTC')}.\n\n"
                        )
        channel = self.bot.get_channel(config.RULES_AND_ROLES_CHANNEL_ID)
        await channel.send( "--- ** New Basic Bitch Game open for signups ** ---\n"
                        f"Sign-ups are now open for {join_hours}! Use `/join` in the <#{config.SIGN_UP_HERE_CHANNEL_ID}> channel to join the game.\n"
                        f"**Game will start at: {self.game_settings["start_time"].strftime('%Y-%m-%d %H:%M:%S UTC')}.**\n\n"
                        f"{self.rules_text}\n"
                        "\n--- **No story generated** ---\n\n"
                        )
        logger.info(f"Game will start at: {start_datetime_obj.strftime('%Y-%m-%d %H:%M:%S UTC')}. With game settings {self.game_settings} and delay = {delay}")
        # Use asyncio.sleep for the delay
        await join_loop(self.bot, start_datetime_obj, self.players, self.game_settings, 0)
        # After the delay, start the game (add NPCs, assign roles, etc.)
        if self.game_settings["current_phase"] == "signup": # Only if it hasn't been stopped.
            await self.prepare_game(phase_hours)
        else:
            logger.info("Game start aborted because signup phase was ended.")

    async def prepare_game(self, phase_hours):
        """Prepares the game by adding NPCs, assigning roles, and starting the night."""
        # Add NPCs if needed
        while len(self.players) < 5:
            npc_name = random.choice(self.npc_names)
            npc_id = -(self.npc_names.index(npc_name) + 1)
            self.players[npc_id] = {
                "name": npc_name,
                "display_name": npc_name,
                "role": None,
                "alive": True,
                "action_target": None,
                "previous_target": None
            }
        logger.debug(f"Players after adding NPCs: {self.players}")
        # Generate and assign roles
        self.generate_game_roles(len(self.players))
        if self.game_roles:
            await self.assign_game_roles(self.players, self.game_roles) # Pass roles.
            logger.debug(f"Roles assigned: {self.players}")
            await self.ctx.send("Roles assigned, starting game!")
            # --- Data Saving (at game start) ---
            # Prepare initial game_data (only at game start)
            self.game_data = {
                "game_id": self.game_settings["game_id"],
                "start_time": self.game_settings["start_time"].isoformat(),  # Use consistent isoformat
                "players": [
                    {
                        "player_id": pid,
                        "name": pdata["name"],
                        "display_name": pdata["display_name"],
                         # Convert to dict for saving
                        "role": pdata["role"].to_dict() if pdata["role"] else None,
                        "alive": pdata["alive"],
                        "action_target": pdata["action_target"],
                        "previous_target": pdata["previous_target"],
                        "death_info": None,  # Initialize death_info
                    }
                    for pid, pdata in self.players.items()
                ],
                "total_phases": [],  # We'll add to this later
                "winner": None,  # We'll set this later
            }

            save_json_data(self.game_data, f"game_{self.game_settings["game_id"]}", sub="stats/testgames")

            # Transition to the night phase and start the game loop
            self.current_phase = "night"
            self.phase_number = 1  # Start at night 1
            self.game_loop_task = self.bot.loop.create_task(
                game_loop(phase_hours,self.discord_role_data,self.players)  # Pass phase_hours
            )
        else:
            await self.ctx.send("Failed to generate roles.")
            logger.critical("Failed to generate mafia roles so aborting the game setup...")
            await self.reset()  # Reset the game if role generation failed.

    async def announce_winner(self, winner, discord_role_data):
        """Announces the winner and resets the game."""
        #global 
        # Send announcement to the stories channel
        #await generate_narration(bot, f"Game Over! The **{winner}** team wins!")
        logger.info(f"Winning team = {winner}")
        channel = self.bot.get_channel(config.STORIES_CHANNEL_ID)
        if winner != "Draw":
            winning_players = []
            for player_id, player_data in self.players.items():
                if player_data["role"].alignment == winner:
                    winning_players.append(f"<@{player_id}>")
            if winning_players:
                winners = ", ".join(winning_players)
                await channel.send(f"GAME ENDED - Congratulations to {winner} - {winners}!")
        else:
            await channel.send(f"GAME ENDED - Game was a draw!")
        # Update roles to remove all players from Living/Dead Players
        guild = self.bot.get_guild(config.SERVER_ID)
        living_role = discord.utils.get(guild.roles, id=discord_role_data.get("living", {}).get("id"))
        dead_role = discord.utils.get(guild.roles, id=discord_role_data.get("dead", {}).get("id"))
        spectator_role = discord.utils.get(guild.roles, id=discord_role_data.get("spectator", {}).get("id"))
        for member in guild.members:
            await member.remove_roles(living_role, dead_role)
            if not member.bot:
                await member.add_roles(spectator_role)  # Add Spectator to non-bots
        # Save game data before resetting
        if self.current_phase != "signup":
            game_data = {
                "game_id": self.game_id,
                "total_phases": (self.phase_number * 2) - (1 if self.current_phase == "night" else 0),
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
                        "phases_lasted": player_data.get("death_info", (self.phase_number * 2) - (1 if self.current_phase == "night" else 0)),
                        #"votes": game_votes.get(player_id, {}).get("votes", []),
                    }
                    for player_id, player_data in self.players.items()
                ],
            }
            if game_data:
                logger.debug(f"DEBUG: {game_data}")
                filename = f"{self.game_id}_Game_Data"
                subdir = f"alpha_testing/{self.game_id}"
                save_json_data(game_data,filename,subdir)  # Save to JSON file

        # --- Construct the final game_data ---
        game_data["winner"] = winner
        game_data["end_time"] = datetime.now(timezone.utc).isoformat()  # Add end time
        game_data["total_phases"] = (self.phase_number * 2) - (1 if self.current_phase == "night" else 0)

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
                "phases_lasted": player_data.get("death_info", {}).get("total phases", self.phase_number), #handle if dead or not
                "votes": [],  # Store vote history here later
            }
            for player_id, player_data in self.players.items()
        ]
        if game_data:
            save_json_data(game_data, f"game_{game_data['game_id']}", f"alpha_testing/{self.game_id}") 
            logger.debug(f"Saved game data to file: {game_data}")  
        # Reset game variables
        self.game_started = False  # Allow new games to be started
        self.game_loop_task.cancel()
        self.game_loop_task = None

    def update_death_info(self,target_id,death_type):
        total_phases = (self.phase_number * 2) - (1 if self.current_phase == "night" else 0)
        self.players[target_id]["death_info"] = {
            "phase": f"{self.current_phase} {self.phase_number}",
            "phase_num": self.phase_number,
            "total_phases": total_phases,
            "how": death_type
        }

    def check_win_conditions(self):
        """
    Checks if any team has won the game.

    Returns:
        str: The name of the winning team ("Mafia", "Town", "Neutral") or None if no team has won yet.
    """
        #global players, current_phase, phase_number
        living_mafia = 0
        living_town = 0
        living_neutral = 0
        for player_id, player_data in self.players.items():
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
            for player_id, player_data in self.players.items():
                if player_data["role"].alignment == "Town" and player_data["alive"] == True:
                    total_phases = ((self.phase_number * 2) - (1 if self.current_phase == "Night" else 0) - 1)
                    self.players[player_id]["alive"] = False
                    self.players[player_id]["death_info"] = {
                        "phase": f"{self.current_phase} {self.phase_number}",
                        "phase num": self.phase_number,
                        "total phases": total_phases,
                        "how": "Killed by Mob",
                        }
            logger.info("The game was won by the Mafia after the SK died and Mafia outnumbered Town")
            return "Mafia"      # Mafia wins if they equal or outnumber Town and SK is dead
        
        elif living_mafia == 0 and living_neutral == 0 and living_town > 0:
            logger.info("The game was Won by the Town as they were the only people left")
            return "Town"       # Town wins if no Mafia or Neutral players are alive
        
        elif self.current_phase == "Night" and living_mafia == 1 and living_town == 1 and living_neutral == 0:
            for player_id, player_data in self.players.items():
                if player_data["alive"] == True:
                    total_phases = ((self.phase_number * 2) - (1 if self.current_phase == "Night" else 0) - 1)
                    self.players[player_id]["alive"] = False
                    self.update_death_info(self,player_id,"Lynched")
                        
            logger.info("The game was a draw as only 2 people left at start of day from mafia and town")
            return "Draw"
        
        elif self.current_phase == "Night" and living_mafia == 1 and living_neutral == 1 and living_town == 0:
            for player_id, player_data in self.players.items():
                if player_data["alive"] == True:
                    total_phases = ((self.phase_number * 2) - (1 if self.current_phase == "Night" else 0) - 1)
                    self.players[player_id]["alive"] = False
                    self.update_death_info(self,player_id,"Lynched")
            logger.info("The game was a draw as only 2 people left at start of day from SK and town")
            return "Draw"
        
        elif self.current_phase == "Day" and living_neutral == 1 and living_town == 1 and living_mafia == 0:
            for player_id, player_data in self.players.items():
                if player_data["alive"] == True and player_data["role"].alignment == "Town":
                    total_phases = ((self.phase_number * 2) - (1 if self.current_phase == "Night" else 0) - 1)
                    self.players[player_id]["alive"] = False
                    self.update_death_info(self,player_id,"Killed by SK")
            logger.info("The game was won by SK as only SK and 1 town alive at start of night - SK will kill last town overnight")
            return "Serial Killer"    # Neutral wins if they are the only one alive
        
        elif self.current_phase == "Day" and living_mafia == 1 and living_neutral == 1 and living_mafia == 0:
            for player_id, player_data in self.players.items():
                if player_data["alive"] == True:
                    total_phases = ((self.phase_number * 2) - (1 if self.current_phase == "Night" else 0) - 1)
                    self.players[player_id]["alive"] = False
                    self.update_death_info(self,player_id,"Killed by SK")
            logger.info("The game was a draw as only 2 people left at start of day from mafia and SK")
            return "Draw"
        
        elif self.current_phase == "Day" and living_mafia == 1 and living_town == 1 and living_neutral == 0:
            for player_id, player_data in self.players.items():
                if player_data["alive"] == True and player_data["role"].alignment == "Town":
                    total_phases = ((self.phase_number * 2) - (1 if self.current_phase == "Night" else 0) - 1)
                    self.players[player_id]["alive"] = False
                    self.update_death_info(self,player_id,"Killed by Mafia")
            logger.info("The game was won by Mob as only mob and 1 town alive at start of night - Mob will kill last town overnight")
            return "Mafia"
        
        elif self.current_phase == "Day" and living_mafia == 1 and living_neutral == 1 and living_town ==0:
            for player_id, player_data in self.players.items():
                if player_data["alive"] == True and player_data["role"].alignment == "Mafia":
                    total_phases = ((self.phase_number * 2) - (1 if self.current_phase == "Night" else 0) - 1)
                    self.players[player_id]["alive"] = False
                    self.update_death_info(self,player_id,"Killed by SK")
            logger.info("SK wins if they and 1 mob left at start of night as they kill first")
            return "Serial Killer" #SK wins if they and 1 mob left at start of night as they kill first
        else:
            logger.info("No winner found")
            return None  # No winner yet 

    async def reset(self):
        """Resets all game variables to their initial state, and cancels game loop."""
        # Cancel the game_loop task if it's running
        if self.game_loop_task is not None:
            logger.info("DEBUG: game_loop is running, cancelling...")
            self.game_loop_task.cancel()
            self.game_loop_task = None
        else:
            logger.info("DEBUG: game_loop is not running")

        # Reset instance variables
        self.players = {}
        self.game_roles = []
        self.lynch_votes = {}
        self.game_settings = {
            "game_id": None,  # Will be set when the game starts
            "game_started": False, # This is a boolean, no changes needed
            "start_time": None,  # Will be set when the game starts
            "current_phase": None,  # Start with an empty string, meaning sign-up phase
            "phase_number": 0,
            "total_phases": 0,
            "time_day_ends": None,
            "time_night_ends": None,
            "winning_team": None,  # Will be set when a team wins
        }

        # DO NOT reset self.game_id or self.game_data here!  Those are for saving.

        #Update roles
        await update_player_discord_roles(self.bot, self.ctx, self.players, self.discord_role_data) #Ensure to pass bot into this function

    def generate_game_roles(self, num_players):
        """Generates a list of GameRole objects based on mafia_setups.json."""
        # Load role data from mafia_setups.json, create GameRole objects
        logger.debug("DEBUG: generate_game_roles called")
        self.game_roles = []
        # Get the appropriate setup from mafia_setups.json
        setups = self.mafia_setups.get(str(num_players))
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
                self.game_roles.append(game_role)
        logger.info("Game Roles Created")

    async def assign_game_roles(self, players, setup):
        """Assigns roles to players randomly."""
        # Shuffle player list and role list, assign roles, send DMs (using a helper)
        # Shuffle the player IDs and roles
        player_ids = list(self.players.keys())
        random.shuffle(player_ids)
        random.shuffle(self.game_roles)
        # Assign roles to players
        for i, player_id in enumerate(player_ids):
            if i < len(self.game_roles):
                role = self.game_roles[i]
                self.players[player_id]["role"] = role
                self.players[player_id]["alive"] = True
                # Send DM with role information *directly*, not as a task
                if player_id > 0:  # Check if it's not an NPC
                    await send_role_dm(self.bot, player_id, role, config.message_send_delay)  # Await the DM!
            else:
                logger.warning(
                    f"WARNING: More players than roles in setup. {players[player_id]['name']} will not be assigned a role."
                )

    async def process_lynch_vote(self, ctx, voter_id, lynch_target):
        """Processes a lynch vote."""
        # Handle vote recording, checks for valid voter and target, updates lynch_votes
        logger.debug(f"DEBUG: Target is {self.lynch_target}")
        lynch_target_id = await get_player_id_by_name(self.players,lynch_target)
        target_alive = await is_player_alive(lynch_target_id,self.players)
        logger.debug(f"DEBUG: target {lynch_target_id} alive => {target_alive}")
        logger.debug(f"DEBUG: Lynch Target ID => {lynch_target_id}")
        # Check if the voter has already voted
        for target_id, vote_data in self.lynch_votes.items():
            if voter_id in vote_data["voters"]:
                # Remove the previous vote
                vote_data["voters"].remove(voter_id)
                vote_data["total_votes"] -= 1
                # If there are no more votes for the previous target, remove the entry
                if vote_data["total_votes"] == 0:
                    del self.lynch_votes[target_id]
                break
        # Add target player to the lynch
        # Record the new vote
        self.players[voter_id]["action_target"] = lynch_target_id
        self.players[lynch_target_id]["votes"] += 1
        # Add the new vote
        if lynch_target_id not in self.lynch_votes:
            self.lynch_votes[lynch_target_id] = {"total_votes": 0, "voters": []}
        self.lynch_votes[lynch_target_id]["total_votes"] += 1
        self.lynch_votes[lynch_target_id]["voters"].append(voter_id)
        channel = self.bot.get_channel(config.VOTING_CHANNEL_ID)
        await channel.send(f"<@{voter_id}> voted for <@{lynch_target}> who now has {self.lynch_votes[lynch_target_id]["total_votes"]}")
        logger.debug(f"DEBUG: Lynch votes after /vote -> {self.lynch_votes}")

    async def tally_votes(self):
        """Counts votes and determines who is lynched."""
        # Count votes, handle ties, announce results, kill player, reset votes.
        lynched_players = []
        story_parts = []
        players = self.players
        current_phase = self.current_phase
        phase_number = self.phase_number
        lynch_votes = self.lynch_votes
        bot = self.bot
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
                self.update_death_info(self,lynched_player_id,"lynched")
                # Announce the player's role
                if lynched_player_id is not None and lynched_player_data["role"]:  # only show role for actual player and they have a role
                    lynched_player_role = lynched_player_data["role"].name
                    story_parts.append(f"{lynched_player_name}'s role was: {lynched_player_role}")
        else:
            story_parts.append("No one was lynched.")
        lynch_data = {
        "game_id": self.game_id,
            "phase": current_phase,
            "phase_num": phase_number,
            "lynch votes": lynch_votes  
        }
        subdir = f"alpha_testing/{self.game_id}"
        filename = f"{self.game_id}_Lynch_Data"
        save_json_data(lynch_data,filename,subdir)
        logger.debug(story_parts)
        story_text = "\n".join(story_parts)
        logger.debug(story_text)
        return (story_text)
    
    async def process_block(self,player_type):
        """Processes the Serial Killer's night kill action."""
        # Handle roleblock logic, update player status
        rb_id = get_specific_player_id(self.players,player_type)
        if rb_id is not None:
            target_id = self.players[rb_id]["action_target"]
            self.player[target_id]["action_target"] = None
            logger.debug(f"{player_type} blocked {target_id} ({self.players[target_id]['role'].name})")
        return
    
    async def process_kill(self,player_type):
        """Processes the kill action for provided player_type"""
        # Handle kill logic, update player status
        story_parts = []
        player_id = get_specific_player_id(self.players,player_type)
        if player_id is None:
            logger.error(f"DEBUG: No living {player_type} found. Skipping {self.current_phase} kill process.")
            return
        else:
            target_id = self.players[player_id]["action_target"]
            if target_id is not None:
                if self.players[target_id]["alive"] == False:
                    logger.error(f"DEBUG: Target player for {player_type} is already dead. Skipping kill process.")
                    await player_id.send("Target player for the night kill is already dead.")
                    return
                if self.players[target_id]["role"].name == "Serial Killer":
                    logger.info(f"{player_type} attempted to kill the Serial Killer")
                    await player_id.send("Invalid Kill")
                    return
                if self.players[target_id]["role"].name == "Godfather":
                    logger.info(f"{player_type} attempted to kill the Godfather")
                    await player_id.send("Invalid Kill")
                    return
                logger.debug(f"{player_type} killed {target_id} ({self.players[target_id]['role'].name})")
                story_parts.append(f"**{self.players[player_id]['role'].name} killed {self.players[target_id]['display_name']} ({self.players[target_id]['role'].name} of {self.players[target_id]['role'].alignment})**")
                self.players[player_id]["action_target"] = None
                self.players[target_id]["alive"] = False
                self.update_death_info(self,target_id,f"killed by {player_type}")
                logger.critical(f"DEBUG: {player_type} kills successfull")
            else:
                await player_id.send("Did not select a kill target")
                logger.debug(f"{player_type} selected no kill target") 
                story_parts.append(f"{player_type} stayed at home and did nothing")
            logger.debug(f"{story_parts}")
            story_text = "\n".join(story_parts)
            logger.debug(f"DEBUG: {story_text}")
            return(story_text)

    async def process_heal(self,player_type):
        """Processes the Doctor's night heal action."""
        # Handle Doctor heal logic, update player status (potentially reviving)
        story_parts = []
        player_id = get_specific_player_id(self.players,player_type)
        if player_id is None:
            logger.error(f"No {player_type} found. Skipping heal process.")  
            return
        else:
            target_id = self.players[player_id]["action_target"]
            if target_id is None:
                logger.error(f"{player_type} selected no heal target")
                story_parts.append(f"{player_type} stayed home and did nothing")
                return
            else:
                heal_target_death_phase = self.players[target_id]["death_info"]["phase_num"]
                logger.debug(f"Current phase = {self.current_phase} and target death phase = {heal_target_death_phase}")
                if heal_target_death_phase == self.current_phase:
                    self.players[target_id]["alive"] = True
                    story_parts.append(f"As the {player_type} walked through town they found {self.players[target_id]["display_name"]} bloodied and dying. The town doctor pulled out their emergency first aid kit and set about saving {self.players[target_id]["display_name"]} from certain death")
                    story_parts.append(f"**{self.players[target_id]["display_name"]} was healed by the {player_type}!**\n\n")
                    logger.debug(f"{player_type} healed {target_id}")
        logger.debug(f"{story_parts}")
        story_text = "\n".join(story_parts)
        logger.debug(f"DEBUG: {story_text}")
        return(story_text)

    async def process_investigate(self,player_type):
        """Processes cop night action"""
        #Handles cop investigation and sends reuslts
        story_parts = []
        player_id= get_specific_player_id(self.players,player_type)
        if player_id is None:
            logger.error(f"No {player_type} found. Skipping investigation process.")
            return
        if self.players[player_id]["alive"] == False:
            logger.error(f"{player_type} is dead")
            return
        else:
            target_id = self.players[player_id]["action_target"]
            if target_id is None:
                logger.error(f"{player_type} selected no investigation target")
                player_id.send("Did not select an investigation target")
                return
            else:
                if self.players[target_id]["alive"] == False:
                    logger.error(f"DEBUG: {player_type} target:{target_id} is dead")
                    player_id.send("Did not select an investigation target")
                    return
                else:
                    # Target is valid, proceed with investigation.
                    target_name = self.players[target_id]["display_name"]  # Use display_name
                    target_role = self.players[target_id]["role"].name #get role name
                    target_alignment = self.players[target_id]["role"].alignment # Get alignment
                    target_short_desc = self.players[target_id]["role"].short_description # get role (short) description
                    if target_role == "Godfather" or target_role == "Serial Killer":
                        target_role = "Plain Townie"
                        target_alignment = "Town"
                        target_short_desc = "Normal member of town"
                    logger.debug(f"Town Cop investigates {target_name} (ID: {target_id}), Role: {target_role}, Alignment: {target_alignment}")
                    try:
                        await player_id.send(f"You investigated {target_name}.  Their role is: {target_role} ({target_short_desc}).  Their alignment is: {target_alignment}.")
                    except discord.Forbidden:
                        logger.error(f"Could not send investigation result to Town Cop ({player_id}) due to their privacy settings.")
                    except Exception as e:
                        logger.error(f"An error occurred while sending investigation result to Town Cop ({player_id}): {e}")
                return

# --- Functions to start the game. Called from Cog ---
# Reset global variable game 
game = None

async def start_new_game(bot, ctx, game_start_date, phase_hours):
    """Starts a new game, called in cogs"""
    #called in the cog to create a new game
    global game
    if game is not None:
        try:
            game = Game(bot,ctx)
            await Game.start(game, game_start_date,phase_hours)
        except Exception as e:
            logger.error(f"An error occurred while starting a new game: {e}")
            game = None

async def join_game(bot, ctx, game):
  """Allows a player to join the current game"""
    # Called from cog, logic for joining, checks channel, adds to players
  pass

async def stop_game(self): #Added parameters
    """Stops the currently running game."""
    pass

tasks.loop(seconds = 10)
async def join_loop(bot, time, players, game_settings, x):
    delay = (time - datetime.now(timezone.utc)).total_seconds()
    logger.info(f"Waiting for {delay} seconds untill {time}")
    SIGNUP_CHANNEL = bot.get_channel(config.SIGN_UP_HERE_CHANNEL_ID)
    x =+ 10
    if x == delay / 4:
        status_message = get_status_message(players, game_settings, time)
        x = 0
        await SIGNUP_CHANNEL.send(status_message)
        logger.info("DEBUG: status message sent")
        logger.debug(f"{status_message}")
    if datetime.now(timezone.utc) >= time:
        join_loop.stop()
        logger.info("DEBUG: Signup time has passed and join_loop has been ended")
        return

tasks.loop(seconds = 1)
async def game_loop(self, phase_hours, discord_role_data, players):
    """The main game loop, which alternates between day and night phases."""
    # Alternate between day and night, check win conditions, call run_day_phase and run_night_phase
    STORY_CHANNEL = self.bot.get_channel(config.STORIES_CHANNEL_ID)
    logger.info(f"Current Phase ==> {self.game_settings["current_phase"]}")
    self.game_settings["current_phase"] = "Night"
    status_message = get_status_message(players, self.game_settings)
    await STORY_CHANNEL.send(status_message)
    asyncio.sleep(phase_hours)
    logger.info(f"Current Phase == {self.game_settings["current_phase"]}")
    self.game_settings["current_phase"] = "Day"
    status_message = get_status_message(players, self.game_settings)
    await STORY_CHANNEL.send(status_message)
    logger.info(f"Current Phase == {self.game_settings["current_phase"]}")
    