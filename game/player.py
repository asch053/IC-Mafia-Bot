# game/player.py
import logging
from Game.roles import GameRole # For type hinting

logger = logging.getLogger('discord')

class Player:
    """Represents a single player in the Mafia game."""

    def __init__(self, user_id, discord_name, display_name):
        # --- Core Attributes ---
        self.id = user_id
        self.name = discord_name
        self.display_name = display_name
        self.is_npc = (user_id <= 0)

         # --- Game State Attributes ---
        self.role: GameRole = None # will be used to attach game role 
        self.is_alive = True # Flag to determine if player is alive or dead
        self.night_immune = False # NEW: Flag for night immunity
        self.action_target = None # Stores current action target
        self.death_info = {} # e.g., {"phase": "Night 1", "how": "Killed by Mafia"}
        self.last_action_target_id = None # Records target ID of last action so can determine if targetting same player 2 nights in a row
        self.missed_votes = 0 # Stores missed lynch votes so can determine if need to be killed for inactivity
        self.votes_on = 0 # an attribute to count how many votes player recieved during lynching
        self.is_winner = None # Flag to determine if player won the game - used at end to help with final narration story

    def __str__(self):
        """String representation for easy debugging."""
        return f"{self.display_name} (ID: {self.id}, Role: {self.role.name if self.role else 'None'}, Alive: {self.is_alive}, Winner: {self.is_winner}, Deaths: {self.death_info})"

    # --- Methods for Game Logic ---

    def assign_role(self, role: GameRole):
        """Assigns a role to this player."""
        self.role = role
        # Set initial night immunity based on the role's property
        if role.is_night_immune:
            self.night_immune = True
        logger.info(f"Assigned role {role.name} to player {self.display_name}.")

    def kill(self, phase_str: str, cause_of_death: str):
        """Marks the player as dead and records the details."""
        if self.is_alive:
            self.is_alive = False
            phase = str(phase_str.split()[0])  # Extract phase type (Day/Night)
            phase_number = int(phase_str.split()[-1])  # Extract phase number from string
            if phase == "Day" or phase == "Pre-night":
                phase_number = phase_number * 2 
            else:
                phase_number = phase_number * 2 - 1 
            self.death_info = {"phase": phase_str, "how": cause_of_death, "phase_number": phase_number}
            logger.info(f"Player {self.display_name} has died. Cause: {cause_of_death}")

    def can_perform_action(self, action_type: str) -> bool:
        """Checks if the player's role allows them to perform a specific action."""
        if self.is_alive and self.role and self.role.abilities:
            return action_type in self.role.abilities
        return False
    
    async def send_dm(self, bot, message: str):
        """Sends a direct message to the player."""
        if self.is_npc:
            return # Don't try to DM bots
        try:
            user = await bot.fetch_user(self.id)
            await user.send(message)
            logger.info(f"Sent DM to {self.display_name}: {message}")
        except Exception as e:
            logger.error(f"Failed to send DM to {self.display_name} (ID: {self.id}): {e}")