import logging
# NEW: Import both of our storyteller specialists
import game.narration_ai as ai_storyteller
import game.narration_static as static_storyteller

logger = logging.getLogger('discord')

class NarrationManager:
    """
    Collects events and orchestrates story generation by delegating to a storyteller.
    """
    def __init__(self):
        self.events = []
        self.header = ""

    def add_event(self, event_type: str, **details):
        """Adds a new event to the list."""
        event = {'type': event_type, **details}
        self.events.append(event)
        logger.info(f"Narration event added: {event_type}")

    def clear(self):
        """Clears all events for the next phase."""
        self.events.clear()
        self.header = ""
        logger.info("Narration events cleared.")

    async def construct_story(self, game_state: dict) -> str | None:
        """
        Builds the final story. It first tries to generate a story using the AI.
        If the AI fails, it falls back to the static storyteller.
        """
        self.header = f"**--- {game_state['phase'].capitalize()} {game_state['number']} ---**"
        
        # --- AI STORY GENERATION ATTEMPT ---
        logger.info("Attempting to generate story with AI storyteller...")
        # Delegate the creative writing to our AI specialist
        ai_story = await ai_storyteller.generate_story(game_state, self.events)

        if ai_story:
            # Success! Return the AI-generated story.
            return f"{self.header}\n{ai_story}"
        
        # --- FALLBACK TO STATIC STORY ---
        logger.warning("AI story generation failed. Falling back to static storyteller.")
        
        # Delegate the fallback story generation to our static specialist.
        static_story = static_storyteller.generate_story(self.header, self.events)
        
        return static_story

