# game/engine/night.py
import asyncio
import logging
import random
from collections import defaultdict
import discord
from game import actions

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def record_night_action(game, actor, action_type: str, target_name: str):
    """Validates and records a night action from a player's DM."""
    if hasattr(actor, 'user'):
        player_id = actor.user.id
    elif hasattr(actor, 'id'):
        player_id = actor.id
    else:
        player_id = int(actor)

    player_obj = game.players.get(player_id)
    logger.info(f"Recording night action from player {player_id} for action '{action_type}' on '{target_name}'")

    if game.game_settings.get("current_phase") != "night":
        return "You can only perform actions during the night."
    if not player_obj or not player_obj.is_alive:
        return "You are not able to perform actions in the game."
    if not player_obj.can_perform_action(action_type):
        return f"Your role does not have the '{action_type}' ability."

    target_obj = game.get_player_by_name(target_name)
    if not target_obj:
        return f"Could not find a player named '{target_name}'."
    if not target_obj.is_alive:
        return f"{target_obj.display_name} is already dead."
    if action_type != 'heal' and target_obj.id == player_obj.id:
        return "You cannot target yourself with this ability."
    if action_type in ['heal', 'block'] and target_obj.id == player_obj.last_action_target_id:
        return "You cannot target the same person two nights in a row with this ability."

    game.night_actions[player_id] = {
        "type": action_type,
        "target_id": target_obj.id,
        'night_priority': getattr(player_obj.role, 'night_priority', 99) if player_obj.role else 99,
    }
    logger.info(f"Recorded night action: {player_obj.display_name} -> {action_type} on {target_obj.display_name}")
    return f"Your action (**{action_type}** on **{target_obj.display_name}**) has been recorded."


async def process_night_actions(game):
    """Processes all recorded night actions in priority order."""
    if not game.night_actions:
        if hasattr(game, 'narration_manager') and game.narration_manager:
            game.narration_manager.add_event('no_actions')
        return

    night_outcomes = {
        player_id: {'action': data['type'], 'target': data['target_id'], 'status': None}
        for player_id, data in game.night_actions.items()
    }
    game.heals_on_players.clear()
    logger.info("Processing night actions...")

    action_priority = {"block": 1, "heal": 2, "kill": 3, "investigate": 4}
    actions_by_priority = defaultdict(list)
    for player_id, data in game.night_actions.items():
        priority = action_priority.get(data['type'], 99)
        actions_by_priority[priority].append(player_id)

    final_processing_order = []
    for priority in sorted(actions_by_priority.keys()):
        priority_group = actions_by_priority[priority]
        random.shuffle(priority_group)
        sorted_group = sorted(priority_group, key=lambda pid: game.night_actions[pid].get('night_priority', 99))
        final_processing_order.extend(sorted_group)

    for player_id in final_processing_order:
        action_data = game.night_actions[player_id]
        handler = actions.ACTION_HANDLERS.get(action_data['type'])
        if handler:
            try:
                handler(game, player_id, action_data['target_id'], night_outcomes)
            except Exception as e:
                logger.error(f"Error processing action for player {player_id}: {e}", exc_info=True)


async def _resolve_night_deaths(game):
    """Compares kill attempts against heals to determine who dies."""
    logger.info("Resolving final night deaths...")
    phase_str = f"Night {game.game_settings.get('phase_number')}"

    for victim_id, killer_ids in list(game.kill_attempts_on.items()):
        victim_obj = game.players.get(victim_id)
        if not victim_obj:
            continue

        if victim_id in game.heals_on_players:
            healer_id = game.heals_on_players[victim_id][0]
            healer_obj = game.players.get(healer_id)
            primary_killer = game.players.get(killer_ids[0])
            event_type = 'save_battle_royale' if game.game_settings.get('game_type') == "battle_royale" else 'save'
            if hasattr(game, 'narration_manager') and game.narration_manager:
                game.narration_manager.add_event(event_type, healer=healer_obj, victim=victim_obj, killer=primary_killer)
            continue

        living_killer = None
        for k_id in killer_ids:
            potential_killer = game.players.get(k_id)
            if potential_killer and potential_killer.is_alive:
                living_killer = potential_killer
                break

        if living_killer:
            killer_role_name = living_killer.role.name if living_killer.role else 'Unknown'
            victim_obj.kill(phase_str, f"Killed by {killer_role_name}")
            game._handle_promotions(victim_obj)
            event_type = 'kill_battle_royale' if game.game_settings.get('game_type') == "battle_royale" else 'kill'
            if hasattr(game, 'narration_manager') and game.narration_manager:
                game.narration_manager.add_event(event_type, killer=living_killer, victim=victim_obj)
            logger.info(f"{victim_obj.display_name} was killed by {living_killer.display_name}.")
        else:
            primary_killer = game.players.get(killer_ids[0])
            event_type = 'kill_missed_battle_royale' if game.game_settings.get('game_type') == "battle_royale" else 'failed_kill_killer_dead'
            if hasattr(game, 'narration_manager') and game.narration_manager:
                game.narration_manager.add_event(event_type, killer=primary_killer, victim=victim_obj)
            logger.info(f"All kill attempts on {victim_obj.display_name} failed because all attackers are dead.")

    game.kill_attempts_on.clear()
    logger.info("Night deaths resolved.")


def _handle_promotions(game, dead_player):
    """Promotes a living Mafia member (Mob Goon first) to kill status upon Godfather death."""
    if dead_player.role and dead_player.role.abilities.get('kill') and dead_player.role.alignment == "Mafia":
        logger.info(f"Processing promotion because {dead_player.display_name} died.")
        mafioso_to_promote = None

        # Priority 1: Mob Goon
        for player in game.players.values():
            if player.is_alive and player.role and player.role.name == "Mob Goon":
                mafioso_to_promote = player
                break

        # Priority 2: Any surviving Mafia member
        if not mafioso_to_promote:
            for player in game.players.values():
                if player.is_alive and player.role and player.role.alignment == "Mafia":
                    mafioso_to_promote = player
                    break

        if mafioso_to_promote:
            if 'kill' not in mafioso_to_promote.role.abilities:
                logger.info(f"Promoting {mafioso_to_promote.display_name} to Godfather status.")
                mafioso_to_promote.role.abilities['kill'] = "Choose a player for the Mafia to kill."
                if hasattr(game, 'narration_manager') and game.narration_manager:
                    game.narration_manager.add_event('promotion', promoted_player=mafioso_to_promote)
                dm_message = (
                    "The Godfather is dead! You have been promoted to the head of the family.\n"
                    "You now have the ability to kill. Use `/kill player-name` in this DM."
                )
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(mafioso_to_promote.send_dm(game.bot, dm_message))
                except RuntimeError:
                    pass
                logger.info(f"PROMOTION: {mafioso_to_promote.display_name} now leads the Mafia.")

