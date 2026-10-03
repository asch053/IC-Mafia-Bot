# game/narration.py
"""
High-Level Story Narration Manager.

Responsibilities:
1. Event Collection (`add_event`):
   - Accumulates mechanical events (kills, saves, blocks, investigations, lynches, promotions)
     as they occur throughout each day and night phase.
2. Story Orchestration (`construct_story`):
   - Formats the phase header (e.g. `**--- Night 1 ---**`).
   - Delegates story creation to the Gemini AI storyteller (`game.narration_ai`), supplying
     recent narrative history (pruned to the last 3 chapters) and the active game state.
   - Gracefully falls back to the deterministic static storyteller (`game.narration_static`)
     if the AI is disabled ("No Story"), rate-limited, or encounters network exceptions.
3. Long-Term Narrative Memory (`story_history`):
   - Retains the official chronicle of all generated chapters for phase-to-phase continuity
     and for the permanent game log file.
"""

import logging
import game.narration_ai as ai_storyteller
import game.narration_static as static_storyteller

logger = logging.getLogger('discord')


class NarrationManager:
    """
    Collects phase events and coordinates AI vs. static fallback storytelling.
    Manages long-term narrative history for continuity across chapters.
    """

    def __init__(self):
        self.events = []        # Events queued during the active phase
        self.header = ""        # Markdown header string for the current phase
        self.story_history = [] # Chronological archive of all finalized story chapters
        logger.info("NarrationManager initialized.")

    def add_event(self, event_type: str, **details):
        """
        Appends a new mechanical game event to the current phase queue.

        Args:
            event_type (str): Key matching known event types ('kill', 'save', 'block', 'lynch', etc.).
            **details: Arbitrary metadata (victim, killer, healer, details, etc.).
        """
        event = {'type': event_type, **details}
        self.events.append(event)
        logger.info(f"Narration event added: {event_type}")

    def get_full_story_log(self) -> str:
        """
        Returns the concatenated chronicle of all stories told so far.
        Saved to disk by the engine at game completion.
        """
        if not self.story_history:
            return "No stories were generated this game."
        return "\n\n" + "=" * 40 + "\n\n".join(self.story_history) + "\n\n" + "=" * 40

    def clear(self):
        """Resets the event queue and phase header at the start of each new phase."""
        self.events.clear()
        self.header = ""
        logger.info("Narration events cleared.")

    async def construct_story(self, game_state: dict) -> str | None:
        """
        Orchestrates narrative chapter generation for the completed phase.

        Pipeline:
        1. Formats phase header (e.g. `**--- Day 1 ---**`).
        2. If `story_type` != "No Story", invokes Gemini AI with pruned history (last 3 chapters).
        3. If AI fails, throws, or is disabled, falls back to the static storyteller.
        4. Saves the finalized story chapter into `self.story_history`.

        Args:
            game_state (dict): State dictionary containing phase, number, living players,
                               game type, and story theme.

        Returns:
            str | None: Complete story chapter text, or None if generation failed completely.
        """
        # 1. Format the phase header
        if game_state.get('phase'):
            phase_name = str(game_state['phase']).capitalize()
            phase_num = game_state.get('number', "")
            if game_state.get('phase') in ["night", "day"]:
                self.header = f"**--- {phase_name} {phase_num} ---**"
            else:
                self.header = f"**--- {phase_name} ---**"
        else:
            self.header = "**--- Phase Update ---**"

        final_story = None

        # 2. Attempt AI story generation (skipped if theme is "No Story")
        logger.info("Attempting to generate story with AI storyteller...")
        if game_state.get('story_type', 'No Story') == "No Story":
            logger.info("Narration type set to 'No Story'. Skipping AI generation.")
            ai_story = None
        else:
            # Pass only the last 3 stories to prevent prompt bloat and keep context focused
            pruned_history = self.story_history[-3:] if self.story_history else []
            ai_story = await ai_storyteller.generate_story(
                game_state,
                self.events,
                pruned_history
            )

        if ai_story:
            # AI story generation succeeded
            final_story = f"{self.header}\n{ai_story}"
        else:
            # 3. Fallback to deterministic static narration with active theme
            logger.warning("AI story generation failed or was bypassed. Falling back to static storyteller.")
            final_story = static_storyteller.generate_story(
                self.header,
                self.events,
                story_type=game_state.get('story_type', 'Classic Mafia')
            )

        # 4. Save to narrative memory for future chapters and log exports
        if final_story:
            self.story_history.append(final_story)

        return final_story