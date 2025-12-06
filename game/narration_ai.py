import logging
import aiohttp
try:
    import config
except ImportError:
    import config_template as config
from utils.utilities import load_data

logger = logging.getLogger('discord')

# Using the specialized creative writing model
MODEL_NAME = "gemma-3n-e2b-it" 
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"

def _generate_mechanical_summary(events: list) -> str:
    """
    Generates a hard-coded, factual summary of deaths and game-ending events.
    This ensures critical info is never lost in AI translation.
    """
    logger.info("Generating mechanical summary of events.")
    lines = []
    # --- Process Events ---
    for event in events:
        #-- Deaths and Game Flow ---
        etype = event['type']
        logger.info(f"Processing event for mechanical summary: {etype}")
        # --- Deaths ---
        # --- Lynches ---
        if etype == 'lynch':
            for v in event.get('victims', []):
                role_name = v.role.name if v.role else "Unknown"
                lines.append(f"- 💀 **{v.display_name}** was lynched. They were the **{role_name}**.")
                logger.info(f"Lynch event processed for {v.display_name} with role {role_name}.")
        # --- Kills ---
        elif etype == 'kill':
            v = event.get('victim')
            if v:
                role_name = v.role.name if v.role else "Unknown"
                # We usually don't reveal the killer's name mechanically unless it's Battle Royale
                # But we can say "Killed by Mafia" if we track it, or just "Killed".
                # For now, let's keep it simple.
                killer_role = event['killer'].role.name if event.get('killer') and event['killer'].role else "Unknown"
                lines.append(f"- 💀 **{v.display_name}** was killed by the {killer_role}. They were the **{role_name}**.")
                logger.info(f"Kill event processed for {v.display_name} with role {role_name}.")
        #--- Special Kill Types ---
        elif etype == 'kill_immune':
            v = event.get('victim')
            k = event.get('killer')
            if v and k:
                role_name = v.role.name if v.role else "Unknown"
                lines.append(f"- 🛡️ **{v.role_name}** survived an attack by **{k.role_name}**.")
                logger.info(f"Kill immune event processed for {v.display_name} with role {role_name}.")
        elif etype == 'kill_battle_royale':
            v = event.get('victim')
            k = event.get('killer')
            if v and k:
                role_name = v.role.name if v.role else "Unknown"
                lines.append(f"- 💀 **{v.display_name}** was killed by **{k.display_name}**. They were the **{role_name}**.")
                logger.info(f"Battle Royale kill event processed for {v.display_name} with role {role_name}.")
        # --- Inactivity ---
        elif etype == 'inactivity_kill':
            for v in event.get('victims', []):
                role_name = v.role.name if v.role else "Unknown"
                lines.append(f"- 💀 **{v.display_name}** died of inactivity. They were the **{role_name}**.")
                logger.info(f"Inactivity kill event processed for {v.display_name} with role {role_name}.")
        elif etype == 'failed_kill_killer_dead':
             # Optional: Report that a kill failed? Maybe too much info. 
             # Sticking to deaths usually is cleaner.
             pass 
        # --- Game Flow ---
        elif etype == 'no_lynch':
             lines.append("- 🕊️ No one was lynched today.")
             logger.info("No lynch event processed.")
        #--- Game Over Jester Win ---
        elif etype == 'jester_win':
             lines.append(f"- 🃏 **{event['victim'].display_name}** (Jester) was lynched and WINS the game!")
             logger.info(f"Jester win event processed for {event['victim'].display_name}.")
        #--- Game Over ---
        elif etype == 'game_over':
             winner = event.get('winner', 'Unknown')
             lines.append(f"- 🏆 **Game Over!** The winner is: **{winner}**")
             logger.info("Game over event processed.")
    if not lines:
        logger.info("No significant events to summarize mechanically.")
        return ""
    logger.info("Mechanical summary generated.")
    return "\n**Summary of Events:**\n" + "\n".join(lines)

