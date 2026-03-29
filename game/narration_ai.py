# game/narration_ai.py
import logging
import asyncio
import json
import os
from datetime import datetime

from discord import Game

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

    # Pre-calculate event counts to group multiple attacks on the same person
    kill_data = {}
    heal_counts = {}
    for event in events:
        etype = event['type']
        if etype in ['kill_battle_royale']:
            v = event.get('victim')
            killer = event.get('killer') or event.get('actor') or event.get('attacker')
            if killer:
                killer_name = getattr(killer, 'display_name', str(killer))
            else:
                killer_name = "Unknown"

            if v:
                if v.display_name not in kill_data:
                    kill_data[v.display_name] = []
                kill_data[v.display_name].append(killer_name)
        elif etype == 'kill_healed':
            v = event.get('target') or event.get('victim')
            if v: heal_counts[v.display_name] = heal_counts.get(v.display_name, 0) + 1
        elif etype == 'save_battle_royale':
            v = event.get('target') or event.get('victim')
            if v: heal_counts[v.display_name] = heal_counts.get(v.display_name, 0) + 1
    
    processed_kills = set()
    
    
    for event in events:
        etype = event['type']
        
        # --- Lynches ---
        if etype == 'lynch':
            for v in event.get('victims', []):
                role_name = v.role.name if v.role else "Unknown"
                lines.append(f"- 💀 **{v.display_name}** was lynched. They were **{role_name}**.")
                
        # --- Kills ---
        elif etype in ['kill', 'kill_battle_royale']:
            # Note: We updated actions.py to use 'victim' instead of 'target' for kills!
            victim = event.get('victim')
            if victim and victim.display_name not in processed_kills:
                processed_kills.add(victim.display_name)
                role_name = victim.role.name if victim.role else "Unknown"
                killers_data = kill_data.get(victim.display_name, [])
                count = len(killers_data)
            killer = event.get('killer') 
            killer_role = killer.role.name if killer and hasattr(killer, 'role') and killer.role else "Unknown"
            killer_name = killer.display_name if killer and hasattr(killer, 'display_name') else "Unknown"
            victum_name = victim.display_name if victim.role else "Unknown"
            if etype == 'kill':
                lines.append(f"- 🔪 **{victum_name}** was killed in the night by {killer_role}. They were the **{role_name}**.")
            elif etype == 'kill_battle_royale':
                known_killers = [k for k in killers_data if k != "Unknown"]
                killers_str = ", ".join(known_killers) if known_killers else "Unknown"
                if count > 1:
                    count_str = f"attacked {count} times! Killers: {killers_str}"
                else:
                    count_str = f"killed by: {killers_str}"
                lines.append(f"- 🔪 **{victim.display_name}** was brutally eliminated in the night. They were {count_str}.")  
            else:
                lines.append(f"- 🔪 **{victim.display_name}** was killed in the night.")
        # --- Mod/Admin Interventions ---
        elif etype == 'inactivity_kill':
            for v in event.get('victims', []):
                role_name = v.role.name if v.role else "Unknown"
                lines.append(f"- ⚡ **{v.display_name}** was struck down for inactivity. They were the **{role_name}**.")
        # --- Blocks ---
        elif etype in ['block', 'block_battle_royale']:
            target = event.get('target')
            blocker = event.get('blocker')
            if target and blocker:
                if etype == 'block_battle_royale':
                    lines.append(f"- 🛡️ **{target.display_name}** was blocked by **{blocker.display_name}** and could not perform their action.")
                else:
                    lines.append(f"- 🛡️ **{target.display_name}** was blocked by a shadowy figure and could not perform their action.")
        elif etype in ['block_missed', 'block_missed_royale']:
            target = event.get('target')
            blocker = event.get('blocker')
            if target and blocker:
                if etype == 'block_missed_royale':
                    lines.append(f"- 🛡️ **{blocker.display_name}** attempted to block **{target.display_name}**, but they had already completed their actions.")
                else:
                    lines.append(f"- 🛡️ A shadowy figure attempted to block **{target.display_name}**, but they had already completed their actions.")
        # --- Heals & Other Saves ---
        elif etype in ['save' , 'save_battle_royale']:
            logger.info(f"Generating save event story part for event: {etype}")
            victim = event.get('victim')
            healer = event.get('healer')
            healer_name = healer.display_name if healer and hasattr(healer, 'display_name') else "Unknown"
            healer_role = healer.role.name if healer and hasattr(healer, 'role') and healer.role else "Unknown"
            if victim:
                role_name = victim.role.name if victim.role else "Unknown"
                if etype == 'save':
                    lines.append(f"- ❤️ **{victim.display_name}** was saved by a the {healer_role}.") 
                elif etype == 'save_battle_royale':
                    lines.append(f"- ❤️ **{victim.display_name}** was saved from a deadly attack by {healer_name}.")
                else: 
                    lines.append(f"- ❤️ **{victim.display_name}** was saved from a deadly attack by a mysterious force.")
        # -- Other Story types can be added here with more elif blocks ---
        elif etype == 'kill_immune':
            victim = event.get('victim')
            logger.info(f"Generating immune kill event story part for victim: {victim}")
            if not victim: return None
            lines.append(f"An assailant ambushed **{victim.role.name}** in the dark, but their target was unfazed. The attack had no effect!")
        elif etype == 'investigate':
            logger.info("Generating investigate event story part.")
            # lines.append("A lone figure was seen snooping around someone's house, trying to uncover secrets.")
        elif etype == 'promotion':     
            logger.info("Generating promotion event story part.")
            lines.append("In the mafia underground, a power vacuum has been filled. A new leader has risen to command the night's dark deeds.")
        
    # Only return a summary if actions occurred
    if not lines:
        return ""
    if lines:
        return "\n**--- Mechanical Summary ---**\n" + "\n".join(lines)
    return ""

