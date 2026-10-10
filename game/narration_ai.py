# game/narration_ai.py
# This module is responsible for generating the AI narration for the game based on the events that occurred during the night and day phases. It uses the Google GenAI SDK to create engaging and thematic summaries of the game's progress, which are then posted in the designated channels. The narration is designed to be dynamic and adapt to different game modes (e.g., Classic Mafia vs Battle Royale) while ensuring that critical information is always clearly conveyed to the players.

import logging
import asyncio
import json
import os
from datetime import datetime

from discord import Game

try:
    import config
except ImportError:
    import templates.config_template as config

from utils.utilities import load_data # Fixed import path
from community import quirk_logic

from config import MODEL_NAME


# Import the new 2026 standard Google GenAI SDK
try:
    from google import genai
    from google.genai import types
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False

logger = logging.getLogger('discord')

# CRITICAL FIX: Update the model name to a known valid identifier
# If gemini-latest-flash still fails, fallback to gemini-2.5-flash
MODEL_NAME = getattr(config, 'MODEL_NAME', 'gemini-2.5-flash') if not MODEL_NAME else MODEL_NAME

# Initialize the client safely depending on how your config is named
_api_key = getattr(config, 'GEMINI_API_KEY', getattr(config, 'GOOGLE_AI_API_KEY', None))
if SDK_AVAILABLE and _api_key:
    # Use the synchronous client initialization as recommended by the new SDK
    client = genai.Client(api_key=_api_key)
else:
    client = None
    logger.error("Google GenAI SDK not installed OR API Key missing. AI Narration will fail.")

# Load themes dynamically from JSON
THEMES_DATA = load_data("data/narration/themes.json") or {} 

