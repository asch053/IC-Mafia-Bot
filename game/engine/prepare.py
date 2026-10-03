# game/engine/prepare.py
import io
import logging
import secrets
import discord
import config
from game.roles import get_role_instance
from game import setup_generator
from utils.sendroledm import send_role_dm
from utils.sendmafiainfodm import send_mafia_info_dm
from utils.updatediscordroles import update_player_discord_roles

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def generate_game_roles(game):
    """Generates a list of GameRole objects based on player count."""
    logger.info("Generating dynamic role list...")
    game_type = game.game_settings.get('game_type', 'classic')
    player_count = len(game.players)

    min_players = getattr(config, 'min_players', 5)
    if player_count < min_players:
        logger.warning(f"Cannot generate {game_type} roles for {player_count} players. Minimum is {min_players}.\n Converting to Battle Royale mode.")
        rules_chan = game.bot.get_channel(getattr(config, 'RULES_AND_ROLES_CHANNEL_ID', 0))
        if rules_chan:
            try:
                import asyncio
                loop = asyncio.get_running_loop()
                loop.create_task(rules_chan.send(f"Error: Could not generate a 'Classic' game for {player_count} players. Minimum is {min_players}.\n Converting to Battle Royale mode."))
            except RuntimeError:
                pass
        game.game_settings['game_type'] = "battle_royale"

    role_names = setup_generator.generate_roles(
        player_count,
        game.game_settings.get('game_type', 'classic'),
        game.game_settings.get("mafia_ratio"),
        game.game_settings.get("town_rb_req"),
        game.game_settings.get("mafia_rb_req"),
        game.game_settings.get("sk_player_count"),
        game.game_settings.get("town_cop_req"),
        game.game_settings.get("town_doctor_req")
    )

    if not role_names:
        logger.critical(f"Could not generate roles for {player_count} players. Aborting game preparation.")
        return []

    game.game_roles = [get_role_instance(name) for name in role_names]
    for role in game.game_roles:
        if not role:
            continue
        if role.name == "Godfather":
            role.investigation_immune = not game.game_settings.get("gf_investigate", True)
        elif role.name == "Serial Killer":
            role.investigation_immune = not game.game_settings.get("sk_investigate", False)
        else:
            role.investigation_immune = False

    logger.info("Game roles generated successfully.")
    return game.game_roles


async def assign_roles(game):
    """Assigns the generated roles to players randomly and sends DMs."""
    player_pool = list(game.players.values())
    role_pool = game.game_roles[:]

    logger.info(f"Securely shuffling {len(role_pool)} roles for {len(player_pool)} players.")
    for i in range(len(role_pool) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        role_pool[i], role_pool[j] = role_pool[j], role_pool[i]

    for player_obj, role in zip(player_pool, role_pool):
        player_obj.assign_role(role)
        if not player_obj.is_npc:
            await send_role_dm(game.bot, player_obj, role, game.guild)

    logger.info("Roles assigned to players successfully.")
    if game.game_settings.get("game_type") == "classic":
        await send_mafia_info_dm(game.bot, game.players)
        logger.info("Mafia team information has been distributed.")


async def prepare_game(game):
    """Prepares the game by adding NPCs, assigning roles, and starting the main loop."""
    logger.info("Sign-up phase ended. Preparing game...")
    game.game_settings["current_phase"] = "preparation"

    min_players = getattr(config, 'min_players', 5)
    while len(game.players) < min_players:
        game.add_npc()

    generate_game_roles(game)
    if not game.game_roles or any(role is None for role in game.game_roles):
        rules_channel = game.bot.get_channel(getattr(config, 'RULES_AND_ROLES_CHANNEL_ID', 0))
        if rules_channel:
            await rules_channel.send("CRITICAL ERROR: Failed to generate roles. Aborting game.")
        await game.reset()
        return

    await assign_roles(game)
    await update_player_discord_roles(game.bot, game.guild, game.players)

    status_message = await game.role_status_message()
    rules_channel = game.bot.get_channel(getattr(config, 'RULES_AND_ROLES_CHANNEL_ID', 0))
    if rules_channel:
        try:
            await rules_channel.send(status_message)
        except Exception as e:
            logger.error(f"Failed to send status message: {e}")

    if hasattr(game, 'game_loop') and hasattr(game.game_loop, 'start'):
        if not game.game_loop.is_running():
            game.game_loop.start()

    story_channel = game.bot.get_channel(getattr(config, 'STORIES_CHANNEL_ID', 0))
    if story_channel:
        await story_channel.send("\n\n--- **GAME STARTED** ---\n\n")

    game_state = {
        "game_id": game.game_settings.get('game_id'),
        "phase": game.game_settings.get('current_phase'),
        "number": game.game_settings.get('phase_number'),
        "living_players": [p for p in game.players.values() if p.is_alive],
        "is_prologue": False,
        "is_introduction": True,
        "is_game_over": False,
        "winner": None,
        "is_epilogue": False,
        "game_type": game.game_settings.get("game_type"),
        "story_type": game.game_settings.get("story_type")
    }
    if hasattr(game, 'narration_manager') and game.narration_manager:
        game.narration_manager.add_event('game_start', game_state=game_state)
    game.is_introduction = False

