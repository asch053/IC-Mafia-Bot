# game/engine/night.py
"""
Night Phase Action Engine and Priority Resolution Subsystem.

Responsibilities:
1. Validation & Recording (`record_night_action`):
   - Verifies active phase is 'night'.
   - Checks living status and role ability authorization.
   - Enforces targeting rules: prevents self-targeting (except Doctor heal) and consecutive targeting
     on the same target for Doctor heals and Roleblocker blocks.
2. NPC Automation (`process_npc_night_actions`):
   - Automatically queues smart random actions for living virtual NPC players before resolution.
   - Mafia bots avoid targeting fellow Mafia members.
3. Priority-Based Execution (`process_night_actions`):
   - Executes actions in strict order: Block (1) -> Heal (2) -> Kill (3) -> Investigate (4).
   - Resolves roleblocks first, preventing blocked players from performing subsequent actions.
4. Death Resolution (`_resolve_night_deaths`):
   - Cross-references kill attempts against heals. Healed targets survive and generate save events.
   - Unprotected targets are killed and emit kill narration events.
5. Mafia Succession (`_handle_promotions`):
   - Automatically promotes a surviving Mob Goon (or other Mafia member) to Godfather kill status
     upon Godfather death.
"""

import asyncio
import logging
import random
from collections import defaultdict
import discord
from game import actions

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def record_night_action(game, actor, action_type: str, target_name: str):
    """
    Validates and queues a night action submitted by a player via DM.

    Args:
        game (Game): The active game engine.
        actor: Player instance, Discord user, or integer ID of the player acting.
        action_type (str): Type of ability being used ('kill', 'heal', 'block', 'investigate').
        target_name (str): Server display name of the intended target.

    Returns:
        str: Confirmation message if successfully queued, or an explanatory error string.
    """
    # 1. Resolve actor player ID safely across mock, Discord user, or Player object types
    if isinstance(actor, int):
        player_id = actor
    elif hasattr(actor, 'user') and hasattr(actor.user, 'id'):
        player_id = actor.user.id
    elif hasattr(actor, 'id'):
        player_id = actor.id
    else:
        player_id = int(actor)

    player_obj = game.players.get(player_id)
    logger.info(f"Recording night action from player {player_id} for action '{action_type}' on '{target_name}'")

    # 2. Phase and living validation
    if game.game_settings.get("current_phase") != "night":
        return "You can only perform actions during the night."
    if not player_obj or not player_obj.is_alive:
        return "You are not able to perform actions in the game."
    if not player_obj.can_perform_action(action_type):
        return f"Your role does not have the '{action_type}' ability."

    # 3. Target existence and living validation
    target_obj = game.get_player_by_name(target_name)
    if not target_obj:
        return f"Could not find a player named '{target_name}'."
    if not target_obj.is_alive:
        return f"{target_obj.display_name} is already dead."

    # 4. Self-targeting restrictions (only Doctors may target themselves)
    if action_type != 'heal' and target_obj.id == player_obj.id:
        return "You cannot target yourself with this ability."

    # 5. Consecutive targeting restriction for Heals and Blocks
    if action_type in ['heal', 'block'] and target_obj.id == player_obj.last_action_target_id:
        return "You cannot target the same person two nights in a row with this ability."

    # 6. Queue the validated night action
    game.night_actions[player_id] = {
        "type": action_type,
        "target_id": target_obj.id,
        'night_priority': getattr(player_obj.role, 'night_priority', 99) if player_obj.role else 99,
    }
    logger.info(f"Recorded night action: {player_obj.display_name} -> {action_type} on {target_obj.display_name}")
    return f"Your action (**{action_type}** on **{target_obj.display_name}**) has been recorded."


