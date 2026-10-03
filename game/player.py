# game/player.py
"""
Player model representing a participant in the Mafia game.
Tracks identity, role, status, action targets, and provides messaging/state methods.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.roles import GameRole

logger = logging.getLogger('discord')


class Player:
    """Represents a single player in the Mafia game."""

    def __init__(self, user_id: int, discord_name: str, display_name: str):
        # --- Core Attributes ---
        self.id = user_id
        self.name = discord_name
        self.display_name = display_name
        self.is_npc = (user_id <= 0)

        # --- Game State Attributes ---
        self.role: 'GameRole | None' = None
        self.is_alive = True
        self.night_immune = False
        self.action_target = None
        self.death_info = {}
        self.last_action_target_id = None
        self.missed_votes = 0
        self.votes_on = 0
        self.is_winner = None

    def __str__(self):
        """String representation for debugging."""
        role_name = self.role.name if self.role else 'None'
        return f"{self.display_name} (ID: {self.id}, Role: {role_name}, Alive: {self.is_alive}, Winner: {self.is_winner}, Deaths: {self.death_info})"

    def assign_role(self, role: 'GameRole'):
        """Assigns a role to this player and updates initial night immunity."""
        self.role = role
        self.night_immune = bool(getattr(role, 'is_night_immune', False))
        logger.info(f"Assigned role {role.name} to player {self.display_name} (Night Immune: {self.night_immune}).")

    def kill(self, phase_str: str, cause_of_death: str):
        """Marks the player as dead and records phase and cause."""
        if self.is_alive:
            self.is_alive = False
            parts = str(phase_str).split()
            phase = parts[0] if parts else "Unknown"
            try:
                phase_number = int(parts[-1])
            except (ValueError, IndexError):
                phase_number = 1

            if phase in ("Day", "Pre-night"):
                computed_phase_num = phase_number * 2
            else:
                computed_phase_num = phase_number * 2 - 1

            self.death_info = {
                "phase": phase_str,
                "how": cause_of_death,
                "phase_number": computed_phase_num
            }
            logger.info(f"Player {self.display_name} has died. Cause: {cause_of_death}")

    def can_perform_action(self, action_type: str) -> bool:
        """Checks if the player's role allows them to perform a specific action."""
        if self.is_alive and self.role and self.role.abilities:
            return action_type in self.role.abilities
        return False

    async def send_dm(self, bot, message: str) -> bool:
        """Sends a direct message to the player (skips NPCs)."""
        if self.is_npc:
            return False
        try:
            user = await bot.fetch_user(self.id)
            await user.send(message)
            logger.info(f"Sent DM to {self.display_name}: {message}")
            return True
        except Exception as e:
            logger.error(f"Failed to send DM to {self.display_name} (ID: {self.id}): {e}")
            return False

