# Cogs/admin.py
import discord
from discord import app_commands
from discord.ext import commands
import logging

# Import the custom decorator for checking admin permissions
from utils.admincheck import is_admin 
# Import the Player class for type checking during re-initialization
from game.player import Player 

# Get the logger instance from the main bot file
logger = logging.getLogger('discord')

class AdminCog(commands.Cog, name="AdminCog"):
    """
    This cog contains all slash commands that are intended for administrator use only.
    It handles functionality like stopping and force-starting games, and provides
    debugging tools like re-initializing the player list.
    """

    def __init__(self, bot: commands.Bot):
        """Initializes the AdminCog, keeping a reference to the bot."""
        self.bot = bot

    def get_game_instance(self):
        """
        A helper method to safely retrieve the active game instance from the GameCog.
        Returns the Game object if a game is running, otherwise returns None.
        """
        # Access the 'GameCog' instance that has been loaded into the bot
        game_cog = self.bot.get_cog('GameCog')
        # Return the 'game' attribute from the cog, which holds the game state
        return game_cog.game if game_cog else None

    def set_game_instance(self, new_instance):
        """
        A helper method to safely update the game instance in the GameCog.
        This is primarily used to set the game to None when it's stopped,
        effectively cleaning up the game state.
        """
        game_cog = self.bot.get_cog('GameCog')
        if game_cog:
            game_cog.game = new_instance
            return True
        return False

    # --- Admin Slash Commands ---

    @app_commands.command(name="mafiastop", description="[Admin] Forcibly stops and resets the current game.")
    @is_admin() # Decorator: This command can only be used by users with the admin role.
    async def stop_game_command(self, interaction: discord.Interaction):
        """Command to forcefully terminate and reset the current game."""
        logger.info(f"'/mafiastop' command invoked by {interaction.user.name}.")
        # Retrieve the current game instance
        game = self.get_game_instance()
        if game is None:
            # Inform the admin if no game is active to stop
            await interaction.response.send_message("No game is currently running.", ephemeral=True)
            return
        # Acknowledge the command publicly before performing the cleanup
        await interaction.response.send_message("🚨 **Game is being stopped by an administrator...**")
        # Call the game engine's reset method to handle role cleanup and task cancellation
        await game.reset()
        # Nullify the game instance in the GameCog to allow a new game to start
        self.set_game_instance(None) 
        # Confirm to the channel that the game has been stopped
        await interaction.channel.send("**Game has been stopped and reset.**")
        logger.warning(f"Game was forcibly stopped by admin: {interaction.user.name}.")
    
    @app_commands.command(name="forcestart", description="[Admin] Ends sign-ups and starts the game immediately.")
    @is_admin() # Decorator: Ensures only admins can use this command.
    async def force_start_command(self, interaction: discord.Interaction):
        """Command to bypass the signup timer and start the game on the next loop."""
        logger.info(f"'/forcestart' command invoked by {interaction.user.name}.")
        game = self.get_game_instance()
        if game is None:
            await interaction.response.send_message("No game is currently running to force start.", ephemeral=True)
            return
        # Check if a game exists and is in the correct phase for this command
        if game and game.game_settings["current_phase"] == "signup":
            # Call the engine's method to set the force start flag
            await game.force_start(interaction)
        else:
            await interaction.response.send_message("No game is in the sign-up phase to force start.", ephemeral=True)

    @app_commands.command(name="mafiareinit", description="[Admin] Debug tool to refresh the player list from Discord roles.")
    @is_admin() # Decorator: Ensures only admins can use this command.
    async def reinitialize_players(self, interaction: discord.Interaction):
        """
        A powerful debug command to rebuild the game's internal player list
        based on which server members have the 'Living' or 'Dead' roles.
        This can help recover from a bot crash or other state-desync issues.
        """
        logger.info(f"'/mafiareinit' command invoked by {interaction.user.name}.")
        game = self.get_game_instance()
        if game is None:
            await interaction.response.send_message("No game is running to re-initialize.", ephemeral=True)
            return
        if not interaction.guild:
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return
        # Get the role objects from the server using IDs stored in the game instance
        living_role = interaction.guild.get_role(game.discord_role_data.get("living", {}).get("id", 0))
        dead_role = interaction.guild.get_role(game.discord_role_data.get("dead", {}).get("id", 0))
        # Check if both roles were found
        if not living_role or not dead_role:
            await interaction.response.send_message("Error: 'Living' or 'Dead' roles not found.", ephemeral=True)
            return
        # Log the start of the re-initialization process
        logger.info("Rebuilding internal player list from server roles...")
        # Create a new, empty dictionary for the updated player list
        new_players = {}
        # Iterate through every member in the server to find players
        for member in interaction.guild.members:
            # If the member has either the living or dead role, they are part of the game
            if living_role in member.roles or dead_role in member.roles:
                # Get their old player data to preserve their assigned role and death info
                old_player = game.players.get(member.id)
                new_player = Player(user_id=member.id, discord_name=member.name, display_name=member.display_name)
                # Set their alive status based on which role they have
                new_player.is_alive = living_role in member.roles
                # If we have their old data, copy it over to the new object
                if old_player:
                    new_player.role = old_player.role
                    new_player.death_info = old_player.death_info
                # Add the newly created/updated player object to our list
                new_players[member.id] = new_player
        # Overwrite the game's player list with our newly constructed one
        game.players = new_players
        await interaction.response.send_message(f"Player list re-initialized. Found {len(new_players)} players.", ephemeral=True)
        logger.warning(f"Player list was manually re-initialized by admin: {interaction.user.name}.")

    @app_commands.command(name="forcephaseend", description="[Admin] Forcibly end the current game phase.")
    @is_admin()  # Ensure only admins can use this command
    async def force_phase_end(self, interaction: discord.Interaction):
        game = self.get_game_instance()
        if game:
            await game.force_end_phase(interaction)
        else:
            await interaction.response.send_message("No game is currently active.", ephemeral=True)

async def setup(bot):
    """The setup function required by discord.py to load the cog."""
    await bot.add_cog(AdminCog(bot))

