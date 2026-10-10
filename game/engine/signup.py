# game/engine/signup.py
import sys
import logging
import random
from datetime import datetime, timezone
import discord
import config
from game.player import Player
from utils.formattimeremain import format_time_remaining
from utils.updatediscordroles import update_player_discord_roles

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def _get_config():
    engine_mod = sys.modules.get('game.engine')
    if engine_mod and hasattr(engine_mod, 'config'):
        return engine_mod.config
    return config


def _get_update_roles_fn():
    engine_mod = sys.modules.get('game.engine')
    if engine_mod and hasattr(engine_mod, 'update_player_discord_roles'):
        return engine_mod.update_player_discord_roles
    return update_player_discord_roles


async def signup_loop(game):
    """Monitors the sign-up phase, sends reminders, and checks for start conditions."""
    try:
        logger.debug("Sign-up loop iteration started.")
        game_should_start = False
        reason = ""

        phase_end = game.game_settings.get("phase_end_time")
        if phase_end and datetime.now(timezone.utc) >= phase_end:
            game_should_start = True
            reason = "The scheduled start time has been reached."
            logger.info("Sign-up phase ended due to reaching scheduled start time.")
        elif len(game.players) >= game.max_players:
            game_should_start = True
            reason = f"The maximum number of players ({game.max_players}) has been reached."
            logger.info(f"Sign-up phase ended due to max player count: {game.max_players}.")
        elif getattr(game, 'force_start_flag', False):
            game_should_start = True
            reason = "The game has been force-started by an administrator."
            logger.info("Sign-up phase ended due to force start flag.")

        if game_should_start:
            logger.info(f"Ending sign-up loop. Reason: {reason}")
            signup_chan = game.bot.get_channel(getattr(config, 'SIGN_UP_HERE_CHANNEL_ID', 0))
            if signup_chan:
                await signup_chan.send(f"**Sign-ups are now closed!** {reason} The game will now begin.")
            ann_chan = game.bot.get_channel(getattr(config, 'ANNOUNCEMENT_CHANNEL_ID', 0))
            if ann_chan:
                await ann_chan.send(f"**Sign-ups are now closed!** {reason} The game will now begin.")

            if hasattr(game, 'signup_loop') and hasattr(game.signup_loop, 'stop'):
                game.signup_loop.stop()

            if game.game_settings.get("current_phase") == "signup":
                await game.prepare_game()
            return

        # Check for reminders
        spectator_role_id = getattr(config, 'SPECTATOR_ROLE_ID', 0)
        spectator_role = game.guild.get_role(spectator_role_id) if game.guild else None
        if not spectator_role or not phase_end:
            return

        time_left = phase_end - datetime.now(timezone.utc)
        time_left_str = format_time_remaining(phase_end)
        total_minutes_left = time_left.total_seconds() / 60

        reminder_points = getattr(config, 'REMINDER_POINTS', {})
        for minutes, text in reminder_points.items():
            if total_minutes_left <= minutes and minutes not in game.reminders_sent:
                signup_chan = game.bot.get_channel(getattr(config, 'SIGN_UP_HERE_CHANNEL_ID', 0))
                if signup_chan:
                    await signup_chan.send(
                        f"**Reminder!** {spectator_role.mention} There's still time to join! Sign-ups close in **{time_left_str}**.\n"
                        f"Use `/mafiajoin` to participate!\n"
                    )
                game.reminders_sent.add(minutes)
                logger.info(f"Sent reminder for {text} remaining in the phase.")
                break
    except Exception as e:
        logger.critical(f"Sign-up loop encountered a critical error: {e}", exc_info=True)


