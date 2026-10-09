# game/engine/start.py
import logging
from datetime import datetime
import config
from utils.formattimeremain import format_time_remaining
from game.data.getrules import build_rules_embed

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def start_game(
    game,
    game_type: str,
    start_datetime_obj: datetime,
    phase_hours: float,
    gf_investigate: bool,
    sk_investigate: bool,
    narration_type: str,
    max_players: int = 99,
    mafia_ratio: float = None,
    town_rb_req: int = None,
    mafia_rb_req: int = None,
    sk_player_count: int = None,
    town_cop_req: int = None,
    town_doctor_req: int = None,
    gf_night_immune: bool = True,
    sk_night_immune: bool = True,
    br_skip_day: bool = False
):
    """Announces the sign-up phase and starts the signup_loop."""
    logger.info("Starting the sign-up phase for the game.")

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

    # 1. Set up game settings
    game.game_settings["game_id"] = start_datetime_obj.strftime("%Y%m%d-%H%M%S")
    game.game_settings["game_type"] = game_type
    game.game_settings["game_started"] = True
    game.game_settings["start_time"] = start_datetime_obj
    game.game_settings["current_phase"] = "signup"
    game.game_settings["phase_end_time"] = start_datetime_obj
    game.game_settings["phase_hours"] = phase_hours
    game.game_settings["gf_investigate"] = gf_investigate
    game.game_settings["sk_investigate"] = sk_investigate
    game.game_settings["gf_night_immune"] = True if gf_night_immune is None else bool(gf_night_immune)
    game.game_settings["sk_night_immune"] = True if sk_night_immune is None else bool(sk_night_immune)
    game.game_settings["br_skip_day"] = bool(br_skip_day)
    game.game_settings["story_type"] = narration_type
    game.game_settings["mafia_ratio"] = mafia_ratio
    game.game_settings["town_rb_req"] = town_rb_req
    game.game_settings["mafia_rb_req"] = mafia_rb_req
    game.game_settings["sk_player_count"] = sk_player_count
    game.game_settings["town_cop_req"] = town_cop_req
    game.game_settings["town_doctor_req"] = town_doctor_req
    game.max_players = max_players
    game.is_prologue = True
    game.is_introduction = False
    game.is_epilogue = False

    # 2. Announce the game
    spectator_role = game.guild.get_role(getattr(config, 'SPECTATOR_ROLE_ID', 0)) if game.guild else None
    spec_mention = spectator_role.mention if spectator_role else "@Spectators"
    signup_channel_mention = f"<#{getattr(config, 'SIGN_UP_HERE_CHANNEL_ID', 0)}>"
    start_time_str = start_datetime_obj.strftime('%Y-%m-%d %H:%M:%S UTC')
    time_left_str = format_time_remaining(start_datetime_obj)

    announcement = (
        f"**A new game of {game.game_settings['game_type']} Mafia has been scheduled!**\n\n"
        f"Theme will be **{game.game_settings['story_type']}**.\n"
        f"Sign-ups are now open for **{time_left_str}**! {spec_mention} Use `/mafiajoin` in {signup_channel_mention} to join.\n"
        f"The game will officially begin at: **{start_time_str}** (or when {game.max_players} players join)."
    )
    if game.game_settings.get("br_skip_day"):
        announcement += (
            "\n\n⚡ **SPECIAL GAME RULE: DAY PHASE SKIPPED!** ⚡\n"
            "> 🌙 **Consecutive Night Action Phases Only — No daytime discussion or lynches!**"
        )
    logger.info(f"Game announcement: {announcement}")

    ann_chan = game.bot.get_channel(getattr(config, 'ANNOUNCEMENT_CHANNEL_ID', 0))
    if ann_chan:
        await ann_chan.send(announcement)

    signup_chan = game.bot.get_channel(getattr(config, 'SIGN_UP_HERE_CHANNEL_ID', 0))
    if signup_chan:
        await signup_chan.send("## New Game ##\n--------------------------\n**Game Starting Soon!**\n\n\n")

    stories_chan = game.bot.get_channel(getattr(config, 'STORIES_CHANNEL_ID', 0))
    if stories_chan:
        await stories_chan.send("## New Game ##\n--------------------------\n**Game Starting Soon!**\n\n\n")

    # 3. Prologue narration
    game_state = {
        "game_id": game.game_settings['game_id'],
        "phase": "Prologue",
        "number": None,
        "living_players": None,
        "is_prologue": True,
        "is_introduction": False,
        "is_epilogue": False,
        "is_game_over": False,
        "winner": None,
        "game_type": game.game_settings["game_type"],
        "story_type": game.game_settings["story_type"]
    }
    if hasattr(game, 'narration_manager') and game.narration_manager:
        prologue_story = await game.narration_manager.construct_story(game_state=game_state)
        if stories_chan and prologue_story:
            await stories_chan.send(f"**--- Prologue ---**\n\n{prologue_story}")
    game.is_prologue = False

    # 4. Rules & roles embed
    rules_chan = game.bot.get_channel(getattr(config, 'RULES_AND_ROLES_CHANNEL_ID', 0))
    if rules_chan:
        try:
            embed = build_rules_embed(game, game=game)
            await rules_chan.send(" ## New Game ##\n--------------------------\n**Game Starting Soon!**\n\n", embed=embed)
        except Exception as e:
            logger.error(f"Error sending rules embed: {e}")

    # 5. Start signup loop
    if hasattr(game, 'signup_loop') and hasattr(game.signup_loop, 'start'):
        if not game.signup_loop.is_running():
            game.signup_loop.start()

