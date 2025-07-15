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

    # --- Cog Utility Functions
    # This is the new autocomplete function
    async def player_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        """An autocomplete function that shows living players."""
        game = self.get_game_instance()
        choices = []
        if not game:
            return []
        # Get a list of living player names
        living_players = [p.display_name for p in game.players.values() if p.is_alive]
        # Filter choices based on what the user has typed so far
        for player_name in living_players:
            if current.lower() in player_name.lower():
                choices.append(app_commands.Choice(name=player_name, value=player_name))         
        # Return up to 25 choices
        return choices[:25]

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
        self.game = Game(self.bot, interaction.guild) # Pass the guild 
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
        logger.info(f"{interaction.user.display_name} joined the game.")
        await interaction.response.send_message("You've joined the game!", ephemeral=True)

    @app_commands.command(name="mafialeave", description="Leave the game during the sign-up phase.")
    async def leave_game_command(self, interaction: discord.Interaction):
        if self.game is None or self.game.game_settings["current_phase"] != "signup":
            await interaction.response.send_message("There is no game to leave, or sign-ups are closed.", ephemeral=True)
            return
        await self.game.remove_player(interaction.user, interaction.channel)
        logger.info(f"{interaction.user.name} is leaving the game.")
        await interaction.response.send_message("You've left the game.", ephemeral=True)

    @app_commands.command(name="mafiastatus", description="Displays the current game status.")
    @app_commands.check(is_game_active)
    async def status_command(self, interaction: discord.Interaction):
        status_message = self.game.get_status_message()
        await interaction.response.send_message(status_message, ephemeral=True)

    @app_commands.command(name="vote", description="Vote to lynch a player during the day.")
    @app_commands.describe(player="The player you want to lynch.")
    @app_commands.autocomplete(player=player_autocomplete) # Provides a list of names as auto-complete
    @app_commands.check(is_game_active)
    async def vote(self, interaction: discord.Interaction, player: str):
        # We pass the interaction object to the engine, which can use interaction.channel
        await self.game.process_lynch_vote(interaction, interaction.user, player)

    @app_commands.command(name="mafiacount", description="Displays the current vote tally.")
    @app_commands.check(is_game_active)
    async def count_votes_command(self, interaction: discord.Interaction):
        await self.game.send_vote_count(interaction.channel)
        await interaction.response.send_message("Vote count displayed.", ephemeral=True)
    
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
        await self.game.record_night_action(interaction, action_type, target_name)
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