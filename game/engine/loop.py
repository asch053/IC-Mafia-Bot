# game/engine/loop.py
"""
Game State Machine and Phase Progression Loop.

Responsibilities:
1. Periodic Deadline Evaluation (`game_loop_iteration`):
   - Compares the current UTC time against `game.game_settings["phase_end_time"]`.
   - Dispatches warning reminders at predefined thresholds (`config.REMINDER_POINTS`).
2. Phase Transition Processing:
   - Day End: Processes votes (`tally_votes()`), executes lynches, updates Discord roles.
   - Night End: Executes night actions (`process_night_actions()`), resolves saves/kills, updates roles.
   - Checks win conditions and ends game if a faction or Jester has won.
   - Triggers dynamic storytelling via `NarrationManager` and broadcasts chapters to `#stories`.
   - Transitions to the next phase: supports standard Day/Night cycles as well as Battle Royale 'skip day' mode.
3. Administrative Overrides (`force_end_phase`):
   - Allows game administrators to prematurely advance deadlocked phases.
"""

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
    """Dynamically resolves update_player_discord_roles to allow runtime monkeypatching during testing."""
    engine_mod = sys.modules.get('game.engine')
    if engine_mod and hasattr(engine_mod, 'update_player_discord_roles'):
        return engine_mod.update_player_discord_roles
    return update_player_discord_roles


async def game_loop_iteration(game):
    """
    Main tick handler executed on each game loop interval.

    Execution Flow:
    1. Checks if the active phase deadline has expired.
    2. If expired:
       a. Resolves day votes or night actions.
       b. Updates Discord server roles (living/dead).
       c. Checks victory conditions.
       d. Generates and broadcasts the narrative story.
       e. Concludes the game or advances to the next phase.
    3. If active:
       a. Computes remaining time and broadcasts interval reminders.
    """
    living_role = game.guild.get_role(getattr(config, 'LIVING_ROLE_ID', 0))
    if not living_role:
        logger.critical("Could not find the living role in the guild. Check the discord_roles.json configuration.")
        return

    try:
        # =====================================================================
        # Phase Deadline Expired: Advance the Game State
        # =====================================================================
        if datetime.now(timezone.utc) >= game.game_settings["phase_end_time"]:
            current_end_time = game.game_settings["phase_end_time"]
            logger.info(f"Phase {game.game_settings['current_phase']} {game.game_settings['phase_number']} ended at {current_end_time}.")
            winner = None

            # -----------------------------------------------------------------
            # Day Phase Expiration: Process Lynches
            # -----------------------------------------------------------------
            if game.game_settings["current_phase"].lower() == "day":
                logger.debug("Day phase ended. Processing lynch votes...")
                voting_channel = game.bot.get_channel(config.VOTING_CHANNEL_ID)
                if voting_channel:
                    await voting_channel.send(
                        f"**{game.game_settings['current_phase'].capitalize()} {game.game_settings['phase_number']} has ended!**\n\n"
                        f"{living_role.mention} the day has ended. Processing lynch votes..."
                    )
                game.game_settings["current_phase"] = "pre-night"
                logger.info(f"Transitioned to pre-night >> Current phase = {game.game_settings['current_phase']}, number = {game.game_settings['phase_number']}")
                winner = await game.tally_votes()

            # -----------------------------------------------------------------
            # Night Phase Expiration: Execute Actions & Deaths
            # -----------------------------------------------------------------
            elif game.game_settings["current_phase"].lower() == "night":
                logger.info("Night phase ended. Processing night actions...")
                logger.info(f"Current phase = {game.game_settings['current_phase']}, number = {game.game_settings['phase_number']}")
                stories_channel = game.bot.get_channel(config.STORIES_CHANNEL_ID)
                if stories_channel:
                    await stories_channel.send(f"{living_role.mention} the night has ended. Processing night actions...")
                game.game_settings["current_phase"] = "pre-day"
                logger.info(f"Transitioned to pre-day >> Current phase = {game.game_settings['current_phase']}, number = {game.game_settings['phase_number']}")
                await game.process_night_actions()
                await game._resolve_night_deaths()

                # Update consecutive action tracking for Doctors and Roleblockers
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
            
            # Synchronize Discord server roles based on who died this phase
            await _get_update_roles_fn()(game.bot, game.guild, game.players)
            logger.info("Updated player roles in Discord based on current game state.")

            # Check if a team or solo player has met their win condition
            if not winner:
                logger.info("Checking win conditions after phase end.")
                winner = game.check_win_conditions()
                if winner:
                    logger.info(f"Win conditions met. Winner: {winner}")

            # -----------------------------------------------------------------
            # Generate and Post Narrative Story
            # -----------------------------------------------------------------
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
            logger.info(
                f"Preparing to construct story for phase: {phase_just_ended}, number: {game.game_settings['phase_number']} "
                f"with {len(game_state['living_players'])} living players."
            )

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

            # -----------------------------------------------------------------
            # Game Over Resolution
            # -----------------------------------------------------------------
            if winner:
                await game.announce_winner(winner)
                logger.info(f"Game ended with winner: {winner}")
                await _get_update_roles_fn()(game.bot, game.guild, game.players)
                logger.info("Updated player roles in Discord based on current game state.")
                await game.reset()

                # Trigger automatic hall of fame and leaderboard updates
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

            # Broadcast updated game status
            status_message = game.get_status_message()
            try:
                rules_chan = game.bot.get_channel(config.RULES_AND_ROLES_CHANNEL_ID)
                if rules_chan:
                    await rules_chan.send(status_message)
            except Exception as e:
                logger.error(f"Error sending status message: {e}")

            # -----------------------------------------------------------------
            # Transition to Next Phase
            # -----------------------------------------------------------------
            game.reminders_sent.clear()
            logger.info(f"Current phase before transition: {game.game_settings['current_phase']}, phase number: {game.game_settings['phase_number']}")
            game.game_settings["phase_end_time"] = current_end_time + timedelta(hours=game.game_settings["phase_hours"])

            # Check if Battle Royale mode is configured to skip the daytime phase
            is_br_skip_day = (
                str(game.game_settings.get("game_type", "")).lower() == "battle_royale"
                and game.game_settings.get("br_skip_day", False)
            )

            if game.game_settings["current_phase"].lower() == "pre-day":
                if is_br_skip_day:
                    # Skip Day: Loop directly back into a new night phase
                    game.game_settings["current_phase"] = "night"
                    game.game_settings["phase_number"] += 1
                    game.night_actions = {}
                    game.lynch_votes = {}
                    announcement = (
                        f"## ⚡ 🌙 Night {game.game_settings['phase_number']} has begun!\n"
                        f"> ⚠️ **DAY PHASE SKIPPED:** Consecutive Night Mode is active — no voting or daytime discussion.\n"
                        f"> ⏱️ You have **{format_time_remaining(game.game_settings['phase_end_time'])}** to submit your night actions via bot DM!"
                    )
                    logger.info(f"Battle Royale (Skip Day): Transitioning directly to Night {game.game_settings['phase_number']}.")
                else:
                    # Standard transition to Day
                    game.game_settings["current_phase"] = "day"
                    announcement = (
                        f"## ☀️ Day {game.game_settings['phase_number']} has begun. "
                        f"You have {format_time_remaining(game.game_settings['phase_end_time'])} to discuss and vote."
                    )
                    logger.info("Transitioning to day phase.")
            else:
                # Transition to Night
                game.game_settings["current_phase"] = "night"
                game.game_settings["phase_number"] += 1
                game.night_actions = {}
                game.lynch_votes = {}
                announcement = (
                    f"## 🌙 Night {game.game_settings['phase_number']} has begun. "
                    f"You have {format_time_remaining(game.game_settings['phase_end_time'])} to use your night actions."
                )
                logger.info("Transitioning to night phase.")

            stories_chan = game.bot.get_channel(config.STORIES_CHANNEL_ID)
            if stories_chan:
                await stories_chan.send(announcement)
            return

        # =====================================================================
        # Phase Still Active: Check and Send Warning Reminders
        # =====================================================================
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

    except Exception as e:
        curr_phase = game.game_settings.get('current_phase', 'unknown')
        phase_num = game.game_settings.get('phase_number', 0)
        logger.critical(
            f"Game loop iteration failed: Phase '{curr_phase}' #{phase_num} failed to advance or encountered fatal error: {e}",
            exc_info=True
        )


