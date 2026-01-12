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
    blocker_action = night_outcomes.get(blocker_id)
    if blocker_action and blocker_action.get('status') == 'blocked':
        logger.info(f"Block attempt by {blocker_id} failed because they were also blocked.")
        return

    # --- FIX: Mark the blocker's action as successful (consumed) ---
    if blocker_action:
        night_outcomes[blocker_id]['status'] = 'successful'

    # --- Step 2: Get player objects for the narration ---
    blocker = game.players.get(blocker_id)
    target = game.players.get(target_id)
    if not blocker or not target:
        logger.warning(f"Could not find player objects for blocker {blocker_id} or target {target_id}.")
        return

    # --- Step 3: Check the target's action status to decide the outcome ---
    target_action = night_outcomes.get(target_id)

    if target_action and target_action.get('status') is None:
        # --- SUCCESSFUL BLOCK ---
        night_outcomes[target_id]['status'] = 'blocked'  
        game.blocked_players_this_night[target_id] = blocker_id
        
        event_type = 'block_battle_royale' if game.game_settings.get('game_type') == "battle_royale" else 'block'
        game.narration_manager.add_event(event_type, blocker=blocker, target=target)
        logger.info(f"Action by {target.display_name} was blocked by {blocker.display_name}.")
    else:
        # --- MISSED BLOCK ---
        event_type = 'block_missed_royale' if game.game_settings.get('game_type') == "battle_royale" else 'block_missed'
        game.narration_manager.add_event(event_type, blocker=blocker, target=target)
        logger.info(f"Block by {blocker.display_name} on {target.display_name} missed as the target's action had already resolved.")


def handle_heal(game, healer_id, target_id, night_outcomes):
    """Records a heal attempt on a target."""
    healer_action = night_outcomes.get(healer_id)
    if healer_action and healer_action.get('status') == 'blocked':
        logger.info(f"Heal attempt by {healer_id} failed because they were blocked.")
        return

    if healer_action:
        night_outcomes[healer_id]['status'] = 'successful'
    
    healer = game.players.get(healer_id)
    target = game.players.get(target_id)
    if not healer or not target: return
    
    game.heals_on_players.setdefault(target_id, []).append(healer_id)
    logger.info(f"{healer.display_name} successfully healed {target.display_name}.")


def handle_kill(game, killer_id, victim_id, night_outcomes):
    """Records a kill attempt on a victim."""
    killer = game.players.get(killer_id)
    victim = game.players.get(victim_id)
    if not killer or not victim: return

    killer_action = night_outcomes.get(killer_id)
    if killer_action and killer_action.get('status') == 'blocked':
        if game.game_settings["game_type"] == "battle_royale": 
            game.narration_manager.add_event('block_battle_royale', killer=killer, target=victim) 
        else: 
            game.narration_manager.add_event('blocked', killer=killer, target=victim)
        logger.info(f"Kill attempt by {killer.display_name} failed because they were blocked.")
        return

    if killer_action:
        night_outcomes[killer_id]['status'] = 'successful'

    if victim.role and victim.role.is_night_immune:
        game.narration_manager.add_event('kill_immune', killer=killer, target=victim)
        logger.info(f"Kill by {killer.display_name} on {victim.display_name} failed due to immunity.")
        return
    # Record the kill attempt
    game.kill_attempts_on.setdefault(victim_id, []).append(killer_id)
    logger.info(f"{killer.display_name} successfully attempted to kill {victim.display_name}.")


def handle_investigation(game, investigator_id, target_id, night_outcomes):
    """Determines investigation result and sends DM."""
    investigator_action = night_outcomes.get(investigator_id)
    if investigator_action and investigator_action.get('status') == 'blocked':
        logger.info(f"Investigation by {investigator_id} failed because they were blocked.")
        return

    if investigator_action:
        night_outcomes[investigator_id]['status'] = 'successful'

    investigator = game.players.get(investigator_id)
    target = game.players.get(target_id)
    if not investigator or not target: return
    
    if not investigator.is_alive: return
    # Check if investigator was killed this night
    if investigator_id in game.kill_attempts_on:
        logger.info(f"Investigation by {investigator.display_name} aborted due to their death.")
        return
        
    role_name_result = target.role.name if target.role else "Unknown"
    short_desc_result = target.role.short_description if target.role else "No details."
    
    if target.role and target.role.investigation_result:
        result_data = target.role.investigation_result
        try:
            # Handle both dict and string (just in case)
            if isinstance(result_data, dict):
                role_name_result, short_desc_result = list(result_data.items())[0]
            else:
                short_desc_result = str(result_data)
        except (IndexError, ValueError):
            logger.warning(f"Malformed investigation_result for role {target.role.name}")

    result_message = (
        f"Your investigation of **{target.display_name}** reveals they are **{role_name_result}**."
        f"\n> *{short_desc_result}*"
    )
    logger.info(f"Sent investigation result: {result_message} to {investigator.display_name}")

    async def send_investigation_dm():
        try:
            user = await game.bot.fetch_user(investigator.id)
            await user.send(result_message)
            logger.info(f"Sent investigation result to {investigator.display_name}.")
        except Exception as e:
            logger.error(f"Failed to send investigation DM to {investigator.display_name}: {e}")

    asyncio.create_task(send_investigation_dm())

    event_type = 'investigate_royale' if game.game_settings.get('game_type') == "battle_royale" else 'investigate'
    game.narration_manager.add_event(event_type, investigator=investigator, target=target)
    logger.info(f"{investigator.display_name} investigated {target.display_name}.")

ACTION_HANDLERS = {
    'block': handle_block,
    'kill': handle_kill,
    'heal': handle_heal,
    'investigate': handle_investigation,
}