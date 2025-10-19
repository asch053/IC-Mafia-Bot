# game/ai_storyteller.py
import logging
import aiohttp
import config

# Use the same logger as the main bot
logger = logging.getLogger('discord')

# The URL for the Google AI API endpoint.
# We'll use the gemini-pro model for text generation.
MODEL_NAME = "gemini-2.0-flash-lite"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={config.GOOGLE_AI_API_KEY}"
def _construct_ai_prompt(game_state: dict, events: list) -> str:
    """
    Constructs a detailed, structured prompt for the AI model based on game state and events.
    """
    # This is where we can get really creative with the AI's persona and instructions.
    prompt_parts = [
        "You are a master storyteller for a dark, gritty game of Mafia.",
        "The theme for this story is '1940s detective noir'.",
        f"It is the end of {game_state['phase']} {game_state['number']}.",
        f"{len(game_state['living_players'])} players are left alive.",
        "\nHere are the key events that just happened:",
    ]

    # Translate our structured event data into plain English for the AI.
    if not events:
        prompt_parts.append("- The night was eerily quiet. Nothing happened.")
    else:
        for event in events:
            if event['type'] == 'kill':
                prompt_parts.append(f"- {event['killer'].display_name} killed {event['victim'].display_name}.")
            elif event['type'] == 'save':
                prompt_parts.append(f"- {event['victim'].display_name} was attacked, but was saved by {event['healer'].display_name}.")
            elif event['type'] == 'block':
                prompt_parts.append(f"- {event['blocker'].display_name} blocked {event['target'].display_name} from performing their action.")
            elif event['type'] == 'lynch':
                victims = ", ".join([v.display_name for v in event.get('victims', [])])
                prompt_parts.append(f"- The town voted to lynch {victims}.")
    
    # Final instructions for the AI's output.
    prompt_parts.append(
        "\nWrite a short, compelling narrative summarizing these events. "
        "Reveal the names of anyone who died. Do not reveal the roles or identities of any living players. "
        "Keep the story to a few dramatic paragraphs."
    )
    return "\n".join(prompt_parts)

async def generate_story(game_state: dict, events: list) -> str | None:
    """
    Makes an asynchronous API call to the Google AI model to generate a story.

    Returns the generated story as a string, or None if the API call fails.
    """
    prompt = _construct_ai_prompt(game_state, events)
    logger.info("Constructed AI Prompt:\n" + prompt)

    payload = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }]
    }

    try:
        async with aiohttp.ClientSession() as session:
            # Set a timeout to prevent the game from hanging if the API is slow.
            async with session.post(API_URL, json=payload, timeout=15.0) as response:
                if response.status == 200:
                    data = await response.json()
                    # Safely navigate the JSON response to get the text.
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
