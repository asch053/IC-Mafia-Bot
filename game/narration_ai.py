# game/narration_ai.py
# This module is responsible for generating the AI narration for the game based on the events that occurred during the night and day phases. It uses the Google GenAI SDK to create engaging and thematic summaries of the game's progress, which are then posted in the designated channels. The narration is designed to be dynamic and adapt to different game modes (e.g., Classic Mafia vs Battle Royale) while ensuring that critical information is always clearly conveyed to the players.

import logging
import asyncio
import json
import os
from datetime import datetime

# This import is often used for type hinting in larger files
from discord import Game

try:
    import config
except ImportError:
    import config_template as config

from utils.utilities import load_data # Fixed import path
from community import quirk_logic


# Import the new 2026 standard Google GenAI SDK
try:
    from google import genai
    from google.genai import types
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False

logger = logging.getLogger('discord')

# CRITICAL FIX: Update the model name to a known valid identifier
# Using gemini-2.5-flash as the stable production standard.
MODEL_NAME = "gemini-2.5-flash" 

# Initialize the client safely depending on how your config is named
_api_key = getattr(config, 'GEMINI_API_KEY', getattr(config, 'GOOGLE_AI_API_KEY', None))
if SDK_AVAILABLE and _api_key:
    client = genai.Client(api_key=_api_key)
else:
    client = None
    logger.error("Google GenAI SDK not installed OR API Key missing. AI Narration will fail.")

# Load themes dynamically from JSON
THEMES_DATA = load_data("data/game_setup/themes.json") or {}

def _get_involved_quirks(game_state: dict, events: list) -> str:
    """
    Identifies relevant player quirks for the current phase/scene.
    
    CLASSIC: Only includes quirks for publicly revealed players (Victims/Lynch targets).
    BATTLE ROYALE: Permissive, includes attackers and targets as they are named in this mode.
    """
    all_approved = quirk_logic.get_all_approved()
    if not all_approved:
        return ""

    involved_ids = set()
    game_mode = str(game_state.get('game_type', 'classic')).lower()
    is_br = game_mode == "battle_royale"
    
    is_intro = game_state.get('is_introduction', False) or game_state.get('is_prologue', False)
    is_outro = game_state.get('is_game_over', False) or game_state.get('is_epilogue', False)
    
    logger.info(f"Gathering quirks for mode: {game_mode.upper()}")

    if is_intro:
        for p in game_state.get('living_players', []):
            involved_ids.add(str(p.id))
    elif is_outro:
        for p in game_state.get('living_players', []):
            if hasattr(p, 'is_alive') and p.is_alive:
                involved_ids.add(str(p.id))
    else:
        # Standard scene logic
        for e in events:
            etype = e.get('type', '')
            
            # Victims and Lynch targets are always public context
            v = e.get('victim')
            if v and hasattr(v, 'id'):
                involved_ids.add(str(v.id))
            
            for lv in e.get('victims', []):
                if hasattr(lv, 'id'):
                    involved_ids.add(str(lv.id))
            
            # If Battle Royale, attackers/actors are also public knowledge
            if is_br:
                for key in ['killer', 'actor', 'attacker', 'healer', 'blocker', 'investigator']:
                    obj = e.get(key)
                    if obj and hasattr(obj, 'id'):
                        involved_ids.add(str(obj.id))

    persona_lines = []
    for p in game_state.get('living_players', []):
        uid_str = str(p.id)
        if uid_str in involved_ids and uid_str in all_approved:
            persona_lines.append(f"- {p.display_name}: {all_approved[uid_str]}")
            
    if not persona_lines:
        return ""
        
    return "\n--- CHARACTER PERSONAS (Incorporate traits ONLY for these specific people) ---\n" + "\n".join(persona_lines)

