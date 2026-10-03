import config
import discord
import logging
from game.engine import Game
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

async def start_game_command(
        self, interaction: discord.Interaction, 
        game_type: str, phase_hours: float, start_datetime: str, narration_type: str = "Classic Mafia",
        gf_investigate_choice: str = "No", sk_investigate_choice: str = "No", 
        mafia_ratio: float = config.mob_ratio, town_rb_req: int = config.min_town_rb_players, 
        mafia_rb_req: int = config.min_mob_rb_mafia_count, sk_player_count: int = config.min_sk_players, 
        town_cop_req: int = config.min_cop_players, town_doctor_req: int = config.min_doctor_players
                                ):
    """Command to start a new game instance with the specified parameters."""
    logger.critical(f"Starting game with parameters: game_type={game_type}, phase_hours={phase_hours}, start_datetime={start_datetime}," 
                    f"narration_type={narration_type}, gf_investigate_choice={gf_investigate_choice}, sk_investigate_choice={sk_investigate_choice}," 
                    f"mafia_ratio={mafia_ratio}, town_rb_req={town_rb_req}, mafia_rb_req={mafia_rb_req}, sk_player_count={sk_player_count}," 
                    f"town_cop_req={town_cop_req}, town_doctor_req={town_doctor_req}")
    if self.game is not None:
        await interaction.response.send_message("A game is already running. Please stop the current game before starting a new one.", ephemeral=True)
        return
    # Validate the input parameters
    # Validate time and date
    logger.error(f"Validating start_datetime: {start_datetime}")
    try:
        start_datetime_obj = datetime.strptime(start_datetime, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        await interaction.response.send_message("Invalid date/time format. Please use 'YYYY-MM-DD HH:MM' format in UTC.", ephemeral=True)
        return
        # Ensure the start time is in the future to prevent immediate, accidental starts
    if start_datetime_obj <= datetime.now(timezone.utc):
            await interaction.response.send_message("The start time must be in the future.", ephemeral=True)
            return
    # Convert investigate choices to booleans
    gf_investigate = (gf_investigate_choice.lower() == "yes") # Default to False if not provided
    sk_investigate = (sk_investigate_choice.lower() == "yes") # Default to False if not provided
    # Check town role blocker requirement and mafia role blocker requirement are integer
    if not isinstance(town_rb_req, int):
        await interaction.response.send_message("Invalid town role blocker requirement. Please provide an integer.", ephemeral=True)
        return
    if not isinstance(mafia_rb_req, int):
        await interaction.response.send_message("Invalid mafia role blocker requirement. Please provide an integer.", ephemeral=True)
        return
    # Check Serial Killer player count requirement is integer
    if not isinstance(sk_player_count, int):
        await interaction.response.send_message("Invalid Serial Killer player count requirement. Please provide an integer.", ephemeral=True)
        return
        # Check mafia ratio is a float between 0 and 1
    if not isinstance(mafia_ratio, float) or mafia_ratio <= 0 or mafia_ratio >= 1:
        await interaction.response.send_message("Invalid mafia ratio. Please provide a float between 0 and 1 (e.g., 0.25 for 25%).", ephemeral=True)
        return  
    # Acknowledge the command while the bot prepares the game announcement
    await interaction.response.defer(ephemeral=True)
        # Create a new Game instance and store it in the cog
    self.game = Game(self.bot, interaction.guild, cleanup_callback=self._cleanup_game)
    logger.info(f"New game instance created by admin: {interaction.user.name}.")
        # Confirm to the admin that the game has been scheduled successfully
    await interaction.followup.send(f"Game scheduled by {interaction.user.mention}!", ephemeral=True)
        # Call the game engine's start method to begin the sign-up phase
    await self.game.start(game_type, start_datetime_obj, phase_hours, gf_investigate, sk_investigate, narration_type, max_players=99, mafia_ratio=mafia_ratio, town_rb_req=town_rb_req, mafia_rb_req=mafia_rb_req, 
                              sk_player_count=sk_player_count, town_cop_req=town_cop_req, town_doctor_req=town_doctor_req)  