async def process_npc_night_actions(game):
    """
    Automatically selects and records night actions for living NPCs who have an active ability.

    NPC Strategy Rules:
    - Kill (Godfather / Serial Killer): Chooses random living player. Mafia avoids fellow Mafia members.
    - Heal (Doctor): Chooses random living player, avoiding the target healed on the previous night.
    - Block (Roleblocker): Chooses random non-self living player, avoiding consecutive targets. Mafia avoids allies.
    - Investigate (Cop): Chooses random non-self living player.
    """
    living_npcs = [p for p in game.players.values() if p.is_npc and p.is_alive]
    if not living_npcs:
        return

    logger.info(f"Processing automated night actions for {len(living_npcs)} living NPCs...")

    for npc in living_npcs:
        # Skip NPC if an action was already queued manually or earlier in the cycle
        if npc.id in game.night_actions:
            continue

        if not npc.role or not npc.role.abilities:
            continue

        abilities = npc.role.abilities
        action_type = None
        if "kill" in abilities:
            action_type = "kill"
        elif "heal" in abilities:
            action_type = "heal"
        elif "block" in abilities:
            action_type = "block"
        elif "investigate" in abilities:
            action_type = "investigate"

        if not action_type:
            continue

        target_obj = None

        # Strategy: Kill
        if action_type == "kill":
            potential_targets = [p for p in game.players.values() if p.is_alive and p.id != npc.id]
            if not potential_targets:
                continue
            if getattr(npc.role, 'alignment', '') == "Mafia":
                non_mafia = [p for p in potential_targets if getattr(p.role, 'alignment', '') != "Mafia"]
                target_obj = random.choice(non_mafia) if non_mafia else random.choice(potential_targets)
            else:
                target_obj = random.choice(potential_targets)

        # Strategy: Heal
        elif action_type == "heal":
            potential_targets = [p for p in game.players.values() if p.is_alive and p.id != npc.last_action_target_id]
            if not potential_targets:
                potential_targets = [p for p in game.players.values() if p.is_alive]
            if potential_targets:
                target_obj = random.choice(potential_targets)

        # Strategy: Block
        elif action_type == "block":
            potential_targets = [
                p for p in game.players.values()
                if p.is_alive and p.id != npc.id and p.id != npc.last_action_target_id
            ]
            if not potential_targets:
                potential_targets = [p for p in game.players.values() if p.is_alive and p.id != npc.id]
            if potential_targets:
                if getattr(npc.role, 'alignment', '') == "Mafia":
                    non_mafia = [p for p in potential_targets if getattr(p.role, 'alignment', '') != "Mafia"]
                    target_obj = random.choice(non_mafia) if non_mafia else random.choice(potential_targets)
                else:
                    target_obj = random.choice(potential_targets)

        # Strategy: Investigate
        elif action_type == "investigate":
            potential_targets = [p for p in game.players.values() if p.is_alive and p.id != npc.id]
            if potential_targets:
                target_obj = random.choice(potential_targets)

        # Queue the NPC's selected action
        if target_obj:
            game.night_actions[npc.id] = {
                "type": action_type,
                "target_id": target_obj.id,
                "night_priority": getattr(npc.role, 'night_priority', 99)
            }
            logger.info(
                f"NPC Night Action: {npc.display_name} ({npc.role.name}) queued '{action_type}' on {target_obj.display_name}"
            )


async def process_night_actions(game):
    """
    Executes all recorded night actions in canonical priority order.

    Resolution Priority Tiers:
    - Tier 1: Roleblock (`block`) - disables target's action before they can act.
    - Tier 2: Heal (`heal`) - registers defensive wards for victim protection.
    - Tier 3: Kill (`kill`) - registers lethal attempts against targets.
    - Tier 4: Investigate (`investigate`) - queries alignment of targets.
    """
    # 1. Automate living NPCs first
    await process_npc_night_actions(game)

    if not game.night_actions:
        if hasattr(game, 'narration_manager') and game.narration_manager:
            game.narration_manager.add_event('no_actions')
        return

    # Track outcomes for each acting player
    night_outcomes = {
        player_id: {'action': data['type'], 'target': data['target_id'], 'status': None}
        for player_id, data in game.night_actions.items()
    }
    game.heals_on_players.clear()
    game.blocked_players_this_night.clear()
    game.pending_blocked_heals = []
    logger.info("Processing night actions...")

    # Group actions into priority bins
    action_priority = {"block": 1, "heal": 2, "kill": 3, "investigate": 4}
    actions_by_priority = defaultdict(list)
    for player_id, data in game.night_actions.items():
        priority = action_priority.get(data['type'], 99)
        actions_by_priority[priority].append(player_id)

    # 1. Resolve Priority 1 (Block) with dependency ordering & cycle resolution
    block_pids = actions_by_priority.get(1, [])
    if block_pids:
        _resolve_block_actions(game, block_pids, night_outcomes)

    # 2. Sort and shuffle remaining priority tiers (heal, kill, investigate, etc.)
    final_processing_order = []
    for priority in sorted(actions_by_priority.keys()):
        if priority == 1:
            continue
        priority_group = actions_by_priority[priority]
        random.shuffle(priority_group)
        sorted_group = sorted(priority_group, key=lambda pid: game.night_actions[pid].get('night_priority', 99))
        final_processing_order.extend(sorted_group)

    # Dispatch to dedicated action handlers in game/actions/
    for player_id in final_processing_order:
        action_data = game.night_actions[player_id]
        handler = actions.ACTION_HANDLERS.get(action_data['type'])
        if handler:
            try:
                handler(game, player_id, action_data['target_id'], night_outcomes)
            except Exception as e:
                logger.error(f"Error processing action for player {player_id}: {e}", exc_info=True)

    # 3. Resolve pending blocked heals: ONLY emit event if the heal would have stopped a kill
    for bh in getattr(game, 'pending_blocked_heals', []):
        act_tgt_id = bh['action_target_id']
        was_attacked = False
        if act_tgt_id and act_tgt_id in getattr(game, 'kill_attempts_on', {}):
            if game.kill_attempts_on[act_tgt_id]:
                was_attacked = True
        if not was_attacked:
            for pid, act in game.night_actions.items():
                if act.get('type') in ('kill', 'kill_battle_royale', 'vigilante_kill') and act.get('target_id') == act_tgt_id:
                    if night_outcomes.get(pid, {}).get('status') != 'blocked':
                        was_attacked = True
                        break
        if was_attacked:
            if hasattr(game, 'narration_manager') and game.narration_manager:
                game.narration_manager.add_event(
                    bh['event_type'],
                    blocker=bh['blocker'],
                    target=bh['target'],
                    action_type='heal',
                    action_target=bh['action_target']
                )
            logger.info(f"Blocked heal by {bh['target'].display_name}: patient was attacked. Emitted block event.")
        else:
            logger.info(f"Blocked heal by {bh['target'].display_name}: patient was NOT attacked. No story event emitted.")


