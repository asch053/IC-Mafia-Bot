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

from utils.utilities import load_data # Fixed import path

# Import the new 2026 standard Google GenAI SDK
try:
    from google import genai
    from google.genai import types
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False

logger = logging.getLogger('discord')

# CRITICAL FIX: Update the model name to a known valid identifier
# If gemini-3.0-flash-preview still fails, fallback to gemini-2.5-flash
MODEL_NAME = "gemini-2.5-flash" 

# Initialize the client safely depending on how your config is named
_api_key = getattr(config, 'GEMINI_API_KEY', getattr(config, 'GOOGLE_AI_API_KEY', None))
if SDK_AVAILABLE and _api_key:
    # Use the synchronous client initialization as recommended by the new SDK
    client = genai.Client(api_key=_api_key)
else:
    client = None
    logger.error("Google GenAI SDK not installed OR API Key missing. AI Narration will fail.")

# Load themes dynamically from JSON
THEMES_DATA = load_data("Data/themes.json") or {}

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
    
    phase_name = str(game_state.get('phase', 'Unknown')).capitalize()
    phase_num = game_state.get('number', 0)
    story_type = game_state.get('story_type', 'Classic Mafia')
    game_mode = str(game_state.get('game_type', game_state.get('mode', 'classic'))).lower()
    living_players = [p.display_name for p in game_state.get('living_players', [])]
    is_prologue = game_state.get('is_prologue', False)
    
    # --- NEW: DYNAMIC MODE CONTEXT ---
    if "battle_royale" in game_mode or game_mode == "br":
        mode_guide = """
*** CRITICAL GAME MODE: BATTLE ROYALE (FREE-FOR-ALL) ***
- This is a brutal, last-man-standing deathmatch. There is no 'Town' and no 'Mafia'.
- Every single player is armed (e.g., holding a knife, a makeshift weapon, etc.).
- Trust does not exist. Everyone is a killer. 
- A 'lynch' represents the group temporarily forming a desperate, violent pact to eliminate the biggest perceived threat during the day.
- A 'night kill' represents a brutal, solitary ambush or duel in the dark.
"""
        lynch_text = "The remaining survivors turned on and slaughtered"
    else:
        mode_guide = """
*** CRITICAL GAME MODE: CLASSIC MAFIA ***
- This is a game of deception and hidden identities. An innocent, uninformed majority (Town) vs a hidden, informed minority (Mafia/Cult).
- Emphasize the fear of the unknown, the tragedy of innocent people turning on each other, and the shadows hiding the true killers.
- A 'lynch' is a frantic, democratic execution by the frightened mob.
"""
        lynch_text = "The town voted to LYNCH"

    # 1. Format Events Context - NOW MODE-AWARE
    events_text = "No mechanical actions resolved this phase. Nobody died."
    if events:
        event_lines = []
        for e in events:
            etype = e['type']
            if etype == 'lynch':
                for v in e.get('victims', []):
                    role_name = v.role.name if v.role else "Unknown"
                    event_lines.append(f"CRITICAL EVENT: {lynch_text} {v.display_name}. Upon searching their body, their true identity was revealed as {role_name}.")
            elif etype == 'kill':
                victim = e.get('victim')
                if victim:
                    role_name = victim.role.name if victim.role else "Unknown"
                    event_lines.append(f"CRITICAL EVENT: {victim.display_name} was MURDERED in the night. Upon searching their body, their true identity was revealed as {role_name}.")
            elif etype == 'inactivity_kill':
                for v in e.get('victims', []):
                    role_name = v.role.name if v.role else "Unknown"
                    event_lines.append(f"CRITICAL EVENT: {v.display_name} mysteriously vanished or dropped dead from weakness/inactivity. Their true identity was {role_name}.")
                    
        if event_lines:
            events_text = "\n".join(event_lines)

    # 2. Prune History to prevent context bloat (Max 3 previous chapters)
    history_text = "This is the very beginning."
    if history:
        pruned_history = history[-3:] 
        history_text = "\n\n".join(pruned_history)

    # 3. Pull Theme Guidelines dynamically from themes.json
    try:
        theme_guide = THEMES_DATA.get(story_type, f"A highly immersive setting focusing on the tropes of: {story_type}.")
    except Exception as e:
        logger.warning(f"Failed to load theme '{story_type}' from themes.json: {e}")
        theme_guide = f"A highly immersive setting focusing on the tropes of: {story_type}."

    # 4. Construct the Reasoning Rubric
    prompt = f"""You are an elite, highly creative Game Moderator (GM) running a text-based survival/deception game. 
Your job is to write the story text for the current phase. 

CURRENT THEME: '{story_type}'
THEME GUIDELINES: {theme_guide}
{mode_guide}

CURRENT PHASE: {phase_name} {phase_num}

--- REASONING RUBRIC (Internal Rules) ---
1. SURVIVORS: {", ".join(living_players)}. 
   CRITICAL: These players are ALIVE. Do NOT describe them dying, being attacked, or being eliminated under any circumstances.
2. THE VICTIM(S): You MUST base the deaths strictly on the "MECHANICAL EVENTS TO NARRATE THIS PHASE" section below. Do NOT kill anyone else. If that section says nobody died, then nobody died.
3. SECRECY: Keep the identities of the killers shadowed and ambiguous (e.g., "a dark figure," "the shadows," "a glint of steel"). Do not name living players as the explicit perpetrators of a murder.
4. ROLE REVEALS: When a player dies, mention their role subtly as part of the death scene (e.g., a medical kit falling from the Doctor's pocket, a sniper rifle strapped to their back). Do not just state their role outright; weave it into the narrative.
5. ATMOSPHERE: Focus on creating a tense, immersive atmosphere that captures the paranoia and drama of the game. 

--- WRITING STYLE: "ELITE STORYTELLER" ---
- Tone: Melodramatic, suspenseful, gritty, and deeply atmospheric.
- Perspective: Third-person omniscient narrator. Focus on the psychology and paranoia.
- Day Phases: Focus on the chaotic confrontation, the shouting, the desperate pleas of the accused, and the grim execution/elimination. 
- Night Phases: Focus on the victim's internal thoughts as they realize they are hunted, the chilling atmosphere, and the morning discovery of the gruesome scene.
- Prologues: If IS PROLOGUE is {is_prologue}, and it is True, DO NOT name any players yet. Focus entirely on world-building, setting the scene, and introducing the tension.
- Length: Keep the story concise, punchy, and highly readable. Aim for exactly 50 to 150 words (2-3 short paragraphs). Do not overwrite. 

--- MECHANICAL EVENTS TO NARRATE THIS PHASE ---
{events_text}

--- PREVIOUS STORY CONTEXT ---
{history_text}

--- YOUR TASK ---
Write the next chapter of the story now:
"""
    return prompt

