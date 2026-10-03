import discord
import logging  
from discord.ext import commands
from discord import app_commands

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

import utils.admincheck as is_admin  # Import the admin check decorator

import cogs.admincogs.getgameinstance as getgameinstance
import cogs.admincogs.setgameinstance as setgameinstance
import cogs.admincogs.startgame as start_game_command
import cogs.admincogs.stopgame as stop_game_command


class AdminCog(commands.Cog, name="Admin Commands", description="Commands for bot administration and management."):
    """
    This cog contains all slash commands that are intended for administrator use only.
    It handles functionality like stopping and force-starting games, and provides
    debugging tools like re-initializing the player list.
    """
    def __init__(self, bot):
        self.bot = bot

    # --- Admin Commands --- #
    # Admin only functions for starting a new game. Accepts options for game type, phase duration, start time, narration type, and role investigation settings.
    # Provides set options for game type, narration type, and investigation choices to ensure valid input. Validates start time to be in the future and acknowledges the command while preparing the game announcement.
    # Then calls the start game function from the admincogs module with the provided parameters. Logs all actions for observability and debugging.
    @app_commands.command(name="mafiastart", description="Schedules a new game")
    @app_commands.describe(
        game_type="The type of Mafia game to start (e.g., Classic, Battle Royale).",
        phase_hours="The duration of each day/night phase in hours.",
        start_datetime="The start time in 'YYYY-MM-DD HH:MM' format (UTC).",
        narration_type="The type of narration for the game.",
        gf_investigate_choice="Whether the Godfather is able to be investigated (yes/no).",
        sk_investigate_choice="Whether the Serial Killer is able to be investigated (yes/no).",
        mafia_ratio="Percentage of players that should be Mafia (e.g., 0.25)",
        town_rb_req="Number of players before adding Roleblockers (e.g. set at 10 to need 10 players before adding Town Roleblockers)",
        town_cop_req="Number of players before adding a Cop (e.g. set at 6 to require at least 6 players before adding a Cop)",
        town_doctor_req="Number of players before adding a Doctor (e.g. set at 7 to require at least 7 players before adding a Doctor)",
        mafia_rb_req="Number of Mafia players before adding Roleblockers (e.g. set at 4 to need 4 Mafia players before adding Mafia Roleblockers)",
        sk_player_count="Minimum number of players required for the Serial Killer role (e.g., set at 9 to require 9 players before adding the Serial Killer)"    
    )
    @app_commands.choices(game_type=[
        app_commands.Choice(name="Classic", value="classic"),
        app_commands.Choice(name="Battle Royale", value="battle_royale")
    ])
    @app_commands.choices(narration_type=[
    # options for AI narration types - can be expanded in the future to include more styles/themes. Add Classic Mafia, High Fantasy, Cyberpunk, Comedy, and lovecraftian horror.
        app_commands.Choice(name="No Story", value="No Story"),
        app_commands.Choice(name="Classic Mafia", value="Classic Mafia"),
        app_commands.Choice(name="High Fantasy", value="High Fantasy"),
        app_commands.Choice(name="Cyberpunk", value="Cyberpunk"),
        app_commands.Choice(name="Comedy", value="Comedy"),
        app_commands.Choice(name="Lovecraftian Horror", value="Lovecraftian Horror")
    ])
    @app_commands.choices(gf_investigate_choice=[
        app_commands.Choice(name="Yes", value="yes"),
        app_commands.Choice(name="No", value="no")
    ])
    @app_commands.choices(sk_investigate_choice=[
        app_commands.Choice(name="Yes", value="yes"),
        app_commands.Choice(name="No", value="no")
    ])
    @is_admin() # Decorator: This command can only be used by admins.
    async def mafiastart(
        self, interaction: discord.Interaction, 
        game_type: str, phase_hours: float, start_datetime: str, narration_type: str = "Classic Mafia",
        gf_investigate_choice: str = "No", sk_investigate_choice: str = "No",
        mafia_ratio: float = 0.25, town_rb_req: int = 10, mafia_rb_req: int = 4, sk_player_count: int = 9, town_cop_req: int = 6, town_doctor_req: int = 7
    ):
        """Schedules a new game with the specified parameters."""
        logger.critical(f"Admin command invoked: /mafiastart by {interaction.user.name}")
        await start_game_command.start_game_command(
            self, interaction, game_type, phase_hours, start_datetime, narration_type,
            gf_investigate_choice, sk_investigate_choice, mafia_ratio, town_rb_req,
            mafia_rb_req, sk_player_count, town_cop_req, town_doctor_req
        )

    # Admin command to stop a current game. This command checks if a game is running and stops it, cleaning up resources and notifying players. It logs the action for observability.
    @app_commands.command(name="mafiastop", description="[Admin] Stops the current game")
    @is_admin() # Decorator: This command can only be used by admins.
    async def mafiastop(self, interaction: discord.Interaction):
        """Command to forcefully terminate and reset the current game."""
        logger.critical(f"Admin command invoked: /mafiastop by {interaction.user.name}")
        await stop_game_command.stop_game_command(self, interaction)