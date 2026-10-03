# game/actions/investigate.py
import asyncio
import logging

logger = logging.getLogger('discord')


def handle_investigation(game, investigator_id: int, target_id: int, night_outcomes: dict):
    """Determines investigation result and sends DM."""
    investigator = game.players.get(investigator_id)
    target = game.players.get(target_id)
    if not investigator or not target:
        return

    if not investigator.is_alive:
        logger.info(f"Investigation aborted: investigator {investigator.display_name} is dead.")
        return

    if investigator_id in getattr(game, 'kill_attempts_on', {}):
        if investigator_id not in getattr(game, 'heals_on_players', {}):
            logger.info(f"Investigation by {investigator.display_name} aborted due to their death.")
            return

    investigator_action = night_outcomes.get(investigator_id)
    if investigator_action and investigator_action.get('status') == 'blocked':
        logger.info(f"Investigation by {investigator_id} failed because they were blocked.")
        return

    if investigator_action:
        night_outcomes[investigator_id]['status'] = 'successful'

    logger.info(f"Preparing investigation result for {investigator.display_name} investigating {target.display_name}.")

    if target.role and getattr(target.role, 'investigation_immune', False):
        result_data = target.role.investigation_result
        if not result_data:
            role_name_result = "Plain Townie"
            short_desc_result = "Normal Member of town"
        else:
            try:
                if isinstance(result_data, dict):
                    role_name_result, short_desc_result = list(result_data.items())[0]
                else:
                    role_name_result = str(result_data)
                    short_desc_result = "Normal Member of town"
            except (IndexError, ValueError):
                role_name_result = "Plain Townie"
                short_desc_result = "Normal Member of town"
    else:
        role_name_result = target.role.name if target.role else "Unknown"
        short_desc_result = target.role.short_description if target.role else "No details."

    result_message = (
        f"Your investigation of **{target.display_name}** reveals they are **{role_name_result}**."
        f"\n> *{short_desc_result}*"
    )
    logger.info(f"Sent investigation result: {result_message} to {investigator.display_name}")

    async def send_investigation_dm():
        if getattr(investigator, 'is_npc', False):
            return
        try:
            user = await game.bot.fetch_user(investigator.id)
            await user.send(result_message)
            logger.info(f"Sent investigation result to {investigator.display_name}.")
        except Exception as e:
            logger.error(f"Failed to send investigation DM to {investigator.display_name}: {e}")

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(send_investigation_dm())
    except RuntimeError:
        pass

    event_type = 'investigate_royale' if game.game_settings.get('game_type') == "battle_royale" else 'investigate'
    game.narration_manager.add_event(event_type, investigator=investigator, target=target)
    logger.info(f"{investigator.display_name} investigated {target.display_name}.")