def _construct_ai_prompt(game_state: dict, events: list, history: list) -> str:
    """Builds the text prompt to send to the LLM."""
    
    phase_name = str(game_state.get('phase', 'Unknown')).capitalize()
    phase_num = game_state.get('number', 0)
    story_type = game_state.get('story_type', 'Classic Mafia')
    game_mode = str(game_state.get('game_type', game_state.get('mode', 'classic'))).lower()
    living_players = [p.display_name for p in game_state.get('living_players', [])] if game_state.get('living_players') else []
    is_prologue = game_state.get('is_prologue', False)
    is_introduction = game_state.get('is_introduction', False)
    is_epilogue = game_state.get('is_epilogue', False)
    is_game_over = game_state.get('is_game_over', False)
    winner = game_state.get('winner', "No Winner")

    # Fix the "Conclusion None" bug
    if phase_num is None or str(phase_num).lower() == 'none':
        current_phase = phase_name
    else:
        current_phase = f"{phase_name} {phase_num}"

    # Pre-calculate counts to give the AI context on multiple attackers
    kill_data = {}
    heal_counts = {}
    for e in events:
        etype = e['type']
        if etype in ['kill', 'kill_royale', 'vigilante_kill']:
            v = e.get('victim')
            killer = e.get('killer') or e.get('actor') or e.get('attacker')
            if killer:
                killer_name = getattr(killer, 'display_name', str(killer))
            else:
                killer_name = "Unknown"

            if v:
                if v.display_name not in kill_data:
                    kill_data[v.display_name] = []
                kill_data[v.display_name].append(killer_name)
        elif etype == 'kill_healed':
            v = e.get('target') or e.get('victim')
            if v: heal_counts[v.display_name] = heal_counts.get(v.display_name, 0) + 1
        elif etype == 'save_battle_royale':
            v = e.get('target') or e.get('victim')
            if v: heal_counts[v.display_name] = heal_counts.get(v.display_name, 0) + 1

    
    # --- NEW: DYNAMIC MODE CONTEXT ---
    if "battle_royale" in game_mode or game_mode == "br":
        mode_guide = """
*** CRITICAL GAME MODE: BATTLE ROYALE (FREE-FOR-ALL) ***
- This is a brutal, last-man-standing deathmatch. There is no 'Town' and no 'Mafia'.
- Every single player is armed (e.g., holding a knife, a makeshift weapon, etc.).
- Trust does not exist. Everyone is a killer. 
- A 'lynch' represents the group temporarily forming a desperate, violent pact to eliminate the biggest perceived threat during the day.
- A 'night kill' represents a brutal, solitary ambush or duel in the dark.
- Make each death unique, ephasizing the chaos, and violence of a world where everyone is out to get everyone else killed.
"""
        lynch_text = "The remaining survivors turned on and slaughtered"
    else:
        mode_guide = """
*** CRITICAL GAME MODE: CLASSIC MAFIA ***
- This is a game of deception and hidden identities. An innocent, uninformed majority (Town) vs a hidden, informed minority (Mafia/Cult).
- Emphasize the fear of the unknown, the tragedy of innocent people turning on each other, and the shadows hiding the true killers.
- A 'lynch' is a frantic, democratic execution by the frightened mob.
- Make each death unique, but fit into the wider story based on previous chapters. 
"""
        lynch_text = "The town voted to LYNCH"

    # 1. Format Events Context - NOW MODE-AWARE
     # Handle dynamic "Uneventful Phase" text so it makes sense contextually
    if "night" in current_phase:
        events_text = "NARRATIVE EVENT: The night passed completely uneventfully. Emphasize the town's restless sleep, paranoia, and waking up to find everyone perfectly safe."
    elif "day" in current_phase:
        events_text = "NARRATIVE EVENT: The day passed with heated arguments but no consensus. The town failed to lynch anyone. Emphasize the rising tensions as the sun sets."
    elif "preparation" in current_phase or "prologue" in current_phase or "introduction" in current_phase:
        events_text = "NARRATIVE EVENT: The game is just beginning. Focus purely on introductions and setting the scene."
    else:
        events_text = "NARRATIVE EVENT: The phase passed completely uneventfully. Build tension and atmosphere."
    if events:
        event_lines = []
        processed_kills = set()
        processed_heals = set()
        for e in events:
            etype = e['type']
            if etype == 'lynch':
                for v in e.get('victims', []):
                    role_name = v.role.name if v.role else "Unknown"
                    if game_mode == "battle_royale":
                        event_lines.append(f"CRITICAL EVENT: {lynch_text} **{v.display_name}** as decided by the survivors.")
                    else:
                        event_lines.append(f"CRITICAL EVENT: {lynch_text} {v.display_name}. Upon searching their body, their true identity was revealed as {role_name}.")
            elif etype == 'kill':
                victim = e.get('victim')
                if victim and victim.display_name not in processed_kills:
                    processed_kills.add(victim.display_name)
                    killers = kill_data.get(victim.display_name, [])
                    count = len(killers)
                    
                if victim:
                    role_name = victim.role.name if victim.role else "Unknown"
                    event_lines.append(f"CRITICAL EVENT: {victim.display_name} was MURDERED in the night. Upon searching their body, their true identity was revealed as {role_name}.")
            elif etype == 'inactivity_kill':
                for v in e.get('victims', []):
                    role_name = v.role.name if v.role else "Unknown"
                    event_lines.append(f"CRITICAL EVENT: {v.display_name} mysteriously vanished or dropped dead from weakness/inactivity. Their true identity was {role_name}.")
            elif etype == 'block':
                target = e.get('target')
                if target:
                    event_lines.append(f"CRITICAL EVENT: {target.display_name} was BLOCKED by a shadowy figure and could not perform their action.")   
            elif etype == 'block_battle_royale':
                target = e.get('target')
                blocker = e.get('blocker')
                if target and blocker:
                    event_lines.append(f"CRITICAL EVENT: **{target.display_name}** was BLOCKED by **{blocker.display_name}** and could not perform their action.")
            elif etype == 'save': 
                victim = e.get('victim')
                if victim:
                    role_name = victim.role.name if victim.role else "Unknown"
                    event_lines.append(f"CRITICAL EVENT: {victim.display_name} was SAVED by a the doctor who heled them after the attack.")
            elif etype == 'save_battle_royale':  
                victim = e.get('victim')
                healer = e.get('healer')
                healer_name = healer.display_name if healer and hasattr(healer, 'display_name') else "Unknown"
                if victim:
                    event_lines.append(f"CRITICAL EVENT: {victim.display_name} was SAVED from a deadly attack by {healer_name} and survived.")
            elif etype == 'kill_battle_royale':
                victim = e.get('victim')
                killer = e.get('killer')
                killer_name = killer.display_name if killer and hasattr(killer, 'display_name') else "Unknown"
                if victim and victim.display_name not in processed_kills:
                    processed_kills.add(victim.display_name)
                    killers = kill_data.get(victim.display_name, [])
                    count = len(killers)
                    known_killers = [k for k in killers if k != "Unknown"]
                    killers_str = ", ".join(known_killers) if known_killers else "Unknown"
                    if count > 1:
                        event_lines.append(f"CRITICAL EVENT: {victim.display_name} was brutally KILLED in the night, suffering {count} separate lethal attacks by {killers_str}!")
                    else:
                        event_lines.append(f"CRITICAL EVENT: {victim.display_name} was brutally KILLED in the night. They were killed by {killers_str}.")
            elif etype == 'kill_immune':
                victim = e.get('victim')
                if victim:
                    role_name = victim.role.name if victim.role else "Unknown"
                    event_lines.append(f"CRITICAL EVENT: An assailant ambushed **{victim.display_name}** in the dark, but their target was unfazed. The attack had no effect! They were the **{role_name}**.")    
            elif etype == 'investigate':
                #event_lines.append("CRITICAL EVENT: A lone figure was seen snooping around someone's house, trying to uncover secrets.")   
                pass    
            elif etype == 'promotion':
                event_lines.append("CRITICAL EVENT: In the mafia underground, a power vacuum has been filled. A new leader has risen to command the night's dark deeds.")                          
            elif etype == 'block_missed_royale':
                target = e.get('target')
                blocker = e.get('blocker')
                if target and blocker:
                    event_lines.append(f"CRITICAL EVENT: {blocker.display_name} attempted to BLOCK {target.display_name}, but they had already completed their actions.")
        if event_lines:
            events_text = "\n".join(event_lines)

    # 2. Prune History to prevent context bloat (Max 3 previous chapters)
    history_text = "This is the very beginning."
    if history:
        pruned_history = history[-3:] 
        history_text = "\n\n".join(pruned_history)
    
    # 3. Pull Theme Guidelines dynamically from nested JSON dictionary
    theme_data_group = THEMES_DATA.get(story_type, {})
    
    # Extract the high-level description if it exists
    theme_description = theme_data_group.get("description", f"A setting focusing on the tropes of: {story_type}") if isinstance(theme_data_group, dict) else ""

    # Drill down by game_mode (e.g., "classic" or "battle_royale")
    if isinstance(theme_data_group, dict) and game_mode in theme_data_group:
        theme_data = theme_data_group[game_mode]
    elif isinstance(theme_data_group, dict) and "classic" in theme_data_group:
        theme_data = theme_data_group["classic"] # Fallback to classic variant
    else:
        theme_data = theme_data_group # Legacy fallback if not nested

    # Handle legacy string format or missing themes gracefully
    if isinstance(theme_data, str):
        atmosphere = theme_data
        custom_rules = "- SECRECY: NEVER reveal a player's exact role UNLESS they are explicitly killed this phase."
        writing_style = "- Tone: Melodramatic, suspenseful.\n- Day Phases: Chaotic democratic process.\n- Night Phases: Morning discovery."
    else:
        atmosphere = theme_data.get("atmosphere", f"Focus on the tropes of: {story_type}")
        custom_rules = theme_data.get("custom_rules", "- SECRECY: NEVER reveal a player's exact role UNLESS they are explicitly killed this phase.")
        writing_style = theme_data.get("writing_style", "- Tone: Suspenseful.")
    
    narrative_directives = ""
    if is_prologue:
        narrative_directives += "- DO NOT name any players yet. Focus on world-building. This should set the scene for the comming conflict, introducing the setting, the tone, and the atmosphere. It should feel like the prequal chapter of a novel, drawing readers in with vivid descriptions and a sense of mystery. Do not reveal any specific player actions or outcomes in the prologue."
    elif is_introduction or phase_name.lower() == "preparation":
        narrative_directives += f"- Write this as the opening chapter of the story, introducing the main characters {living_players} and setting the scene for the conflict. This should be a gripping introduction that hooks the reader, providing just enough context to understand the stakes without revealing any outcomes yet. This should not include any specific events, but can reference the general situation and the relationships between characters. Do not mention players roles or specific actions, but you can use their names and hint at their personalities and motivations based on the theme."
    elif is_game_over:
        if winner == "Draw":
            narrative_directives += "- Write this as a tragic conclusion to the story based on the Draw result. In a Draw, all players are dead, so the story should reflect on the senseless loss and the futility of the conflict. This should conclude the story and reflect on the overall narrative arc, referencing key events and moments from the game."
        elif winner == "Mafia":
            narrative_directives += f"- Write this as a tragic conclusion to the story based on the Mafia win result. Mafia win is always tragic, so the story should reflect on the darkness and corruption that has taken over, and the loss of innocent lives. Name all surviving players ({living_players}) and their fates, emphasizing the grim consequences of the Mafia's victory. This should conclude the story and reflect on the overall narrative arc, referencing key events and moments from the game."
        elif winner == "Town":
            narrative_directives += f"- Write this as a triumphant conclusion to the story based on the Town win result. Town win is always triumphant, so the story should reflect on the heroism and resilience of the town, and the defeat of the Mafia. Name all surviving players ({living_players}) and their fates, emphasizing the positive outcomes of their efforts. This should conclude the story and reflect on the overall narrative arc, referencing key events and moments from the game."
        else: # battle royale winner or unknown winner
             narrative_directives += f"- Write this as a conclusion to the story based on the {winner} result. Focus on the fate of the winner {living_players} and the overall narrative arc, referencing key events and moments from the game."
    elif is_epilogue:
        narrative_directives += "- Write this as an epilogue chapter reflecting on the aftermath of the conflict. This should provide closure to the story, reflecting on the fates of the surviving players (if any) and the consequences of the conflict. This can be more reflective and less action-oriented, providing a sense of resolution to the narrative arc. This shold difinitely finish the story, providing a sense of closure and finality to the game."
    # 4. Construct the Reasoning Rubric
    prompt = f"""You are an elite, highly creative Game Moderator (GM) running a text-based forum game of Mafia/Social Deduction. 
Your job is to write the flavor text for the current phase. 

CURRENT THEME: '{story_type}'
OVERARCHING PREMISE: {theme_description} 
ATMOSPHERE: {atmosphere}

CURRENT PHASE: {phase_name} {phase_num}

--- REASONING RUBRIC (Internal Rules) ---
1. LIVING PLAYERS ONLY: {", ".join(living_players)}. 
   CRITICAL: If a player is NOT in this list, or died in previous chapters, they are a CORPSE. Corpses cannot speak, react, or perform actions.
{custom_rules}

--- MECHANICAL EVENTS TO NARRATE THIS PHASE ---
{events_text}

--- PREVIOUS STORY CONTEXT ---
{history_text}
- Never directly copy previous story text, but use it to understand the narrative arc and character development so far.

--- WRITING STYLE ---
- Length: Keep the story concise, punchy, and highly readable. Aim for exactly 150 to 250 words (2-3 short paragraphs). Do not overwrite.
- Originality: NEVER directly copy or repeat paragraphs from the PREVIOUS STORY CONTEXT. Use it only for continuity, but ensure your new chapter is completely originally written.

{narrative_directives}
{writing_style}
Do not reference chapter numbers or phase numbers in the story. Do not break the fourth wall or reference the game mechanics directly.
Note: never use gendered pronouns, you can use non-gender pronouns such as "they" or "them". Refer to all players by their display names only. Do not reveal exact roles unless a player was killed this phase. If a player was killed, you may reveal their role in the narration. Always follow the mechanical events closely and narrate them in a way that fits the theme and style.

Write the next chapter of the story now:
"""
    return prompt

