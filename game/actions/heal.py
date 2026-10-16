# game/actions/heal.py
import logging

logger = logging.getLogger('discord')


def handle_heal(game, healer_id: int, target_id: int, night_outcomes: dict):
    """Records a heal attempt on a target."""
    healer_action = night_outcomes.get(healer_id)
    is_blocked = False
    if healer_action and healer_action.get('status') == 'blocked':
        is_blocked = True
    if healer_id in getattr(game, 'blocked_players_this_night', {}):
        is_blocked = True
    if str(healer_id) in [str(k) for k in getattr(game, 'blocked_players_this_night', {}).keys()]:
        is_blocked = True

    if is_blocked:
        logger.info(f"Heal attempt by {healer_id} failed because they were blocked.")
        return

    if healer_action:
        night_outcomes[healer_id]['status'] = 'successful'

    healer = game.players.get(healer_id)
    target = game.players.get(target_id)
    if not healer or not target:
        return

    game.heals_on_players.setdefault(target_id, []).append(healer_id)
    logger.info(f"{healer.display_name} successfully healed {target.display_name}.")

