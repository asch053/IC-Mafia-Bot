# game/setup_generator.py
"""
Dynamically generates a list of roles for a Mafia game based on player count,
game type, and custom ratio/threshold parameters.
"""

import math
from typing import List
import config

# --- Constants for Role Names ---
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


def generate_roles(
    player_count: int,
    game_type: str,
    mob_ratio: float,
    town_rb_req: int,
    mafia_rb_req: int,
    sk_player_count: int,
    min_cop_players: int,
    min_doctor_players: int
) -> List[str]:
    """
    Generates a balanced list of role names based on player count and game type.
    """
    roles = []

    # Battle Royale mode gives all players Vigilante
    if game_type.lower() != "classic":
        return [VIGILANTE] * player_count

    # Minimum player requirement for Classic mode
    min_players = getattr(config, 'min_players', 5)
    if player_count < min_players:
        return []

    # --- 1. Calculate Evil Roles ---
    if mob_ratio <= 0 or mob_ratio >= 1:
        mob_ratio = getattr(config, 'mob_ratio', 0.25)
    mafia_count = math.floor(player_count * mob_ratio)
    if mafia_count == 0:
        mafia_count = 1

    # Add base Mafia roles
    for _ in range(mafia_count):
        roles.append(MAFIA_GOON)

    # Always replace one Goon with Godfather
    try:
        roles.remove(MAFIA_GOON)
        roles.append(MAFIA_GF)
    except ValueError:
        pass

    # Serial Killer requirement
    if sk_player_count <= 0:
        sk_player_count = getattr(config, 'min_sk_players', 4)
    if player_count >= sk_player_count:
        roles.append(SERIAL_KILLER)

    # Mafia Role Blocker requirement
    if mafia_count >= mafia_rb_req:
        try:
            index_to_replace = roles.index(MAFIA_GOON)
            roles[index_to_replace] = MAFIA_RB
        except ValueError:
            pass

    # --- 2. Calculate Town Power Roles ---
    if player_count >= min_cop_players:
        roles.append(TOWN_COP)
    if player_count >= min_doctor_players:
        roles.append(TOWN_DOCTOR)
    if player_count >= town_rb_req:
        roles.append(TOWN_RB)

    # --- 3. Fill Remaining Slots with Townies ---
    remaining_slots = player_count - len(roles)
    for _ in range(remaining_slots):
        roles.append(TOWNIE)

    return roles