def _archive_phase_data(game_state: dict, phase_key: str, prompt: str, thoughts: str, result: str):
    """Stores the complete AI transaction for debugging and observability."""
    game_id = game_state.get('game_id', 'unknown_game')
    logger.info(f"Archiving AI data for game {game_id} - game mode {game_state.get('game_type', 'classic')}")
    game_mode_raw = str(game_state.get('game_type', 'classic')).lower()
    folder_name = "Battle Royale" if "battle_royale" in game_mode_raw else "Classic"
    
    archive_dir = os.path.join("Stats", str(config.game_type).title(), folder_name, game_id)
    os.makedirs(archive_dir, exist_ok=True)
    
    archive_path = os.path.join(archive_dir, f"{game_id}_ai_prompts.json")
    
    logger.info(f"Archiving AI data for {phase_key} to {archive_path}...")
    
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
        
    logger.info(f"Successfully archived AI data for {phase_key}.")

async def generate_story(game_state: dict, events: list, history: list) -> str | None:
    """
    Main entry point. Generates the story asynchronously using the Gemini API.
    """
    if not client:
        return None

    phase_name = str(game_state.get('phase', 'Unknown')).capitalize()
    phase_num = game_state.get('number', "") if game_state.get('number') != 0 else ""
    phase_key = f"{phase_name} {phase_num} - {int(datetime.now().timestamp())}"
    game_mode = str(game_state.get('game_type', 'classic')).lower().replace(" ", "_")
    
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

    max_retries = config.AI_MAX_RETRIES if hasattr(config, 'AI_MAX_RETRIES') else 3
    retry_count = 0
    base_delay = config.AI_RETRY_DELAY if hasattr(config, 'AI_RETRY_DELAY') else 5   # Base delay in seconds for retries

    for attempt in range(max_retries):
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
                logger.error(f"AI returned an empty story on attempt {attempt + 1}.")
                if attempt == max_retries - 1:
                    return None
                await asyncio.sleep(base_delay ** (attempt + 1))
                continue

            # 5. Archive the interaction
            _archive_phase_data(game_state, phase_key, prompt, thoughts, story_text.strip())

            # 6. Append Factual Summary
            mechanical_summary = _generate_mechanical_summary(events)
            final_output = f"{story_text.strip()}\n{mechanical_summary}"
            
            logger.info(f"Successfully generated and archived AI story for {phase_key}.")
            return final_output

        except asyncio.TimeoutError:
            logger.error(f"Gemini API timed out on attempt {attempt + 1}.")
            if attempt == max_retries - 1:
                return None
            await asyncio.sleep(base_delay ** (attempt + 1))
        except Exception as e:
            logger.error(f"Gemini API Error on attempt {attempt + 1}: {type(e).__name__} - {e}", exc_info=True)
            if attempt == max_retries - 1:
                return None
            # Wait exponentially before retrying (2s, 4s, 8s)
            await asyncio.sleep(base_delay ** (attempt + 1))