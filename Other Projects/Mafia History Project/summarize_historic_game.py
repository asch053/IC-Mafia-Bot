# summarize_historic_game.py
"""
AI Game Summarizer for the Imperial Conflict Mafia History Project.
Uses Google Gemini to synthesize moderator stories, player comments,
night actions, and day lynches into a Narrative Chronicle and Mechanical Box Score.
"""

import os
import json
import re
from typing import Dict, Any, Tuple
from dotenv import load_dotenv
from google import genai
from segment_game_thread import get_posts_for_thread, segment_game_thread

# 1. Load Environment Configuration
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(ROOT_DIR, '.env'))
load_dotenv(os.path.join(ROOT_DIR, '.env.test'))

API_KEY = os.getenv('GOOGLE_AI_API_KEY_HISTORIC_PROJECT') or os.getenv('GOOGLE_AI_API_KEY')
PRIMARY_MODEL = "gemini-3.1-flash-lite"
FALLBACK_MODELS = ["gemini-3.1-pro-preview", "gemini-2.5-flash"]

SYSTEM_PROMPT = """You are the official Head Historian and Chronicler for the Imperial Conflict Mafia community.
Your mission is to analyze historical Mafia game threads (transcribed from forum and chat archives) and produce two distinct sections:

1. A captivating NARRATIVE GAME CHRONICLE (in Markdown):
   - Retell the story of the game as an exciting, literary chronicle honoring the moderator's original theme and setting (e.g. sci-fi generation ship, Gotham City, James Bond 007 espionage, medieval fantasy).
   - Divide into thematic chapters (e.g., Chapter 1: The Gathering, Chapter 2: First Blood, Chapter 3: Web of Deceit, Chapter 4: The Final Stand).
   - Highlight the dramatic tension, pivotal lynches, secret night murders, and player deceptions.

2. A strictly formatted MECHANICAL BOX SCORE (in JSON):
   - winning_faction: "Town", "Mafia", "Serial Killer", "Draw", or "Neutral"
   - inferred: boolean (True if you had to infer the outcome due to an incomplete or missing closing post; False if explicitly confirmed by the moderator)
   - mvp: { "player": "Name", "rationale": "Why this player made the decisive impact" }
   - roster: List of objects [ { "player": "Name", "role": "Role Name", "alignment": "Town"|"Mafia"|"Neutral", "survived": bool, "death_phase": "Day X / Night X" } ]
   - timeline: List of phase events [ { "phase": "Day 1 / Night 1", "event": "Lynch"|"Kill"|"Save"|"Modkill", "target": "Name", "details": "Brief note" } ]
   - notable_moments: List of key plays, blunders, or clever claims.

Format your output with clear markdown headings:
# NARRATIVE CHRONICLE
...[Markdown story chapters]...

# MECHANICAL BOX SCORE
```json
...[Structured JSON]...
```
"""

def build_prompt_context(game_meta: Dict[str, Any], segmented: Dict[str, Any]) -> str:
    """Builds a structured, token-efficient prompt string from the segmented game data."""
    lines = []
    lines.append(f"GAME TITLE: {game_meta.get('title', 'Unknown Game')}")
    lines.append(f"THREAD ID: {game_meta.get('thread_id', 'Unknown')}")
    lines.append(f"MODERATOR: {segmented.get('moderator', 'Unknown')}")
    lines.append(f"TOTAL POSTS: {segmented.get('total_posts', 0)}")
    lines.append(f"EXPLICIT CLOSING POST FOUND: {segmented.get('has_explicit_closing', False)}")
    lines.append("\n=================== MODERATOR OPENING THEME & RULES ===================")
    lines.append(segmented.get('opening_theme', 'No opening theme recorded.')[:3000])

    lines.append("\n=================== CHRONOLOGICAL PHASE STORIES & VOTE COUNTS ===================")
    for i, ps in enumerate(segmented.get('phase_stories', [])):
        lines.append(f"\n--- Phase Event #{i+1} ({ps['type']} at {ps['timestamp']}) ---")
        lines.append(ps['text'])

    lines.append("\n=================== MODERATOR ENDGAME / CLOSING DEBRIEF ===================")
    if segmented.get('endgame_post'):
        lines.append(segmented['endgame_post'])
    else:
        lines.append("NOTE: No explicit closing reveal post was found. Please INFER the final outcome, surviving players, and winning faction based on the preceding phase events and player eliminations, and mark 'inferred': true in the JSON box score.")

    lines.append("\n=================== NOTABLE PLAYER CLAIMS & ACCUSATIONS ===================")
    for p in segmented.get('high_signal_player_posts', [])[:20]:
        lines.append(f"[{p['author']}]: {p['content'][:300]}")

    return "\n".join(lines)

