# game/actions.py
import logging
import asyncio

logger = logging.getLogger('discord')

def handle_block(game, blocker_id, target_id, night_outcomes):
    """
    If the target has an action, marks it as 'blocked' and creates
    the narration event for the story.
    """
    # Check if the person we are blocking actually submitted an action.
    if target_id in night_outcomes:
        # The block is successful and meaningful.
        night_outcomes[target_id]['status'] = 'blocked'
        
        # Now, create the story event immediately with the correct players.
        blocker = game.players.get(blocker_id)
        target = game.players.get(target_id)
        game.narration_manager.add_event('block', blocker=blocker, target=target)
        
        logger.info(f"Action by {target.display_name} was blocked by {blocker.display_name}.")

def handle_heal(game, healer_id, target_id, night_outcomes):
    """
    If the healer was not blocked, adds the target to the protected set for this night.
    """
    if night_outcomes[healer_id]['status'] == 'blocked':
        logger.info(f"Heal by {healer_id} was blocked.")
        return

    game.protected_players_this_night.add(target_id)
    logger.info(f"Player {target_id} was marked as protected.")

def handle_kill(game, killer_id, target_id, night_outcomes):
    """
    Checks for immunity, blocks, or saves, then updates the kill action's status.
    """
    if night_outcomes[killer_id]['status'] == 'blocked':
        return

    killer = game.players.get(killer_id)
    target = game.players.get(target_id)
    if not killer or not target: return

    if getattr(target.role, 'is_night_immune', False):
        night_outcomes[killer_id]['status'] = 'immune'
        game.narration_manager.add_event('immune_kill', killer=killer, victim=target)
        logger.info(f"Kill by {killer_id} on {target_id} failed due to night immunity.")
        return

    if target_id in game.protected_players_this_night:
        night_outcomes[killer_id]['status'] = 'saved'
        game.narration_manager.add_event('save', victim=target, killer=killer)
        logger.info(f"Kill by {killer_id} on {target_id} was marked as saved.")
    else:
        phase_str = f"Night {game.game_settings['phase_number']}"
        target.kill(phase_str, f"Killed by the {killer.role.alignment}")
        logger.info(f"Kill by {killer_id} on {target_id} was successful.")

def handle_investigation(game, investigator_id, target_id, night_outcomes):
    """
    If not blocked, determines investigation result and sends it to the investigator.
    """
    if night_outcomes[investigator_id]['status'] == 'blocked':
        return
   
    investigator = game.players.get(investigator_id)
    target = game.players.get(target_id)
    if not investigator or not target: return
    if investigator.alive is False:
        logger.info(f"Investigation by {investigator_id} did not happen because the investigator is dead.")
        return
    # --- Determine the result of the investigation ---
    role_name_result = target.role.name if target.role else "Unknown"
    short_desc_result = target.role.short_description if target.role else "No details."
    if target.role and target.role.investigation_result:
        result_data = target.role.investigation_result
        try:
            role_name_result, short_desc_result = list(result_data.items())[0]
        except (IndexError, ValueError):
            logger.warning(f"Malformed investigation_result for role {target.role.name}")
            pass
    result_message = (
        f"Your investigation of **{target.display_name}** reveals they are **{role_name_result}**."
        f"\n> *{short_desc_result}*"
    )

    # Send the message via DM to the investigator in the background
    async def send_investigation_dm():
        try:
            user = await game.bot.fetch_user(investigator.id)
            await user.send(result_message)
            logger.info(f"Sent investigation result to {investigator.display_name}.")
        except Exception as e:
            logger.error(f"Failed to send investigation DM to {investigator.display_name}: {e}")

    # Create a task to avoid blocking the game loop
    game.bot.loop.create_task(send_investigation_dm())

# This dictionary maps the action type string to the correct handler function.
ACTION_HANDLERS = {
    "kill": handle_kill,
    "heal": handle_heal,
    "block": handle_block,
    "investigate": handle_investigation,
}
