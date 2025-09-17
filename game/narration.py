import logging

# Get the same logger instance as in the main bot file
logger = logging.getLogger('discord')

class NarrationManager:
    """
    Collects events throughout a game phase and constructs a narrative story from them.
    """
    def __init__(self):
        """Initializes the NarrationManager with an empty list of events."""
        self.events = []

    def add_event(self, event_type: str, **details):
        """Adds a new event to the list using a flat structure."""
        event = {'type': event_type, **details}
        self.events.append(event)
        logger.info(f"Narration event added: {event_type}")

    def clear(self):
        """Clears all events, typically after a story has been told."""
        self.events.clear()
        logger.info("Narration events cleared.")

    def construct_story(self, phase: str, number: int) -> str | None:
        """Builds the final story string from the recorded events."""
        logger.info("Constructing the narrative story.")
        if not self.events:
            logger.info("No events to construct a story from.")
            return None

        story_parts = [f"**--- {phase.capitalize()} {number} ---**"]
        
        for event in self.events:
            story_part = self._generate_story_part(event)
            if story_part:
                story_parts.append(story_part)
                
        logger.info("Narrative story constructed.")
        return "\n\n".join(story_parts) if len(story_parts) > 1 else None

    def _generate_story_part(self, event: dict) -> str | None:
        """Generates a single paragraph of the story for a given event."""
        event_type = event.get('type')

        # --- Night Events ---
        if event_type == 'no_actions':
            return "The night was eerily quiet. No one seemed to make a move."

        if event_type == 'block':
            target = event.get('target')
            if not target or not target.role: return None
            return f"A shadowy figure paid a visit to the **{target.role.name}** last night, preventing them from performing their action."
        
        if event_type == 'block_missed':
            target = event.get('target')
            blocker = event.get('blocker')
            if not target or not target.role or not blocker: return None
            return f"A shadowy figure stalked the **{target.role.name}**.\n However, when they managed to catch up to them, they had already completed their night activities and had returned home."
        
        if event_type == 'battle_royale_block':
            target = event.get('target')
            blocker = event.get('blocker')
            if not target or not target.role or not blocker: return None
            return f"In the chaos of the night, **{target.display_name}** was ambushed by **{blocker.display_name}** and unable to act."
        
        if event_type == 'block_missed_royale':
            target = event.get('target')
            blocker = event.get('blocker')
            if not target or not target.role or not blocker: return None
            return f"**{blocker.display_name}** attempted to ambush **{target.display_name}**, but they had already completed their actions and returned home to safety."

        if event_type == 'save':
            victim = event.get('victim')
            if not victim: return None
            return (
                f"Someone launched a deadly attack on **{victim.display_name}** in the dead of night... "
                f"but a Doctor was standing guard and saved their life!"
            )
        
        if event_type == 'battle_royale_save':
            victim = event.get('victim')
            killer = event.get('killer')
            healer = event.get('healer')
            if not victim or not killer or not healer: return None
            return (
                f"Amidst the turmoil of the night, **{victim.display_name}** was targeted for elimination by {killer.display_name}... "
                f"but {healer.display_name} proved to be a kind and quick-thinking ally who intervened and saved them!"
            )

        if event_type == 'immune_kill':
            victim = event.get('victim')
            if not victim: return None
            return f"An assailant ambushed **{victim.role.name}** in the dark, but their target was unfazed. The attack had no effect!"

        if event_type == 'kill':
            victim = event.get('victim')
            if not victim or not victim.role: return None
            return (
                    f"A scream pierced the night! When the sun rose, the body of **{victim.display_name}** was found. "
                    f"They were the **{victim.role.alignment} - {victim.role.name}**."
                )
        if event_type == 'kill_battle_royale':
            victim = event.get('victim')
            killer = event.get('killer')
            if not victim or not killer: return None
            return (
                    f"A gunshot rang out in the night! When the sun rose, the body of **{victim.display_name}** was found. "
                    f"They were killed by **{killer.display_name}**."
                )

        if event_type == 'investigate':
            return #"A lone figure was seen snooping around someone's house, trying to uncover secrets."

        if event_type == 'promotion':
            return "In the mafia underground, a power vacuum has been filled. A new leader has risen to command the night's dark deeds."

        # --- Day Events ---
        if event_type == 'lynch':
            victims = event.get('victims', [])
            details = event.get('details', {})
            if not victims: return None

            if len(victims) == 1:
                victim = victims[0]
                voters = details.get(victim, [])
                voter_names = ", ".join([f"**{v.display_name}**" for v in voters])
                if not voter_names: voter_names = "an angry mob"
                
                return (
                    f"The town square fell silent as the crowd, led by {voter_names}, pointed their fingers at one individual. A verdict had been reached.\n\n"
                    f"**{victim.display_name}** was dragged into the middle of the town square and strung up. They were the **{victim.role.alignment} - {victim.role.name}**."
                )
            else:
                victim_names = [f"**{v.display_name}** (the **{v.role.alignment} - {v.role.name}**)" for v in victims]
                return (
                    f"A heated argument resulted in a shocking outcome! The town couldn't decide on a single target, and in the ensuing chaos, a mob turned on multiple people.\n\n"
                    f"**{', '.join(victim_names)}** have all been lynched by the town!"
                )
    
        if event_type == 'no_lynch':
            return "The sun sets on a tense but indecisive town. With no consensus, no one was lynched."

        # Inactive player killed story
        if event_type == 'inactivity_kill':
            victims = event.get('victims', [])
            if not victims: return None
            victim_names = ", ".join([f"**{v.display_name}**" for v in victims])
            return f"The town has no patience for silence. For failing to participate in the day's crucial vote, {victim_names} is/are executed for inactivity!"
          
        # --- Game End Events ---
        if event_type == 'jester_win':
            victim = event.get('victim')
            if not victim: return None
            return (
                f"**{victim.display_name}** cackles madly as the town realizes its mistake. "
                f"By lynching the Jester, the town has signed its own death warrant! The Jester wins!"
            )
        
        if event_type == 'game_over':
            winner = event.get('winner')
            if not winner: return None
            if winner == 'draw':
                return "\n**The game is over! The game has ended in a draw! No one wins!**"
            else:
                return f"\n**The game is over! The {winner} has won!**"
    

        
        return None