# utils/narration.py
import logging

logger = logging.getLogger('discord')

class NarrationManager:
    """Collects game events and constructs a narrative story."""

    def __init__(self):
        self.events = []

    def add_event(self, event_type, **details):
        """
        Adds a single game event to the list.
        'details' is a dictionary containing relevant objects.
        """
        self.events.append({"type": event_type, "details": details})
        logger.info(f"Narration event added: {event_type}")

    def clear(self):
        """Clears all recorded events for the next phase."""
        self.events = []

    def construct_story(self, current_phase, phase_number):
        """Builds the final story string from the recorded events."""
        logger.info("Constructing the narrative story.")
        if not self.events:
            logger.info("No events to construct a story from.")
            return None # Return nothing if there are no events
        # Construct the story from the events logged so far
        story_parts = []
        story_parts.append(f"======={current_phase} {phase_number}=========")
        for event in self.events:
            story_part = self._generate_story_part(event)
            if story_part:
                story_parts.append(story_part)
        logger.info(f"Narrative story constructed.\n{story_parts}")
        return "\n\n".join(story_parts) if story_parts else None

    def _generate_story_part(self, event):
        """Generates the text for a single event using simple templates."""
        event_type = event["type"]
        details = event["details"]

        # --- Lynch Events ---
        if event_type == 'lynch':
            victims = details.get('victims', [])
            lynch_details = details.get('details', {})
            if not victims: return None
            logger.info(f"Generating lynch story for {victims} + {lynch_details}")
            if len(victims) == 1:
                victim = victims[0]
                voters = lynch_details.get(victim, [])
                voter_names = ", ".join([v.display_name for v in voters])
                return (
                    f"The town square fell silent as the crowd pointed their fingers at one individual. A verdict had been reached."
                    f"**{victim.display_name}** was dragged out into the middle of the town square and strung up.\n"
                    f"**{victim.display_name}, ({victim.role.alignment} - {victim.role.name}) has been lynched.**"
                )
            else:
                victim_names = [f"**{v.display_name}** (the **{v.role.alignment} - {v.role.name}**)" for v in victims]
                return (
                    f"A heated argument resulted in a shocking outcome! The town couldn't decide on a single target, "
                    f"and in the ensuing chaos, a mob turned on multiple people.\n"
                    f"**{', '.join(victim_names)}** have all been lynched by the town!"
                )

        if event_type == 'no_lynch':
            logger.info("No Lynch")
            return "The sun sets on a tense but indecisive town. No votes were cast, and no one was lynched."

        if event_type == 'no_lynch_tie':
            logger.info("No Lynch -> Tie")
            return "The town was divided. With the votes tied, the crowd dispersed in a stalemate. No one was lynched."

        # --- Night Action Events ---
        if event_type == 'no_actions':
            logger.info("No actions logged")
            return "It was a quiet night. Nothing seemed to happen."
            
        if event_type == 'kill':
            killer = details.get('killer')
            victim = details.get('victim')
            logger.info(f"Generating kill story for {killer} + {victim}")
            return f"Under the cover of darkness, a figure strikes! **{victim.display_name}** has been found dead, killed by the **{killer.role.name}**!"
        
        if event_type == 'heal':
            doctor = details.get('doctor')
            patient = details.get('patient')
            healer_name = doctor.display_name if doctor else "a mysterious figure"
            logger.info(f"Generating heal story for {healer_name} + {patient}")
            return f"A doctor rushed to the aid of **{patient.display_name}**, saving them from a grisly fate."

        if event_type == 'block':
            blocker = details.get('blocker')
            target = details.get('target')
            logger.info(f"Generating block story for {blocker} + {target}")
            return f"**{blocker.display_name}** paid a visit to **{target.display_name}** last night, preventing them from performing their action."

        # --- Game State Events ---
        if event_type == 'promotion':
            promoted_player = details.get('promoted_player')
            logger.info(f"Generating promotion story for {promoted_player}")
            return "With the death of the latest head of the Mafia , a power vacuum has formed.\nWho will step up to become the new Godfather?"

        if event_type == 'jester_win':
            victim = details.get('victim')
            logger.info(f"Generating jester win story for {victim}")
            return (
                f"As the town lynched **{victim.display_name}**, a wicked grin spread across their face. "
                f"They were the **Jester**! Their goal was to be executed, and the town has foolishly granted their wish."
            )

        if event_type == 'game_over':
            winner = details.get('winner', 'An unknown force')
            logger.info(f"Generating game over story for {winner}")
            return f"The game has ended. The **{winner}** team is victorious!"
        
        # This is for actions that have no public story, like an investigation
        if event_type == 'investigate':
            logger.info("Investigation action captured, but currently not added to story")
            return None
        logger.critical(f"Event type for {event} not found, returning nothing")
        return None