def _resolve_block_actions(game, blocker_pids: list, night_outcomes: dict):
    """
    Resolves roleblock actions with proper dependency ordering and cycle handling.
    - Blockers with 0 active blockers targeting them resolve first.
    - If a blocker is blocked, their queued block is cancelled and cannot block their target.
    - Mutual blocks or cycles are resolved simultaneously so all participants are blocked.
    """
    remaining_blockers = set(blocker_pids)

    while remaining_blockers:
        # 1. Any remaining blocker that is already blocked cannot act
        already_blocked = [
            b for b in remaining_blockers
            if night_outcomes.get(b, {}).get('status') == 'blocked'
        ]
        if already_blocked:
            for b in already_blocked:
                remaining_blockers.remove(b)
                logger.info(f"Blocker {b} was already blocked and cannot perform their action.")
            continue

        # 2. Find blockers with 0 unblocked blockers targeting them
        zero_incoming = [
            b for b in remaining_blockers
            if not any(
                game.night_actions.get(other, {}).get('target_id') == b
                for other in remaining_blockers
                if other != b
            )
        ]

        if zero_incoming:
            # Sort by night_priority if set, then shuffle for fairness
            random.shuffle(zero_incoming)
            zero_incoming.sort(key=lambda pid: game.night_actions[pid].get('night_priority', 99))

            acting_pid = zero_incoming[0]
            remaining_blockers.remove(acting_pid)

            action_data = game.night_actions[acting_pid]
            handler = actions.ACTION_HANDLERS.get('block')
            if handler:
                try:
                    handler(game, acting_pid, action_data['target_id'], night_outcomes)
                except Exception as e:
                    logger.error(f"Error processing block for player {acting_pid}: {e}", exc_info=True)
        else:
            # Cycle detected (e.g. A blocks B, B blocks A)
            # All remaining blockers in this cycle mutually block each other
            logger.info(f"Mutual block cycle detected among blockers: {remaining_blockers}")
            is_br = str(game.game_settings.get("game_type", "")).lower() in ("battle_royale", "battle royale", "br")
            event_type = 'block_battle_royale' if is_br else 'block'

            for b in list(remaining_blockers):
                target_id = game.night_actions[b]['target_id']
                night_outcomes[b]['status'] = 'blocked'
                game.blocked_players_this_night[b] = target_id

                blocker_obj = game.players.get(b)
                target_obj = game.players.get(target_id)
                if blocker_obj and target_obj and hasattr(game, 'narration_manager') and game.narration_manager:
                    game.narration_manager.add_event(
                        event_type,
                        blocker=target_obj,
                        target=blocker_obj,
                        action_type='block',
                        action_target=target_obj
                    )
                logger.info(f"Mutual block: {blocker_obj.display_name if blocker_obj else b} blocked by target.")

            remaining_blockers.clear()


