# cogs/game.py
import discord
import config
import logging
from discord import app_commands # Import app_commands
from discord.ext import commands
from game.engine import Game
from datetime import datetime, timezone


logger = logging.getLogger('discord')

# A helper function to check if a game is active
def is_game_active(interaction: discord.Interaction) -> bool:
    cog = interaction.client.get_cog("GameCog")
    return cog and cog.game is not None

class GameCog(commands.Cog, name="GameCog"):
    def __init__(self, bot):
        self.bot = bot
        self.game = None
    
    # Add this helper function
    def get_game_instance(self):
        """A helper method to safely get the game instance."""
        return self.game
    
    # Game cleanup utility
    def _cleanup_game(self):
        """Callback function to reset the game instance in the cog."""
        logger.info("GameCog: Cleaning up and resetting game instance.")
        self.game = None

    # --- Cog Utility Functions
    # This is the new autocomplete function
    async def player_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        """An autocomplete function that shows living players, with added logging."""
        logger.debug(f"--- Autocomplete triggered for player: '{current}' ---")
        game = self.get_game_instance()
        if not game:
            logger.debug("Autocomplete failed: No active game instance found.")
            return []
        logger.debug("Autocomplete: Found active game instance.")
        choices = []
        # Get a list of living player names
        living_players = [p.display_name for p in game.players.values() if p.is_alive]
        logger.debug(f"Autocomplete: Found living players: {living_players}")
        if not living_players:
            logger.debug("Autocomplete finished: No living players to suggest.")
            return []
        # Filter choices based on what the user has typed so far
        for player_name in living_players:
            if current.lower() in player_name.lower():
                choices.append(app_commands.Choice(name=player_name, value=player_name))
        logger.debug(f"Autocomplete finished. Returning {len(choices)} choices: {[c.name for c in choices]}")
        # Discord shows a maximum of 25 choices
        return choices[:25]
    
    # --- Channel Listening Helper ---
    # In cogs/game.py, inside the GameCog class

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots and DMs
        if message.author.bot or not message.guild:
            return
        # Check if a game is running and the message is in the voting channel
        game = self.get_game_instance()
        if game and message.channel.id == config.VOTING_CHANNEL_ID:
            content = message.content.lower().strip()
            # If the user types a command that looks like a slash command
            if content.startswith(f"{config.BOT_PREFIX}vote"):
                await message.reply(
                    "It looks like you're trying to vote! Please use the **slash command** `/vote`, press tab and select a player from the list that appears."
                )
            else:
                await message.reply(
                    f"Please do not talk in the voting channel. Use the slash command `/vote` to vote, or keep the talky-talky to <#{config.TALKY_TALKY_CHANNEL_ID}>."
                )
        if game and message.channel.id == config.SIGN_UP_HERE_CHANNEL_ID:
            content = message.content.lower().strip()
            if content.startswith(f"{config.BOT_PREFIX}join"):
                await message.reply(
                    "It looks like you're trying to join the game! Please use the **slash command** `/mafiajoin`"
                )
            else:
                await message.reply(
                    f"Please do not talk in the sign-up channel. Use the slash command `/mafiajoin` to join, or keep the talky-talky to <#{config.TALKY_TALKY_CHANNEL_ID}>."
                )

    # --- Game Management Commands ---
    @app_commands.command(name="mafiastart", description="[Admin] Schedules a new Mafia game.")
    @app_commands.describe(
        phase_hours="The duration of each day/night phase in hours.",
        start_datetime="The start time in 'YYYY-MM-DD HH:MM' format (UTC)."
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def start_game_command(self, interaction: discord.Interaction, phase_hours: float, start_datetime: str):
        if self.game is not None:
            await interaction.response.send_message("A game is already in progress!", ephemeral=True)
            return
        try:
            start_datetime_obj = datetime.strptime(start_datetime, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        except ValueError:
            await interaction.response.send_message("Invalid date/time format. Please use 'YYYY-MM-DD HH:MM' format in UTC.", ephemeral=True)
            return
        if start_datetime_obj <= datetime.now(timezone.utc):
            await interaction.response.send_message("The start time must be in the future.", ephemeral=True)
            return
         # UPDATED: Pass the cleanup method when creating the Game instance
        self.game = Game(self.bot, interaction.guild, cleanup_callback=self._cleanup_game)
        logger.info(f"New game instance created by {interaction.user.name}.")
        await interaction.response.send_message(f"Game scheduled by {interaction.user.mention}!", ephemeral=True)
        await self.game.start(start_datetime_obj, phase_hours)

    # --- Player Commands (available in channels) ---
    @app_commands.command(name="mafiajoin", description="Joins the current game during the sign-up phase.")
    async def join_game_command(self, interaction: discord.Interaction):
        if self.game is None or self.game.game_settings["current_phase"] != "signup":
            await interaction.response.send_message("No game is currently accepting sign-ups.", ephemeral=True)
            return
        # Defer the interaction immediately
        await interaction.response.defer(ephemeral=True)
        # Use interaction.channel to send public messages
        await self.game.add_player(interaction.user, interaction.user.display_name, interaction.channel)
        # Send the follow-up
        await interaction.followup.send("You've joined the game!", ephemeral=True)
        logger.info(f"{interaction.user.display_name} joined the game.")

    @app_commands.command(name="mafialeave", description="Leave the game during the sign-up phase.")
    async def leave_game_command(self, interaction: discord.Interaction):
        if self.game is None or self.game.game_settings["current_phase"] != "signup":
            await interaction.response.send_message("There is no game to leave, or sign-ups are closed.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        # Do the work
        await self.game.remove_player(interaction.user, interaction.channel)
        # Send the follow-up
        await interaction.followup.send("You've left the game.", ephemeral=True)
        logger.info(f"{interaction.user.name} is leaving the game.")

    @app_commands.command(name="mafiastatus", description="Displays the current game status.")
    @app_commands.check(is_game_active)
    async def status_command(self, interaction: discord.Interaction):
        logger.info(f"`/mafiastatus` command was called - {self.game}.")
        if self.game is None:
            await interaction.response.send_message("No game is currently running.", ephemeral=True)
            logger.info("`/mafiastatus` command was used but no game is currently running.")
            return
        logger.info(f"`/mafiastatus` command was used by {interaction.user.name}.")
        status_message = self.game.get_status_message()
        await interaction.response.send_message(status_message, ephemeral=False)

    @app_commands.command(name="vote", description="Vote to lynch a player during the day.")
    @app_commands.describe(player="The player you want to lynch.")
    @app_commands.autocomplete(player=player_autocomplete) # Provides a list of names as auto-complete
    @app_commands.check(is_game_active)
    async def vote(self, interaction: discord.Interaction, player: str):
        await interaction.response.defer(ephemeral=True)
        # We pass the interaction object to the engine, which can use interaction.channel
        message = await self.game.process_lynch_vote(interaction, interaction.user, player)
        # Send it as a follow-up
        await interaction.followup.send(message, ephemeral=True)

    @app_commands.command(name="mafiacount", description="Displays the current vote tally.")
    @app_commands.check(is_game_active)
    async def count_votes_command(self, interaction: discord.Interaction):
        await self.game.send_vote_count(interaction.channel)
        await interaction.response.send_message("Vote count displayed.", ephemeral=False)
    
    # --- Night Action Commands (intended for DMs) ---
    async def _handle_night_action(self, interaction: discord.Interaction, action_type: str, target_name: str):
        """Helper function to reduce code duplication for night actions."""
        if not is_game_active(interaction):
            await interaction.response.send_message("No game is currently running.", ephemeral=True)
            return
        if interaction.guild:
            await interaction.response.send_message("Night actions must be used in DMs.", ephemeral=True)
            return
        # The game engine handles all the logic.
        await interaction.response.defer(ephemeral=False)
        message = await self.game.record_night_action(interaction, action_type, target_name)
        await interaction.followup.send(message, ephemeral=False)
        logger.debug(f"{interaction.user.id} has requested to {action_type} {target_name}.")

    @app_commands.command(name="kill", description="[DM Only] Action for roles that can kill.")
    @app_commands.describe(player="The player you want to kill.")
    @app_commands.autocomplete(player=player_autocomplete)
    async def kill(self, interaction: discord.Interaction, player: str):
        await self._handle_night_action(interaction, 'kill', player)
        
    @app_commands.command(name="heal", description="[DM Only] Action for the Doctor to heal a player.")
    @app_commands.describe(player="The player you want to heal.")
    @app_commands.autocomplete(player=player_autocomplete)
    async def heal(self, interaction: discord.Interaction, player: str):
        await self._handle_night_action(interaction, 'heal', player)
    
    @app_commands.command(name="investigate", description="[DM Only] Action for the Cop to investigate a player.")
    @app_commands.describe(player="The player you want to investigate.")
    @app_commands.autocomplete(player=player_autocomplete)
    async def investigate(self, interaction: discord.Interaction, player: str):
        await self._handle_night_action(interaction, 'investigate', player)

    @app_commands.command(name="block", description="[DM Only] Action for the Role Blocker to block an action.")
    @app_commands.describe(player="The player you want to block.")
    @app_commands.autocomplete(player=player_autocomplete)
    async def block(self, interaction: discord.Interaction, player: str):
        await self._handle_night_action(interaction, 'block', player)

    
  

async def setup(bot):
    await bot.add_cog(GameCog(bot))
    logger.info("GameCog loaded.")