def _archive_phase_data(phase_key: str, prompt: str, thoughts: str, result: str):
    """Stores the complete AI transaction for debugging and observability."""
    archive_path = os.path.join("Logs", "prompts_archive.json")
    os.makedirs("Logs", exist_ok=True)
    
    archive_data = {}
    if os.path.exists(archive_path):
        try:
            with open(archive_path, 'r', encoding='utf-8') as f:
                archive_data = json.load(f)
        except json.JSONDecodeError:
            archive_data = {}

    archive_data[phase_key] = {
        "timestamp": datetime.now().isoformat(),
        "prompt_sent": prompt,
        "ai_reasoning": thoughts if thoughts else "No thoughts recorded.",
        "final_story": result
    }

    with open(archive_path, 'w', encoding='utf-8') as f:
        json.dump(archive_data, f, indent=4)

async def generate_story(game_state: dict, events: list, history: list) -> str | None:
    """
    Main entry point. Generates the story asynchronously using the Gemini API.
    """
    if not client:
        return None

    phase_name = str(game_state.get('phase', 'Unknown')).capitalize()
    phase_num = game_state.get('number', 0)
    phase_key = f"{phase_name} {phase_num} - {int(datetime.now().timestamp())}"
    
    # 1. Build Prompt
    prompt = _construct_ai_prompt(game_state, events, history)

    # 2. Configure Thinking depth based on phase
    is_prologue = game_state.get('is_prologue', False)
    
    # Note: Not all models support 'thinking_config' or 'thinking_level' yet.
    # For stability with gemini-2.5-flash, we omit the thinking_config 
    # unless you are strictly using a model that requires it.
    generation_config = types.GenerateContentConfig(
        temperature=0.7,
    )

    logger.info(f"Requesting AI story for {phase_name} {phase_num} using {MODEL_NAME}...")

    try:
        # 3. Async Call to Gemini using the recommended method
        response = await client.aio.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=generation_config
        )

        # 4. Extract Text
        story_text = ""
        thoughts = "" # Default to empty if the model doesn't return thoughts
        
        if response.text:
           story_text = response.text
           
        # Attempt to extract thoughts if they exist in the response structure
        # This is a safe fallback in case we switch back to a thinking model
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if getattr(part, 'thought', False): 
                    thoughts += part.text

        if not story_text:
            logger.error("AI returned an empty story.")
            return None

        # 5. Archive the interaction
        _archive_phase_data(phase_key, prompt, thoughts, story_text.strip())

        # 6. Append Factual Summary
        mechanical_summary = _generate_mechanical_summary(events)
        final_output = f"{story_text.strip()}\n{mechanical_summary}"
        
        logger.info(f"Successfully generated and archived AI story for {phase_key}.")
        return final_output

    except asyncio.TimeoutError:
        logger.error("Gemini API timed out. Falling back to static story.")
        return None
    except Exception as e:
        # Catching all exceptions to ensure the bot doesn't crash
        logger.error(f"Gemini API Error during generate_story: {type(e).__name__} - {e}", exc_info=True)
        return None