def _get_involved_quirks(game_state: dict, events: list) -> str:
    """
    Identifies relevant player quirks for the current phase/scene.
    Optimizes context by only including quirks for players mentioned in current events
    or relevant based on the game stage (Intro/Outro).
    """
    logger.info("Gathering involved player quirks for AI narration context.")
    if game_state.get('is_prologue', True):
        # Do not get quirks for prologue to save tokens and because players haven't chosen them yet
        logger.info("Prologue phase detected. Skipping quirk gathering to save tokens.")
        return ""
    # Also do not get quirks if no living players in game_state to save tokens and because would not be relevant
    if not game_state.get('living_players'):
        logger.info("No living players found in game state. Skipping quirk gathering.")
        return ""
    # For the introduction, include quirks for all living players to set the stage. For the outro, focus on survivors/winners. 
    # For standard scenes, use 'Just-in-Time' context to save tokens.
    all_approved = quirk_logic.get_all_approved()
    if not all_approved:
        logger.info("No approved quirks found. Skipping quirk context.")
        return ""
    # Identify involved player IDs from the current events and game state
    involved_ids = set()
    # Check if we are in a special narrative phase
    is_intro = game_state.get('is_introduction', False) 
    is_outro = game_state.get('is_game_over', False) 
    # For intros and outros, we want to include quirks for all living players to set the stage and focus on survivors/winners respectively. 
    # For standard scenes, we only include quirks for players directly involved in the events of that phase to optimize token usage.
    if is_intro:
        # For the start of the game, include all living players to set the stage
        for p in game_state.get('living_players', []):
            involved_ids.add(str(p.id))
    elif is_outro:
        # For the end, focus on the survivors/winners
        for p in game_state.get('living_players', []):
            if hasattr(p, 'is_alive') and p.is_alive:
                involved_ids.add(str(p.id))
    else:
        # Standard scene: Use 'Just-in-Time' context to save tokens.
        # After: Only pull quirks for players who are public knowledge (Victims/Lynch Targets)
        for e in events:
            etype = e.get('type', '')
            # 1. Victims and Lynch targets are always public context
            v = e.get('victim')
            # Safer check that only hides immune players during "kill" events
            v = e.get('victim')
            if v and hasattr(v, 'id'):
                # Determine if we should hide this victim
                # Hide if: It's a kill event AND the victim is immune
                is_immune = getattr(v.role, 'is_night_immune', False)
                is_kill_event = etype in ['kill', 'kill_royale', 'kill_immune']
                # We will include victims in the involved_ids for all events except when it's a kill event and the victim is immune, because in that case we want to 
                # avoid revealing too much about immune players through their death events. For example, if a player is killed but they are immune, we don't want the 
                # AI to see their quirks and meta-game that information to figure out they are immune. By excluding immune victims from the involved_ids during kill events, 
                # we can help preserve the mystery around immune players while still providing rich context for all other events and players.
                if not (is_kill_event and is_immune):
                    involved_ids.add(str(v.id))
            # Also include lynch victims even if they are immune, because their death is public knowledge and they are relevant to the story, but we can choose to hide their 
            # role/quirks if they are immune to preserve some mystery. For now, we will include them in the involved_ids so their quirks can be used, but we will rely on 
            # the MECHANICAL EVENTS section of the prompt to clearly communicate the immunity to the AI so it doesn't meta-game or reveal too much in the narration.
            for lv in e.get('victims', []) : # handle lynch victims list
                if hasattr(lv, 'id'): # Safer check to ensure we don't error out if 'victims' is not a list of player objects
                    is_immune = getattr(lv.role, 'is_night_immune', False)
                    is_kill_event = etype in ['kill', 'kill_royale', 'kill_immune']
                    # We will include lynch victims in the involved_ids even if they are immune, because their death is public knowledge and relevant to the story, 
                    # but we will rely on the MECHANICAL EVENTS section of the prompt to clearly communicate the immunity to the AI so it doesn't meta-game or reveal 
                    # too much in the narration. This allows us to use their quirks for richer storytelling while still preserving some mystery about their role if 
                    # they were immune.
                    if not (is_kill_event and is_immune):
                        involved_ids.add(str(lv.id))
            # 2. Actors / perpetrators in events are included so their personas can be woven into the narration
            for key in ['killer', 'actor', 'attacker', 'healer', 'blocker']:
                obj = e.get(key)
                if obj and hasattr(obj, 'id'):
                    involved_ids.add(str(obj.id))
    # Format the personas into a readable block for the AI
    persona_lines = []
    for p in game_state.get('living_players', []):
        uid_str = str(p.id)
        if uid_str in involved_ids and uid_str in all_approved:
            persona_lines.append(f"- {p.display_name}: {all_approved[uid_str]}")  
    if not persona_lines:
        return ""
    return "\n--- CHARACTER PERSONAS (Incorporate these traits naturally) ---\n" + "\n".join(persona_lines)

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
        etype = event.get('type')
        if etype in ['kill_battle_royale', 'kill', 'kill_royale', 'vigilante_kill']:
            v = event.get('victim')
            killers_list = event.get('killers')
            killer = event.get('killer') or event.get('actor') or event.get('attacker')

            if v:
                v_name = getattr(v, 'display_name', str(v))
                if v_name not in kill_data:
                    kill_data[v_name] = []
                if killers_list:
                    for k in killers_list:
                        k_name = getattr(k, 'display_name', str(k))
                        if k_name not in kill_data[v_name]:
                            kill_data[v_name].append(k_name)
                elif killer:
                    k_name = getattr(killer, 'display_name', str(killer))
                    if k_name not in kill_data[v_name]:
                        kill_data[v_name].append(k_name)
        elif etype in ['kill_healed', 'save', 'save_battle_royale']:
            v = event.get('target') or event.get('victim')
            if v:
                v_name = getattr(v, 'display_name', str(v))
                heal_counts[v_name] = heal_counts.get(v_name, 0) + 1
    
    processed_kills = set()
    
    for event in events:
        etype = event.get('type')
        
        # --- Lynches ---
        if etype == 'lynch':
            for v in event.get('victims', []):
                role_name = v.role.name if getattr(v, 'role', None) else "Unknown"
                lines.append(f"- 💀 **{v.display_name}** was lynched. They were **{role_name}**.")
                
        # --- Kills ---
        elif etype in ['kill', 'kill_battle_royale']:
            victim = event.get('victim')
            if victim and victim.display_name not in processed_kills:
                processed_kills.add(victim.display_name)
                role_name = victim.role.name if getattr(victim, 'role', None) else "Unknown"
                killers_data = kill_data.get(victim.display_name, [])
                count = len(killers_data)
                killer = event.get('killer') 
                killer_role = killer.role.name if killer and hasattr(killer, 'role') and killer.role else "Unknown"
                victim_name = victim.display_name
                if etype == 'kill':
                    if count > 1:
                        lines.append(f"- 🔪 **{victim_name}** was killed in the night, attacked {count} times! They were the **{role_name}**.")
                    else:
                        lines.append(f"- 🔪 **{victim_name}** was killed in the night by {killer_role}. They were the **{role_name}**.")
                elif etype == 'kill_battle_royale':
                    known_killers = [k for k in killers_data if k != "Unknown"]
                    if len(known_killers) == 1:
                        killers_str = known_killers[0]
                    elif len(known_killers) == 2:
                        killers_str = f"{known_killers[0]} and {known_killers[1]}"
                    elif len(known_killers) > 2:
                        killers_str = ", ".join(known_killers[:-1]) + f", and {known_killers[-1]}"
                    else:
                        killers_str = "Unknown"
                    if count > 1:
                        count_str = f"attacked {count} times! Killers: {killers_str}"
                    else:
                        count_str = f"killed by: {killers_str}"
                    lines.append(f"- 🔪 **{victim.display_name}** was brutally eliminated in the night. They were {count_str}.")
        # --- Mod/Admin Interventions ---
        elif etype == 'inactivity_kill':
            for v in event.get('victims', []):
                role_name = v.role.name if v.role else "Unknown"
                lines.append(f"- ⚡ **{v.display_name}** was struck down for inactivity. They were the **{role_name}**.")
        # --- Blocks ---
        elif etype in ['block', 'block_battle_royale']:
            action_type = event.get('action_type', 'action')
            action_target = event.get('action_target')
            target = event.get('target')
            blocker = event.get('blocker')

            # Investigation blocks must never show in summaries or stories
            if action_type == 'investigate':
                pass
            elif etype == 'block_battle_royale':
                blocker_name = blocker.display_name if blocker else "Someone"
                target_name = target.display_name if target else "someone"
                act_tgt_str = f" on **{action_target.display_name}**" if action_target else ""

                if action_type == 'kill':
                    lines.append(f"- 🛡️ **{blocker_name}** intervened and blocked **{target_name}**'s attack{act_tgt_str}!")
                elif action_type == 'heal':
                    lines.append(f"- 🛡️ **{blocker_name}** intervened and blocked **{target_name}** from providing medical aid{act_tgt_str}!")
                elif action_type == 'block':
                    lines.append(f"- 🛡️ **{blocker_name}** intervened and blocked **{target_name}** from interfering with someone!")
            else:
                # Classic Mafia: Only Blocked Kill, Blocked Heal (when stopping kill), and Blocked Block
                if action_type == 'kill':
                    lines.append("- 🛡️ An attempted murder in the night was thwarted by a shadowy figure!")
                elif action_type == 'heal':
                    lines.append("- 🛡️ An attempt to provide medical protection was intercepted and blocked by a shadowy figure.")
                elif action_type == 'block':
                    lines.append("- 🛡️ An attempt to interfere with another citizen was thwarted by a shadowy figure.")
        elif etype in ['block_missed', 'block_missed_royale']:
            pass
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
                    lines.append(f"- ❤️ **{victim.display_name}** was saved from a deadly attack.") 
                elif etype == 'save_battle_royale':
                    lines.append(f"- ❤️ **{victim.display_name}** was saved from a deadly attack by {healer_name}.")
                else: 
                    lines.append(f"- ❤️ **{victim.display_name}** was saved from a deadly attack by a mysterious force.")
        # -- Other Story types can be added here with more elif blocks ---
        elif etype == 'kill_immune':
            victim = event.get('victim')
            logger.info(f"Generating immune kill event story part for victim: {victim}")
            if not victim: return None
            lines.append(f"An assailant ambushed **{victim.display_name}** in the dark, but their target was unfazed. The attack had no effect!")
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
        etype = e.get('type')
        if etype in ['kill', 'kill_battle_royale', 'kill_royale', 'vigilante_kill']:
            v = e.get('victim')
            killers_list = e.get('killers')
            killer = e.get('killer') or e.get('actor') or e.get('attacker')

            if v:
                v_name = getattr(v, 'display_name', str(v))
                if v_name not in kill_data:
                    kill_data[v_name] = []
                if killers_list:
                    for k in killers_list:
                        k_name = getattr(k, 'display_name', str(k))
                        if k_name not in kill_data[v_name]:
                            kill_data[v_name].append(k_name)
                elif killer:
                    k_name = getattr(killer, 'display_name', str(killer))
                    if k_name not in kill_data[v_name]:
                        kill_data[v_name].append(k_name)
        elif etype in ['kill_healed', 'save', 'save_battle_royale']:
            v = e.get('target') or e.get('victim')
            if v:
                v_name = getattr(v, 'display_name', str(v))
                heal_counts[v_name] = heal_counts.get(v_name, 0) + 1

    
    # --- NEW: DYNAMIC MODE CONTEXT ---
    if "battle_royale" in game_mode or game_mode == "br":
        if story_type == "Rom Com":
            mode_guide = """
*** CRITICAL GAME MODE: BATTLE ROYALE (ROM COM SPEED-DATING FREE-FOR-ALL) ***
- A chaotic dating free-for-all where every single person is competing to be the last eligible bachelor/bachelorette standing!
- STRICTLY NON-DEATH: No physical violence or murder. 'Kills' are dramatic breakups, cold ghostings, and public dumpings.
- A 'lynch' represents the group intervening to dump the most toxic red-flag dater.
- A 'night kill' represents a private date turning into an awkward disaster and instant breakup.
"""
            lynch_text = "The singles group voted to publicly DUMP"
        elif story_type == "Office Restructuring":
            mode_guide = """
*** CRITICAL GAME MODE: BATTLE ROYALE (OFFICE DOWNSIZING CUTTHROAT WAR) ***
- A high-stakes corporate cutthroat war where only ONE employee gets to keep their job and annual bonus!
- STRICTLY NON-DEATH: No physical violence. 'Kills' are termination pink slips, layoffs, and HR escorts.
- A 'lynch' represents an emergency performance review where the team votes to terminate a competitor.
- A 'night kill' represents covert corporate sabotage or sudden executive firing.
"""
            lynch_text = "The committee voted to TERMINATE"
        else:
            mode_guide = """
*** CRITICAL GAME MODE: BATTLE ROYALE (FREE-FOR-ALL) ***
- This is a brutal, last-man-standing deathmatch. There is no 'Town' and no 'Mafia'.
- Every single player is armed (e.g., holding a knife, a makeshift weapon, etc.).
- Trust does not exist. Everyone is a killer. 
- A 'lynch' represents the group temporarily forming a desperate, violent pact to eliminate the biggest perceived threat during the day.
- A 'night kill' represents a brutal, solitary ambush or duel in the dark.
- Make each death unique, emphasizing the chaos, and violence of a world where everyone is out to get everyone else killed.
"""
            lynch_text = "The remaining survivors turned on and slaughtered"
    else:
        if story_type == "Rom Com":
            mode_guide = """
*** CRITICAL GAME MODE: CLASSIC ROM COM (SFW ROMANTIC COMEDY) ***
- A witty, fast-paced romantic comedy. Genuine Hopeful Singles (Town) vs Toxic Serial Heartbreakers (Mafia) and a Commitment-Phobe (Serial Killer).
- STRICTLY NON-DEATH: Absolutely NO killing, blood, gore, or corpses. Eliminations are heartbreaks: dumped, ghosted, or friend-zoned!
- A 'lynch' is an emergency brunch intervention where the group agrees to dump someone.
- A 'night kill' is a cold breakup or ghosting text.
"""
            lynch_text = "The group voted to publicly DUMP"
        elif story_type == "Office Restructuring":
            mode_guide = """
*** CRITICAL GAME MODE: CLASSIC CORPORATE RESTRUCTURING (OFFICE SATIRE) ***
- An office comedy and corporate downsizing drama. Hardworking Employees (Town) vs Ruthless Restructuring Consultants (Mafia) and a Rogue Headhunter (Serial Killer).
- STRICTLY NON-DEATH: Absolutely NO physical violence or killing. Eliminations are corporate layoffs, pink slips, and resignations!
- A 'lynch' is a tense all-hands performance vote to make someone redundant.
- A 'night kill' is an after-hours pink slip or HR escort from the premises.
"""
            lynch_text = "The company voted to LAY OFF"
        else:
            mode_guide = """
*** CRITICAL GAME MODE: CLASSIC MAFIA ***
- This is a game of deception and hidden identities. An innocent, uninformed majority (Town) vs a hidden, informed minority (Mafia/Cult).
- Emphasize the fear of the unknown, the tragedy of innocent people turning on each other, and the shadows hiding the true killers.
- A 'lynch' is a frantic, democratic execution by the frightened crowd.
- Make each death unique, but fit into the wider story based on previous chapters. 
- There are up to three separate factions (Town, Mafia, Serial Killer) with different motivations and goals.
"""
            lynch_text = "The town voted to LYNCH"

    # 1. Format Events Context - NOW MODE-AWARE
     # Handle dynamic "Uneventful Phase" text so it makes sense contextually
    if "night" in current_phase:
        if story_type == "Rom Com":
            events_text = "NARRATIVE EVENT: The night passed with no breakups. Everyone had peaceful dates or restful sleep."
        elif story_type == "Office Restructuring":
            events_text = "NARRATIVE EVENT: The night shift was quiet. No termination notices or pink slips were issued."
        else:
            events_text = "NARRATIVE EVENT: The night passed completely uneventfully. Emphasize the town's restless sleep, paranoia, and waking up to find everyone perfectly safe."
    elif "day" in current_phase:
        if story_type == "Rom Com":
            events_text = "NARRATIVE EVENT: The group argued over dating habits but couldn't agree to dump anyone today."
        elif story_type == "Office Restructuring":
            events_text = "NARRATIVE EVENT: The all-hands meeting concluded with no layoffs or terminations today."
        else:
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
            # Lynch event (Classic and Battle Royale)
            if etype == 'lynch':
                for v in e.get('victims', []):
                    role_disp = v.role.display_name if v.role and getattr(v.role, 'display_name', v.role.name) != v.role.name else (v.role.name if v.role else "Unknown")
                    role_name = f"{role_disp} ({v.role.name})" if v.role and getattr(v.role, 'display_name', v.role.name) != v.role.name else role_disp
                    if game_mode == "battle_royale":
                        event_lines.append(f"CRITICAL EVENT: {lynch_text} **{v.display_name}** as decided by the group.")
                    else:
                        if story_type == "Rom Com":
                            event_lines.append(f"CRITICAL EVENT: {lynch_text} {v.display_name}. Their true dating role was {role_name}.")
                        elif story_type == "Office Restructuring":
                            event_lines.append(f"CRITICAL EVENT: {lynch_text} {v.display_name}. Their corporate role was {role_name}.")
                        else:
                            event_lines.append(f"CRITICAL EVENT: {lynch_text} {v.display_name}. Upon searching their body, their true identity was revealed as {role_name}.")
            # Kill events (Classic)
            elif etype == 'kill':
                victim = e.get('victim')
                if victim and victim.display_name not in processed_kills:
                    processed_kills.add(victim.display_name)
                    killers = kill_data.get(victim.display_name, [])
                    count = len(killers)    
                if victim:
                    role_disp = victim.role.display_name if victim.role and getattr(victim.role, 'display_name', victim.role.name) != victim.role.name else (victim.role.name if victim.role else "Unknown")
                    role_name = f"{role_disp} ({victim.role.name})" if victim.role and getattr(victim.role, 'display_name', victim.role.name) != victim.role.name else role_disp
                    if story_type == "Rom Com":
                        event_lines.append(f"CRITICAL EVENT: {victim.display_name} was DUMPED / HEARTBROKEN in the night. Their true role was {role_name}.")
                    elif story_type == "Office Restructuring":
                        event_lines.append(f"CRITICAL EVENT: {victim.display_name} was TERMINATED / LAID OFF in the night. Their true corporate role was {role_name}.")
                    else:
                        event_lines.append(f"CRITICAL EVENT: {victim.display_name} was MURDERED in the night. Upon searching their body, their true identity was revealed as {role_name}.")
            # Inactivity kill events (Classic and Battle Royale) 
            elif etype == 'inactivity_kill':
                for v in e.get('victims', []):
                    role_name = v.role.name if v.role else "Unknown"
                    event_lines.append(f"CRITICAL EVENT: {v.display_name} mysteriously vanished or dropped dead from weakness/inactivity. Their true identity was {role_name}.")
            # Block event (Classic)
            elif etype == 'block':
                action_type = e.get('action_type', 'action')
                action_target = e.get('action_target')
                action_target_name = action_target.display_name if action_target else "their target"

                if action_type == 'kill':
                    if story_type == "Rom Com":
                        event_lines.append(f"CRITICAL EVENT: An attempted BREAKUP / DUMPING in the night was INTERCEPTED and STOPPED by a mysterious figure before anyone's heart could be broken! An angry suitor was stopped before they could dump {action_target_name}. Focus the narrative on the thwarted breakup, NOT on the identity of the person who tried to dump them.")
                    elif story_type == "Office Restructuring":
                        event_lines.append(f"CRITICAL EVENT: An attempted TERMINATION / FIRING was INTERCEPTED and BLOCKED before an employee could be handed their pink slip! Management or HR was stopped before {action_target_name} could be laid off. Focus the narrative on the blocked firing, NOT on who ordered it.")
                    else:
                        event_lines.append(f"CRITICAL EVENT: An attempted MURDER / ASSASSINATION in the night was INTERCEPTED and THWARTED by a shadowy figure! An attacker was stopped in their tracks before they could eliminate {action_target_name}. Focus the narrative on the suspense of the thwarted attack and the intervention, NOT on the identity of the attacker.")
                elif action_type == 'heal':
                    if story_type == "Rom Com":
                        event_lines.append(f"CRITICAL EVENT: An attempt by a loyal wingman to protect {action_target_name} from a breakup was INTERCEPTED and BLOCKED by a meddling third party, leaving them completely vulnerable to heartbreak!")
                    elif story_type == "Office Restructuring":
                        event_lines.append(f"CRITICAL EVENT: An attempt to provide job protection for {action_target_name} was INTERCEPTED and BLOCKED by red tape, leaving them vulnerable to termination!")
                    else:
                        event_lines.append(f"CRITICAL EVENT: An attempt to provide medical protection to {action_target_name} was INTERCEPTED and BLOCKED by a shadowy figure before it could take effect, leaving them completely defenseless against the attack tonight!")
                elif action_type == 'block':
                    if story_type == "Rom Com":
                        event_lines.append("CRITICAL EVENT: An attempt to cockblock / interfere with someone was INTERCEPTED and THWARTED in the shadows!")
                    elif story_type == "Office Restructuring":
                        event_lines.append("CRITICAL EVENT: An attempt to sabotage / stonewall a coworker's shift was INTERCEPTED and THWARTED!")
                    else:
                        event_lines.append("CRITICAL EVENT: A shadowy figure's attempt to interfere with / roleblock another citizen was INTERCEPTED and THWARTED in the dark.")

            # Block event (Battle Royale)
            elif etype == 'block_battle_royale':
                target = e.get('target')
                blocker = e.get('blocker')
                action_type = e.get('action_type', 'action')
                action_target = e.get('action_target')
                target_name = target.display_name if target else "someone"
                blocker_name = blocker.display_name if blocker else "Someone"
                act_tgt_name = action_target.display_name if action_target else "their target"

                if action_type == 'kill':
                    event_lines.append(f"CRITICAL EVENT: **{blocker_name}** intervened and BLOCKED **{target_name}** from executing an attack on **{act_tgt_name}**!")
                elif action_type == 'heal':
                    event_lines.append(f"CRITICAL EVENT: **{blocker_name}** intervened and BLOCKED **{target_name}** from healing **{act_tgt_name}**!")
                elif action_type == 'block':
                    event_lines.append(f"CRITICAL EVENT: **{blocker_name}** intervened and BLOCKED **{target_name}** from interfering with **{act_tgt_name}**!")
            # Missed Block event: no prompt emitted
            elif etype in ['block_missed', 'block_missed_royale']:
                pass
            # Save (Heal) event (Classic)
            elif etype == 'save': 
                victim = e.get('victim')
                if victim:
                    role_name = victim.role.name if victim.role else "Unknown"
                    event_lines.append(f"CRITICAL EVENT: {victim.display_name} was SAVED by a the doctor who heled them after the attack.")
            # Save (Heal) event (Battle Royale)
            elif etype == 'save_battle_royale':  
                victim = e.get('victim')
                healer = e.get('healer')
                healer_name = healer.display_name if healer and hasattr(healer, 'display_name') else "Unknown"
                if victim:
                    event_lines.append(f"CRITICAL EVENT: {victim.display_name} was SAVED from a deadly attack by {healer_name} and survived.")
            # Kill events (Battle Royale)   
            elif etype == 'kill_battle_royale':
                victim = e.get('victim')
                killer = e.get('killer')
                killer_name = killer.display_name if killer and hasattr(killer, 'display_name') else "Unknown"
                if victim and victim.display_name not in processed_kills:
                    processed_kills.add(victim.display_name)
                    killers = kill_data.get(victim.display_name, [])
                    count = len(killers)
                    known_killers = [k for k in killers if k != "Unknown"]
                    if len(known_killers) == 1:
                        killers_str = known_killers[0]
                    elif len(known_killers) == 2:
                        killers_str = f"{known_killers[0]} and {known_killers[1]}"
                    elif len(known_killers) > 2:
                        killers_str = ", ".join(known_killers[:-1]) + f", and {known_killers[-1]}"
                    else:
                        killers_str = "Unknown"
                    if count > 1:
                        event_lines.append(f"CRITICAL EVENT: {victim.display_name} was brutally KILLED in the night, suffering {count} separate lethal attacks by {killers_str}! In your story, vividly describe how all {count} attackers ({killers_str}) targeted and overwhelmed {victim.display_name} together or in succession.")
                    else:
                        event_lines.append(f"CRITICAL EVENT: {victim.display_name} was brutally KILLED in the night. They were killed by {killers_str}.")
            # Kill immunity event (Classic and Battle Royale)
            elif etype == 'kill_immune':
                victim = e.get('victim')
                if victim:
                    if game_state.get('game_type', '').lower() in ['battle_royale', 'br']:
                        # After: Masks the target of a failed kill in Classic mode
                            v = e.get('victim')
                            t_name = v.display_name if v else "a target"
                            event_lines.append(f"PUBLIC EVENT: {t_name} survived an assassination attempt.")
                    else:
                        # Strictly anonymous for Classic Mafia
                        event_lines.append("SECRET EVENT: An assassination attempt failed. The target survived anonymously.") 
                        role_name = victim.role.name if victim.role else "Unknown"
                        event_lines.append(f"SECRET EVENT: An assailant ambushed **{role_name}** in the dark, but their target was unfazed. The attack had no effect!.")    
            # Investigation event (Classic and Battle Royale) - This is a secret event that gives the AI context but is not revealed to players, so we can be more descriptive to help the AI generate better stories without worrying about meta-gaming or players using the narration as a source of information about investigations.
            elif etype in ['investigate', 'investigate_royale']:
                #event_lines.append("SECRET EVENT: A lone figure was seen snooping around someone's house, trying to uncover secrets.")   
                pass  
            # Promotion event (Classic and Battle Royale)
            elif etype == 'promotion':
                event_lines.append("INFORMATION EVENT: In the mafia underground, a power vacuum has been filled. A new leader has risen to command the night's dark deeds.")                          
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
    
    # QUIRKS INTEGRATION
    quirks_block = _get_involved_quirks(game_state, events) if not is_prologue else "" # Don't include quirks in the prologue to save tokens and focus on world-building

    narrative_directives = ""
    if is_prologue:
        narrative_directives += "- DO NOT name any players yet. Focus on world-building. This should set the scene for the comming conflict, introducing the setting, the tone, and the atmosphere. It should feel like the prequal chapter of a novel, drawing readers in with vivid descriptions and a sense of mystery. Do not reveal any specific player actions or outcomes in the prologue."
    elif is_introduction or phase_name.lower() == "preparation":
        narrative_directives += f"- Write this as the opening chapter of the story, introducing the main characters {living_players} and setting the scene for the conflict. This should be a gripping introduction that hooks the reader, providing just enough context to understand the stakes without revealing any outcomes yet. This should not include any specific events, but can reference the general situation and the relationships between characters. Do not mention players roles or specific actions, but you can use their names and hint at their personalities and motivations based on the theme."
    elif is_game_over:
        winner_clean = str(winner).strip()
        winner_lower = winner_clean.lower()
        if winner_lower == "draw":
            if story_type == "Rom Com":
                narrative_directives += "- Write this as a comedic or bittersweet conclusion where nobody found love and everyone ended up single and heartbroken. Reflect on the chaotic dates, bad breakups, and missed romantic connections. CRITICAL: The conclusion narrative MUST explicitly declare that the game/match ended in a DRAW with no winners!"
            elif story_type == "Office Restructuring":
                narrative_directives += "- Write this as a conclusion where corporate downsizing went too far and the entire office closed down. Everyone was laid off and the building is empty. CRITICAL: The conclusion narrative MUST explicitly declare that the game/conflict ended in a DRAW with no winners left standing!"
            else:
                narrative_directives += "- Write this as a tragic conclusion to the story based on the Draw result. In a Draw, all players are dead, so the story should reflect on the senseless loss and the futility of the conflict. This should conclude the story and reflect on the overall narrative arc, referencing key events and moments from the game. CRITICAL: The conclusion narrative MUST explicitly declare that the conflict ended in a DRAW with all participants eliminated and no one left to claim victory!"
        elif winner_lower == "mafia":
            if story_type == "Rom Com":
                narrative_directives += f"- Write this as a conclusion where the Heartbreakers / Toxic Daters have taken over the dating scene, leaving broken hearts everywhere. Name all surviving players ({living_players}) and their fates. CRITICAL: The conclusion narrative MUST explicitly announce that the Heartbreakers (Mafia) have WON the game!"
            elif story_type == "Office Restructuring":
                narrative_directives += f"- Write this as a conclusion where Corporate Downsizing successfully purged the office. Name all surviving players ({living_players}) and their corporate fates. CRITICAL: The conclusion narrative MUST explicitly announce that Corporate Downsizing (Mafia) has WON the game!"
            else:
                narrative_directives += f"- Write this as a tragic conclusion to the story based on the Mafia win result. Mafia win is always tragic, so the story should reflect on the darkness and corruption that has taken over, and the loss of innocent lives. Name all surviving players ({living_players}) and their fates, emphasizing the grim consequences of the Mafia's victory. This should conclude the story and reflect on the overall narrative arc, referencing key events and moments from the game. CRITICAL: The conclusion narrative MUST explicitly announce that the MAFIA has WON the game!"
        elif winner_lower == "town":
            if story_type == "Rom Com":
                narrative_directives += f"- Write this as a triumphant, feel-good romantic comedy conclusion where the Hopeless Romantics defeated toxicity and found genuine love. Name all surviving players ({living_players}) and celebrate their romance. CRITICAL: The conclusion narrative MUST explicitly announce that the Hopeless Romantics (Town) have WON the game!"
            elif story_type == "Office Restructuring":
                narrative_directives += f"- Write this as a triumphant conclusion where the Honest Staff successfully banded together to protect their jobs and company culture. Name all surviving players ({living_players}) and their career triumphs. CRITICAL: The conclusion narrative MUST explicitly announce that the Honest Staff (Town) has WON the game!"
            else:
                narrative_directives += f"- Write this as a triumphant conclusion to the story based on the Town win result. Town win is always triumphant, so the story should reflect on the heroism and resilience of the town, and the defeat of the Mafia. Name all surviving players ({living_players}) and their fates, emphasizing the positive outcomes of their efforts. This should conclude the story and reflect on the overall narrative arc, referencing key events and moments from the game. CRITICAL: The conclusion narrative MUST explicitly announce that the TOWN has WON the game!"
        elif winner_lower == "serial killer":
            narrative_directives += f"- Write this as a dark and chilling conclusion where the Serial Killer has outlasted and eliminated all opposition. Name the surviving player ({living_players}). CRITICAL: The conclusion narrative MUST explicitly announce that the SERIAL KILLER has WON the game!"
        else: # battle royale winner or individual player winner
            narrative_directives += f"- Write this as a conclusion to the story based on the {winner} result. Focus on the fate of the winner {living_players} and the overall narrative arc, referencing key events and moments from the game. CRITICAL: The conclusion narrative MUST explicitly announce that {winner} has WON the game!"
    elif is_epilogue:
        narrative_directives += "- Write this as an epilogue chapter reflecting on the aftermath of the conflict. This should provide closure to the story, reflecting on the fates of the surviving players (if any) and the consequences of the conflict. This can be more reflective and less action-oriented, providing a sense of resolution to the narrative arc. This shold difinitely finish the story, providing a sense of closure and finality to the game."
    # After: Explicit "Fog of War" instructions
    if game_mode in ['battle_royale', 'br']:
        rules_block = """--- BATTLE ROYALE RULES (OPEN INFORMATION) ---
    1. TRANSPARENCY: Attackers and targets are public knowledge. Use names freely."""
    else:
        rules_block = """--- IRONCLAD RULES OF ANONYMITY (CLASSIC MAFIA) ---
    1. DO NOT GUESS: If a perpetrator is not named in the MECHANICAL EVENTS, do NOT assign the action to a living player.
    2. FOG OF WAR: Night killers and healers are ALWAYS anonymous. Refer to them as 'the assailant' or 'a shadowy figure' or a 'helpful bystander'.
    3. NO OUTING: Never describe a named living player as being part of an aggressive act unless explicitly told."""

    # 4. Construct the Reasoning Rubric
    if story_type == "Rom Com":
        living_rubric = (
            f"1. ACTIVE DATERS ONLY: {', '.join(living_players)}. \n"
            f"   CRITICAL: If a player is NOT in this list, or was eliminated in previous chapters, they have been DUMPED, GHOSTED, or are NO LONGER ON THE DATING MARKET. "
            f"STRICTLY NO MURDER, NO DEATH, NO CORPSES, NO BLOOD, NO PHYSICAL VIOLENCE. Eliminated players are nursing broken hearts or moving on, unable to participate."
        )
    elif story_type == "Office Restructuring":
        living_rubric = (
            f"1. CURRENT EMPLOYEES ONLY: {', '.join(living_players)}. \n"
            f"   CRITICAL: If a player is NOT in this list, or was eliminated in previous chapters, they have been FIRED, LAID OFF, or MADE REDUNDANT. "
            f"STRICTLY NO MURDER, NO DEATH, NO CORPSES, NO VIOLENCE. Former employees have surrendered their keycards, packed their cardboard boxes, and left the building."
        )
    elif story_type == "Explicit Kinky NSFW":
        living_rubric = (
            f"1. ACTIVE PARTICIPANTS (ALL R18 CONSENTING ADULTS): {', '.join(living_players)}. \n"
            f"   CRITICAL: All characters are consenting adults (18+). If a player is NOT in this list, they have tapped out, reached their limit, or retired to the aftercare lounge."
        )
    else:
        living_rubric = (
            f"1. LIVING PLAYERS ONLY: {', '.join(living_players)}. \n"
            f"   CRITICAL: If a player is NOT in this list, or died in previous chapters, they are a CORPSE. Corpses cannot speak, react, or perform actions."
        )

    elim_instruction = (
        "Do not reveal exact roles unless a player was eliminated (e.g. dumped, ghosted) this phase. If a player was eliminated, you may reveal their role in the narration. REMEMBER: Strictly NO murder, death, corpses, or physical violence." if story_type == "Rom Com" else (
            "Do not reveal exact roles unless a player was eliminated (e.g. fired, laid off) this phase. If a player was eliminated, you may reveal their role in the narration. REMEMBER: Strictly NO murder, death, corpses, or physical violence." if story_type == "Office Restructuring" else
            "Do not reveal exact roles unless a player was killed this phase. If a player was killed, you may reveal their role in the narration."
        )
    )

    prompt = f"""You are an elite, highly creative Game Moderator (GM) running a text-based forum game of Mafia/Social Deduction. 
Your job is to write the flavor text for the current phase. 

CURRENT THEME: '{story_type}'
OVERARCHING PREMISE: {theme_description} 
ATMOSPHERE: {atmosphere}

CURRENT PHASE: {phase_name} {phase_num}

--- REASONING RUBRIC (Internal Rules) ---
{living_rubric}
{custom_rules}
3. CHARACTER PERSONAS: If traits are listed below, weave them into dialogue and behavior naturally. Show, don't tell. Do not label them as 'quirks'.
{quirks_block}




--- MECHANICAL EVENTS TO NARRATE THIS PHASE ---
{events_text}

--- PREVIOUS STORY CONTEXT ---
{history_text}
- Never directly copy previous story text, but use it to understand the narrative arc and character development so far.
- Where possible have narrative arcs described out

--- WRITING STYLE ---
- Length: Keep the story concise, punchy, and highly readable. Aim for exactly 150 to 250 words (2-3 short paragraphs). Do not overwrite. Do not use more than 250 words. Be concise and impactful. Less is better.
- Originality: NEVER directly copy or repeat paragraphs from the PREVIOUS STORY CONTEXT. Use it only for continuity, but ensure your new chapter is completely originally written, but follows the same plot and character development.

{narrative_directives}
{writing_style}
Do not reference chapter numbers or phase numbers in the story. Do not break the fourth wall or reference the game mechanics directly.
Note: never use gendered pronouns, you can use non-gender pronouns such as "they" or "them". Refer to all players by their display names only. {elim_instruction} Always follow the mechanical events closely and narrate them in a way that fits the theme and style.

Write the next chapter of the story now:
"""
    return prompt

