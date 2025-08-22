# Cogs/admin.py
import discord
from discord import app_commands
from discord.ext import commands
import logging
import utils.utilities as utilities
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
    
    async def stop_game_command(self, interaction: discord.Interaction):
         # --- MANUAL ROLE CHECK ---
        # 1. Get the required admin role ID from your loaded JSON data.
        #    The exact path might be different depending on how you store it.
        try:    
            discord_role_data = utilities.load_data("Data/discord_roles.json")
        except Exception as e:
            logger.error(f"Error loading discord roles: {e}")
            logger.critical("No discord roles loaded. The game cannot start.")
        if discord_role_data:
            logger.info("Discord roles loaded successfully.")
        admin_role_id = interaction.guild.get_role(discord_role_data.get("mod", {}).get("id", 0))
        logger.critical(f"Admin role ID: {admin_role_id.id if admin_role_id else 'None'}")
        # 2. Check if the user has the role.
        #    We get the user's roles from the interaction object.
        user_roles = [role.id for role in interaction.user.roles]
        logger.critical(f"User roles: {user_roles}")
        if admin_role_id.id not in user_roles:
            # 3. If they don't have the role, send an error and stop.
            logger.warning(f"{interaction.user.name} attempted to start a game without the required role.")
            logger.critical(f"{user_roles} // {admin_role_id.id if admin_role_id else 'None'}")
            await interaction.response.send_message(
                "You do not have the required role to start a game.", 
                ephemeral=True
            )
            return
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
    async def force_start_command(self, interaction: discord.Interaction):
         # --- START: MANUAL ROLE CHECK ---
        # 1. Get the required admin role ID from your loaded JSON data.
        #    The exact path might be different depending on how you store it.
        try:    
            discord_role_data = utilities.load_data("Data/discord_roles.json")
        except Exception as e:
            logger.error(f"Error loading discord roles: {e}")
            logger.critical("No discord roles loaded. The game cannot start.")
        if discord_role_data:
            logger.info("Discord roles loaded successfully.")
        admin_role_id = interaction.guild.get_role(discord_role_data.get("mod", {}).get("id", 0))
        logger.critical(f"Admin role ID: {admin_role_id.id if admin_role_id else 'None'}")
        # 2. Check if the user has the role.
        #    We get the user's roles from the interaction object.
        user_roles = [role.id for role in interaction.user.roles]
        logger.critical(f"User roles: {user_roles}")
        if admin_role_id.id not in user_roles:
            # 3. If they don't have the role, send an error and stop.
            logger.warning(f"{interaction.user.name} attempted to start a game without the required role.")
            logger.critical(f"{user_roles} // {admin_role_id.id if admin_role_id else 'None'}")
            await interaction.response.send_message(
                "You do not have the required role to start a game.", 
                ephemeral=True
            )
            return
        game = self.get_game_instance()
        if game:
            await game.force_start(interaction)
        else:
            await interaction.response.send_message("No game is in the sign-up phase to force start.", ephemeral=True)

    @app_commands.command(name="mafiareinit", description="[Admin] Debug tool to refresh the player list from Discord roles.")
    async def reinitialize_players(self, interaction: discord.Interaction):
         # --- START: MANUAL ROLE CHECK ---
        # 1. Get the required admin role ID from your loaded JSON data.
        #    The exact path might be different depending on how you store it.
        try:    
            discord_role_data = utilities.load_data("Data/discord_roles.json")
        except Exception as e:
            logger.error(f"Error loading discord roles: {e}")
            logger.critical("No discord roles loaded. The game cannot start.")
        if discord_role_data:
            logger.info("Discord roles loaded successfully.")
        admin_role_id = interaction.guild.get_role(discord_role_data.get("mod", {}).get("id", 0))
        logger.critical(f"Admin role ID: {admin_role_id.id if admin_role_id else 'None'}")
        # 2. Check if the user has the role.
        #    We get the user's roles from the interaction object.
        user_roles = [role.id for role in interaction.user.roles]
        logger.critical(f"User roles: {user_roles}")
        if admin_role_id.id not in user_roles:
            # 3. If they don't have the role, send an error and stop.
            logger.warning(f"{interaction.user.name} attempted to start a game without the required role.")
            logger.critical(f"{user_roles} // {admin_role_id.id if admin_role_id else 'None'}")
            await interaction.response.send_message(
                "You do not have the required role to start a game.", 
                ephemeral=True
            )
            return
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