async def before_game_loop(game):
    """Initializes phase deadline when the background loop begins."""
    await game.bot.wait_until_ready()
    logger.info("Main game loop is starting.")
    game.game_settings["phase_end_time"] = datetime.now(timezone.utc)


async def before_signup_loop(game):
    """Initializes sign-up period when the bot is ready."""
    await game.bot.wait_until_ready()
    logger.info("Sign-up loop is starting.")


async def after_game_loop(game):
    """Cleans up tasks and resets state when the loop stops."""
    logger.info("Game loop has finished. Triggering cleanup.")
    if getattr(game, 'cleanup_callback', None):
        game.cleanup_callback()


async def force_end_phase(game, interaction: discord.Interaction):
    """
    [ADMIN ONLY] Forcibly expires the active game phase (sign-up, day, or night) immediately.
    """
    current_phase = str(game.game_settings.get("current_phase", "")).lower()
    if current_phase == "signup":
        await game.force_start(interaction)
    elif current_phase in ["day", "night"]:
        game.game_settings["phase_end_time"] = datetime.now(timezone.utc)
        logger.warning(f"Phase '{current_phase}' forcibly ended by admin: {interaction.user.name}")
        await interaction.response.send_message(
            f"Phase '{current_phase.capitalize()}' end time has been set to now. The game will advance on the next loop tick.", 
            ephemeral=False
        )
    else:
        await interaction.response.send_message("No active phase to force end.", ephemeral=True)
