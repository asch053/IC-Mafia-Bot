# game/roles.py
import logging
from Utils.utilities import load_data

# Get the logger instance from the main bot file
logger = logging.getLogger('discord')

class GameRole:
    """The base class for all roles in the game."""
    def __init__(self, name, alignment, description, short_description, abilities=None, uses=None, win_condition=None, investigation_immune=False ,investigate_result=None, is_night_immune=False, night_priority=99):
        self.name = name
        self.alignment = alignment
        self.description = description
        self.short_description = short_description
        self.abilities = abilities if abilities is not None else {}
        self.uses = uses
        self.win_condition = win_condition
        self.investigation_result = investigate_result
        self.is_night_immune = is_night_immune
        self.night_priority = night_priority
        self.investigation_immune = investigation_immune # Default, can be overridden

    def __str__(self):
        """String representation of the role is its name."""
        return self.name

# --- Base Role Classes by Alignment/Type ---
# These classes define the alignment for roles loaded from the JSON file.

class TownInvestigative(GameRole):
    def __init__(self, name, **kwargs):
        super().__init__(name, "Town", **kwargs)

class TownProtective(GameRole):
    def __init__(self, name, **kwargs):
        super().__init__(name, "Town", **kwargs)

class TownKilling(GameRole):
    def __init__(self, name, **kwargs):
        super().__init__(name, "Town", **kwargs)

class MafiaKilling(GameRole):
    def __init__(self, name, **kwargs):
        super().__init__(name, "Mafia", **kwargs)

class MafiaSupport(GameRole):
    def __init__(self, name, **kwargs):
        super().__init__(name, "Mafia", **kwargs)

class NeutralKilling(GameRole):
    def __init__(self, name, **kwargs):
        super().__init__(name, "Serial Killer", **kwargs)

class NeutralEvil(GameRole):
    def __init__(self, name, **kwargs):
        super().__init__(name, "Jester", **kwargs)

class NeutralRoyale(GameRole):
    def __init__(self, name, **kwargs):
        super().__init__(name, "Vigilante", **kwargs)

# --- Data-Driven Role Creation ---

# This dictionary maps the 'base' string from roles_config.json to the actual Python class
ROLE_CLASSES = {
    "TownInvestigative": TownInvestigative,
    "TownProtective": TownProtective,
    "TownKilling": TownKilling,
    "MafiaKilling": MafiaKilling,
    "MafiaSupport": MafiaSupport,
    "NeutralKilling": NeutralKilling,
    "NeutralEvil": NeutralEvil,
    "NeutralRoyale": NeutralRoyale,
}

# Load all role definitions from the JSON file once when this module is first imported
ALL_ROLES_DATA = load_data("Data/role_definition.json")

def get_role_instance(role_name: str) -> GameRole | None:
    """
    Creates a complete role instance by looking up its definition in the 
    role_definition.json file and initializing the correct base class.
    """
    role_data = ALL_ROLES_DATA.get(role_name)
    if not role_data:
        logger.error(f"No role definition found for '{role_name}' in role_definition.json")
        return None
    
    base_class_name = role_data.get("base")
    RoleClass = ROLE_CLASSES.get(base_class_name)
    
    if not RoleClass:
        logger.error(f"Invalid base class '{base_class_name}' specified for role '{role_name}'")
        return None
        
    # Create the role instance by passing the data from the JSON file as keyword arguments
    return RoleClass(
        name=role_name,
        description=role_data.get("description", ""),
        short_description=role_data.get("short_description", ""),
        abilities=role_data.get("abilities"),
        uses=role_data.get("uses"),
        win_condition=role_data.get("win_condition"),
        investigate_result=role_data.get("investigate_result"),
        investigation_immune=role_data.get("ineveestigation_immune", True),
        is_night_immune=role_data.get("is_night_immune", False),
        night_priority=role_data.get("night_priority", 99)
    )

