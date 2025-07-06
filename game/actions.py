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
    blocker = game.players.get(blocker_id)
    target = game.players.get(target_id)
    if not blocker or not target:
        return
    # Check if the target was going to perform an action
    if target_id in game.night_actions:
        # The target's action is nullified by removing it
        del game.night_actions[target_id]
        game.narration_manager.add_event('block', blocker=blocker, target=target)
        logger.info(f"{blocker.display_name} successfully blocked {target.display_name}.")
    else:
        logger.info(f"{blocker.display_name} attempted to block {target.display_name}, but they weren't performing an action.")

def handle_heal(game, healer_id, target_id):
    """
    Resolves a heal action. This should run after blocks.
    It adds the target to a set of protected players for the night.
    """
    healer = game.players.get(healer_id)
    target = game.players.get(target_id)
    if not healer or not target:
        return
    # Add the target's ID to a temporary set of protected players for this night
    game.protected_players_this_night.add(target_id)
    logger.info(f"{healer.display_name} is protecting {target.display_name} tonight.")

def handle_kill(game, killer_id, target_id):
    """
    Resolves a kill action. This should run after blocks and heals.
    It checks if the target is in the protected set before killing them.
    """
    killer = game.players.get(killer_id)
    target = game.players.get(target_id)
    if not killer or not target or not target.is_alive:
        logger.warning(f"Kill action failed: Killer/target not found, or target already dead.")
        return
    # Check if the target was protected by a heal that occurred earlier
    if target_id in game.protected_players_this_night:
        # The kill fails. The NarrationManager receives a "heal" event to describe the save.
        # We need to find who the doctor was to narrate it.
        doctor = None
        for p_id, action in game.night_actions.items():
            if action.get('type') == 'heal' and action.get('target_id') == target_id:
                doctor = game.players.get(p_id)
                break
        game.narration_manager.add_event('heal', doctor=doctor, patient=target)
        logger.info(f"{killer.display_name}'s kill on {target.display_name} was stopped by a heal.")
    else:
        # The kill succeeds.
        phase_str = f"Night {game.game_settings['phase_number']}"
        target.kill(phase_str, f"Killed by the {killer.role.name}")
        game.narration_manager.add_event('kill', killer=killer, victim=target)
        logger.info(f"{killer.display_name} successfully killed {target.display_name}.")

def handle_investigation(game, investigator_id, target_id):
    """
    Resolves an investigation action and sends the result to the investigator.
    """
    investigator = game.players.get(investigator_id)
    target = game.players.get(target_id)
    if not investigator or not target:
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
    # Create a task to send the DM through the bot's event loop
    game.bot.loop.create_task(investigator.send_dm(game.bot, message))
    # Add an event for the narrator, but it might not be used publicly
    game.narration_manager.add_event('investigate', investigator=investigator, target=target)

# This dictionary maps the action type string to the correct handler function.
ACTION_HANDLERS = {
    "kill": handle_kill,
    "heal": handle_heal,
    "block": handle_block,
    "investigate": handle_investigation,
    # When you add a new action, you just add a new line here.
}