def _construct_ai_prompt(game_state: dict, events: list, story_history: list) -> str:
    """Constructs a detailed, structured prompt for the AI model."""
    logger.info("Constructing AI prompt for story generation.")
    players = game_state.get('living_players', [])
    is_game_over = game_state.get('is_game_over', False)
    logger.info(f"Game state: phase={game_state.get('phase')}, number={game_state.get('number')}, is_game_over={is_game_over}")
    # Check if this is the very start of the game
    is_prologue = game_state.get('is_prologue', False)
    logger.info(f"Is prologue: {is_prologue}")
    # --- Dynamic Tone Selection ---
    story_type = game_state.get('story_type', 'Classic Mafia')
    themetypes = load_data("Data/themes.json")
    logger.info(f"Loaded theme types: {list(themetypes.keys()) if themetypes else 'None'}")
    if not themetypes:
        logger.warning("Data/themes.json could not be loaded. Using default theme.")
        themetypes = {
            'Classic Mafia': 'suspenseful, noir-inspired, and laden with paranoia'
        }
    # Select tone description based on story type
    tone_desc = themetypes.get(story_type, 'suspenseful, noir-inspired, and laden with paranoia')
    logger.info(f"Selected tone description: {tone_desc}")   
    # Logic to hide roles if the game is still active
    if is_game_over:
        player_list_str = ", ".join([f"{p.display_name} ({p.role.name})" for p in players])
    else:
        player_list_str = ", ".join([f"{p.display_name}" for p in players])
    logger.info(f"Player list for prompt: {player_list_str}")
    prompt_parts = []
    # --- SYSTEM INSTRUCTIONS ---
    prompt_parts.append(
        "\nYou are a master story writer, tasked with writing a short, punchy scene for a chat-based Mafia game." 
        f"The theme is '{story_type}'. Your tone must be {tone_desc}." 
        "\n\n*** STYLE GUIDELINES (MANDATORY) ***"
        "\n1. **BE CONCISE:** Write no more than 150 words. Be sharp, direct, and impactful. Quality over quantity."
        "\n2. **SHOW, DON'T TELL:** Do not use mechanical terms like 'blocked', 'immune', 'saved', or 'roleblocked'. Describe the action. (e.g., instead of 'He was blocked', write 'He was waylaid in the alley')."
        "\n3. **WEAVE THE NARRATIVE:** Do NOT list the events sequentially. Combine them into a single, fluid scene."
        "\n4. **FACTUALITY:** You must include the *outcomes* of the events listed below, do not invent new deaths, or any other action. Only the actions described need to be in the story."
        # Note: We removed the strict "state the role" instruction here because the Mechanical Summary now handles it perfectly.
        # This frees the AI to focus on the drama of the death without sounding like a stat sheet.
        "\n5. **DRAMA:** When a player dies, focus on the final moment or the discovery of the body."
        "\n6. **Build Atmosphere:** Use vivid, sensory language to immerse the reader in the scene."
        "\n7. **Ensure Continuity:** Maintain consistency with previous chapters in character behavior, setting, and plot. Weave in storylines for different characters where appropiate and possible."
    )
    logger.info("System instructions added to prompt.")
    # --- PROLOGUE HANDLING ---
    if is_prologue:
        prompt_parts.append(
            "\n**CONTEXT:** The game is just beginning. Describe the setting and the ominous atmosphere. **DO NOT mention player numbers, or any specific player names.** Focus purely on setting the mood. If possible, hint at the conflicts to come. If you use named NPCs, ensure they fit the theme."
        )
        logger.info("Prologue context added to prompt.")
    else:
        prompt_parts.append(
             "\n**CONTEXT:** Continue the story from the previous chapter."
             "\n**Consistency:** Maintain consistency with established characters and plotlines."
        )
        logger.info("Regular game context added to prompt.")
    logger.info("Context instructions added to prompt.")
    # --- DATA INPUT ---
    prompt_parts.append(f"\n\n*** CURRENT STATE ***")
    prompt_parts.append(f"Phase: {game_state['phase']} {game_state['number']}.")
    # Only show players if it's NOT the prologue (to prevent AI from listing them)
    if not is_prologue:
        prompt_parts.append(f"Living Characters: {player_list_str}.")
        logger.info(f"Is not prologue, so Living Characters have been added to prompt: {player_list_str}")
    # --- MEMORY INJECTION ---
    if story_history:
        prompt_parts.append("\n*** PREVIOUS CHAPTER (For Context) ***")
        # Only show the very last chapter to save tokens and keep it focused
        last_chapter = story_history[-1]
        prompt_parts.append(f"{last_chapter}\n")
        prompt_parts.append("*** END CONTEXT ***\n")
    prompt_parts.append("\n*** KEY OUTCOMES TO NARRATE ***")
    logger.info("Key outcomes section added to prompt.")
    # --- EVENT DESCRIPTIONS ---
    if not events:
        if is_prologue:
             prompt_parts.append("- Outcome: Introduce the world.")
        else:
             prompt_parts.append("- Outcome: The night was quiet. No deaths occurred.")
        logger.info("No events to add to AI prompt.")
    else:
        for event in events:
            # --- Kill Events ---
            if event['type'] == 'kill':
                prompt_parts.append(f"- Outcome: {event['killer'].role.name} killed {event['victim'].display_name}. The victim was the **{event['victim'].role.name}**.")
                logger.info(f"Added kill event to prompt: {event['killer'].role.name} killed {event['victim'].display_name}.")
            if event['type'] == 'kill_battle_royale':
                prompt_parts.append(f"- Outcome: {event['killer'].display_name} killed {event['victim'].display_name}. The victim was the **{event['victim'].role.name}**.")
                logger.info(f"Added battle royale kill event to prompt: {event['killer'].display_name} killed {event['victim'].display_name}.")
            if event['type'] == 'kill_immune':
                prompt_parts.append(f"- Outcome: {event['killer'].role.name} tried to kill {event['victim'].role.name}, but failed (target was tough/armored).")
                logger.info(f"Added kill immune event to prompt: {event['killer'].role.name} tried to kill {event['victim'].role.name}.")
            # --- Failed Kill Events ---
            if event['type'] == 'kill_blocked':
                prompt_parts.append(f"- Outcome: {event['killer'].role.name} tried to kill {event['target'].display_name}, but was stopped/intercepted.")
                logger.info(f"Added kill blocked event to prompt: {event['killer'].role.name} tried to kill {event['target'].display_name}.")
            if event['type'] == 'failed_kill_killer_dead':
                prompt_parts.append(f"- Outcome: {event['killer'].display_name} tried to kill {event['victim'].display_name}, but died before they could strike.")
                logger.info(f"Added failed kill killer dead event to prompt: {event['killer'].display_name} tried to kill {event['victim'].display_name}.")
            # --- Defensive Events ---
            # --- Heal Events ---
            if event['type'] == 'save':
                prompt_parts.append(f"- Outcome: {event['victim'].display_name} was attacked, but the Doctor saved them at the last second.")
                logger.info(f"Added save event to prompt: {event['victim'].display_name} was saved.")
            if event['type'] == 'save_battle_royale':
                prompt_parts.append(f"- Outcome: {event['victim'].display_name} was attacked, but {event['healer'].display_name} saved them at the last second.")
                logger.info(f"Added battle royale save event to prompt: {event['victim'].display_name} was saved by {event['healer'].display_name}.")
            # --- Block Events ---
            if event['type'] == 'block':
                prompt_parts.append(f"- Outcome: {event['blocker'].role.name} distracted or detained {event['target'].role.name}, stopping their action.")
                logger.info(f"Added block event to prompt: {event['blocker'].role.name} distracted or detained {event['target'].role.name}.")
            if event['type'] == 'block_missed':
                prompt_parts.append(f"- Outcome: {event['blocker'].role.name} tried to stop {event['target'].role.name}, but arrived too late.")
                logger.info(f"Added block missed event to prompt: {event['blocker'].role.name} tried to stop {event['target'].role.name}, but arrived too late.")
            if event['type'] == 'block_battle_royale':
                prompt_parts.append(f"- Outcome: {event['blocker'].display_name} distracted or detained {event['target'].display_name}, stopping their action.")
                logger.info(f"Added battle royale block event to prompt: {event['blocker'].display_name} distracted or detained {event['target'].display_name}.")
            # --- Investigate Events ---
            if event['type'] == 'investigate':
                prompt_parts.append(f"- Outcome: Someone was snooping around for information. Do not include names of investigators or targets."
                                        " Only illude to the act of investigation itself in a very hidden manner.")
                logger.info("Added investigate event to prompt: Someone was snooping around for information.")
            # --- Day Events ---
            if event['type'] == 'lynch':
                victims = event.get('victims', [])
                details = event.get('details', {})
                for victim in victims:
                    voters = details.get(victim, [])
                    voter_names = ", ".join([v.display_name for v in voters if v])
                    if not voter_names:
                        voter_names = "the town"
                    prompt_parts.append(f"- Outcome: The town voted to LYNCH {victim.display_name}. They died. They were the **{victim.role.name}**. (Voters: {voter_names}).")
                    logger.info(f"Added lynch event to prompt: {victim.display_name} was lynched by {voter_names}.")
            if event['type'] == 'no_lynch':
                prompt_parts.append("- Outcome: The town was indecisive. No execution today.")
                logger.info("Added no lynch event to prompt: No execution today.")
            # --- Inactivity Events ---
            if event['type'] == 'inactivity_kill':
                victims = event.get('victims', [])
                names = ", ".join([f"{v.display_name}" for v in victims])
                prompt_parts.append(f"- Outcome: {names} died/disappeared due to inactivity/absence.")
                logger.info(f"Added inactivity kill event to prompt: {names} died due to inactivity.")
            # --- Special/Meta Events ---
            if event['type'] == 'promotion':
                prompt_parts.append(f"- Outcome: The Mafia leadership changed. Do not mention any names other than the name of the just killed mafia member, just the event." 
                                        "Create a seperate paragraph describing the scene of the promotion if possible. in the shadows, based on the theme")
                logger.info("Added promotion event to prompt: Mafia leadership changed.")
            # --- Game Start/End Events ---
            if event['type'] == 'game_start':
                # For prologue, we just want atmosphere, but we record the event for logging
                if not is_prologue:
                    p_list = event.get('players')
                    if not p_list and event.get('game_state'):
                        p_list = event['game_state'].get('living_players', [])
                    player_names = ", ".join([p.display_name for p in (p_list or [])])
                    prompt_parts.append(f"- Outcome: The game begins with these players: {player_names}.")
                else:
                    prompt_parts.append(f"- Outcome: The game begins. Set the scene.")
                logger.info("Added game start event to prompt.")
            if event['type'] == 'game_over': 
                winners = event.get('winner', 'No one')
                prompt_parts.append(f"- Outcome: Game Over. The winners are {winners}. "
                                     "Write an ending scene reflecting the victory of the winners and the defeat of the losers." 
                                     "If town are winners, focus on relief and rebuilding. If mafia wins focus on their total domination, "
                                     "if neutrals win, focus on the chaos and uncertainty that was brought. " 
                                     "Keep to the theme and setting established. Tie sup any plot lines not yet resolved.")
                logger.info("Added game over event to prompt.")
            if event['type'] == 'jester_win':
                prompt_parts.append(f"- Outcome: The Jester ({event['victim'].display_name}) tricked the town into killing them and wins!")
                logger.info("Added jester win event to prompt.")
    logger.info("All events added to prompt.")
    # --- FINAL INSTRUCTIONS ---
    prompt_parts.append(
        "\nWrite the narrative now. Focus on atmosphere and brevity. Do not use bullet points."
    )
    logger.info("Final instructions added to prompt.")
    return "\n".join(prompt_parts)

