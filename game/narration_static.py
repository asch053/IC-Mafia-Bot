# game/narration_static.py
"""
Static Fallback Storyteller Subsystem.

Responsibilities:
1. Deterministic Story Generation (`generate_story`):
   - Acts as the primary fallback narrator when AI generation is unavailable, disabled ("No Story"),
     or fails API quotas/network calls.
   - Converts queued mechanical events (kills, blocks, saves, lynches, promotions) into clear,
     thematic narrative prose.
2. Thematic Adaptation (`_generate_static_story_part`):
   - Rom Com Theme: Strictly non-lethal, romantic comedy stakes.
     Replaces murders, bodies, and executions with breakups, ghosting, being dumped,
     wingman saves, and awkward third-wheeling.
   - Office Restructuring Theme: Strictly non-lethal, corporate downsizing satire.
     Replaces murders, bodies, and executions with layoffs, terminations, severance packages,
     HR contract shields, and IT permission revokations.
   - Classic & Other Themes: Dramatic murder mystery flavor with Fog of War anonymity.
"""

import logging

logger = logging.getLogger('discord')


def _get_role_title(player) -> str:
    """
    Helper function resolving the public role label for eliminated players.
    
    Returns:
        str: Format `"{Alignment} - {Display Skin Name}"` (e.g., "Town - Relationship Detective").
    """
    if not player or not getattr(player, 'role', None):
        return "Unknown"
    role_disp = getattr(player.role, 'display_name', None) or player.role.name
    return f"{player.role.alignment} - {role_disp}"


def generate_story(header: str, events: list, story_type: str = "Classic Mafia") -> str:
    """
    Generates a pre-written, thematic narrative summary from a list of mechanical events.

    Args:
        header (str): Markdown header for the phase (e.g., "**--- Day 2 ---**").
        events (list): List of event dictionaries collected by NarrationManager during the phase.
        story_type (str): Active narrative theme (e.g. "Rom Com", "Office Restructuring", "Classic Mafia").

    Returns:
        str: Complete phase story formatted in Discord Markdown.
    """
    logger.info("Generating story using static storyteller...")

    # Case: No significant events occurred during the phase
    if not events:
        if story_type == "Rom Com":
            return f"{header}\nThe evening was quiet. Everyone was busy scrolling dating apps or watching reality TV alone."
        elif story_type == "Office Restructuring":
            return f"{header}\nThe office was quiet after hours. Just the hum of fluorescent lights and empty cubicles."
        else:
            return f"{header}\nThe night passed in an unsettling silence. Not a soul stirred."

    # Group kill events by victim to handle multiple attackers on a single player
    aggregated_events = []
    kill_events_by_victim = {}

    for event in events:
        etype = event.get('type')
        if etype in ['kill_battle_royale', 'kill']:
            victim = event.get('victim')
            v_name = getattr(victim, 'display_name', str(victim)) if victim else None
            if v_name:
                if v_name not in kill_events_by_victim:
                    combined = dict(event)
                    all_killers = []
                    if event.get('killers'):
                        all_killers.extend(event['killers'])
                    elif event.get('killer'):
                        all_killers.append(event['killer'])
                    combined['all_killers'] = all_killers
                    kill_events_by_victim[v_name] = combined
                    aggregated_events.append(combined)
                else:
                    combined = kill_events_by_victim[v_name]
                    if event.get('killers'):
                        for k in event['killers']:
                            if k not in combined['all_killers']:
                                combined['all_killers'].append(k)
                    elif event.get('killer'):
                        if event['killer'] not in combined['all_killers']:
                            combined['all_killers'].append(event['killer'])
                continue
        aggregated_events.append(event)

    # Process each event sequentially
    story_parts = [header]
    for event in aggregated_events:
        story_part = _generate_static_story_part(event, story_type=story_type)
        if story_part:
            story_parts.append(story_part)

    return "\n".join(story_parts)


