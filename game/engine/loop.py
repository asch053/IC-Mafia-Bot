# game/engine/loop.py
import sys
import logging
from datetime import datetime, timedelta, timezone
import discord
import config
from utils.formattimeremain import format_time_remaining
from utils.sendchunkedmessage import send_chunked_message
from utils.updatediscordroles import update_player_discord_roles

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def _get_update_roles_fn():
    engine_mod = sys.modules.get('game.engine')
    if engine_mod and hasattr(engine_mod, 'update_player_discord_roles'):
        return engine_mod.update_player_discord_roles
    return update_player_discord_roles


async def game_loop_iteration(game):
    """
    The main game loop. Runs every interval to check phase deadlines and send reminders.
    It handles the transition between phases, processes end-of-phase events, and checks for win conditions.
    """
    living_role = game.guild.get_role(getattr(config, 'LIVING_ROLE_ID', 0))
    if not living_role:
        logger.critical("Could not find the living role in the guild. Check the discord_roles.json configuration.")
        return

    # --- If the phase has ended, process it and start the next one ---
    if datetime.now(timezone.utc) >= game.game_settings["phase_end_time"]:
        current_end_time = game.game_settings["phase_end_time"]
        logger.info(f"Phase {game.game_settings['current_phase']} {game.game_settings['phase_number']} ended at {current_end_time}.")
        winner = None

        if game.game_settings["current_phase"].lower() == "day":
            logger.debug("Day phase ended. Processing lynch votes...")
            voting_channel = game.bot.get_channel(config.VOTING_CHANNEL_ID)
            if voting_channel:
                await voting_channel.send(
                    f"**{game.game_settings['current_phase'].capitalize()} {game.game_settings['phase_number']} has ended!**\n\n{living_role.mention} the day has ended. Processing lynch votes..."
                )
            game.game_settings["current_phase"] = "pre-night"
            logger.info(f"Transitioned to pre-night so >> Current phase = {game.game_settings['current_phase']}, phase number = {game.game_settings['phase_number']}")
            winner = await game.tally_votes()
            logger.debug("Day phase ended. Processing lynch votes...")
        elif game.game_settings["current_phase"].lower() == "night":
            logger.info("Night phase ended. Processing night actions...")
            logger.info(f"Current phase = {game.game_settings['current_phase']}, phase number = {game.game_settings['phase_number']}")
            stories_channel = game.bot.get_channel(config.STORIES_CHANNEL_ID)
            if stories_channel:
                await stories_channel.send(f"{living_role.mention} the night has ended. Processing night actions...")
            game.game_settings["current_phase"] = "pre-day"
            logger.info(f"Transitioned to pre-day so >> Current phase = {game.game_settings['current_phase']}, phase number = {game.game_settings['phase_number']}")
            await game.process_night_actions()
            await game._resolve_night_deaths()

            # Update last_action_target for players who acted
            processed_actions = game.night_actions.copy()
            for player in game.players.values():
                if player.id not in processed_actions:
                    player.last_action_target_id = None
            for p_id, action_data in processed_actions.items():
                if action_data.get('type') in ['heal', 'block']:
                    acting_player = game.players.get(p_id)
                    if acting_player:
                        acting_player.last_action_target_id = action_data.get('target_id')

        logger.info(f"{game.game_settings['current_phase'].capitalize()} phase ended. Events processed, creating story...")
        await _get_update_roles_fn()(game.bot, game.guild, game.players)
        logger.info("Updated player roles in Discord based on current game state.")

        if not winner:
            logger.info("Checking win conditions after phase end.")
            winner = game.check_win_conditions()
            if winner:
                logger.info(f"Win conditions met. Winner: {winner}")

        logger.info("Constructing story from narration manager events...")
        if game.game_settings['current_phase'] == "pre-day":
            phase_just_ended = "night"
        elif game.game_settings['current_phase'] == "pre-night":
            phase_just_ended = "day"
        else:
            phase_just_ended = game.game_settings['current_phase']

        game_state = {
            "game_id": game.game_settings['game_id'],
            "phase": phase_just_ended,
            "number": game.game_settings['phase_number'],
            "living_players": [p for p in game.players.values() if p.is_alive],
            "game_type": game.game_settings.get("game_type", "classic"),
            "story_type": game.game_settings.get('story_type', 'Classic Mafia'),
            "is_prologue": False,
            "is_introduction": False,
            "is_game_over": False if not winner else True,
            "is_epilogue": False,
            "winner": winner if winner else "No Winner",
        }
        logger.info(f"Preparing to construct story for phase: {phase_just_ended}, number: {game.game_settings['phase_number']} with {len(game_state['living_players'])} living players.\n{game_state}")

        story = await game.narration_manager.construct_story(game_state=game_state)
        if getattr(game, 'is_prologue', False):
            game.is_prologue = False

        if story:
            logger.info("Story constructed from narration manager events.")
            story_channel = game.bot.get_channel(config.STORIES_CHANNEL_ID)
            if story_channel:
                await send_chunked_message(game, story_channel, story)
                logger.info("Story sent to stories channel.")

        logger.info(f"Phase {game.game_settings['current_phase']} {game.game_settings['phase_number']} ended. Story constructed.")
        game.narration_manager.clear()

        if winner:
            await game.announce_winner(winner)
            logger.info(f"Game ended with winner: {winner}")
            await _get_update_roles_fn()(game.bot, game.guild, game.players)
            logger.info("Updated player roles in Discord based on current game state.")
            await game.reset()

            logger.info("Updating champion roles...")
            fame_cog = game.bot.get_cog("FameCog")
            if fame_cog:
                logger.info("Triggering automatic Champion Role update.")
                champion_message = await fame_cog.update_champion_roles(game.guild, game.game_settings["game_type"])
                rules_channel = game.bot.get_channel(config.RULES_AND_ROLES_CHANNEL_ID)
                if rules_channel and champion_message:
                    await rules_channel.send(embed=champion_message)
                    logger.info("Champion Role update sent to rules channel.")
            return

        status_message = game.get_status_message()
        try:
            rules_chan = game.bot.get_channel(config.RULES_AND_ROLES_CHANNEL_ID)
            if rules_chan:
                await rules_chan.send(status_message)
        except Exception as e:
            logger.error(f"Error sending status message: {e}")

        # Transition to new phase
        game.reminders_sent.clear()
        logger.info(f"Current phase before transition: {game.game_settings['current_phase']}, phase number: {game.game_settings['phase_number']}")
        game.game_settings["phase_end_time"] = current_end_time + timedelta(hours=game.game_settings["phase_hours"])

        if game.game_settings["current_phase"].lower() == "pre-day":
            game.game_settings["current_phase"] = "day"
            announcement = f"## ☀️ Day {game.game_settings['phase_number']} has begun. You have {format_time_remaining(game.game_settings['phase_end_time'])}  to discuss and vote."
            logger.info("Transitioning to day phase.")
        else:
            game.game_settings["current_phase"] = "night"
            game.game_settings["phase_number"] += 1
            game.night_actions = {}
            game.lynch_votes = {}
            announcement = f"## 🌙 Night {game.game_settings['phase_number']} has begun. You have {format_time_remaining(game.game_settings['phase_end_time'])} hours to use your night actions."
            logger.info("Transitioning to night phase.")

        stories_chan = game.bot.get_channel(config.STORIES_CHANNEL_ID)
        if stories_chan:
            await stories_chan.send(announcement)
        return

    # --- If phase has NOT ended, check for reminders ---
    time_left = game.game_settings["phase_end_time"] - datetime.now(timezone.utc)
    total_minutes_left = time_left.total_seconds() / 60
    living_role = game.guild.get_role(getattr(config, 'LIVING_ROLE_ID', 0))
    if not living_role:
        logger.critical("Could not find the living role in the guild. Check the discord_roles.json configuration.")
        return

    reminder_points = config.REMINDER_POINTS
    logger.debug(f"Checking for reminders. Total minutes left: {total_minutes_left}")
    for minutes, text in reminder_points.items():
        if total_minutes_left <= minutes and minutes not in game.reminders_sent:
            stories_chan = game.bot.get_channel(config.STORIES_CHANNEL_ID)
            if stories_chan:
                await stories_chan.send(
                    f"**Reminder:** There is **{text}** left in the phase! {living_role.mention}"
                )
            game.reminders_sent.add(minutes)
            logger.info(f"Sent reminder for {text} remaining in the phase.")
            break


async def before_game_loop(game):
    await game.bot.wait_until_ready()
    logger.info("Main game loop is starting.")
    game.game_settings["phase_end_time"] = datetime.now(timezone.utc)


async def before_signup_loop(game):
    await game.bot.wait_until_ready()
    logger.info("Sign-up loop is starting.")


async def after_game_loop(game):
    logger.info("Game loop has finished. Triggering cleanup.")
    if getattr(game, 'cleanup_callback', None):
        game.cleanup_callback()


async def force_end_phase(game, interaction: discord.Interaction):
    """[ADMIN ONLY] Forcibly ends the current day or night phase."""
    if game.game_settings["current_phase"] in ["day", "night"]:
        game.game_settings["phase_end_time"] = datetime.now(timezone.utc)
        logger.warning(f"Phase forcibly ended by admin: {interaction.user.name}")
        await interaction.response.send_message(
            "Phase end time has been set to now. The game will advance on the next loop. This will set the next phase end time from now.", 
            ephemeral=False
        )
    else:
        await interaction.response.send_message("A day or night phase is not currently active.", ephemeral=True)