def _generate_mechanical_summary(game_state: dict, events: list = None) -> str:
    """Generates a factual summary. Secrecy level depends on game mode."""
    # Backward compatibility for legacy call: _generate_mechanical_summary(events)
    if events is None:
        if isinstance(game_state, list):
            events = game_state
            game_state = {}
        else:
            events = []

    lines = []
    processed_kills = set()
    game_mode = str(game_state.get('game_type', 'classic')).lower()
    is_br = game_mode == "battle_royale"
    
    # Pre-process kill data for BR to list multiple attackers
    kill_data = {}
    if is_br:
        for event in events:
            if event.get('type') in ['kill', 'kill_battle_royale']:
                v = event.get('victim')
                if v:
                    killer = event.get('killer') or event.get('actor') or event.get('attacker')
                    killer_name = killer.display_name if killer else "Unknown"
                    if v.display_name not in kill_data: kill_data[v.display_name] = []
                    kill_data[v.display_name].append(killer_name)

    for event in events:
        etype = event['type']
        
        # --- Lynch Events ---
        if etype == 'lynch':
            for v in event.get('victims', []):
                role_name = v.role.name if v.role else "Unknown"
                lines.append(f"- 💀 **{v.display_name}** was lynched. They were **{role_name}**.")
        elif etype == 'no_lynch':
            lines.append("- ⚖️ The town could not reach a consensus; no one was lynched.")
            
        # --- Kill Events ---
        elif etype in ['kill', 'kill_battle_royale'] and 'failed' not in etype:
            victim = event.get('victim')
            if victim and victim.display_name not in processed_kills:
                processed_kills.add(victim.display_name)
                role_name = victim.role.name if victim.role else "Unknown"
                if is_br:
                    killers_str = ", ".join(kill_data.get(victim.display_name, ["Unknown"]))
                    lines.append(f"- 🔪 **{victim.display_name}** was eliminated by: {killers_str}.")
                else:
                    lines.append(f"- 🔪 **{victim.display_name}** was killed. They were the **{role_name}**.")
        
        # --- Action Failures / Saves ---
        elif etype in ['save', 'save_battle_royale', 'kill_failed']:
            if is_br:
                v = event.get('victim')
                if v:
                    lines.append(f"- ❤️ **{v.display_name}** was attacked but survived!")
                else:
                    lines.append(f"- ❤️ An attempt on a life was thwarted tonight.")
            else:
                # Classic mode anonymity to protect immune roles/healers
                lines.append(f"- ❤️ An attempt on a life was thwarted tonight.")
        
        # --- Utility Actions (BR Specific or detailed info) ---
        elif etype in ['block', 'block_royale'] and is_br:
            target = event.get('target')
            if target: lines.append(f"- 🛡️ **{target.display_name}** was role-blocked.")
            
        elif etype in ['investigate', 'investigate_royale'] and is_br:
            target = event.get('target')
            if target: lines.append(f"- 🔍 **{target.display_name}** was investigated.")

    if not lines:
        return ""
    return "\n**--- Mechanical Summary ---**\n" + "\n".join(lines)

def _construct_ai_prompt(game_state: dict, events: list, history: list) -> str:
    """Builds the AI prompt with dynamic rules based on game type."""
    phase_name = str(game_state.get('phase', 'Unknown')).capitalize()
    phase_num = game_state.get('number', 0)
    story_type = game_state.get('story_type', 'Classic Mafia')
    game_mode_label = str(game_state.get('game_type', 'classic')).lower()
    is_br = game_mode_label == "battle_royale"
    
    living_players = [p.display_name for p in game_state.get('living_players', [])]
    
    is_prologue = game_state.get('is_prologue', False)
    is_introduction = game_state.get('is_introduction', False)
    is_game_over = game_state.get('is_game_over', False)
    winner = game_state.get('winner', "No Winner")

    current_phase = f"{phase_name} {phase_num}" if phase_num else phase_name
    events_text = "The phase passed uneventfully."
    
    if events:
        event_lines = []
        for e in events:
            etype = e['type']
            if etype == 'lynch':
                for v in e.get('victims', []):
                    event_lines.append(f"PUBLIC EVENT: {v.display_name} was lynched. Reveal: {v.role.name if v.role else 'Unknown'}.")
            elif etype in ['kill', 'kill_battle_royale'] and 'failed' not in etype:
                victim = e.get('victim')
                if victim:
                    if is_br:
                        killer = e.get('killer') or e.get('actor') or e.get('attacker')
                        k_name = killer.display_name if killer else "Someone"
                        event_lines.append(f"PUBLIC EVENT: {victim.display_name} was killed by {k_name}.")
                    else:
                        event_lines.append(f"PUBLIC DISCOVERY: {victim.display_name} was found dead. Reveal: {victim.role.name if victim.role else 'Unknown'}.")
            elif etype in ['save', 'save_battle_royale', 'kill_failed']:
                if is_br:
                    v = e.get('victim')
                    t_name = v.display_name if v else "a target"
                    event_lines.append(f"PUBLIC EVENT: {t_name} survived an assassination attempt.")
                else:
                    event_lines.append(f"SECRET EVENT: An assassination attempt failed. The target survived anonymously.")
        if event_lines:
            events_text = "\n".join(event_lines)

    history_text = "\n\n".join(history[-3:]) if history else "Start of the story."
    quirks_block = _get_involved_quirks(game_state, events)

    # DYNAMIC RULE SET
    if is_br:
        rules_block = """--- BATTLE ROYALE RULES (OPEN INFORMATION) ---
1. TRANSPARENCY: Attackers and targets are public knowledge. Use their names freely.
2. COMBAT: Describe the clashes between specific named players as reported in the events.
3. NO SECRECY: You do not need to hide the identities of those involved in night actions."""
    else:
        rules_block = """--- IRONCLAD RULES OF ANONYMITY (CLASSIC MAFIA) ---
1. DO NOT GUESS: If a perpetrator is not named in the MECHANICAL EVENTS, do NOT assign the action to a living player.
2. FOG OF WAR: Night killers, healers, and blockers are ALWAYS anonymous. Refer to them as 'the assailant' or 'a shadowy figure'.
3. NO OUTING: Never describe a named living player as committing an aggressive act unless explicitly told.
4. TARGET SECRECY: If an attempt failed, do NOT reveal which named player was targeted."""

    narrative_directives = ""
    if is_prologue:
        narrative_directives = "DIRECTIVE: Establish the world. Do not name specific players."
    elif is_introduction:
        narrative_directives = f"DIRECTIVE: Introduce the cast: {living_players}."
    elif is_game_over:
        narrative_directives = f"DIRECTIVE: The game is over. {winner} won. Survivors: {living_players}."

    prompt = f"""You are a suspenseful Storyteller for a Mafia game.
THEME: '{story_type}'
CURRENT CHAPTER: {current_phase}

{rules_block}

--- LIVING PLAYERS (For context only, do NOT assume roles) ---
{", ".join(living_players)}
{quirks_block}

--- MECHANICAL EVENTS TO NARRATE ---
{events_text}

--- PREVIOUS STORY CONTEXT ---
{history_text}

--- STYLE ---
- Length: 150-250 words.
- Tone: Noir, suspenseful, and theatrical.
{narrative_directives}

Write the next chapter:
"""
    return prompt

