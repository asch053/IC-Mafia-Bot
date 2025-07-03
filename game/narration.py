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
        logger.info(f"Narration event added: {event_type} with details {details}")
    def clear(self):
        """Clears all recorded events for the next phase."""
        self.events = []
    def construct_story(self):
        """Builds the final story string from the recorded events."""
        if not self.events:
            return None # Return nothing if there are no events
        story_parts = []
        for event in self.events:
            story_part = self._generate_story_part(event)
            if story_part:
                story_parts.append(story_part) 
        return "\n\n".join(story_parts) if story_parts else None

    def _generate_story_part(self, event):
        """Generates the text for a single event. (Phase 1: Simple Templates)"""
        event_type = event["type"]
        details = event["details"]
        if event_type == 'lynch':
            victims = details.get('victims', [])
            lynch_details = details.get('details', {})
            if not victims:
                return None
            # Handle single lynch
            if len(victims) == 1:
                victim = victims[0]
                voters = lynch_details.get(victim, [])
                voter_names = ", ".join([v.display_name for v in voters])
                story = (
                    f"The town square fell silent as the crowd, led by **{voter_names}**, "
                    f"pointed their fingers at one individual. A verdict was reached. "
                    f"**{victim.display_name}** has been lynched by the town.\n"
                    f"Flipping over their role card, the town discovered they were the **{victim.role.name}** ({victim.role.alignment})."
                )
                return story
            # Handle multiple lynch (tie)
            else:
                victim_names = [f"**{v.display_name}** (the **{v.role.name}**)" for v in victims]
                story = (
                    f"A heated argument resulted in a shocking outcome! The town couldn't decide on a single target, "
                    f"and in the ensuing chaos, a mob turned on multiple people.\n"
                    f"**{', '.join(victim_names)}** have all been lynched by the town!"
                )
                return story
        if event_type == 'no_lynch':
            return "The sun sets on a tense but indecisive town. No votes were cast, and no one was lynched."
        if event_type == 'no_actions':
            return "It was a quiet night. Nothing seemed to happen."
        if event_type == 'game_over':
            winner = details.get('winner', 'An unknown force')
            return f"The game has ended. The **{winner}** team is victorious!"
        # ... add more event types here (kill, heal, etc.) ...
        
        return None
