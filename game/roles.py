# game/roles.py
"""
GameRole classes and dynamic role factory.

Architecture & Design:
----------------------
1. Role Identity Separation:
   - `role.name`: The canonical, mechanical identifier (e.g. "Town Cop", "Godfather", "Serial Killer").
     Engine actions (/kill, /heal, /block, /investigate), night priority sorting, win conditions,
     and promotion chains rely strictly on this immutable name.
   - `role.display_name`: The dynamic, user-facing skin title loaded from `data/game_setup/theme_roles.json`
     (e.g. "Relationship Detective" in Rom Com, "Compliance Auditor" in Office Restructuring).
   - `role.theme`: The active story theme (e.g. "Rom Com", "Horror", "Office Restructuring").

2. Data Sources:
   - `data/game_setup/role_definition.json`: Defines base classes, priorities, mechanical abilities,
     and immunity tags.
   - `data/game_setup/theme_roles.json`: Contains thematic skin overlays for each theme and canonical role.
"""

import logging
from utils.loaddata import load_data

logger = logging.getLogger('discord')

# Load raw role definitions and theme skins once at startup
ALL_ROLES_DATA = load_data("data/game_setup/role_definition.json") or {}
THEME_ROLES_DATA = load_data("data/game_setup/theme_roles.json") or {}


class GameRole:
    """
    The base class for all roles in the game.
    
    Attributes:
        name (str): Immutable canonical role name (e.g. "Town Cop", "Godfather").
        display_name (str): Themed display name (e.g. "Relationship Detective").
        theme (str): Active narrative theme.
        alignment (str): Faction alignment ("Town", "Mafia", "Serial Killer", "Jester", "Vigilante").
        description (str): Full role explanation sent in the player's private DM.
        short_description (str): One-line summary of role abilities.
        abilities (dict): Action mapping (e.g. {"kill": "...", "heal": "..."}).
        uses (int): Maximum ability charges per game (None = unlimited).
        win_condition (str): Description of faction victory condition.
        investigation_result (str): Override alignment returned to investigating Cops.
        investigation_immune (bool): If True, appears innocent/Town to Cop investigations.
        is_night_immune (bool): If True, survives standard nightly kill attempts.
        night_priority (int): Resolution order tier (1 = Block, 2 = Heal, 3 = Kill, 4 = Investigate).
    """

    def __init__(
        self,
        name: str,
        alignment: str,
        description: str,
        short_description: str,
        abilities: dict = None,
        uses: int = None,
        win_condition: str = None,
        investigation_immune: bool = False,
        investigate_result: str = None,
        is_night_immune: bool = False,
        night_priority: int = 99
    ):
        self.name = name
        self.display_name = name  # Defaults to canonical name until skin is applied
        self.theme = "Classic Mafia"
        self.alignment = alignment
        self.description = description
        self.short_description = short_description
        self.abilities = abilities if abilities is not None else {}
        self.uses = uses
        self.win_condition = win_condition
        self.investigation_result = investigate_result
        self.is_night_immune = is_night_immune
        self.night_priority = night_priority
        self.investigation_immune = investigation_immune

    def apply_theme(self, theme_name: str):
        """
        Applies a thematic re-skin (display name, DM description) from theme_roles.json.
        
        Args:
            theme_name (str): The active theme key (e.g., "Rom Com", "Horror", "Office Restructuring").
        """
        if not theme_name or theme_name == "No Story":
            self.display_name = self.name
            return

        self.theme = theme_name
        theme_dict = THEME_ROLES_DATA.get(theme_name, {})
        role_skin = theme_dict.get(self.name)

        if role_skin:
            # Update user-facing skin properties while leaving mechanical attributes unchanged
            self.display_name = role_skin.get("display_name", self.name)
            if "description" in role_skin:
                self.description = role_skin["description"]
            if "short_description" in role_skin:
                self.short_description = role_skin["short_description"]

    def __str__(self):
        """String representation prioritizes the themed display name."""
        return self.display_name if getattr(self, 'display_name', None) else self.name


# =====================================================================
# Base Role Classes by Alignment & Type
# =====================================================================

class TownInvestigative(GameRole):
    """Town alignment specializing in night intelligence (e.g. Town Cop)."""
    def __init__(self, name, **kwargs):
        super().__init__(name, "Town", **kwargs)


class TownProtective(GameRole):
    """Town alignment specializing in defense and obstruction (e.g. Town Doctor, Town Role Blocker)."""
    def __init__(self, name, **kwargs):
        super().__init__(name, "Town", **kwargs)


class TownKilling(GameRole):
    """Town alignment with daytime voting power or lethal vigilante actions (e.g. Plain Townie)."""
    def __init__(self, name, **kwargs):
        super().__init__(name, "Town", **kwargs)


class MafiaKilling(GameRole):
    """Mafia leadership with nightly kill directive authority (e.g. Godfather)."""
    def __init__(self, name, **kwargs):
        super().__init__(name, "Mafia", **kwargs)


class MafiaSupport(GameRole):
    """Mafia support faction members (e.g. Mob Goon, Mob Role Blocker)."""
    def __init__(self, name, **kwargs):
        super().__init__(name, "Mafia", **kwargs)


class NeutralKilling(GameRole):
    """Neutral solo killer aiming to be the last survivor (e.g. Serial Killer)."""
    def __init__(self, name, **kwargs):
        super().__init__(name, "Serial Killer", **kwargs)


class NeutralEvil(GameRole):
    """Neutral player winning through self-destruction (e.g. Jester)."""
    def __init__(self, name, **kwargs):
        super().__init__(name, "Jester", **kwargs)


class NeutralRoyale(GameRole):
    """Free-for-all contestant capable of killing and blocking (e.g. Vigilante in Battle Royale)."""
    def __init__(self, name, **kwargs):
        super().__init__(name, "Vigilante", **kwargs)


# Registry mapping definition "base" strings to their corresponding class constructors
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


def get_role_instance(role_name: str, theme: str = "Classic Mafia") -> GameRole | None:
    """
    Creates and initializes a role instance from role_definition.json and applies thematic skinning.

    Args:
        role_name (str): The canonical role name (e.g., "Town Cop", "Godfather").
        theme (str): Active story theme (e.g., "Classic Mafia", "Rom Com", "Office Restructuring").

    Returns:
        GameRole: Fully initialized GameRole instance, or None if the role definition is missing.
    """
    # 1. Retrieve canonical mechanical parameters
    role_data = ALL_ROLES_DATA.get(role_name)
    if not role_data:
        logger.error(f"No role definition found for '{role_name}' in role_definition.json")
        return None

    # 2. Resolve target Python class
    base_class_name = role_data.get("base")
    RoleClass = ROLE_CLASSES.get(base_class_name)

    if not RoleClass:
        logger.error(f"Invalid base class '{base_class_name}' specified for role '{role_name}'")
        return None

    # 3. Instantiate mechanical role
    role = RoleClass(
        name=role_name,
        description=role_data.get("description", ""),
        short_description=role_data.get("short_description", ""),
        abilities=role_data.get("abilities"),
        uses=role_data.get("uses"),
        win_condition=role_data.get("win_condition"),
        investigate_result=role_data.get("investigate_result"),
        investigation_immune=role_data.get("investigate_immune", False),
        is_night_immune=role_data.get("is_night_immune", False),
        night_priority=role_data.get("night_priority", 99)
    )

    # 4. Apply thematic skin if requested
    if theme:
        role.apply_theme(theme)

    return role