def _archive_phase_data(game_state: dict, phase_key: str, prompt: str, thoughts: str, result: str):
    """
    Archives the AI interaction for debugging and history.
    Saves to a game-specific directory within the Stats folder.
    """
    try:
        game_id = game_state.get('game_id', 'unknown_game')
        game_mode = str(game_state.get('game_type', 'classic')).capitalize()
        env_mode = getattr(config, 'game_type', 'Development').capitalize()
        
        # Path structure: Stats/{Env}/{Mode}/{GameID}/{GameID}_ai_prompts.json
        base_dir = os.path.join("Stats", env_mode, game_mode, game_id)
        os.makedirs(base_dir, exist_ok=True)
        
        archive_path = os.path.join(base_dir, f"{game_id}_ai_prompts.json")
        logger.info(f"Archiving AI data for {phase_key} to {archive_path}...")
        
        archive_data = {}
        if os.path.exists(archive_path):
            with open(archive_path, 'r', encoding='utf-8') as f:
                try:
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
            
    except Exception as e:
        logger.error(f"Failed to archive phase data: {e}", exc_info=True)

async def generate_story(game_state: dict, events: list, history: list) -> str | None:
    """Main entry point for AI story generation."""
    if not client:
        logger.error("AI Client not initialized. Skipping story generation.")
        return None

    phase_name = str(game_state.get('phase', 'Unknown')).capitalize()
    phase_num = str(game_state.get('number', ""))
    phase_key = f"{phase_name} {phase_num}"
    
    logger.info(f"Requesting AI story for {phase_key} using {MODEL_NAME}...")
    
    prompt = _construct_ai_prompt(game_state, events, history)
    gen_config = types.GenerateContentConfig(temperature=0.7)

    max_retries = getattr(config, 'AI_MAX_RETRIES', 3)
    base_delay = getattr(config, 'AI_RETRY_DELAY', 2)

    for attempt in range(max_retries):
        try:
            response = await client.aio.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=gen_config
            )
            
            story_text = response.text
            thoughts = ""
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if getattr(part, 'thought', False):
                        thoughts += part.text

            if not story_text:
                logger.error(f"AI returned an empty story on attempt {attempt + 1}.")
                if attempt < max_retries - 1:
                    await asyncio.sleep(base_delay ** (attempt + 1))
                continue

            # 1. Archive the raw interaction
            _archive_phase_data(game_state, phase_key, prompt, thoughts, story_text.strip())

            # 2. Append Factual Summary
            mechanical_summary = _generate_mechanical_summary(game_state, events)
            final_output = f"{story_text.strip()}\n{mechanical_summary}"
            
            logger.info(f"Successfully generated and archived AI story for {phase_key}.")
            return final_output

        except asyncio.TimeoutError:
            logger.error(f"Gemini API timed out on attempt {attempt + 1}.")
            if attempt < max_retries - 1:
                await asyncio.sleep(base_delay ** (attempt + 1))
        except Exception as e:
            logger.error(f"Gemini API Error on attempt {attempt + 1}: {type(e).__name__} - {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(base_delay ** (attempt + 1))
            
    return None