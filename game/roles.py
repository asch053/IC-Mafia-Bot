# game/roles.py
class GameRole:
    def __init__(self, name, alignment, description, short_description, abilities=None, uses=None, win_condition=None, investigate_result=None, is_night_immune=False, night_priority=99):
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

    def __str__(self):
        return self.name

    def to_dict(self):
        return {
            "name": self.name,
            "alignment": self.alignment,
            "description": self.description,
            "short_description": self.short_description,
            "abilities": self.abilities,
            "uses": self.uses,
            "win_condition": self.win_condition,
            "investigate_result": self.investigate_result,  # Optional field for investigative roles
            "is_night_immune": self.is_night_immune,  # For night immune characters (i.e. original GF + SK)
            "night_priority": self.night_priority
        }
# --- Specific Role Classes ---

class TownInvestigative(GameRole):
    """Base class for Town Investigative roles (Cop, etc.)."""
    def __init__(self, name, **kwargs):
        super().__init__(name, "Town", **kwargs)

class TownProtective(GameRole):
    """Base class for Town Protective roles (Doctor, etc.)."""
    def __init__(self, name, **kwargs):
        super().__init__(name, "Town", **kwargs)

class TownKilling(GameRole):
    """Base class for Town Killing roles."""
    def __init__(self, name, **kwargs):
        super().__init__(name, "Town", **kwargs)

class MafiaKilling(GameRole):
    """Base class for Mafia Killing roles (Godfather, etc.)."""
    def __init__(self, name, **kwargs):
        super().__init__(name, "Mafia", **kwargs)

class MafiaSupport(GameRole):
    """Base class for Mafia Support roles."""
    def __init__(self, name, **kwargs):
        super().__init__(name, "Mafia", **kwargs)

class NeutralKilling(GameRole):
    """Base class for Neutral Killing roles."""
    def __init__(self, name, **kwargs):
        super().__init__(name, "Serial Killer", **kwargs)

class NeutralEvil(GameRole):
    """Base class for Neutral Evil roles."""
    def __init__(self, name, **kwargs):
        super().__init__(name, "Jester", **kwargs)

class NeutralRoyale(GameRole):
    """Base class for Neutral Royale roles."""
    def __init__(self, name, **kwargs):
        super().__init__(name, "Vigilante", **kwargs)

# --- Specific Role Instances (Examples) ---

def create_town_cop_role():
    """Creates an instance of the Town Cop role."""
    return TownInvestigative(
        name="Town Cop",
        description="You are town alligned and can investigates one player each night to learn their alignment.\n Use _investigate player-name_ during the night phase in this DM with the bot to investigate your chosen player.\n Results will be sent as soon as day phase starts. Use them wisely.\n During the day you can use _/vote player-name_ in the voting channel to cast your vote on who should be lynched for that day.\n You win when all mob and the SK are dead",
        short_description="Can investigates one player each night to learn their alignment.",
        abilities={"investigate": "Learn a player's alignment (Town/Mafia/Neutral)."}
    )

def create_town_doctor_role():
    """Creates an instance of the Town Doctor role."""
    return TownProtective(
        name="Town Doctor",
        description="You are town alligned and can protect one player each night from being killed.\n Use _heal player-name_ during the night phase in this DM with the bot to heal your chosen player.\n During the day you can use _/vote player-name_ in the voting channel to cast your vote on who should be lynched for that day.\n You win when all mob and the SK are dead",
        short_description="Can heal one player each night",
        abilities={"heal": "Prevent a player from being killed."}
    )

def create_townie_role():
    """Creates an instance of the vanilla Townie role."""
    return TownKilling(
        name="Plain Townie",
        description="A regular member of the town.\n During the day you can use _/vote player-name_ in the voting channel to cast your vote on who should be lynched for that day.\n You win when all mob and the SK are dead",
        short_description="Normal member of town",
    )

def create_godfather_role():
    """Creates an instance of the Godfather role."""
    return MafiaKilling(
        name="Godfather",
        description="Chooses the Mafia's target each night. \n Use _/kill player-name_ in this DM with the bo to kill your chosen player. \n A seperate message will be sent with the identity of the other mob member. \n During the day you can use _/vote player-name_ in the voting channel to cast your vote on who should be lynched for that day.\n You win when there are more mob than other factions",
        short_description="Chooses the Mafia's target each night.",
        abilities={"kill": "Choose a player for the Mafia to kill."},
        investigate_result = {"Plain Townie": "Normal Member of town"},  # Godfather appears as Town to investigators
        is_night_immune = True, # Original godfather is night immune to kills
        night_priority = 4
    )

