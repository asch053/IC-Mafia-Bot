import config
import discord
import logging
from game.engine import Game
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def start_game_command(
    self,
    interaction: discord.Interaction,
    game_type: str,
    phase_hours: float,
    start_datetime: str,
    narration_type: str = "Classic Mafia",
    gf_investigate_choice: str = "No",
    sk_investigate_choice: str = "No",
    mafia_ratio: float = None,
    town_rb_req: int = None,
    mafia_rb_req: int = None,
    sk_player_count: int = None,
    town_cop_req: int = None,
    town_doctor_req: int = None,
    gf_night_immune_choice: str = "Yes",
    sk_night_immune_choice: str = "Yes",
    br_skip_day_choice: str = "No"
):
    """Command to start a new game instance with the specified parameters."""
    if mafia_ratio is None:
        mafia_ratio = getattr(config, 'mob_ratio', 0.25)
    if town_rb_req is None:
        town_rb_req = getattr(config, 'min_town_rb_players', 10)
    if mafia_rb_req is None:
        mafia_rb_req = getattr(config, 'min_mob_rb_mafia_count', 4)
    if sk_player_count is None:
        sk_player_count = getattr(config, 'min_sk_players', 9)
    if town_cop_req is None:
        town_cop_req = getattr(config, 'min_cop_players', 6)
    if town_doctor_req is None:
        town_doctor_req = getattr(config, 'min_doctor_players', 7)

    logger.info(
        f"Starting game with parameters: game_type={game_type}, phase_hours={phase_hours}, start_datetime={start_datetime},"
        f"narration_type={narration_type}, gf_investigate_choice={gf_investigate_choice}, sk_investigate_choice={sk_investigate_choice},"
        f"gf_night_immune_choice={gf_night_immune_choice}, sk_night_immune_choice={sk_night_immune_choice},"
        f"br_skip_day_choice={br_skip_day_choice},"
        f"mafia_ratio={mafia_ratio}, town_rb_req={town_rb_req}, mafia_rb_req={mafia_rb_req}, sk_player_count={sk_player_count},"
        f"town_cop_req={town_cop_req}, town_doctor_req={town_doctor_req}"
    )

    current_game = self.get_game_instance()
    if current_game is not None:
        await interaction.response.send_message("A game is already running. Please stop the current game before starting a new one.", ephemeral=True)
        return

    logger.info(f"Validating start_datetime: {start_datetime}")
    try:
        start_datetime_obj = datetime.strptime(start_datetime, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        await interaction.response.send_message("Invalid date/time format. Please use 'YYYY-MM-DD HH:MM' format in UTC.", ephemeral=True)
        return

    if start_datetime_obj <= datetime.now(timezone.utc):
        await interaction.response.send_message("The start time must be in the future.", ephemeral=True)
        return

    gf_investigate = (gf_investigate_choice.lower() == "yes")
    sk_investigate = (sk_investigate_choice.lower() == "yes")
    gf_night_immune = (str(gf_night_immune_choice).strip().lower() in ("yes", "true", "1"))
    sk_night_immune = (str(sk_night_immune_choice).strip().lower() in ("yes", "true", "1"))
    br_skip_day = (str(br_skip_day_choice).strip().lower() in ("yes", "true", "1"))

    if not isinstance(town_rb_req, int):
        await interaction.response.send_message("Invalid town role blocker requirement. Please provide an integer.", ephemeral=True)
        return
    if not isinstance(mafia_rb_req, int):
        await interaction.response.send_message("Invalid mafia role blocker requirement. Please provide an integer.", ephemeral=True)
        return
    if not isinstance(sk_player_count, int):
        await interaction.response.send_message("Invalid Serial Killer player count requirement. Please provide an integer.", ephemeral=True)
        return
    if not isinstance(mafia_ratio, (float, int)) or mafia_ratio <= 0 or mafia_ratio >= 1:
        await interaction.response.send_message("Invalid mafia ratio. Please provide a float between 0 and 1 (e.g., 0.25 for 25%).", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    cleanup_cb = getattr(self, '_cleanup_game', None)
    new_game = Game(self.bot, interaction.guild, cleanup_callback=cleanup_cb, game_type=game_type)
    self.set_game_instance(new_game)
    logger.info(f"New game instance created by admin: {interaction.user.name}.")

    await interaction.followup.send(f"Game scheduled by {interaction.user.mention}!", ephemeral=True)

    await new_game.start_game(
        game_type=game_type,
        start_datetime_obj=start_datetime_obj,
        phase_hours=phase_hours,
        gf_investigate=gf_investigate,
        sk_investigate=sk_investigate,
        narration_type=narration_type,
        max_players=99,
        mafia_ratio=float(mafia_ratio),
        town_rb_req=town_rb_req,
        mafia_rb_req=mafia_rb_req,
        sk_player_count=sk_player_count,
        town_cop_req=town_cop_req,
        town_doctor_req=town_doctor_req,
        gf_night_immune=gf_night_immune,
        sk_night_immune=sk_night_immune,
        br_skip_day=br_skip_day
    )

    # Log rules setup to Google Sheets
    try:
        from cogs.exportcogs.sheets_client import log_game_setup_to_sheets
        setup_data = {
            "game_id": new_game.game_settings.get("game_id", start_datetime_obj.strftime("%Y%m%d-%H%M%S")),
            "scheduled_at_utc": datetime.now(timezone.utc).isoformat(),
            "scheduled_by": getattr(interaction.user, "name", str(interaction.user)),
            "game_type": game_type,
            "story_type": narration_type,
            "start_time_utc": start_datetime_obj.isoformat(),
            "phase_hours": phase_hours,
            "mafia_ratio": float(mafia_ratio),
            "town_cop_req": town_cop_req,
            "town_doctor_req": town_doctor_req,
            "town_rb_req": town_rb_req,
            "mafia_rb_req": mafia_rb_req,
            "sk_player_count": sk_player_count,
            "gf_investigate": gf_investigate,
            "sk_investigate": sk_investigate,
            "gf_night_immune": gf_night_immune,
            "sk_night_immune": sk_night_immune,
            "br_skip_day": br_skip_day
        }
        await log_game_setup_to_sheets(setup_data)
    except Exception as e:
        logger.error(f"Error logging rules setup to Google Sheets: {e}", exc_info=True)