def summarize_historic_game(thread_id: str, game_meta: Dict[str, Any] = None) -> Dict[str, Any]:
    """Summarizes a historic game thread, returning chronicle, box score, and metadata."""
    if game_meta is None:
        game_meta = {"title": f"Historic Game {thread_id}", "thread_id": thread_id}

    posts = get_posts_for_thread(thread_id)
    if not posts:
        raise ValueError(f"No posts found for thread ID {thread_id}")

    segmented = segment_game_thread(posts)
    prompt_context = build_prompt_context(game_meta, segmented)

    result = {
        "thread_id": thread_id,
        "title": game_meta.get('title', f"Mafia {thread_id}"),
        "moderator": segmented.get('moderator'),
        "total_posts": segmented.get('total_posts'),
        "has_explicit_closing": segmented.get('has_explicit_closing', False),
        "inferred_outcome": not segmented.get('has_explicit_closing', False)
    }

    # Attempt Gemini LLM Generation
    client = None
    if API_KEY:
        try:
            client = genai.Client(api_key=API_KEY)
        except Exception as e:
            print(f"Warning: Could not initialize Gemini client: {e}")

    llm_success = False
    if client:
        models = [PRIMARY_MODEL] + FALLBACK_MODELS
        for model in models:
            try:
                print(f"Calling Gemini API with model: {model} for thread {thread_id}...")
                response = client.models.generate_content(
                    model=model,
                    contents=f"{SYSTEM_PROMPT}\n\nHere is the historical game thread data:\n{prompt_context}"
                )
                raw_text = response.text
                result["raw_llm_output"] = raw_text
                # Parse Chronicle and JSON box score from LLM output
                chronicle_match = re.search(r'# NARRATIVE CHRONICLE\s*(.*?)(?=# MECHANICAL BOX SCORE|$)', raw_text, re.DOTALL)
                box_score_match = re.search(r'```json\s*(.*?)\s*```', raw_text, re.DOTALL)

                result["narrative_chronicle"] = chronicle_match.group(1).strip() if chronicle_match else raw_text
                if box_score_match:
                    result["box_score"] = json.loads(box_score_match.group(1))
                result["model_used"] = model
                result["ai_status"] = "live_generated"
                llm_success = True
                print(f"Successfully generated summary for {thread_id} using {model}!")
                break
            except Exception as e:
                print(f"Gemini call with {model} failed: {e}")
                if "RESOURCE_EXHAUSTED" in str(e):
                    result["quota_exhausted"] = True

    # Fallback / Initial Reconstruction Draft if LLM Quota Exhausted
    if not llm_success:
        print(f"Using structured rule-based synthesizer fallback for thread {thread_id}...")
        result["ai_status"] = "reconstructed_draft (pending LLM quota)"
        result["narrative_chronicle"] = _generate_rule_based_chronicle(game_meta, segmented)
        result["box_score"] = _extract_rule_based_box_score(game_meta, segmented)

    return result

def _generate_rule_based_chronicle(game_meta: Dict[str, Any], segmented: Dict[str, Any]) -> str:
    """Generates a clean markdown chronicle from parsed moderator posts when LLM is offline."""
    title = game_meta.get('title', 'Historic Mafia Game')
    mod = segmented.get('moderator', 'Game Moderator')
    lines = [f"# {title}", f"*Chronicle of the historical match hosted by {mod}*\n"]
    lines.append("### Chapter 1: The Briefing & Setting")
    lines.append(segmented.get('opening_theme', 'The game began with the crew gathering.')[:1200] + "\n")

    lines.append("### Chapter 2: The Struggle & Escalation")
    for i, ps in enumerate(segmented.get('phase_stories', [])[:6]):
        lines.append(f"**Phase Event {i+1}**: {ps['text'][:400]}...\n")

    lines.append("### Chapter 3: The Climax & Resolution")
    lines.append(segmented.get('endgame_post', 'The match concluded after intense deliberation.')[:1200] + "\n")
    return "\n".join(lines)

def _extract_rule_based_box_score(game_meta: Dict[str, Any], segmented: Dict[str, Any]) -> Dict[str, Any]:
    """Extracts structured box score data from moderator posts."""
    endgame = segmented.get('endgame_post', '')
    inferred = not segmented.get('has_explicit_closing', False)
    
    winning_faction = "Town"
    if "the crew win" in endgame.lower() or "town win" in endgame.lower():
        winning_faction = "Town"
        inferred = False
    elif "mafia win" in endgame.lower():
        winning_faction = "Mafia"
        inferred = False
    elif "serial killer" in endgame.lower() and "win" in endgame.lower():
        winning_faction = "Serial Killer"
        inferred = False

    return {
        "winning_faction": winning_faction,
        "inferred": inferred,
        "mvp": {
            "player": "You_fool" if "You_fool is the sole survivor" in endgame else "Determined by Game Play",
            "rationale": "Sole survivor and victorious town leader" if "You_fool is the sole survivor" in endgame else "Key participant in phase resolutions"
        },
        "total_phases_recorded": len(segmented.get('phase_stories', [])),
        "notable_moments": [
            f"Hosted by {segmented.get('moderator')}",
            f"{len(segmented.get('phase_stories', []))} recorded phase transitions"
        ]
    }

if __name__ == "__main__":
    summary = summarize_historic_game("203868", {"title": "Mafia 54 - USS Ziusudra", "thread_id": "203868"})
    print("Summary title:", summary["title"])
    print("Box score:", summary.get("box_score"))
