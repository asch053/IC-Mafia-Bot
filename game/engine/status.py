# game/engine/status.py
"""
Game Status and Role Count Reporting Subsystem.

Responsibilities:
1. Generates structured, theme-aware game status messages for `/mafiastatus` and phase updates.
2. Formats theme-appropriate headers for eliminated players:
   - "💔 Dumped / Off Market" (Rom Com)
   - "📦 Terminated / Former Staff" (Office Restructuring)
   - "Dead Players" (Classic Mafia and standard themes)
3. Enforces Fog of War secrecy: living player roles are never revealed during an ongoing match.
4. Generates aggregated public role tallies for the rules channel via `role_status_message()`.
"""

import logging
from collections import Counter
from utils.formattimeremain import format_time_remaining

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def get_player_by_name(game, name: str):
    """
    Finds a Player object by their server display name (case-insensitive).
    
    Args:
        game (Game): The current game engine instance.
        name (str): The display name to search for.

    Returns:
        Player | None: Matching Player instance, or None if not found.
    """
    for player_obj in game.players.values():
        if player_obj.display_name.lower() == name.lower():
            return player_obj
    return None


def get_status_message(game) -> str:
    """
    Generates a formatted status message representing the current state of the game.

    Content Breakdown:
    - Game ID, Active Narrative Theme, Current Phase & Phase Number
    - Countdown timer remaining in the active phase
    - List of Living Players (roles hidden during ongoing play)
    - List of Eliminated Players (revealing their themed and canonical roles, phase of exit, and cause)
    - Winning Players section if victory conditions have been met

    Args:
        game (Game): The active game engine instance.

    Returns:
        str: Markdown-formatted game status report.
    """
    logger.info("Generating status message.")

    # 1. Resolve active phase string (handling internal pre-day / pre-night transitions gracefully)
    if game.game_settings["current_phase"] == "pre-day":
        current_phase = "Night"
    elif game.game_settings["current_phase"] == "pre-night":
        current_phase = "Day"
    else:
        current_phase = game.game_settings["current_phase"].capitalize()

    # 2. Select theme-appropriate elimination terminology
    story_type = game.game_settings.get("story_type", "Classic Mafia")
    if story_type == "Rom Com":
        elim_header = "💔 Dumped / Off Market:"
        elim_label = "Dumped"
    elif story_type == "Office Restructuring":
        elim_header = "📦 Terminated / Former Staff:"
        elim_label = "Terminated"
    else:
        elim_header = "Dead Players:"
        elim_label = "Dead"

    # 3. Construct header metadata
    status_message = f"**Game Status: {game.game_settings['game_id']}**\n"
    status_message += f"**Theme:** {story_type}\n"
    status_message += f"**Phase:** {current_phase.capitalize()} {game.game_settings['phase_number']}\n"
    if game.game_settings.get("br_skip_day"):
        status_message += "⚡ **Mode Rule:** Day Phase Skipped (Consecutive Nights Only)\n"

    # 4. Append remaining time countdown for active phases
    if game.game_settings['current_phase'] in ['day', 'night', 'signup']:
        time_left = format_time_remaining(game.game_settings['phase_end_time'])
        status_message += f"**Time Remaining:** {time_left}\n"

    # 5. Partition players into winners, living, and eliminated
    all_players = list(game.players.values())
    winning_players = sorted([p for p in all_players if p.is_winner], key=lambda p: p.display_name)
    dead_players = sorted([p for p in all_players if not p.is_alive], key=lambda p: p.display_name)

    if winning_players:
        # --- GAME OVER: Display triumphant winners and their full identities ---
        status_message += f"\n**🏆 Winners:** ({len(winning_players)})\n"
        for player_obj in winning_players:
            role_disp = (
                player_obj.role.display_name
                if player_obj.role and getattr(player_obj.role, 'display_name', player_obj.role.name) != player_obj.role.name
                else (player_obj.role.name if player_obj.role else "Unknown Role")
            )
            role_alignment = player_obj.role.alignment if player_obj.role else "Unknown Alignment"
            status_message += f"- {player_obj.display_name} ({role_alignment}: {role_disp})"
            if not player_obj.is_alive:
                death_phase = player_obj.death_info.get('phase', 'N/A')
                death_cause = player_obj.death_info.get('how', 'N/A')
                is_br = str(game.game_settings.get("game_type", "")).lower() in ("battle_royale", "battle royale", "br")
                if is_br and player_obj.death_info.get('killers'):
                    k_list = player_obj.death_info['killers']
                    if len(k_list) == 1:
                        k_str = k_list[0]
                    elif len(k_list) == 2:
                        k_str = f"{k_list[0]} and {k_list[1]}"
                    else:
                        k_str = ", ".join(k_list[:-1]) + f", and {k_list[-1]}"
                    death_cause = f"Killed by {k_str}"
                status_message += f" ({elim_label} on {death_phase} - {death_cause})"
            status_message += "\n"

        # List any remaining surviving players who did not win
        living_losers = sorted([p for p in all_players if p.is_alive and not p.is_winner], key=lambda p: p.display_name)
        if living_losers:
            status_message += f"\n**Other Living Players:** ({len(living_losers)})\n"
            for player_obj in living_losers:
                role_disp = (
                    player_obj.role.display_name
                    if player_obj.role and getattr(player_obj.role, 'display_name', player_obj.role.name) != player_obj.role.name
                    else (player_obj.role.name if player_obj.role else "Unknown Role")
                )
                role_alignment = player_obj.role.alignment if player_obj.role else "Unknown Alignment"
                status_message += f"- {player_obj.display_name} ({role_alignment}: {role_disp})\n"
    else:
        # --- GAME ONGOING: Display living players with roles hidden to preserve secrecy ---
        living_players = sorted([p for p in all_players if p.is_alive], key=lambda p: p.display_name)
        status_message += f"\n**Living Players:** ({len(living_players)})\n"
        for player_obj in living_players:
            status_message += f"- {player_obj.display_name}\n"

    # 6. Always list eliminated players with struck-through names and revealed roles
    if dead_players:
        status_message += f"\n**{elim_header}** ({len(dead_players)})\n"
        is_br = str(game.game_settings.get("game_type", "")).lower() in ("battle_royale", "battle royale", "br")
        for player_obj in dead_players:
            role_disp = (
                player_obj.role.display_name
                if player_obj.role and getattr(player_obj.role, 'display_name', player_obj.role.name) != player_obj.role.name
                else (player_obj.role.name if player_obj.role else "Unknown Role")
            )
            role_alignment = player_obj.role.alignment if player_obj.role else "Unknown Alignment"
            death_phase = player_obj.death_info.get('phase', 'N/A')
            death_cause = player_obj.death_info.get('how', 'N/A')
            if is_br and player_obj.death_info.get('killers'):
                k_list = player_obj.death_info['killers']
                if len(k_list) == 1:
                    k_str = k_list[0]
                elif len(k_list) == 2:
                    k_str = f"{k_list[0]} and {k_list[1]}"
                else:
                    k_str = ", ".join(k_list[:-1]) + f", and {k_list[-1]}"
                death_cause = f"Killed by {k_str}"
            status_message += (
                f"- ~~{player_obj.display_name}~~ ({elim_label}, {role_alignment}: {role_disp}, "
                f"Exit on {death_phase} - {death_cause})\n"
            )

    logger.info(f"Generated status message for game {game.game_settings['game_id']}.")
    return status_message


async def role_status_message(game) -> str:
    """
    Generates a public breakdown of the roles in play for the rules channel.

    Shows the count of each role present in the game (e.g. `Relationship Detective (Town Cop): 1`).
    """
    logger.debug("Generating role status message for the game.")
    role_counts = Counter(
        f"{role.display_name} ({role.name})" if getattr(role, 'display_name', role.name) != role.name else role.name
        for role in game.game_roles
    )
    status_message = "\n\n---------------------------------------\n"
    status_message += "\n## Current Roles in the Game: ##\n"
    for role_name, count in role_counts.items():
        status_message += f" - **{role_name}**: {count}\n"
    return status_message
