# game/setup_generator.py
"""
Dynamically generates a list of roles for a 'Classic' Mafia game
based on the number of players. This replaces the static mafia_setups.json.
"""

import math
from typing import List
import simulate_config as config
import logging

# Create simulation logger here
logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)
if logger.hasHandlers():
    logger.handlers.clear()
file_handler = logging.FileHandler("sim_debug.log", mode='w', encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S'))
logger.addHandler(file_handler)
logger.propagate = False


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

# -- Simulation Parameters
# --- PLAYER SETUP CONFIGURATION PARAMETERS ---
min_players: int = config.min_players                           # Minimum number of players to start the game
min_cop_players: int = config.min_cop_players                   # Minimum players required to include a Cop
min_doctor_players: int = config.min_doctor_players             # Minimum players required to include a Doctor
min_town_rb_players: int = config.min_town_rb_players           # Minimum players required to include a Town Role Blocker
min_mob_rb_mafia_count: int = config.min_mob_rb_mafia_count     # Minimum Mafia count required to include a Mafia Role Blocker
min_sk_players: int = config.min_sk_players                     # Minimum players required to include a Serial Killer

# --- Battle Royale Roles ---
VIGILANTE = "Vigilante"

#-- Role Generation Function ---
def generate_roles(player_count: int, game_type: str, game_parameters: dict = None) -> List[str]:
    """
    Generates a balanced list of role names based on player count and game type.

    Args:
        player_count: The number of players in the game.
        game_type: The type of game (e.g., "Classic", "Battle Royale").
                   Currently, only "Classic" is dynamically generated.

    Returns:
        A list of strings, where each string is a role name.
    """
    logger.info(f"Generating {player_count} Roles for game type: {game_type} with parameters: {game_parameters}")
    # Initialize the list of roles
    roles = []
    
    # Add vigilante roles to list for all players if not classic (i.e. is Battle Royale mode).
    if game_type.lower() != "classic":
        # Return all Vigilantes for Battle Royale mode.
        return [VIGILANTE] * player_count

    # We need a minimum number of players to run this logic.
    # For a classic game, the minimum is defined in the config file.
    if player_count < min_players:
        # We can't generate a balanced game with fewer than 5.
        # Returning an empty list will signal the engine to stop.
        return [] 
      
    # --- 1. Calculate Evil Roles ---
    # Rule: 25% of players, rounded down.
    logger.info(f"Creating {player_count * (1/(game_parameters.get('mob_ratio', 4)))} mob roles for {player_count} players with ratio {game_parameters.get('mob_ratio', 4)}")
    mafia_count = math.floor(player_count * (1/(game_parameters.get('mob_ratio', 4))))
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
    # Rule: 1 Mob RB if Mafia count >= 4.
    # This REPLACES one Goon to keep the Mafia count correct.
    if mafia_count >= game_parameters.get('mrb_player_count', min_mob_rb_mafia_count):
        logger.info(f"Adding Mafia Role Block as {player_count} is greater than {game_parameters.get('mrb_player_count', min_mob_rb_mafia_count)}")
        # Find the first "Mafia" and replace it
        try:
            index_to_replace = roles.index(MAFIA_GOON)
            roles[index_to_replace] = MAFIA_RB
        except ValueError:
            # This should never happen if mafia_count >= 4,
            # but it's good practice to be safe.
            pass 

    # Rule: 1 SK if players >= 9.
    if player_count >= game_parameters.get('sk_player_count', min_sk_players):
        logger.info(f"Adding Serial Killer as {player_count} is greater than {game_parameters.get('sk_player_count', min_sk_players)}")
        roles.append(SERIAL_KILLER)
    
    # --- 2. Calculate Town Power Roles ---
    # Rule: 1 Cop if players >= 6.
    if player_count >= game_parameters.get('cop_player_count', min_cop_players):
        logger.info(f"Adding Town Cop as {player_count} is greater than {game_parameters.get('cop_player_count', min_cop_players)}")
        roles.append(TOWN_COP)
    # Rule: 1 Doctor if players >= 7.
    if player_count >= game_parameters.get('cop_player_count', min_cop_players):
        logger.info(f"Adding Town Doctor as {player_count} is greater than {game_parameters.get('doc_player_count', min_doctor_players)}")
        roles.append(TOWN_DOCTOR)
    # Rule: 1 Town RB if players >= 8.
    if player_count >= game_parameters.get('trb_player_count', min_town_rb_players):
        logger.info(f"Adding Town Role Blocker as {player_count} is greater than {game_parameters.get('trb_player_count', min_town_rb_players)}")
        roles.append(TOWN_RB)

    # --- 3. Fill Remaining Slots with Townies ---
    # Calculate how many spots are left to fill
    remaining_slots = player_count - len(roles)
    logger.info(f"Filling up {remaining_slots} slots with Townies")
    # Fill all remaining spots with Townies
    for _ in range(remaining_slots):
        roles.append(TOWNIE)
    # We don't need to shuffle here!
    # The engine's secure Fisher-Yates shuffle  will
    # handle that after this list is returned.
    return roles