async def _resolve_night_deaths(game):
    """
    Compares registered kill attempts against active heals to determine final deaths.

    If a target was healed by a Doctor, the kill is prevented and a save event is emitted.
    If the target was unprotected, they are marked dead, their death info recorded,
    promotions checked, and kill events dispatched.
    """
    logger.info("Resolving final night deaths...")
    phase_str = f"Night {game.game_settings.get('phase_number')}"

    for victim_id, killer_ids in list(game.kill_attempts_on.items()):
        victim_obj = game.players.get(victim_id)
        if not victim_obj:
            continue

        # Case 1: Target was healed by a Doctor
        if victim_id in game.heals_on_players:
            healer_id = game.heals_on_players[victim_id][0]
            healer_obj = game.players.get(healer_id)
            primary_killer = game.players.get(killer_ids[0])
            event_type = 'save_battle_royale' if game.game_settings.get('game_type') == "battle_royale" else 'save'
            if hasattr(game, 'narration_manager') and game.narration_manager:
                game.narration_manager.add_event(event_type, healer=healer_obj, victim=victim_obj, killer=primary_killer)
            continue

        # Case 2: Identify all eligible living killers who made the strike
        living_killers = []
        for k_id in killer_ids:
            potential_killer = game.players.get(k_id)
            if potential_killer and potential_killer.is_alive:
                living_killers.append(potential_killer)

        if living_killers:
            is_br = str(game.game_settings.get("game_type", "")).lower() in ("battle_royale", "battle royale", "br")

            # Format killer names string (used for Battle Royale summary)
            killer_names = [k.display_name for k in living_killers]
            if len(killer_names) == 1:
                killer_names_str = killer_names[0]
            elif len(killer_names) == 2:
                killer_names_str = f"{killer_names[0]} and {killer_names[1]}"
            else:
                killer_names_str = ", ".join(killer_names[:-1]) + f", and {killer_names[-1]}"

            # Format killer roles string (used for Classic Mafia / non-BR to preserve anonymity)
            unique_roles = list(dict.fromkeys(k.role.name if k.role else 'Unknown' for k in living_killers))
            if len(unique_roles) == 1:
                killer_roles_str = unique_roles[0]
            elif len(unique_roles) == 2:
                killer_roles_str = f"{unique_roles[0]} and {unique_roles[1]}"
            else:
                killer_roles_str = ", ".join(unique_roles[:-1]) + f", and {unique_roles[-1]}"

            if is_br:
                death_cause = f"Killed by {killer_names_str}"
            else:
                death_cause = f"Killed by {killer_roles_str}"

            victim_obj.kill(phase_str, death_cause)
            victim_obj.death_info['killers'] = killer_names
            victim_obj.death_info['killer_roles'] = [k.role.name if k.role else 'Unknown' for k in living_killers]
            game._handle_promotions(victim_obj)

            event_type = 'kill_battle_royale' if is_br else 'kill'
            if hasattr(game, 'narration_manager') and game.narration_manager:
                for killer in living_killers:
                    game.narration_manager.add_event(
                        event_type,
                        killer=killer,
                        victim=victim_obj,
                        killers=living_killers,
                        attack_count=len(living_killers)
                    )
            logger.info(f"{victim_obj.display_name} was killed by {death_cause} ({len(living_killers)} attacker(s)).")
        else:
            # All attackers died earlier this night; kill failed
            primary_killer = game.players.get(killer_ids[0])
            is_br = str(game.game_settings.get("game_type", "")).lower() in ("battle_royale", "battle royale", "br")
            event_type = 'kill_missed_battle_royale' if is_br else 'failed_kill_killer_dead'
            if hasattr(game, 'narration_manager') and game.narration_manager:
                game.narration_manager.add_event(event_type, killer=primary_killer, victim=victim_obj)
            logger.info(f"All kill attempts on {victim_obj.display_name} failed because all attackers are dead.")

    game.kill_attempts_on.clear()
    logger.info("Night deaths resolved.")


def _handle_promotions(game, dead_player):
    """
    Handles automatic leadership promotion when a Mafia killer (Godfather) is eliminated.

    Promotion Chain:
    1. First living Mob Goon is promoted to lead the Mafia and given the 'kill' ability.
    2. If no Mob Goon survives, any surviving Mafia member (e.g. Mob Role Blocker) is promoted.
    3. Sends a private DM informing the promoted player of their new leadership and `/kill` power.
    """
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
