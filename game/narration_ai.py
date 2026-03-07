# game/narration_ai.py
import logging
import asyncio
import json
import os
from datetime import datetime

try:
    import config
except ImportError:
    import config_template as config

from Utils.utilities import load_data
from Utils.utilities import archive_phase_data as _archive_phase_data
from Utils.utilities import log_prompt_to_json as _log_prompt_to_json

# Import the new 2026 standard Google GenAI SDK
try:
    from google import genai
    from google.genai import types
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False

logger = logging.getLogger('discord')

# Using the specialized thinking model
MODEL_NAME = "gemini-3.0-flash" 

# Initialize the client safely depending on how your config is named
_api_key = getattr(config, 'GEMINI_API_KEY', getattr(config, 'GOOGLE_AI_API_KEY', None))
if SDK_AVAILABLE and _api_key:
    client = genai.Client(api_key=_api_key)
else:
    client = None
    logger.error("Google GenAI SDK not installed OR API Key missing. AI Narration will fail.")

def _generate_mechanical_summary(events: list) -> str:
    """
    Generates a hard-coded, factual summary of deaths and game-ending events.
    This ensures critical info is never lost in AI translation.
    """
    logger.info("Generating mechanical summary of events.")
    lines = []
    
    for event in events:
        etype = event['type']
        # --- Lynches ---
        if etype == 'lynch':
            for v in event.get('victims', []):
                role_name = v.role.name if v.role else "Unknown"
                lines.append(f"- 💀 **{v.display_name}** was lynched. They were the **{role_name}**.")   
        # --- Kills ---
        elif etype == 'kill':
            # Note: We updated actions.py to use 'victim' instead of 'target' for kills!
            victim = event.get('victim') 
            if victim:
                role_name = victim.role.name if victim.role else "Unknown"
                lines.append(f"- 🔪 **{victim.display_name}** was killed in the night. They were the **{role_name}**.")
        # --- Mod/Admin Interventions ---
        elif etype == 'inactivity_kill':
            for v in event.get('victims', []):
                role_name = v.role.name if v.role else "Unknown"
                lines.append(f"- ⚡ **{v.display_name}** was struck down for inactivity. They were the **{role_name}**.")
    # Only return a summary if deaths occurred
    if lines:
        return "\n**--- Mechanical Summary ---**\n" + "\n".join(lines)
    return ""

def _construct_ai_prompt(game_state: dict, events: list, history: list) -> str:
    """Builds the text prompt to send to the LLM."""
    logger.info("Constructing AI prompt for story generation.")
    phase_name = str(game_state.get('phase', 'Unknown')).capitalize()
    phase_num = game_state.get('number', 0)
    story_type = game_state.get('story_type', 'Classic Mafia')
    living_players = [p.display_name for p in game_state.get('living_players', [])]
    is_prologue = game_state.get('is_prologue', False)
    logger.info(f"Game State for Prompt: Phase={phase_name} {phase_num}, Story Type={story_type}, Living Players={living_players}, Is Prologue={is_prologue}")
    # 1. Format Events Context
    events_text = "No mechanical actions resolved this phase." # Default message if no events to narrate
    # We will pass a simplified version of the events to the AI, stripping out complex objects and just giving it the key info (type, victim/target names). 
    # The full details of the events will be captured in the Mechanical Summary instead to ensure nothing is lost.
    if events:
        event_lines = []
        for e in events:
            # We strip out the raw objects and just pass names/types to the AI
            line = f"Event Type: {e['type']}"
            if 'victim' in e: line += f" | Victim: {e['victim'].display_name}"
            if 'target' in e: line += f" | Target: {e['target'].display_name}"
            event_lines.append(line)
        events_text = "\n".join(event_lines)
    # 2. Prune History to prevent context bloat (Max 3 previous chapters)
    # We will pass the last 3 stories to the AI to provide context, but we need to be careful about token limits. 
    # The AI doesn't need the entire history, just the most recent chapters to understand the current narrative flow.
    history_text = "This is the very beginning." # Default message if no history exists yet
    # We updated the narration manager to store the full text of each chapter in story_history, so we can pass that directly to the AI.
    if history:
        pruned_history = history[-3:] 
        history_text = "\n\n".join(pruned_history)
    # 3. Construct the Reasoning Rubric
    # This is a critical part of the prompt that guides the AI's thinking process. 
    # We want to make sure it understands the current game state, the importance of only narrating living players, and the secrecy rules around roles.
    prompt = f"""You are the Narrator for a game of Mafia. 
                    Write a highly engaging, immersive story in the style of: '{story_type}'.
                    Current Phase: {phase_name} {phase_num}
                    --- REASONING RUBRIC (Think before you write) ---
                    1. CURRENT LIVING PLAYERS: {", ".join(living_players)}. 
                    CRITICAL RULE: Only living players can perform actions or speak in the scene. Dead players are gone.
                    2. IS PROLOGUE? {is_prologue}. 
                    If True: Do NOT name any players. Just set the atmosphere for the town.
                    If False: Use the events below to describe what happened.
                    3. SECRECY RULE: NEVER reveal a player's exact role (like 'Mafia' or 'Doctor') unless they died this phase. 
                    --- MECHANICAL EVENTS TO NARRATE ---
                    {events_text}
                    --- PREVIOUS STORY CONTEXT ---
                    {history_text}
                    Write the next chapter of the story now:
                    """
    return prompt

