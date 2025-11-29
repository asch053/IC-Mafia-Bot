import logging

# Get the same logger instance as in the main bot file
logger = logging.getLogger('discord')

class NarrationManager:
    """
    Collects events throughout a game phase and constructs a narrative story from them.
    """
    def __init__(self):
        """Initializes the NarrationManager with an empty list of events."""
        self.events = [] # List to store events for the current phase
        self.story_history = [] # To keep track of past stories to be stored for future analysis
        logger.info("NarrationManager initialized.")

    def add_event(self, event_type: str, **details):
        """Adds a new event to the list using a flat structure."""
        event = {'type': event_type, **details}
        self.events.append(event)
        logger.info(f"Narration event added: {event_type}\nEvent: {event}")

    def get_full_story_log(self) -> str:
        """
        NEW: Returns the complete history of all stories told in the game so far.
        This is perfect for saving to a file at the end of the game.
        """
        if not self.story_history:
            return "No stories were generated this game."
        
        return "\n\n" + "="*40 + "\n\n".join(self.story_history) + "\n\n" + "="*40

    def clear(self):
        """Clears all events, typically after a story has been told."""
        self.events.clear()
        logger.info("Narration events cleared.")

    def construct_story(self, current_phase: str, number: int) -> str | None:
        """Builds the final story string from the recorded events."""
        logger.info("Constructing the narrative story.")
        if not self.events:
            logger.info("No events to construct a story from.")
            return None
        if current_phase.lower() == "pre-day":
            phase = "night"
        elif current_phase.lower() == "pre-night":
            phase = "day"
        else:
            phase = current_phase.lower()
        story_parts = [f"**--- {phase.capitalize()} {number} ---**"]
        logger.info(f"Starting story construction for phase {phase} {number} with {len(self.events)} events.\n\nEvents: {self.events}")
        for event in self.events:
            story_part = self._generate_story_part(event)
            logger.info(f"Generated story part: {story_part}")
            if story_part:
                story_parts.append(story_part)
        # 4. NEW: Save to history!
        final_story = "\n\n".join(story_parts) if len(story_parts) > 1 else None
        if final_story:
            self.story_history.append(final_story)
            logger.info(f"Story history updated. Total stories so far: {len(self.story_history)}")
        logger.info("Narrative story constructed.\n" + "\n".join(story_parts))
        return "\n\n".join(story_parts) if len(story_parts) > 1 else None

    def _generate_story_part(self, event: dict) -> str | None:
        """Generates a single paragraph of the story for a given event."""
        event_type = event.get('type')
        logger.info(f"Generating story part for event type: {event_type} with details: {event}")

        # --- Night Events ---
        if event_type == 'no_actions':
            logger.info("Generating no actions event story part.")
            return "The night was eerily quiet. No one seemed to make a move."
        
        if event_type == 'block':
            target = event.get('target')
            logger.info(f"Generating block event story part for target: {target}")
            if not target or not target.role: return None
            logger.info(f"Target role abilities: {target.role.abilities}")
            if not target.role.abilities: return None
            return f"A shadowy figure paid a visit to the **{target.role.name}** last night, preventing them from performing their action."
        
        if event_type == 'block_missed':
            target = event.get('target')
            blocker = event.get('blocker')
            logger.info(f"Generating block missed event story part for target: {target} and blocker: {blocker}")
            if not target or not target.role or not blocker: return None
            logger.info(f"Target role abilities: {target.role.abilities}")
            if not target.role.abilities: return None
            return f"A shadowy figure stalked their target.\n However, when they managed to catch up to them, they had already completed their night activities and had returned home."
        
        if event_type == 'block_battle_royale':
            target = event.get('target')
            blocker = event.get('blocker')
            logger.info(f"Generating battle royale block event story part for target: {target} and blocker: {blocker}")
            if not target or not target.role or not blocker: return None
            return f"In the chaos of the night, **{target.display_name}** was ambushed by **{blocker.display_name}** and unable to act."
        
        if event_type == 'block_missed_royale':
            target = event.get('target')
            blocker = event.get('blocker')
            logger.info(f"Generating battle royale block missed event story part for target: {target} and blocker: {blocker}")
            if not target or not target.role or not blocker: return None
            return f"**{blocker.display_name}** attempted to ambush **{target.display_name}**, but they had already completed their actions and returned home to safety."

        if event_type == 'save':
            victim = event.get('victim')
            logger.info(f"Generating save event story part for victim: {victim}")
            if not victim: return None
            return (
                f"Someone launched a deadly attack on **{victim.display_name}** in the dead of night... "
                f"but a Doctor was standing guard and saved their life!"
            )
        
        if event_type == 'save_battle_royale':
            victim = event.get('victim')
            killer = event.get('killer')
            healer = event.get('healer')
            logger.info(f"Generating battle royale save event story part for victim: {victim}, killer: {killer}, healer: {healer}")
            if not victim or not killer or not healer: return None
            return (
                f"Amidst the turmoil of the night, **{victim.display_name}** was targeted for elimination by {killer.display_name}... "
                f"but {healer.display_name} proved to be a kind and quick-thinking ally who intervened and saved them!"
            )

        if event_type == 'kill_immune':
            victim = event.get('target')
            logger.info(f"Generating immune kill event story part for victim: {victim}")
            if not victim: return None
            return f"An assailant ambushed **{victim.role.name}** in the dark, but their target was unfazed. The attack had no effect!"

        if event_type == 'kill':
            victim = event.get('victim')
            logger.info(f"Generating kill event story part for victim: {victim}")
            if not victim or not victim.role: return None
            return (
                    f"A scream pierced the night! When the sun rose, the body of **{victim.display_name}** was found. "
                    f"They were the **{victim.role.alignment} - {victim.role.name}**."
                )
        if event_type == 'kill_battle_royale':
            victim = event.get('victim')
            killer = event.get('killer')
            logger.info(f"Generating battle royale kill event story part for victim: {victim} and killer: {killer}")
            if not victim or not killer: return None
            return (
                    f"A gunshot rang out in the night! When the sun rose, the body of **{victim.display_name}** was found. "
                    f"They were killed by **{killer.display_name}**."
                )
        
        if event_type == 'kill_missed_battle_royale':
            killer = event.get('killer')
            victim = event.get('target')
            logger.info(f"Generating missed kill event story part for killer: {killer} and victim: {victim}")
            if not killer or not victim: return None
            return f"An attempt on **{victim.display_name}**'s life by **{killer.display_name}** failed to materialize as the killer was already dead."

        if event_type == 'investigate':
            logger.info("Generating investigate event story part.")
            return None #"A lone figure was seen snooping around someone's house, trying to uncover secrets."

        if event_type == 'promotion':
            logger.info("Generating promotion event story part.")
            return "In the mafia underground, a power vacuum has been filled. A new leader has risen to command the night's dark deeds."

        # --- Day Events ---
        if event_type == 'lynch':
            victims = event.get('victims', [])
            details = event.get('details', {})
            logger.info(f"Generating lynch event story part for victims: {victims} with details: {details}")
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
    

        
       # --- Fallback for unknown events ---
        return f"A mysterious event ({event_type}) occurred."