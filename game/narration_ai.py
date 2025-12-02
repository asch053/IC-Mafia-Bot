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

def _construct_ai_prompt(game_state: dict, events: list, story_history: list) -> str:
    """Constructs a detailed, structured prompt for the AI model."""
    
    players = game_state.get('living_players', [])
    is_game_over = game_state.get('is_game_over', False)
    
    # Check if this is the very start of the game
    is_prologue = (game_state.get('phase') == 'preparation' and game_state.get('number') == 0)
    
    # --- Dynamic Tone Selection ---
    story_type = game_state.get('story_type', 'Classic Mafia')
    themetypes = load_data("Data/themes.json")
    
    if not themetypes:
        logger.warning("Data/themes.json could not be loaded. Using default theme.")
        themetypes = {
            'Classic Mafia': 'suspenseful, noir-inspired, and laden with paranoia'
        }
    
    tone_desc = themetypes.get(story_type, 'suspenseful, noir-inspired, and laden with paranoia')
    theme = game_state.get('theme', f'a {story_type} game of Mafia')
    
    # Logic to hide roles if the game is still active
    if is_game_over:
        player_list_str = ", ".join([f"{p.display_name} ({p.role.name})" for p in players])
    else:
        player_list_str = ", ".join([f"{p.display_name}" for p in players])

    prompt_parts = []
    
    # --- SYSTEM INSTRUCTIONS ---
    prompt_parts.append(
        "\nYou are the omniscient, atmospheric narrator for a forum-based game of Mafia." 
        "Your goal is to heighten the tension and immersion for the players." 
        f"The theme is '{story_type}', so utilize a tone that is {tone_desc}." 
        "\n\n*** CRITICAL RULES (VIOLATION = FAILURE) ***"
        "\n1. **FACTUALITY:** You strictly narrate ONLY the events listed in 'Current Phase Events'. Do NOT invent kills, attacks, saves, or character interactions that are not explicitly listed. If the event list says 'Nothing happened', you must write that the night was quiet."
        "\n2. **ROLES:** Do NOT guess, hint at, or invent roles for living players. Refer to them ONLY by their names. You may only reveal the role of a player if the 'Current Phase Events' says they died."
    )

    # --- PROLOGUE HANDLING ---
    if is_prologue:
        prompt_parts.append(
            "\n3. **PROLOGUE:** This is the PREPARATION phase. The game is just starting. **NO ONE HAS DIED YET.** Do not describe any violence, deaths, or eliminations. Focus purely on the atmosphere, the setting, and the gathering of the players."
        )
    else:
        prompt_parts.append(
             "\n3. **CONTINUITY:** Use 'The Story So Far' for context, but your main focus is the 'Current Phase Events'."
        )

    # --- DATA INPUT ---
    prompt_parts.append(f"\n\n*** CURRENT GAME STATE ***")
    prompt_parts.append(f"Phase: {game_state['phase']} {game_state['number']}.")
    prompt_parts.append(f"Living Players ({len(players)}): {player_list_str}.")

    # --- MEMORY INJECTION ---
    if story_history:
        prompt_parts.append("\n*** THE STORY SO FAR (Context) ***")
        recent_history = story_history[-3:] 
        for i, past_chapter in enumerate(recent_history):
            prompt_parts.append(f"--- Chapter {len(story_history) - len(recent_history) + i + 1} ---\n{past_chapter}\n")
        prompt_parts.append("*** END CONTEXT ***\n")

    prompt_parts.append("\n*** CURRENT PHASE EVENTS (The prompt you must write) ***")


    # --- EVENT DESCRIPTIONS ---
    if not events:
        prompt_parts.append("- The night was eerily quiet. Nothing happened.")
        logger.info("No events to add to AI prompt.")
    else:
        for event in events:
            # --- Kill Events ---
            if event['type'] == 'kill':
                prompt_parts.append(f"- EVENT: {event['killer'].role.name} KILLED {event['victim'].display_name}.")
                logger.info(f"Added kill event: {event['killer'].role.name} killed {event['victim'].display_name}.")
            if event['type'] == 'kill_immune':
                prompt_parts.append(f"- EVENT: {event['killer'].role.name} attempted to KILL {event['victim'].role.name}, but they were immune.")
                logger.info(f"Added kill immune event: {event['killer'].role.name} attempted to kill {event['victim'].role.name}, but they were immune.")
            if event['type'] == 'kill_blocked':
                # Generated in actions.py if killer is blocked
                prompt_parts.append(f"- EVENT {event['killer'].role.name} attempted to KILL {event['target'].display_name}, but was blocked.")
                logger.info(f"Added kill blocked event: {event['killer'].role.name} attempted to kill {event['target'].display_name}, but was blocked.")
            if event['type'] == 'failed_kill_killer_dead':
                # Generated in engine.py if killer died same night
                prompt_parts.append(f"- EVENT:{event['killer'].display_name} attempted to KILL {event['victim'].display_name}, but died before they could strike.")
                logger.info(f"Added failed kill event: {event['killer'].display_name} attempted to kill {event['victim'].display_name}, but died before they could strike.")            # --- Defensive Events ---
            # --- Save Events ---
            if event['type'] == 'save':
                prompt_parts.append(f"- EVENT: {event['victim'].display_name} was attacked, but was SAVED by {event['healer'].role.name}.")
                logger.info(f"Added save event: {event['victim'].display_name} was saved by {event['healer'].role.name}.")
            # --- Block Events ---
            logger.info("Adding block events to AI prompt.")
            if event['type'] == 'block':
                prompt_parts.append(f"- EVENT: {event['blocker'].role.name} BLOCKED {event['target'].role.name} from performing their action.")
                logger.info(f"Added block event: {event['blocker'].role.name} BLOCKED {event['target'].role.name} from performing their action.")
            if event['type'] == 'block_missed':
                prompt_parts.append(f"- EVENT: {event['blocker'].role.name} tried to BLOCK {event['target'].role.name}, but the target had already acted.")
                logger.info(f"Added block missed event: {event['blocker'].role.name} tried to BLOCK {event['target'].role.name}, but the target had already acted.")
            # --- Investigate Events ---
            logger.info("Currently not adding investigate events to AI prompt.")
            if event['type'] == 'investigate':
                prompt_parts.append(f"- EVENT: An investigator snooped around, trying to uncover secrets.")
                logger.info("Added investigate event.")
            # --- Day Events ---
            logger.info("Adding day events to AI prompt.")
            if event['type'] == 'lynch':
                victims = event.get('victims', [])
                details = event.get('details', {})
                for victim in victims:
                    voters = details.get(victim, [])
                    voter_names = ", ".join([v.display_name for v in voters if v])
                    if not voter_names:
                        voter_names = "an angry mob"
                    prompt_parts.append(f"- EVENT: The town, led by {voter_names}, voted to LYNCH {victim.display_name}.")
                    logger.info(f"Added lynch event: {victim.display_name} was lynched by {voter_names}.")
            if event['type'] == 'no_lynch':
                prompt_parts.append("- EVENT: The town could not agree on who to lynch. No one died today.")
                logger.info("Added no lynch event.")
            # --- Inactivity Events ---
            if event['type'] == 'inactivity_kill':
                victims = event.get('victims', [])
                names = ", ".join([f"{v.display_name}" for v in victims])
                prompt_parts.append(f"- EVENT: The town has no patience for silence. {names} was/were executed for inactivity.")
                logger.info(f"Added inactivity kill event for: {names}.")
            # --- Special/Meta Events ---
            if event['type'] == 'promotion':
                prompt_parts.append(f"- EVENT: A power shift occurred in the mafia. A new leader has risen.")
                logger.info("Added promotion event.")
            # --- Game Start/End Events ---
            if event['type'] == 'game_start':
                # FIX: engine.py passes 'game_state' inside the event, handle both ways
                p_list = event.get('players')
                if not p_list and event.get('game_state'):
                    p_list = event['game_state'].get('living_players', [])
                logger.info("Added game start event.")
                player_names = ", ".join([p.display_name for p in (p_list or [])])
                prompt_parts.append(f"- EVENT: The game has begun. The players are: {player_names}. Write a story to set the scene for the story to come.")
                logger.info(f"Added game start event for: {player_names}.")
            if event['type'] == 'game_over': # FIX: Changed from 'game_end' to match engine.py
                winners = event.get('winner', 'No one')
                prompt_parts.append(f"- EVENT: The game has ended. The victors are {winners}. Write a story to conclude the game." 
                                    "Wrap up any story arcs and highlight the winners.")
                logger.info(f"Added game over event. Winners: {winners}.")
            # --- Special Jester Win Event ---
            if event['type'] == 'jester_win':
                prompt_parts.append(f"- EVENT: The town made a fatal mistake. They lynched {event['victim'].display_name}, the Jester! The Jester wins!")
                logger.info(f"Added jester win event for: {event['victim'].display_name}.")
            # --- Battle Royale Events ---
            if event['type'] == 'battle_royale_kill':
                prompt_parts.append(f"- EVENT: In the Battle Royale: {event['killer'].display_name} eliminated {event['victim'].display_name}.")
                logger.info(f"Added battle royale kill event: {event['killer'].display_name} eliminated {event['victim'].display_name}.")
            if event['type'] == 'battle_royale_save':
                prompt_parts.append(f"- EVENT: In the Battle Royale: {event['healer'].display_name} saved {event['victim'].display_name}.")
                logger.info(f"Added battle royale save event: {event['healer'].display_name} saved {event['victim'].display_name}.")
            if event['type'] == 'block_battle_royale':
                prompt_parts.append(f"- EVENT: In the Battle Royale: {event['blocker'].display_name} blocked {event['target'].display_name}.")
                logger.info(f"Added battle royale block event: {event['blocker'].display_name} blocked {event['target'].display_name}.")
            if event['type'] == 'block_missed_royale':
                prompt_parts.append(f"- EVENT: In the Battle Royale: {event['blocker'].display_name} tried to block {event['target'].display_name}, but missed.")
                logger.info(f"Added battle royale block missed event: {event['blocker'].display_name} tried to block {event['target'].display_name}, but missed.")
            if event['type'] == 'kill_missed_battle_royale':
                prompt_parts.append(f"- EVENT: In the Battle Royale: {event['killer'].display_name} tried to kill {event['victim'].display_name}, but died first.")
                logger.info(f"Added battle royale kill missed event: {event['killer'].display_name} tried to kill {event['victim'].display_name}, but died first.")
            if event['type'] == 'investigate_royale':
                prompt_parts.append(f"- EVENT: In the Battle Royale: {event['investigator'].display_name} investigated {event['target'].display_name}.")
                logger.info(f"Added battle royale investigate event: {event['investigator'].display_name} investigated {event['target'].display_name}.")
    # --- FINAL INSTRUCTIONS ---
    prompt_parts.append(
        "If the game is over, you may reveal all roles of living players as part of the finale." 
        "Winning team should be highlighted, with surviving winners given special credit."
        "Any surviving players that are not the winning team should be noted as having lost, and died, or left as part of the finale." 
        "Weave the mechanics of the deaths naturally into the story." 
        "Keep the story to a few dramatic paragraphs."
        "\n\nBased ONLY on the 'Current Phase Events' write the narrative update."
        "Ensure the story follows a narrative as set in the story so far and fits the theme of the game. Use 'The story so far' listed above to keep continuity."
        "Keep it to 3-4 paragraphs."
    )
    return "\n".join(prompt_parts)

async def generate_story(game_state: dict, events: list, story_history: list) -> str | None:
    """Makes an asynchronous API call to the Google AI model to generate a story."""
    if not hasattr(config, 'GOOGLE_AI_API_KEY') or not config.GOOGLE_AI_API_KEY:
        logger.warning("GOOGLE_AI_API_KEY not found or is empty in config. Cannot generate AI story.")
        return None
    logger.info("Generating story using AI...")
    # Pass history to the prompt constructor
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
                    logger.info(f"AI API returned {len(candidates)} candidate stories.")
                    try:
                        text = candidates[0].get('content', {}).get('parts', [{}])[0].get('text')
                    except (IndexError, KeyError):
                        logger.error(f"AI API returned malformed data structure. Response: {data}")
                        return None
                    logger.info(f"AI generated story length: {len(text) if text else 0} characters.")
                    if text:
                        logger.info("Successfully generated story from AI.")
                        return text.strip()
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