def create_mafioso_role():
    """Creates an instance of the Mafioso role."""
    return MafiaSupport(
        name="Mob Goon",
        description="A member of the Mafia.\n A seperate message will be sent with the identity of the other mob member.\n You will be promoted to Mob Godfather if the Mob Godfather dies.\n During the day you can use _/vote player-name_ in the voting channel to cast your vote on who should be lynched for that day.\n You win when there are more mob than other factions",
        short_description="Standard Mafia member.",
        night_priority = 4
    )
def create_mob_role_blocker_role():
    """Creates an instance of the Mafioso role."""
    return MafiaSupport(
        name="Mob Role Blocker",
        description= "A member of the Mafia.\n A seperate message will be sent with the identity of the other mob member.\n You can prevent one player from performing their night action each night. Use `/block player-name` during the night phase in this DM with the bot to block your chosen player.You will be promoted to Mob Godfather when no other mob are alive but you. If this happens you can use /block and /kill\n During the day you can use `/vote player-name` in the voting channel to cast your vote on who should be lynched for that day. \nYou win when there are more mob than other factions",
        short_description="Stops a player from acting.",
        abilities={"block": "Prevent a player from performing their night action."},
        night_priority = 4
    )

def create_serial_killer_role():
    """Creates an instance of the Serial Killer role."""
    return NeutralKilling(
        name="Serial Killer",
        description="Kills one player each night.\n Use _/kill player-name_ in this DM with the bot to kill your chosen player.\n During the day you can use _/vote player-name_ in the voting channel to cast your vote on who should be lynched for that day.\n You win when all mob and town players are dead",
        short_description="Kills one player each night.",
        abilities={"kill": "Choose a player to kill."},
        win_condition="Be the last player alive.",
        investigate_result = {"Plain Townie": "Normal Member of town"},  # Serial Killer appears as Town to investigators
        is_night_immune = True, # Serial killer is night immune to kills
        night_priority = 3
    )
def create_jester_role():
    """Creates an instance of the Jester role."""
    return NeutralEvil(
        name="Jester",
        description="Your goal is to get yourself lynched by the town. You have no night action.",
        short_description = "Gets lynched to win",
        win_condition = "Get yourself lynched"
    )
def create_town_role_blocker_role():
    """Creates an instance of the Town Role Blocker role."""
    return TownProtective(
        name="Town Role Blocker",
        description="You are town aligned and can prevent one player from performing their night action each night. Use `/block player-name` during the night phase in this DM with the bot to block your chosen player. During the day you can use `/vote player-name` in the voting channel to cast your vote on who should be lynched for that day. You win when all Mafia and the SK are dead.",
        short_description="Prevents one player from performing their night action.",
        abilities={"block": "Prevent a player from performing their night action."}
    )

def create_vigilante_role():
    """Create an instance of a neutral vigilante role for battle royales"""
    return NeutralRoyale(
        name="Vigilante",
        description="You can kill one player each night. Use `/kill player-name` in this DM with the bot to kill your chosen player. You win when all other factions are dead.",
        short_description="Kills one player each night.",
        abilities={"kill": "Choose a player to kill."},
        win_condition="Be the last player alive.",
        is_night_immune=False  # Vigilante is not night immune to kills
    )

# --- Role Setup Function ---
def get_role_instance(role_name):
    """Returns an instance of the specified role class."""
    role_mapping = {
        "Town Cop": create_town_cop_role,
        "Town Doctor": create_town_doctor_role,
        "Godfather": create_godfather_role,
        "Mob Goon": create_mafioso_role,  
        "Mob Role Blocker": create_mob_role_blocker_role,
        "Plain Townie": create_townie_role,
        "Town Role Blocker": create_town_role_blocker_role,
        "Jester": create_jester_role,
        "Serial Killer": create_serial_killer_role,
        "Vigilante": create_vigilante_role
        # Add other roles here
    }
    role_creation_function = role_mapping.get(role_name)
    if role_creation_function:
      return role_creation_function()
    return None