async def generate_story(game_state: dict, events: list, story_history: list) -> str | None:
    """Makes an asynchronous API call to the Google AI model to generate a story."""
    if not hasattr(config, 'GOOGLE_AI_API_KEY') or not config.GOOGLE_AI_API_KEY:
        logger.warning("GOOGLE_AI_API_KEY not found or is empty in config. Cannot generate AI story.")
        return None
    logger.info("Generating story using AI...")
    
    # 1. Build Prompt
    prompt = _construct_ai_prompt(game_state, events, story_history)
    
    # Debug log restricted to 1000 chars to avoid clutter
    logger.info("Constructed AI Prompt:\n" + prompt[:1000] + "...")
    logger.debug(f"Full AI Prompt:\n{prompt}")
    
    payload = { "contents": [{ "parts": [{"text": prompt}] }] }
    full_api_url = f"{API_URL}?key={config.GOOGLE_AI_API_KEY}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(full_api_url, json=payload, timeout=20.0) as response:
                if response.status == 200:
                    data = await response.json()
                    candidates = data.get('candidates')
                    if not candidates:
                        logger.error(f"AI API returned 200 but no candidates. Response: {data}")
                        return None
                    
                    try:
                        text = candidates[0].get('content', {}).get('parts', [{}])[0].get('text')
                    except (IndexError, KeyError):
                        logger.error(f"AI API returned malformed data structure. Response: {data}")
                        return None
                    
                    if text:
                        # --- SUCCESS: APPEND MECHANICAL SUMMARY ---
                        logger.info("Successfully generated story from AI.")
                        ai_text = text.strip()
                        
                        # Generate the non-AI functional summary
                        mechanical_summary = _generate_mechanical_summary(events)
                        
                        # Combine them
                        final_output = f"{ai_text}\n{mechanical_summary}"
                        return final_output
                    else:
                        logger.error(f"AI API returned valid structure but empty text.")
                        return None
                else:
                    error_text = await response.text()
                    logger.error(f"AI API call failed with status {response.status}: {error_text}")
                    return None
    except Exception as e:
        logger.error(f"An exception occurred during the AI API call: {e}", exc_info=True)
        return None