def _archive_phase_data(game_state: dict, phase_key: str, prompt: str, thoughts: str, result: str):
    """Stores the complete AI transaction for debugging and observability."""
    game_id = game_state.get('game_id', 'unknown_game')
    logger.info(f"Archiving AI data for game {game_id} - game mode {game_state.get('game_type', 'classic')}")
    game_mode_raw = str(game_state.get('game_type', 'classic')).lower()
    folder_name = "Battle Royale" if "battle_royale" in game_mode_raw else "Classic"
    
    archive_dir = os.path.join(str(config.data_save_path).title(), folder_name, game_id)
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
    # 2. Configure Thinking depth safely based on the model
    # Only append the thinking config if we are using a reasoning model
    generation_config_args = {"temperature": 0.7}
    
    # Configure Thinking depth safely based on the model
    # Gemini 3 Flash, 2.5, and explicitly named thinking models support this!
    model_lower = MODEL_NAME.lower()
    if "thinking" in model_lower or "gemini-3" in model_lower:
        generation_config_args["thinking_config"] = types.ThinkingConfig(
            include_thoughts=True,
            thought_token_limit=1024
        )
        
    generation_config = types.GenerateContentConfig(**generation_config_args)

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
            
            # Attempt to extract thoughts safely
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if getattr(part, 'thought', False): 
                        # Safe concatenation in case part.text is None
                        thoughts += (part.text or "")

            if not story_text:
                logger.error(f"AI returned an empty story on attempt {attempt + 1}.")
                if attempt == max_retries - 1:
                    return None
                # FIXED: Changed ** back to * to prevent massive minute-long hangs
                await asyncio.sleep(base_delay * (attempt + 1))
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
            # FIXED: Math operator corrected here too
            await asyncio.sleep(base_delay * (attempt + 1))
        except Exception as e:
            logger.error(f"Gemini API Error on attempt {attempt + 1}: {type(e).__name__} - {e}", exc_info=True)
            if attempt == max_retries - 1:
                return None
            # FIXED: Math operator corrected here too
            await asyncio.sleep(base_delay * (attempt + 1))