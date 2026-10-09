# game/actions/kill.py
import logging

logger = logging.getLogger('discord')


def handle_kill(game, killer_id: int, victim_id: int, night_outcomes: dict):
    """Records a kill attempt on a victim."""
    killer = game.players.get(killer_id)
    victim = game.players.get(victim_id)
    if not killer or not victim:
        return

    killer_action = night_outcomes.get(killer_id)
    if killer_action and killer_action.get('status') == 'blocked':
        logger.info(f"Kill attempt by {killer.display_name} failed because they were blocked.")
        return

    if killer_action:
        night_outcomes[killer_id]['status'] = 'successful'

    if victim.role and victim.role.is_night_immune:
        game.narration_manager.add_event('kill_immune', killer=killer, victim=victim)
        logger.info(f"Kill by {killer.display_name} on {victim.display_name} failed due to immunity.")
        return

    game.kill_attempts_on.setdefault(victim_id, []).append(killer_id)
    logger.info(f"{killer.display_name} successfully attempted to kill {victim.display_name}.")

