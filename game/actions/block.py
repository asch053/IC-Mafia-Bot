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
        event_type = 'block_missed_royale' if game.game_settings.get('game_type') == "battle_royale" else 'block_missed'
        game.narration_manager.add_event(event_type, blocker=game.players.get(blocker_id), target=game.players.get(target_id))
        return

    if blocker_action:
        night_outcomes[blocker_id]['status'] = 'successful'

    blocker = game.players.get(blocker_id)
    target = game.players.get(target_id)
    if not blocker or not target:
        logger.warning(f"Could not find player objects for blocker {blocker_id} or target {target_id}.")
        return

    target_action = night_outcomes.get(target_id)
    if target_action and target_action.get('status') is None:
        night_outcomes[target_id]['status'] = 'blocked'
        game.blocked_players_this_night[target_id] = blocker_id

        event_type = 'block_battle_royale' if game.game_settings.get('game_type') == "battle_royale" else 'block'
        game.narration_manager.add_event(event_type, blocker=blocker, target=target)
        logger.info(f"Action by {target.display_name} was blocked by {blocker.display_name}.")
    else:
        event_type = 'block_missed_royale' if game.game_settings.get('game_type') == "battle_royale" else 'block_missed'
        game.narration_manager.add_event(event_type, blocker=blocker, target=target)
        logger.info(f"Block by {blocker.display_name} on {target.display_name} missed as the target's action had already resolved.")