async def generate_story(game_state: dict, events: list, history: list) -> str | None:
    """
    Main entry point. Generates the story asynchronously using Gemini 3.
    """
    if not client:
        return None
    logger.info("Starting story generation process...")
    # We create a unique key for this phase to use in logging and archiving the prompt and response. 
    # This helps us keep track of all interactions with the AI for debugging and future analysis.
    phase_name = str(game_state.get('phase', 'Unknown')).capitalize()
    phase_num = game_state.get('number', 0)
    phase_key = f"{phase_name} {phase_num} - {int(datetime.now().timestamp())}"
    logger.info(f"Phase Key for Logging: {phase_key}")
    # 1. Build Prompt
    prompt = _construct_ai_prompt(game_state, events, history)
    logger.debug(f"Constructed AI Prompt: {prompt}")
    # 2. Configure Thinking depth based on phase (Prologue needs less math, more vibes)
    # Gemini 3 allows dynamic reasoning budgets
    is_prologue = game_state.get('is_prologue', False)
    depth = "minimal" if is_prologue else "high"
    # Note: The thinking_level parameter is a newer addition to the SDK. 
    # If your version doesn't support it, you can still control reasoning through prompt engineering and temperature settings.
    generation_config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(include_thoughts=True),
        temperature=0.7,
        thinking_level=depth, 
    )
    logger.info(f"Requesting AI story for {phase_name} {phase_num} (Thinking Level: {depth})...")
    # We will handle the API call and response in a try-except block to ensure any issues with the AI don't crash the bot.
    try:
        # 3. Async Call to Gemini
        # We use a wrapper or the native async client (client.aio)
        response = await client.aio.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=generation_config
        )
        # 4. Extract Thoughts and Text
        thoughts = ""
        story_text = ""
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if getattr(part, 'thought', False): # Using getattr to be safe against older SDK versions
                    thoughts += part.text
                elif part.text:
                    story_text += part.text
        if not story_text:
            logger.error("AI returned an empty story.")
            return None
        # 5. Archive the interaction
        _archive_phase_data(phase_key, prompt, thoughts, story_text.strip())
        # 6. Append Factual Summary
        mechanical_summary = _generate_mechanical_summary(events)
        final_output = f"{story_text.strip()}\n{mechanical_summary}"
        logger.info(f"Successfully generated and archived AI story for {phase_key}.")
        logger.debug(f"Final Story Output: {final_output}")
        return final_output
    except Exception as e:
        # Catching all exceptions (TimeoutError, NetworkError, etc.) to ensure the bot doesn't crash
        logger.error(f"Gemini API Error during generate_story: {type(e).__name__} - {e}", exc_info=True)
        return None