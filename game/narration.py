import logging


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class NarrationManager:
    """
    Collects events and orchestrates story generation by delegating to a storyteller.
    Manages the long-term memory (history) of the game's narrative.
    """
    def __init__(self):
        self.events = []
        self.header = ""
        # The official record of all previous story chapters
        self.story_history = [] 
        logger.info("NarrationManager initialized.")