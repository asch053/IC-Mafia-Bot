# game/actions.py
import logging
import asyncio

logger = logging.getLogger('discord')

def handle_block(game, blocker_id, target_id, night_outcomes):
    """
    Blocks a target's action if it is still pending. If the action
    was already resolved (blocked, or succeeded), it triggers a 'miss' event.
    """
    # --- Step 1: Check if the blocker's own action was cancelled ---
    # This is the first and most important check. If the blocker was
    # themselves blocked, their action should have no effect on anyone.
    blocker_action = night_outcomes.get(blocker_id)
    if blocker_action and blocker_action.get('status') == 'blocked':
        logger.info(f"Block attempt by {blocker_id} failed because they were also blocked.")
        return

    # --- Step 2: Get player objects for the narration ---
    # We will need these objects for any potential story event.
    blocker = game.players.get(blocker_id)
    target = game.players.get(target_id)
    if not blocker or not target:
        logger.warning(f"Could not find player objects for blocker {blocker_id} or target {target_id}.")
        return

    # --- Step 3: Check the target's action status to decide the outcome ---
    target_action = night_outcomes.get(target_id)

    # A block is successful ONLY if the target has an action AND that action's
    # status is `None`, which indicates it hasn't been processed yet.
    if target_action and target_action.get('status') is None:
        # --- SUCCESSFUL BLOCK ---
        night_outcomes[target_id]['status'] = 'blocked'  # Mark the target's action as resolved.
        game.blocked_players_this_night[target_id] = blocker_id
        
        # Determine the correct narration event based on game type.
        event_type = 'battle_royale_block' if game.game_settings.get('game_type') == "battle_royale" else 'block'
        game.narration_manager.add_event(event_type, blocker=blocker, target=target)
        
        logger.info(f"Action by {target.display_name} was blocked by {blocker.display_name}.")
    else:
        # --- MISSED BLOCK ---
        # This branch is taken if the target either had no action, or their
        # action was already processed (e.g., succeeded or was blocked by someone else).
        event_type = 'block_missed_royale' if game.game_settings.get('game_type') == "battle_royale" else 'block_missed'
        game.narration_manager.add_event(event_type, blocker=blocker, target=target)
        
        logger.info(f"Block by {blocker.display_name} on {target.display_name} missed as the target's action had already resolved.")


def handle_heal(game, healer_id, target_id, night_outcomes):
    """
    Records a heal attempt on a target. The heal fails only if the 
    healer themselves was blocked.
    """
    # --- Step 1: Check if the healer's action was blocked ---
    healer_action = night_outcomes.get(healer_id)
    if healer_action and healer_action.get('status') == 'blocked':
        logger.info(f"Heal attempt by {healer_id} failed because they were blocked.")
        return

    # --- Step 2: Mark the action as resolved and record the heal ---
    # If the healer wasn't blocked, their action is considered successful.
    if healer_action:
        night_outcomes[healer_id]['status'] = 'successful'
    
    healer = game.players.get(healer_id)
    target = game.players.get(target_id)
    if not healer or not target: return
    
    # We record the heal attempt. The resolution engine at the end of the night
    # will check this list to see if any kills were prevented.
    game.heals_on_players.setdefault(target_id, []).append(healer_id)

    # Add a narration event for the healer's personal story.
    game.narration_manager.add_event('heal', healer=healer, target=target)
    logger.info(f"{healer.display_name} successfully healed {target.display_name}.")


def handle_kill(game, killer_id, victim_id, night_outcomes):
    """
    Records a kill attempt on a victim. The kill can fail if the killer 
    is blocked or if the victim has night immunity.
    """
    # --- Step 1: Get Player Objects ---
    killer = game.players.get(killer_id)
    victim = game.players.get(victim_id)
    if not killer or not victim: return

    # --- Step 2: Check if the killer's own action was blocked ---
    killer_action = night_outcomes.get(killer_id)
    if killer_action and killer_action.get('status') == 'blocked':
        game.narration_manager.add_event('kill_blocked', killer=killer, target=victim)
        logger.info(f"Kill attempt by {killer.display_name} failed because they were blocked.")
        return

    # --- Step 3: Mark the killer's action as used ---
    # The action is consumed regardless of whether the target is immune.
    if killer_action:
        night_outcomes[killer_id]['status'] = 'successful'

    # --- Step 4: Check if the victim has night immunity ---
    if victim.role and victim.role.is_night_immune:
        # The event name and keyword arguments must match the test expectations.
        game.narration_manager.add_event('kill_immune', killer=killer, target=victim)
        logger.info(f"Kill by {killer.display_name} on {victim.display_name} failed due to immunity.")
        return
        
    # --- Step 5: If not blocked or immune, log the kill attempt ---
    # This list will be checked against the heals list during final resolution.
    game.kill_attempts_on.setdefault(victim_id, []).append(killer_id)
    logger.info(f"{killer.display_name} successfully attempted to kill {victim.display_name}.")


def handle_investigation(game, investigator_id, target_id, night_outcomes):
    """
    If not blocked, determines investigation result, marks the action as
    successful, and sends the result to the investigator.
    """
    # --- Step 1: Check if the investigator's action was blocked ---
    investigator_action = night_outcomes.get(investigator_id)
    if investigator_action and investigator_action.get('status') == 'blocked':
        logger.info(f"Investigation by {investigator_id} failed because they were blocked.")
        return

    # --- Step 2: Mark the action as resolved ---
    # This is critical for consistency with other action handlers.
    if investigator_action:
        night_outcomes[investigator_id]['status'] = 'successful'

    # --- Step 3: Perform the investigation logic ---
    investigator = game.players.get(investigator_id)
    target = game.players.get(target_id)
    if not investigator or not target: return
    
    if not investigator.is_alive:
        logger.info(f"Investigation by {investigator_id} did not happen because the investigator is dead.")
        return
        
    # Determine the result message based on the target's role.
    role_name_result = target.role.name if target.role else "Unknown"
    short_desc_result = target.role.short_description if target.role else "No details."
    
    if target.role and target.role.investigation_result:
        result_data = target.role.investigation_result
        try:
            role_name_result, short_desc_result = list(result_data.items())[0]
        except (IndexError, ValueError):
            logger.warning(f"Malformed investigation_result for role {target.role.name}")

    result_message = (
        f"Your investigation of **{target.display_name}** reveals they are **{role_name_result}**."
        f"\n> *{short_desc_result}*"
    )

    # --- Step 4: Send the result as a background task ---
    # This prevents the game loop from waiting for the Discord API.
    async def send_investigation_dm():
        try:
            user = await game.bot.fetch_user(investigator.id)
            await user.send(result_message)
            logger.info(f"Sent investigation result to {investigator.display_name}.")
        except Exception as e:
            logger.error(f"Failed to send investigation DM to {investigator.display_name}: {e}")

    game.bot.loop.create_task(send_investigation_dm())

# This dictionary maps the action type string to the correct handler function.
ACTION_HANDLERS = {
    'block': handle_block,
    'kill': handle_kill,
    'heal': handle_heal,
    'investigate': handle_investigation,
}

