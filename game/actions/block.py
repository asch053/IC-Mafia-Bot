# game/actions/block.py
import logging

logger = logging.getLogger('discord')


def handle_block(game, blocker_id: int, target_id: int, night_outcomes: dict):
    """
    Resolves a role block attempt.
    """
    blocker_action = night_outcomes.get(blocker_id)
    if blocker_action and blocker_action.get('status') == 'blocked':
        logger.info(f"Block attempt by {blocker_id} failed because they were also blocked.")
        return

    if blocker_action:
        night_outcomes[blocker_id]['status'] = 'successful'

    blocker = game.players.get(blocker_id)
    target = game.players.get(target_id)
    if not blocker or not target:
        logger.warning(f"Could not find player objects for blocker {blocker_id} or target {target_id}.")
        return

    # Record that target was blocked tonight
    game.blocked_players_this_night[target_id] = blocker_id

    target_action = night_outcomes.get(target_id)
    if target_action and target_action.get('status') is None:
        target_action['status'] = 'blocked'

        blocked_action_type = target_action.get('action') or 'action'
        action_target_id = target_action.get('target')
        action_target = game.players.get(action_target_id) if action_target_id else None

        is_br = str(game.game_settings.get("game_type", "")).lower() in ("battle_royale", "battle royale", "br")
        event_type = 'block_battle_royale' if is_br else 'block'

        # 1. Investigation blocks must NEVER show in story or summaries
        if blocked_action_type == 'investigate':
            logger.info(f"Action 'investigate' by {target.display_name} was blocked. Investigation blocks are never shown.")
            return

        # 2. Blocked heals should ONLY show when the heal would have stopped a kill
        if blocked_action_type == 'heal':
            if hasattr(game, 'pending_blocked_heals'):
                game.pending_blocked_heals.append({
                    'blocker': blocker,
                    'target': target,
                    'action_target': action_target,
                    'action_target_id': action_target_id,
                    'event_type': event_type
                })
                logger.info(f"Blocked heal by {target.display_name} on {action_target_id} queued for kill-check.")
                return
            else:
                # Standalone call fallback (e.g. tests calling handle_block directly):
                was_attacked = False
                if action_target_id and action_target_id in getattr(game, 'kill_attempts_on', {}):
                    if game.kill_attempts_on[action_target_id]:
                        was_attacked = True
                if not was_attacked and hasattr(game, 'night_actions'):
                    for pid, act in game.night_actions.items():
                        if act.get('type') in ('kill', 'kill_battle_royale', 'vigilante_kill') and act.get('target_id') == action_target_id:
                            if night_outcomes.get(pid, {}).get('status') != 'blocked':
                                was_attacked = True
                                break
                if was_attacked:
                    if hasattr(game, 'narration_manager') and game.narration_manager:
                        game.narration_manager.add_event(
                            event_type,
                            blocker=blocker,
                            target=target,
                            action_type='heal',
                            action_target=action_target
                        )
                    logger.info(f"Action 'heal' by {target.display_name} was blocked and patient was attacked. Event emitted.")
                else:
                    logger.info(f"Action 'heal' by {target.display_name} was blocked but patient was not attacked. No event emitted.")
                return

        # 3. Blocked kill and Blocked block are always shown
        if blocked_action_type in ('kill', 'block'):
            if hasattr(game, 'narration_manager') and game.narration_manager:
                game.narration_manager.add_event(
                    event_type,
                    blocker=blocker,
                    target=target,
                    action_type=blocked_action_type,
                    action_target=action_target
                )
            logger.info(f"Action '{blocked_action_type}' by {target.display_name} was blocked by {blocker.display_name}. Event emitted.")
            return

        logger.info(f"Action '{blocked_action_type}' by {target.display_name} was blocked. No story event emitted.")
    else:
        logger.info(f"Block on {target.display_name} by {blocker.display_name}: target had no active action. No story event emitted.")