def _generate_static_story_part(event: dict, story_type: str = "Classic Mafia") -> str | None:
    """
    Translates an individual mechanical event into a themed narrative sentence or paragraph.

    Args:
        event (dict): The event dictionary containing 'type' and contextual metadata (victim, killer, etc.).
        story_type (str): Active narrative theme.

    Returns:
        str | None: Themed narrative line, or None if the event generates no public text.
    """
    event_type = event.get('type')

    # =========================================================================
    # Night Events
    # =========================================================================

    # Event: No night actions were submitted by any player
    if event_type == 'no_actions':
        logger.info("Generating no actions event story part.")
        if story_type == "Rom Com":
            return "The evening was quiet. No bold moves were made on the dating scene."
        elif story_type == "Office Restructuring":
            return "No after-hours emails or sudden reorganizations occurred overnight."
        return "The night was eerily quiet. No one seemed to make a move."

    # Event: Successful roleblock in Classic mode (action thwarted, actor anonymous)
    if event_type == 'block':
        action_type = event.get('action_type', 'action')
        logger.info(f"Generating block event story part for action_type: {action_type}")
        if action_type == 'kill':
            if story_type == "Rom Com":
                return "A meddling friend intervened in the nick of time, stopping a cold breakup before someone's heart could be broken!"
            elif story_type == "Office Restructuring":
                return "An emergency intervention halted an after-hours termination in its tracks before an employee could be handed a pink slip!"
            return "A shadowy figure struck in the dark and thwarted an attempted murder before the killer could reach their mark."
        elif action_type == 'heal':
            if story_type == "Rom Com":
                return "An attempt to offer wingman advice and relationship support was intercepted and blocked before reaching its destination."
            elif story_type == "Office Restructuring":
                return "HR red tape obstructed an attempt to provide job security and severance protection overnight."
            return "A shadowy figure intercepted an attempt to deliver medical aid in the night, preventing protection from reaching its destination."
        elif action_type == 'investigate':
            logger.info("Investigation blocks are never shown in story generation.")
            return None
        elif action_type == 'block':
            if story_type == "Rom Com":
                return "An attempt to third-wheel and cockblock a date was intercepted and foiled before it could cause drama."
            elif story_type == "Office Restructuring":
                return "An attempt to stonewall a colleague's workflow was intercepted and stopped in the hallway."
            return "A shadowy figure's attempt to stalk and interfere with another citizen was intercepted and thwarted in the dark."
        else:
            if story_type == "Rom Com":
                return "A meddling friend third-wheeled a romantic move last night, preventing it from taking place."
            elif story_type == "Office Restructuring":
                return "IT support unexpectedly revoked system permissions and blocked an after-hours initiative from being carried out."
            return "A shadowy figure intervened in the night and thwarted an action before it could take effect."

    # Event: Roleblocker attempted block, but target had no action or already acted (no story emitted)
    if event_type in ['block_missed', 'block_missed_royale']:
        logger.info(f"Skipping story generation for missed block event: {event_type}")
        return None

    # Event: Battle Royale transparent roleblock (attacker and target named)
    if event_type == 'block_battle_royale':
        target = event.get('target')
        blocker = event.get('blocker')
        action_type = event.get('action_type', 'action')
        action_target = event.get('action_target')
        logger.info(f"Generating battle royale block event story part for target: {target} and blocker: {blocker}")
        if not target or not blocker: return None
        if action_type == 'investigate':
            logger.info("Investigation blocks are never shown in battle royale narration.")
            return None
        target_name = target.display_name
        blocker_name = blocker.display_name
        act_tgt_name = action_target.display_name if action_target else "their target"

        if action_type == 'kill':
            if story_type == "Rom Com":
                return f"In the middle of the mixer, **{blocker_name}** cut in and prevented **{target_name}** from dumping **{act_tgt_name}**!"
            elif story_type == "Office Restructuring":
                return f"In the hallway, **{blocker_name}** stepped in and stopped **{target_name}** from serving a pink slip to **{act_tgt_name}**!"
            return f"In the heat of battle, **{blocker_name}** ambushed **{target_name}** and prevented their deadly strike against **{act_tgt_name}**!"
        elif action_type == 'heal':
            if story_type == "Rom Com":
                return f"**{blocker_name}** cornered **{target_name}**, preventing them from offering emotional support to **{act_tgt_name}**!"
            elif story_type == "Office Restructuring":
                return f"**{blocker_name}** held up **{target_name}** in meetings, blocking them from aiding **{act_tgt_name}**!"
            return f"**{blocker_name}** intercepted **{target_name}**, stopping them from administering medical aid to **{act_tgt_name}**!"
        elif action_type == 'block':
            return f"**{blocker_name}** tackled **{target_name}**, shutting down their attempt to interfere with others!"
        else:
            return None

    # Event: Doctor protection save in Classic mode (killer anonymous)
    if event_type == 'save':
        victim = event.get('victim')
        logger.info(f"Generating save event story part for victim: {victim}")
        if not victim: return None
        if story_type == "Rom Com":
            return (
                f"Someone attempted to ruthlessly dump **{victim.display_name}** in the dead of night... "
                f"but a loyal Wingman was standing guard and saved their romantic prospects!"
            )
        elif story_type == "Office Restructuring":
            return (
                f"A termination notice was prepared for **{victim.display_name}** in the dead of night... "
                f"but HR Legal was standing guard and protected their employment!"
            )
        return (
            f"Someone launched a deadly attack on **{victim.display_name}** in the dead of night... "
            f"but a Doctor was standing guard and saved their life!"
        )

    # Event: Doctor protection save in Battle Royale mode (names public)
    if event_type == 'save_battle_royale':
        victim = event.get('victim')
        killer = event.get('killer')
        healer = event.get('healer')
        logger.info(f"Generating battle royale save event story part for victim: {victim}, killer: {killer}, healer: {healer}")
        if not victim or not killer or not healer: return None
        if story_type == "Rom Com":
            return (
                f"Amidst the drama of the mixer, **{victim.display_name}** was targeted for dumping by {killer.display_name}... "
                f"but {healer.display_name} proved to be an incredible wingman who intervened and saved them!"
            )
        elif story_type == "Office Restructuring":
            return (
                f"Amidst the restructuring turmoil, **{victim.display_name}** was targeted for layoff by {killer.display_name}... "
                f"but {healer.display_name} proved to be a loyal ally who intervened with budget approval and saved their job!"
            )
        return (
            f"Amidst the turmoil of the night, **{victim.display_name}** was targeted for elimination by {killer.display_name}... "
            f"but {healer.display_name} proved to be a kind and quick-thinking ally who intervened and saved them!"
        )

    # Event: Night kill attempted on an immune target (Godfather or Serial Killer)
    if event_type == 'kill_immune':
        victim = event.get('victim')
        logger.info(f"Generating immune kill event story part for victim: {victim}")
        if not victim or not getattr(victim, 'role', None): return None
        role_label = getattr(victim.role, 'display_name', None) or victim.role.name
        if story_type == "Rom Com":
            return f"An admirer tried to break **{victim.display_name}**'s ({role_label}) heart in the dark, but they were completely emotionally unavailable. The rejection had no effect!"
        elif story_type == "Office Restructuring":
            return f"Management attempted to lay off **{victim.display_name}** ({role_label}) in the dark, but their ironclad executive severance protected them. The termination had no effect!"
        return f"An assailant ambushed **{victim.display_name}** ({role_label}) in the dark, but their target was unfazed. The attack had no effect!"

    # Event: Successful night kill in Classic mode (killer anonymous)
    if event_type == 'kill':
        victim = event.get('victim')
        killers = event.get('all_killers') or event.get('killers') or ([event.get('killer')] if event.get('killer') else [])
        count = len(killers)
        logger.info(f"Generating kill event story part for victim: {victim}")
        if not victim: return None
        if story_type == "Rom Com":
            if count > 1:
                return (
                    f"The drama reached a boiling point! **{victim.display_name}** faced {count} devastating breakups in a single night and left the mixer. "
                    f"They were the **{_get_role_title(victim)}**."
                )
            return (
                f"A dramatic breakup shocked the singles scene! When the sun rose, **{victim.display_name}** was dumped and removed from the dating market. "
                f"They were the **{_get_role_title(victim)}**."
            )
        elif story_type == "Office Restructuring":
            if count > 1:
                return (
                    f"Downsizing reached unprecedented levels! **{victim.display_name}** was hit with {count} separate termination notices in a single night. "
                    f"They were the **{_get_role_title(victim)}**."
                )
            return (
                f"An urgent morning email arrived from Human Resources. **{victim.display_name}** has been laid off effective immediately and escorted from the office. "
                f"They were the **{_get_role_title(victim)}**."
            )
        if count > 1:
            return (
                f"A brutal ambush struck in the night! When the sun rose, the body of **{victim.display_name}** was discovered with evidence of {count} separate lethal attacks. "
                f"They were the **{_get_role_title(victim)}**."
            )
        return (
            f"A scream pierced the night! When the sun rose, the body of **{victim.display_name}** was found. "
            f"They were the **{_get_role_title(victim)}**."
        )

    # Event: Successful night kill in Battle Royale mode (killer named)
    if event_type == 'kill_battle_royale':
        victim = event.get('victim')
        killers = event.get('all_killers') or event.get('killers') or ([event.get('killer')] if event.get('killer') else [])
        logger.info(f"Generating battle royale kill event story part for victim: {victim} and killers: {killers}")
        if not victim or not killers: return None

        count = len(killers)
        if count == 1:
            killer_disp = f"**{killers[0].display_name}**"
        elif count == 2:
            killer_disp = f"**{killers[0].display_name}** and **{killers[1].display_name}**"
        else:
            killer_disp = ", ".join(f"**{k.display_name}**" for k in killers[:-1]) + f", and **{killers[-1].display_name}**"

        if story_type == "Rom Com":
            if count > 1:
                return (
                    f"Drama exploded across the mixer! **{victim.display_name}** was simultaneously dumped and ghosted by {count} suitors: {killer_disp}, leaving the dating scene in complete heartbreak."
                )
            return (
                f"Drama exploded across the mixer! **{victim.display_name}** was dumped and ghosted by {killer_disp} and left the dating scene."
            )
        elif story_type == "Office Restructuring":
            if count > 1:
                return (
                    f"Corporate politics claimed another casualty! In a coordinated strike by {count} colleagues ({killer_disp}), **{victim.display_name}** was abruptly fired and their badge access revoked."
                )
            return (
                f"Corporate politics claimed another casualty! **{victim.display_name}** was abruptly fired by {killer_disp} and their badge access revoked."
            )
        
        if count > 1:
            return (
                f"A chaotic clash erupted in the darkness! When the sun rose, the body of **{victim.display_name}** was found, overwhelmed by {count} separate attackers. They were killed by {killer_disp}."
            )
        return (
            f"A gunshot rang out in the night! When the sun rose, the body of **{victim.display_name}** was found. "
            f"They were killed by {killer_disp}."
        )

    # Event: Cop investigation (kept completely private in player DMs, no public story text)
    if event_type in ['investigate', 'investigate_royale']:
        logger.info(f"Generating {event_type} event story part (private DM only).")
        return None

    # Event: Mafia member promoted to Godfather status upon leader death
    if event_type == 'promotion':
        logger.info("Generating promotion event story part.")
        if story_type == "Rom Com":
            return "Among the heartbreakers, a new ringleader has taken charge of running the dating games."
        elif story_type == "Office Restructuring":
            return "In upper management, an emergency executive appointment took effect. A new Director of Restructuring has taken charge."
        return "In the mafia underground, a power vacuum has been filled. A new leader has risen to command the night's dark deeds."

    # =========================================================================
    # Day Events
    # =========================================================================

    # Event: Daytime player lynch
    if event_type == 'lynch':
        victims = event.get('victims', [])
        details = event.get('details', {})
        logger.info(f"Generating lynch event story part for victims: {victims} with details: {details}")
        if not victims: return None

        # Case 1: Single condemned player
        if len(victims) == 1:
            victim = victims[0]
            voters = details.get(victim, [])
            voter_names = ", ".join([f"**{v.display_name}**" for v in voters])
            if not voter_names: 
                voter_names = (
                    "the singles group" if story_type == "Rom Com"
                    else ("the all-hands meeting" if story_type == "Office Restructuring" else "an angry mob")
                )

            if story_type == "Rom Com":
                return (
                    f"The singles group gathered for a tense intervention. Led by {voter_names}, the group decided that **{victim.display_name}** was bringing too much toxic drama to the circle.\n\n"
                    f"**{victim.display_name}** was officially ghosted and voted off the dating market! They were the **{_get_role_title(victim)}**."
                )
            elif story_type == "Office Restructuring":
                return (
                    f"The all-hands meeting concluded with decisive peer reviews. Led by {voter_names}, the department voted to eliminate **{victim.display_name}**'s position.\n\n"
                    f"**{victim.display_name}** was summoned to HR, handed their final severance package, and terminated! They were the **{_get_role_title(victim)}**."
                )
            return (
                f"The town square fell silent as the crowd, led by {voter_names}, pointed their fingers at one individual. A verdict had been reached.\n\n"
                f"**{victim.display_name}** was dragged into the middle of the town square and strung up. They were the **{_get_role_title(victim)}**."
            )

        # Case 2: Multi-lynch in case of an exact vote tie
        else:
            victim_titles = [f"**{v.display_name}** (the **{_get_role_title(v)}**)" for v in victims]
            if story_type == "Rom Com":
                return (
                    f"An emotional confrontation erupted! The friend group couldn't agree on who had more red flags, and in the ensuing chaos, multiple people were cut off.\n\n"
                    f"**{', '.join(victim_titles)}** were all ghosted and dumped by the group!"
                )
            elif story_type == "Office Restructuring":
                return (
                    f"Emergency departmental budget cuts caused total upheaval! Multiple positions were eliminated at once.\n\n"
                    f"**{', '.join(victim_titles)}** have all been made redundant and laid off!"
                )
            return (
                f"A heated argument resulted in a shocking outcome! The town couldn't decide on a single target, and in the ensuing chaos, a mob turned on multiple people.\n\n"
                f"**{', '.join(victim_titles)}** have all been lynched by the town!"
            )

    # Event: Day phase concluded with zero votes cast
    if event_type == 'no_lynch':
        if story_type == "Rom Com":
            return "The group debated back and forth about who was leading who on, but couldn't reach a consensus. No one was ghosted today."
        elif story_type == "Office Restructuring":
            return "The steering committee debated layoff proposals for hours without consensus. No employees were let go today."
        return "The sun sets on a tense but indecisive town. With no consensus, no one was lynched."

    # Event: Player eliminated for failing to vote across multiple consecutive days
    if event_type == 'inactivity_kill':
        victims = event.get('victims', [])
        if not victims: return None
        victim_names = ", ".join([f"**{v.display_name}**" for v in victims])
        if story_type == "Rom Com":
            return f"Leaving the group chat on read is unforgivable! For failing to participate in today's group chat, {victim_names} was ghosted for inactivity!"
        elif story_type == "Office Restructuring":
            return f"Unexcused absence! For failing to attend today's mandatory all-hands voting meeting, {victim_names} was terminated for job abandonment!"
        return f"The town has no patience for silence. For failing to participate in the day's crucial vote, {victim_names} is/are executed for inactivity!"

    # =========================================================================
    # Game End Events
    # =========================================================================

    # Event: Jester successfully tricked the town into lynching them
    if event_type == 'jester_win':
        victim = event.get('victim')
        if not victim: return None
        if story_type == "Rom Com":
            return (
                f"**{victim.display_name}** smiles smugly as everyone realizes what happened. "
                f"By deliberately getting dumped in public, the Drama Queen wins everyone's undivided attention! The Drama Queen wins!"
            )
        elif story_type == "Office Restructuring":
            return (
                f"**{victim.display_name}** smiles as they pack their cardboard box with a golden parachute! "
                f"By deliberately orchestrating their own layoff, the Disgruntled Temp wins!"
            )
        return (
            f"**{victim.display_name}** cackles madly as the town realizes its mistake. "
            f"By lynching the Jester, the town has signed its own death warrant! The Jester wins!"
        )

    # Event: Match conclusion and victor announcement
    if event_type == 'game_over':
        winner = event.get('winner')
        if not winner: return None
        winner_str = str(winner).strip().lower()
        if winner_str == 'draw':
            if story_type == "Rom Com":
                return "\n**The game is over! Everyone ended up single and heartbroken! The game has ended in a DRAW — No one wins!**"
            elif story_type == "Office Restructuring":
                return "\n**The game is over! The entire office has been liquidated and downsized! The game has ended in a DRAW — No one wins!**"
            return "\n**The game is over! The game has ended in a DRAW — No one wins!**"
        else:
            win_target = winner if str(winner).startswith("The ") else f"The {winner}"
            if story_type == "Rom Com":
                return f"\n**The game is over! {win_target} has triumphed in love!**"
            elif story_type == "Office Restructuring":
                return f"\n**The game is over! {win_target} has taken complete control of the company!**"
            return f"\n**The game is over! {win_target} has WON the game!**"

    return None