async def force_start(game, interaction: discord.Interaction):
    """
    [ADMIN ONLY] Forcibly ends the current phase.
    If in signups, ends signups and starts the game. If in day/night, ends that phase.
    """
    current_phase = str(game.game_settings.get("current_phase", "")).lower()
    if current_phase == "signup":
        game.force_start_flag = True
        delay = getattr(config, 'signup_loop_interval_seconds', 30)
        logger.warning(f"Sign-ups forcibly ended by admin: {interaction.user.name}")
        await interaction.response.send_message(
            f"Sign-ups have been ended by admin. The game will begin on the next loop iteration (within {delay} seconds).",
            ephemeral=False
        )
    elif current_phase in ["day", "night"]:
        await game.force_end_phase(interaction)
    else:
        await interaction.response.send_message("No active phase to force end.", ephemeral=True)


async def add_player(game, user, player_name, channel):
    """Adds a player to the game during the signup phase."""
    async with game.player_lock:
        if game.game_settings.get("current_phase") != "signup":
            if channel:
                await channel.send("Sorry, the game is not currently accepting new players.")
            logger.error(f"{user.name} tried to join the game outside of the sign-up phase.")
            return

        if user.id in game.players:
            if channel:
                await channel.send("You have already joined the game!")
            logger.warning(f"{user.name} tried to join the game again with player name {player_name}.")
            return

        if len(game.players) >= game.max_players:
            if channel:
                await channel.send(f"Sorry, the game is full with {game.max_players} players.")
            logger.warning(f"{user.name} tried to join the game but it is already full.")
            return

        game.players[user.id] = Player(user_id=user.id, discord_name=user.name, display_name=player_name)
        game.players[user.id].is_alive = True

        if channel:
            await channel.send(f"Welcome to the game, **{player_name}**! You are player #{len(game.players)}.")
        logger.info(f"{user.name} ({player_name}) has joined the game.")

        await _get_update_roles_fn()(game.bot, game.guild, game.players)

        status_message = game.get_status_message()
        signup_chan = game.bot.get_channel(getattr(config, 'SIGN_UP_HERE_CHANNEL_ID', 0))
        if signup_chan:
            try:
                await signup_chan.send(status_message)
            except Exception as e:
                logger.error(f"Failed to send status message: {e}")

        return f"You have successfully signed up as **{player_name}**! You are player #{len(game.players)}."


async def remove_player(game, user, channel):
    """Removes a player from the game during the signup phase."""
    async with game.player_lock:
        if game.game_settings.get("current_phase") != "signup":
            if channel:
                await channel.send("You can only leave the game during the sign-up phase.")
            logger.error(f"{user.name} tried to leave the game outside of the sign-up phase.")
            return False

        if user.id in game.players:
            player_name = game.players[user.id].display_name
            del game.players[user.id]
            if channel:
                await channel.send(f"**{player_name}** has left the game.")
            logger.info(f"{user.name} ({player_name}) has left the game.")
            await _get_update_roles_fn()(game.bot, game.guild, game.players)
            return True
        else:
            if channel:
                await channel.send("You are not currently in the game.")
            logger.warning(f"{user.name} tried to leave the game but was not a participant.")
            return False


def add_npc(game):
    """Adds a single NPC to the game."""
    if not getattr(game, 'npc_names', None):
        logger.critical("CRITICAL ERROR: game.npc_names is missing or empty when adding NPC. Generating fallback bot names in 'Bot_##' format.")
        fallback_count = max(50, getattr(game, 'max_players', 19) * 2)
        game.npc_names = [f"Bot_{i:02d}" for i in range(1, fallback_count + 1)]

    available_names = [name for name in game.npc_names if name not in [p.display_name for p in game.players.values()]]
    if not available_names:
        logger.critical("CRITICAL ERROR: All unique NPC names in game.npc_names are exhausted! Generating next 'Bot_##' name.")
        existing_names = {p.display_name for p in game.players.values()}
        idx = 1
        while f"Bot_{idx:02d}" in existing_names:
            idx += 1
        npc_name = f"Bot_{idx:02d}"
    else:
        npc_name = random.choice(available_names)

    npc_id = -(len(game.players) + 1)
    game.players[npc_id] = Player(user_id=npc_id, discord_name=npc_name, display_name=npc_name)
    logger.info(f"Added NPC: {npc_name}")
    return npc_name
