import logging
import game.narration_ai as ai_storyteller
import game.narration_static as static_storyteller

logger = logging.getLogger('discord')

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

    def add_event(self, event_type: str, **details):
        """Adds a new event to the list."""
        event = {'type': event_type, **details}
        self.events.append(event)
        logger.info(f"Narration event added: {event_type}")
    
    def get_full_story_log(self) -> str:
        """
        Returns the complete history of all stories told in the game so far.
        Used by the engine to save the game log file.
        """
        if not self.story_history:
            return "No stories were generated this game."
        
        return "\n\n" + "="*40 + "\n\n".join(self.story_history) + "\n\n" + "="*40

    def clear(self):
        """Clears all events for the next phase."""
        self.events.clear()
        self.header = ""
        logger.info("Narration events cleared.")

    async def construct_story(self, game_state: dict) -> str | None:
        """
        Builds the final story. 
        1. Tries to generate a story using the AI (passing history).
        2. Falls back to static if AI fails.
        3. Saves the result to history for next time.
        """
        self.header = f"**--- {game_state['phase'].capitalize()} {game_state['number']} ---**"
        final_story = None
        
        # --- 1. AI STORY GENERATION ATTEMPT ---
        logger.info("Attempting to generate story with AI storyteller...")
        
        # PASS HISTORY HERE so the AI knows the context!
        ai_story = await ai_storyteller.generate_story(
            game_state, 
            self.events, 
            self.story_history
        )

        if ai_story:
            # Success! Use the AI story.
            final_story = f"{self.header}\n{ai_story}"
        else:
            # --- 2. FALLBACK TO STATIC STORY ---
            logger.warning("AI story generation failed. Falling back to static storyteller.")
            final_story = static_storyteller.generate_story(self.header, self.events)
        
        # --- 3. SAVE TO MEMORY ---
        # This is the critical step for both the Log File AND the AI's future context
        if final_story:
            self.story_history.append(final_story)
            
        return final_story