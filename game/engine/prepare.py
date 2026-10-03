# game/engine/prepare.py
"""
Game Preparation and Role Assignment Subsystem.

Responsibilities:
1. Validates player counts against lobby minimums (auto-filling with virtual NPCs if required).
2. Generates balanced role rosters based on user game settings (mafia ratio, cop/doc thresholds).
3. Applies thematic role skins dynamically based on the active `story_type`.
4. Shuffles roles securely using CSPRNG (`secrets.randbelow`) and assigns them to participants.
5. Dispatches role briefing DMs to players and reveals Mafia teammate rosters privately.
6. Synchronizes Discord guild roles (Living role assigned, Spectator removed).
7. Initializes the background game state loop.
"""

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
    """
    Generates a balanced list of GameRole objects based on player count and gamestart settings.

    Steps:
    1. Check minimum player threshold; convert to Battle Royale if insufficient for Classic.
    2. Invoke setup_generator to calculate faction proportions.
    3. Instantiate each role with the active theme's visual skin.
    4. Configure custom night-immunity and investigation-immunity toggles per gamestart rules.

    Args:
        game (Game): The current game engine instance.

    Returns:
        list[GameRole]: List of instantiated, themed GameRole objects.
    """
    logger.info("Generating dynamic role list...")
    game_type = game.game_settings.get('game_type', 'classic')
    player_count = len(game.players)

    # 1. Enforce minimum player requirements for Classic mode
    min_players = getattr(config, 'min_players', 5)
    if player_count < min_players:
        logger.warning(
            f"Cannot generate {game_type} roles for {player_count} players. Minimum is {min_players}.\n"
            f"Converting to Battle Royale mode."
        )
        rules_chan = game.bot.get_channel(getattr(config, 'RULES_AND_ROLES_CHANNEL_ID', 0))
        if rules_chan:
            try:
                import asyncio
                loop = asyncio.get_running_loop()
                loop.create_task(
                    rules_chan.send(
                        f"Error: Could not generate a 'Classic' game for {player_count} players. "
                        f"Minimum is {min_players}.\n Converting to Battle Royale mode."
                    )
                )
            except RuntimeError:
                pass
        game.game_settings['game_type'] = "battle_royale"

    # 2. Generate canonical role names via balancing matrix
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

    # 3. Instantiate GameRoles with the active narrative theme applied
    active_theme = game.game_settings.get('story_type', 'Classic Mafia')
    game.game_roles = [get_role_instance(name, theme=active_theme) for name in role_names]

    # 4. Apply custom gamestart immunity toggles (GF & SK night kill / investigation immunity)
    for role in game.game_roles:
        if not role:
            continue
        if role.name == "Godfather":
            role.investigation_immune = not game.game_settings.get("gf_investigate", True)
            role.is_night_immune = game.game_settings.get("gf_night_immune", True)
        elif role.name == "Serial Killer":
            role.investigation_immune = not game.game_settings.get("sk_investigate", False)
            role.is_night_immune = game.game_settings.get("sk_night_immune", True)
        else:
            role.investigation_immune = False

    logger.info("Game roles generated successfully.")
    return game.game_roles


async def assign_roles(game):
    """
    Securely shuffles the generated roles and distributes them to players.

    Uses Fisher-Yates shuffle powered by secrets.randbelow to ensure cryptographically
    unbiased role distribution. Sends private DMs to real players with their role briefings,
    and dispatches a dedicated Mafia teammate reveal message in Classic games.
    """
    player_pool = list(game.players.values())
    role_pool = game.game_roles[:]

    # 1. Cryptographically secure Fisher-Yates shuffle
    logger.info(f"Securely shuffling {len(role_pool)} roles for {len(player_pool)} players.")
    for i in range(len(role_pool) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        role_pool[i], role_pool[j] = role_pool[j], role_pool[i]

    # 2. Pair each player with a shuffled role and dispatch private DMs
    for player_obj, role in zip(player_pool, role_pool):
        player_obj.assign_role(role)
        if not player_obj.is_npc:
            await send_role_dm(game.bot, player_obj, role, game.guild)

    logger.info("Roles assigned to players successfully.")

    # 3. In Classic Mafia, reveal teammate identities to all living Mafia members
    if game.game_settings.get("game_type") == "classic":
        await send_mafia_info_dm(game.bot, game.players)
        logger.info("Mafia team information has been distributed.")


async def prepare_game(game):
    """
    Main preparation orchestrator invoked when sign-ups close.
    
    Orchestration Sequence:
    1. Backfills lobby with NPCs up to config.min_players if needed.
    2. Calls generate_game_roles() and assign_roles().
    3. Updates Discord member roles (assigns Living Player role).
    4. Posts role breakdown summary to the rules channel.
    5. Starts the periodic game_loop task.
    6. Emits the 'game_start' introduction narration event.
    """
    logger.info("Sign-up phase ended. Preparing game...")
    game.game_settings["current_phase"] = "preparation"

    try:
        # Step 1: Backfill lobby with NPCs if below minimum required players
        min_players = getattr(config, 'min_players', 5)
        while len(game.players) < min_players:
            game.add_npc()

        # Step 2: Generate and balance roles
        generate_game_roles(game)
        if not game.game_roles or any(role is None for role in game.game_roles):
            logger.critical(f"Could not generate roles for {len(game.players)} players. Aborting game preparation.")
            rules_channel = game.bot.get_channel(getattr(config, 'RULES_AND_ROLES_CHANNEL_ID', 0))
            if rules_channel:
                await rules_channel.send("CRITICAL ERROR: Failed to generate roles. Aborting game.")
            await game.reset()
            return

        # Step 3: Assign roles and notify players
        await assign_roles(game)
        await update_player_discord_roles(game.bot, game.guild, game.players)

        # Step 4: Publish public role list to rules channel
        status_message = await game.role_status_message()
        rules_channel = game.bot.get_channel(getattr(config, 'RULES_AND_ROLES_CHANNEL_ID', 0))
        if rules_channel:
            try:
                await rules_channel.send(status_message)
            except Exception as e:
                logger.error(f"Failed to send status message: {e}")

        # Step 5: Start the asynchronous game loop task
        if hasattr(game, 'game_loop') and hasattr(game.game_loop, 'start'):
            if not game.game_loop.is_running():
                game.game_loop.start()

        # Step 6: Post game start announcement to the stories channel
        story_channel = game.bot.get_channel(getattr(config, 'STORIES_CHANNEL_ID', 0))
        if story_channel:
            await story_channel.send("\n\n--- **GAME STARTED** ---\n\n")

        # Step 7: Queue the introductory narrative chapter
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

    except Exception as e:
        logger.critical(f"Game preparation encountered a critical error: {e}", exc_info=True)
        await game.reset()
