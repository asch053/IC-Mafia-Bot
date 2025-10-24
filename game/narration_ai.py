import logging
import aiohttp
try:
    import config
except ImportError:
    import config_template as config

logger = logging.getLogger('discord')

MODEL_NAME = "gemma-3n-e2b-it" 
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"

def _construct_ai_prompt(game_state: dict, events: list) -> str:
    """Constructs a detailed, structured prompt for the AI model."""
    theme = game_state.get('theme', 'a classic game of Mafia')
    players = game_state.get('living_players', [])
    prompt_parts = [
        f"You are a master storyteller for a game of Mafia with the theme '{theme}'.",
        f"It is the end of {game_state['phase']} {game_state['number']}.",
        f"{len(game_state['living_players'])} players are left alive. Their names and roles are: " +
        ", ".join([f"{p.display_name} ({p.role.name})" for p in players]),
        "\nHere are the key events that just happened:",
    ]

    if not events:
        prompt_parts.append("- The night was eerily quiet. Nothing happened.")
    else:
        for event in events:
            if event['type'] == 'kill_immune':
                prompt_parts.append(f"- {event['killer'].role.name} attempted to kill {event['victim'].role.name}, but they were immune to the attack.")
            
            if event['type'] == 'kill':
                prompt_parts.append(f"- {event['killer'].role.name} killed {event['victim'].display_name}.")
            
            if event['type'] == 'save':
                prompt_parts.append(f"- {event['victim'].display_name} was attacked, but was saved by {event['healer'].role.name}.")
            
            if event['type'] == 'block':
                prompt_parts.append(f"- {event['blocker'].role.name} blocked {event['target'].role.name} from performing their action.")
            
            if event['type'] == 'lynch':
                victims = event.get('victims', [])
                details = event.get('details', {})
                # Iterate through each victim of the lynch to create a detailed sentence.
                for victim in victims:
                    # Find the list of voters for this specific victim from the details dictionary.
                    voters = details.get(victim, [])
                    voter_names = ", ".join([v.display_name for v in voters if v])
                    if not voter_names:
                        voter_names = "an angry mob with no clear leader"
                    prompt_parts.append(f"- The town, led by {voter_names}, voted to lynch {victim.display_name}.")

            if event['type'] == 'promotion':
                prompt_parts.append(f"- A power shift occurred in the mafia. A new leader has risen.")
            
            if event['type'] == 'investigate':
                prompt_parts.append(f"- An investigator snooped around, trying to uncover secrets.")
            
            if event['type'] == 'battle_royale_kill':
                prompt_parts.append(f"- In the chaos of the battle royale, {event['killer'].display_name} eliminated {event['victim'].display_name}.")
            
            if event['type'] == 'battle_royale_save':
                prompt_parts.append(f"- Amidst the turmoil, {event['healer'].display_name} saved {event['victim'].display_name} from elimination by {event['killer'].display_name}.")
            
            if event['type'] == 'block_missed':
                prompt_parts.append(f"- {event['blocker'].role.name} attempted to block {event['target'].role.name}, but the block failed as the target's action had already resolved.")
            
            if event['type'] == 'block_missed_royale':
                prompt_parts.append(f"- In the battle royale, {event['blocker'].role.name} attempted to block {event['target'].role.name}, but the block failed as the target's action had already resolved.")
            
            if event['type'] == 'block_battle_royale':
                prompt_parts.append(f"- In the battle royale, {event['blocker'].role.name} successfully blocked {event['target'].role.name} from performing their action.")
            
            if event['type'] == 'game_start':
                player_names = ", ".join([p.display_name for p in event.get('players', [])])
                prompt_parts.append(f"- The game has begun. {player_names} are all members of the town. Some are mafia, some are town, one is a lone killer. None trust their neighbours.")
            
            if event['type'] == 'game_end':
                winners = event.get('winners', 'No one')
                winning_players = ", ".join([p.display_name for p in event.get('winning_players', [])])
                prompt_parts.append(f"- The game has ended. The victors are {winners}, consisting of {winning_players}.")
            
            # This is a new event type from your log! Let's add it.
            if event['type'] == 'inactivity_kill':
                victims = event.get('victims', [])
                victim_names = ", ".join([f"**{v.display_name}**" for v in victims])
                prompt_parts.append(f"- The town has no patience for silence. {victim_names} was/were executed for inactivity.")


    prompt_parts.append(
        "\nWrite a short, compelling narrative summarizing these events. "
        "Reveal the names of anyone who died. Do not reveal the roles or identities of any living players. "
        "Keep the story to a few dramatic paragraphs."
    )
    return "\n".join(prompt_parts)

async def generate_story(game_state: dict, events: list) -> str | None:
    """Makes an asynchronous API call to the Google AI model to generate a story."""
    if not hasattr(config, 'GOOGLE_AI_API_KEY') or not config.GOOGLE_AI_API_KEY:
        logger.warning("GOOGLE_AI_API_KEY not found or is empty in config. Cannot generate AI story.")
        return None

    logger.info("Generating story using AI...")
    prompt = _construct_ai_prompt(game_state, events)
    logger.info("Constructed AI Prompt:\n" + prompt)

    payload = { "contents": [{ "parts": [{"text": prompt}] }] }
    full_api_url = f"{API_URL}?key={config.GOOGLE_AI_API_KEY}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(full_api_url, json=payload, timeout=20.0) as response:
                if response.status == 200:
                    data = await response.json()
                    text = data.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text')
                    if text:
                        logger.info("Successfully generated story from AI.")
                        return text.strip()
                    else:
                        logger.error(f"AI API returned a successful status but no text. Response: {data}")
                        return None
                else:
                    error_text = await response.text()
                    logger.error(f"AI API call failed with status {response.status}: {error_text}")
                    return None
    except Exception as e:
        logger.error(f"An exception occurred during the AI API call: {e}", exc_info=True)
        return None

