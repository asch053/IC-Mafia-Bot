# game/setup_generator.py
# This module dynamically generates a list of roles for a 'Classic' Mafia game based on the number of players. This replaces the static mafia_setups.json and allows for more flexible and scalable game setups. The generate_roles function takes the player count and game type as input and returns a balanced list of role names that can be used to create the game. The logic is based on common Mafia game design principles, such as maintaining a certain ratio of Town to Mafia players and including specific roles at certain player thresholds.

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
def generate_roles(player_count: int, game_type: str, mob_ratio: float, town_rb_req: int, mafia_rb_req: int, sk_player_count: int, min_cop_players: int, min_doctor_players: int) -> List[str]:
    """
    Generates a balanced list of role names based on player count and game type.

    Args:
        player_count: The number of players in the game.
        game_type: The type of game (e.g., "Classic", "Battle Royale").
                   Currently, only "Classic" is dynamically generated.
        mob_ratio: The ratio of Mafia players to total players.
        town_rb_req: The minimum number of players required for a Town Role Blocker.
        mafia_rb_req: The minimum number of Mafia players required for a Mob Role Blocker.
        sk_player_count: The minimum number of players required for the Serial Killer role.
        min_cop_players: The minimum number of players required for the Town Cop role.
        min_doctor_players: The minimum number of players required for the Town Doctor role.
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
    if mob_ratio <= 0 or mob_ratio >= 1:
        mob_ratio = config.mob_ratio if hasattr(config, 'mob_ratio') else 0.25  # Default to 0.25 if not defined
    mafia_count = math.floor(player_count * mob_ratio)
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
    
    # Rule: 1 SK if players >= sk_player_count.
    if sk_player_count <= 0:
        sk_player_count = config.min_sk_players if hasattr(config, 'min_sk_players') else 4  # Default to 4 if not defined
    if player_count >= sk_player_count:
        roles.append(SERIAL_KILLER)
    # Rule: 1 Mob RB if Mafia count >= 4.
    # This REPLACES one Goon to keep the Mafia count correct.
    if mafia_count >= mafia_rb_req:
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
    if player_count >= min_cop_players:
        roles.append(TOWN_COP)
    # Rule: 1 Doctor if players >= 7.
    if player_count >= min_doctor_players:
        roles.append(TOWN_DOCTOR)
    # Rule: 1 Town RB if players >= town_rb_req.
    if player_count >= town_rb_req:
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