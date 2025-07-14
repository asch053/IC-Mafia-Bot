# Cogs/admin.py
import discord
from discord import app_commands
from discord.ext import commands
import logging

from game.player import Player # Keep this import for the re-init command

logger = logging.getLogger('discord')

class AdminCog(commands.Cog, name="AdminCog"):
    """Cog for all administrator-only game commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def get_game_instance(self):
        """Helper to safely get the game instance from GameCog."""
        game_cog = self.bot.get_cog('GameCog')
        return game_cog.game if game_cog else None

    def set_game_instance(self, new_instance):
        """Helper to safely set the game instance in GameCog."""
        game_cog = self.bot.get_cog('GameCog')
        if game_cog:
            game_cog.game = new_instance
            return True
        return False

    @app_commands.command(name="mafiastop", description="[Admin] Forcibly stops and resets the current game.")
    @app_commands.checks.has_permissions(administrator=True)
    async def stop_game_command(self, interaction: discord.Interaction):
        game = self.get_game_instance()
        if game is None:
            await interaction.response.send_message("No game is currently running.", ephemeral=True)
            return

        await interaction.response.send_message("🚨 **Game is being stopped by an administrator...**")
        
        await game.reset()
        self.set_game_instance(None) # Clear the game instance
        
        await interaction.channel.send("**Game has been stopped and reset.**")
        logger.warning(f"Game was forcibly stopped by {interaction.user.name}.")
    
    @app_commands.command(name="forcestart", description="[Admin] Ends sign-ups and starts the game immediately.")
    @app_commands.checks.has_permissions(administrator=True)
    async def force_start_command(self, interaction: discord.Interaction):
        game = self.get_game_instance()
        if game:
            await game.force_start(interaction)
        else:
            await interaction.response.send_message("No game is in the sign-up phase to force start.", ephemeral=True)

    @app_commands.command(name="mafiareinit", description="[Admin] Debug tool to refresh the player list from Discord roles.")
    @app_commands.checks.has_permissions(administrator=True)
    async def reinitialize_players(self, interaction: discord.Interaction):
        game = self.get_game_instance()
        if game is None:
            await interaction.response.send_message("No game is running to re-initialize.", ephemeral=True)
            return
        if not interaction.guild:
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return

        living_role = interaction.guild.get_role(game.discord_role_data.get("living", {}).get("id", 0))
        dead_role = interaction.guild.get_role(game.discord_role_data.get("dead", {}).get("id", 0))

        if not living_role or not dead_role:
            await interaction.response.send_message("Error: 'Living' or 'Dead' roles not found.", ephemeral=True)
            return

        new_players = {}
        for member in interaction.guild.members:
            if living_role in member.roles or dead_role in member.roles:
                old_player = game.players.get(member.id)
                new_player = Player(user_id=member.id, discord_name=member.name, display_name=member.display_name)
                new_player.is_alive = living_role in member.roles
                if old_player:
                    new_player.role = old_player.role
                    new_player.death_info = old_player.death_info
                new_players[member.id] = new_player

        game.players = new_players
        await interaction.response.send_message(f"Player list re-initialized. Found {len(new_players)} players.", ephemeral=True)
        logger.warning(f"Player list was manually re-initialized by {interaction.user.name}.")

async def setup(bot):
    await bot.add_cog(AdminCog(bot))