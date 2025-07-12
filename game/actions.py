# game/actions.py
import logging

logger = logging.getLogger('discord')

# This file contains the logic for resolving night actions.
# Each function takes the game instance as an argument to access its state.


def handle_block(game, blocker_id, target_id):
    """
    Resolves a block action. This should run first.
    It removes the target's action from the night's queue.
    """
    logger.info(f"Resolving block action: Blocker ID {blocker_id}, Target ID {target_id}")
    # Get the blocker and target players from the game state
    blocker = game.players.get(blocker_id)
    target = game.players.get(target_id)
    logger.debug(f"Blocker: {blocker}, Target: {target}")
    # If either player is not found, we can't proceed
    if not blocker or not target:
        logger.warning(f"Block action failed: Blocker or target not found. Blocker ID: {blocker_id}, Target ID: {target_id}")
        return
    # Check if the target was going to perform an action
    if target_id in game.night_actions:
        # The target's action is nullified by removing it
        del game.night_actions[target_id]
        game.narration_manager.add_event('block', blocker=blocker, target=target)
        logger.debug(f"{blocker.display_name} successfully blocked {target.display_name}.")
    else:
        # The target wasn't performing an action, so we log it
        logger.debug(f"{blocker.display_name} attempted to block {target.display_name}, but they weren't performing an action.")

def handle_heal(game, healer_id, target_id):
    """
    Resolves a heal action. This should run after blocks.
    It adds the target to a set of protected players for the night.
    """
    logger.info(f"Resolving heal action: Healer ID {healer_id}, Target ID {target_id}")
    # Get the healer and target players from the game state
    healer = game.players.get(healer_id)
    target = game.players.get(target_id)
    #if either player is not found, we can't proceed
    if not healer or not target:
        logger.warning(f"Heal action failed: Healer or target not found. Healer ID: {healer_id}, Target ID: {target_id}")
        return
    # Add the target's ID to a temporary set of protected players for this night
    game.protected_players_this_night.add(target_id)
    logger.debug(f"{healer.display_name} is protecting {target.display_name} tonight.")

def handle_kill(game, killer_id, target_id):
    """
    Resolves a kill action. This should run after blocks and heals.
    It checks if the target is in the protected set before killing them.
    """
    logger.info(f"Resolving kill action: Killer ID {killer_id}, Target ID {target_id}")
    # Get the killer and target players from the game state
    killer = game.players.get(killer_id)
    target = game.players.get(target_id)
    # If either player is not found or the target is already dead, we can't proceed
    if not killer or not target or not target.is_alive:
        logger.warning(f"Kill action failed: Killer/target not found, or target already dead. Killer ID: {killer_id}, Target ID: {target_id}")
        return
    # Check if the target was protected by a heal that occurred earlier
    if target_id in game.protected_players_this_night:
        # The kill fails. The NarrationManager receives a "heal" event to describe the save.
        doctor = None
        # Find the player who healed the target to credit them in the story.
        for p_id, action in game.night_actions.items():
            if action.get('type') == 'heal' and action.get('target_id') == target_id:
                doctor = game.players.get(p_id)
                break      
        # The kill fails, so we log it and notify the game state
        game.narration_manager.add_event('heal', doctor=doctor, patient=target)
        logger.debug(f"{killer.display_name}'s kill on {target.display_name} was stopped by a heal.")
    else:
        # The kill succeeds.
        phase_str = f"Night {game.game_settings['phase_number']}"
        # If the target is not protected, we proceed with the kill
        target.kill(phase_str, f"Killed by the {killer.role.name}")
        game.narration_manager.add_event('kill', killer=killer, victim=target)
        logger.debug(f"{killer.display_name} successfully killed {target.display_name}.")

def handle_investigation(game, investigator_id, target_id):
    """
    Resolves an investigation action and sends the result to the investigator.
    """
    logger.info(f"Resolving investigation action: Investigator ID {investigator_id}, Target ID {target_id}")
    # Get the investigator and target players from the game state
    investigator = game.players.get(investigator_id)
    target = game.players.get(target_id)
    # If either player is not found, we can't proceed
    if not investigator or not target:
        logger.warning(f"Investigation action failed: Investigator or target not found. Investigator ID: {investigator_id}, Target ID: {target_id}")
        return
    # UPDATED: Check for a special investigation result dictionary.
    if target.role and target.role.investigation_result:
        result_data = target.role.investigation_result
        role_name_result = result_data.get("name", "Unknown")
        short_desc_result = result_data.get("short_description", "No details available.")
    # Otherwise, use the real role info.
    elif target.role:
        role_name_result = target.role.name
        short_desc_result = target.role.short_description
    else:
        role_name_result = "Unknown Role"
        short_desc_result = "Could not determine role."
    # Send the result via DM
    message = f"Your investigation of **{target.display_name}** reveals they are {role_name_result} - **{short_desc_result}**."
    logger.debug(f"Sending investigation result to {investigator.display_name}: {message}")
    # Create a task to send the DM through the bot's event loop
    game.bot.loop.create_task(investigator.send_dm(game.bot, message))
    # Add an event for the narrator, but it might not be used publicly
    game.narration_manager.add_event('investigate', investigator=investigator, target=target)
    logger.debug(f"Investigation result sent to {investigator.display_name} for target {target.display_name}.")

# This dictionary maps the action type string to the correct handler function.
ACTION_HANDLERS = {
    "kill": handle_kill,
    "heal": handle_heal,
    "block": handle_block,
    "investigate": handle_investigation,
    # When you add a new action, you just add a new line here.
}