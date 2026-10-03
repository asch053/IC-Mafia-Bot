# game/engine/status.py
import logging
from collections import Counter
from utils.formattimeremain import format_time_remaining

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def get_player_by_name(game, name: str):
    """Finds a Player object by their display name (case-insensitive)."""
    for player_obj in game.players.values():
        if player_obj.display_name.lower() == name.lower():
            return player_obj
    return None


def get_status_message(game) -> str:
    """Generates a formatted status message with the current game state."""
    logger.info("Generating status message.")
    if game.game_settings["current_phase"] == "pre-day":
        current_phase = "Night"
    elif game.game_settings["current_phase"] == "pre-night":
        current_phase = "Day"
    else:
        current_phase = game.game_settings["current_phase"].capitalize()

    status_message = f"**Game Status: {game.game_settings['game_id']}**\n"
    status_message += f"**Phase:** {current_phase.capitalize()} {game.game_settings['phase_number']}\n"

    # Add time remaining only for active phases
    if game.game_settings['current_phase'] in ['day', 'night', 'signup']:
        time_left = format_time_remaining(game.game_settings['phase_end_time'])
        status_message += f"**Time Remaining:** {time_left}\n"

    # --- Player Status Section ---
    all_players = list(game.players.values())
    winning_players = sorted([p for p in all_players if p.is_winner], key=lambda p: p.display_name)
    dead_players = sorted([p for p in all_players if not p.is_alive], key=lambda p: p.display_name)

    # Check if the game has ended by seeing if there are any winners
    if winning_players:
        # Game Over: Display winners and their roles
        status_message += f"\n**🏆 Winners:** ({len(winning_players)})\n"
        for player_obj in winning_players:
            role_name = player_obj.role.name if player_obj.role else "Unknown Role"
            role_alignment = player_obj.role.alignment if player_obj.role else "Unknown Alignment"
            status_message += f"- {player_obj.display_name} ({role_alignment}: {role_name})"
            if not player_obj.is_alive:
                death_phase = player_obj.death_info.get('phase', 'N/A')
                death_cause = player_obj.death_info.get('how', 'N/A')
                status_message += f" (Died on {death_phase} - {death_cause})"
            status_message += "\n"

        living_losers = sorted([p for p in all_players if p.is_alive and not p.is_winner], key=lambda p: p.display_name)
        if living_losers:
            status_message += f"\n**Other Living Players:** ({len(living_losers)})\n"
            for player_obj in living_losers:
                role_name = player_obj.role.name if player_obj.role else "Unknown Role"
                role_alignment = player_obj.role.alignment if player_obj.role else "Unknown Alignment"
                status_message += f"- {player_obj.display_name} ({role_alignment}: {role_name})\n"
    else:
        # Game Ongoing: Display living players without revealing roles
        living_players = sorted([p for p in all_players if p.is_alive], key=lambda p: p.display_name)
        status_message += f"\n**Living Players:** ({len(living_players)})\n"
        for player_obj in living_players:
            status_message += f"- {player_obj.display_name}\n"

    # Always display the list of dead players
    if dead_players:
        status_message += f"\n**Dead Players:** ({len(dead_players)})\n"
        for player_obj in dead_players:
            role_name = player_obj.role.name if player_obj.role else "Unknown Role"
            role_alignment = player_obj.role.alignment if player_obj.role else "Unknown Alignment"
            death_phase = player_obj.death_info.get('phase', 'N/A')
            death_cause = player_obj.death_info.get('how', 'N/A')
            status_message += f"- ~~{player_obj.display_name}~~ (Dead, {role_alignment}: {role_name}, Died on {death_phase} - {death_cause})\n"

    logger.info(f"Generated status message for game {game.game_settings['game_id']}.")
    return status_message


async def role_status_message(game) -> str:
    """Generates a status message with the roles being played."""
    logger.debug("Generating role status message for the game.")
    role_counts = Counter(role.name for role in game.game_roles)
    status_message = "\n\n---------------------------------------\n"
    status_message += "\n## Current Roles in the Game: ##\n"
    for role_name, count in role_counts.items():
        status_message += f" - **{role_name}**: {count}\n"
    return status_message

