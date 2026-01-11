# game/setup_generator.py
"""
Dynamically generates a list of roles for a 'Classic' Mafia game
based on the number of players. This replaces the static mafia_setups.json.
"""

import math
from typing import List
import config

# --- Constants for Role Names ---
# Using constants makes it easy to change role names later if we need to!
# This is a classic example of the DRY (Don't Repeat Yourself) principle.

# --- Classic Roles ---
MAFIA_GF = "Godfather"
MAFIA_GOON = "Mob Goon"
MAFIA_RB = "Mob Role Blocker"
SERIAL_KILLER = "Serial Killer"
TOWN_COP = "Town Cop"
TOWN_DOCTOR = "Town Doctor"
TOWN_RB = "Town Role Blocker"
TOWNIE = "Plain Townie"
JESTER = "Jester"

# --- Battle Royale Roles ---
VIGILANTE = "Vigilante"

#-- Role Generation Function ---
def generate_roles(player_count: int, game_type: str) -> List[str]:
    """
    Generates a balanced list of role names based on player count and game type.

    Args:
        player_count: The number of players in the game.
        game_type: The type of game (e.g., "Classic", "Battle Royale").
                   Currently, only "Classic" is dynamically generated.

    Returns:
        A list of strings, where each string is a role name.
    """
    # Initialize the list of roles
    roles = []
    
    # Add vigilante roles to list for all players if not classic (i.e. is Battle Royale mode).
    if game_type.lower() != "classic":
        # Return all Vigilantes for Battle Royale mode.
        return [VIGILANTE] * player_count

    # We need a minimum number of players to run this logic.
    # For a classic game, the minimum is defined in the config file.
    if player_count < config.min_players:
        # We can't generate a balanced game with fewer than 5.
        # Returning an empty list will signal the engine to stop.
        return [] 
      
    # --- 1. Calculate Evil Roles ---
    # Rule: 25% of players, rounded down.
    mafia_count = math.floor(player_count * config.mob_ratio)
    # Ensure at least 1 Mafia in a >= 5 player game
    if mafia_count == 0:
        mafia_count = 1
    # Add base Mafia roles
    for _ in range(mafia_count):
        roles.append(MAFIA_GOON)
    # Always add 1 Godfather
    try:
        roles.remove(MAFIA_GOON)  # Replace one Goon with Godfather
        roles.append(MAFIA_GF)
    except ValueError:
        # This should never happen if mafia_count >= 1,
        # but it's good practice to be safe.
        pass
    
    # Rule: 1 SK if players >= 9.
    if player_count >= config.min_sk_players:
        roles.append(SERIAL_KILLER)
    # Rule: 1 Mob RB if Mafia count >= 4.
    # This REPLACES one Goon to keep the Mafia count correct.
    if mafia_count >= config.min_mob_rb_mafia_count:
        # Find the first "Mafia" and replace it
        try:
            index_to_replace = roles.index(MAFIA_GOON)
            roles[index_to_replace] = MAFIA_RB
        except ValueError:
            # This should never happen if mafia_count >= 4,
            # but it's good practice to be safe.
            pass 

    # --- 2. Calculate Town Power Roles ---
    # Rule: 1 Cop if players >= 6.
    if player_count >= config.min_cop_players:
        roles.append(TOWN_COP)
    # Rule: 1 Doctor if players >= 7.
    if player_count >= config.min_doctor_players:
        roles.append(TOWN_DOCTOR)
    # Rule: 1 Town RB if players >= 8.
    if player_count >= config.min_town_rb_players:
        roles.append(TOWN_RB)

    # --- 3. Fill Remaining Slots with Townies ---
    # Calculate how many spots are left to fill
    remaining_slots = player_count - len(roles)
    # Fill all remaining spots with Townies
    for _ in range(remaining_slots):
        roles.append(TOWNIE)
    # We don't need to shuffle here!
    # The engine's secure Fisher-Yates shuffle  will
    # handle that after this list is returned.
    return roles