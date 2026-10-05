# segment_game_thread.py
"""
Segments raw forum/discourse game threads into structured phases,
identifying moderator posts, vote tallies, night deaths, and player discourse.
"""

import json
import re
import os
from typing import Dict, List, Any
from clean_bbcode import clean_forum_text

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(CURRENT_DIR, "output")
FORUM_EXTRACTED_FILE = os.path.join(OUTPUT_DIR, "extracted_history.jsonl")
DISCOURSE_EXTRACTED_FILE = os.path.join(OUTPUT_DIR, "discourse_history.jsonl")

def get_posts_for_thread(thread_id: str, jsonl_path: str = None) -> List[Dict[str, Any]]:
    """Retrieves all post records matching thread_id from either the forum or discourse JSONL archive."""
    thread_posts = []
    paths_to_check = [jsonl_path] if jsonl_path else [FORUM_EXTRACTED_FILE, DISCOURSE_EXTRACTED_FILE]

    for p in paths_to_check:
        if not os.path.exists(p):
            continue
        with open(p, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                    src = rec.get('source_id', '')
                    if f'id={thread_id}' in src or f'/{thread_id}/' in src or src.endswith(f'/{thread_id}'):
                        thread_posts.append(rec)
                except Exception:
                    continue
        if thread_posts:
            break

    return thread_posts

def segment_game_thread(thread_posts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyzes raw posts from a single thread and segments them into:
    - Metadata (Title, Moderator, Total Posts, Era)
    - Mod Opening Theme & Rules
    - Chronological Phase Events (Lynches, Night Kills, Vote Counts)
    - Endgame Debrief / Role Reveals
    - Outcome Status (Explicit vs Inferred)
    """
    if not thread_posts:
        return {}

    # 1. Identify Moderator (Author of post #1)
    first_post = thread_posts[0]
    moderator = first_post.get('username', 'Unknown Mod')

    # 2. Separate Moderator posts from Player posts
    mod_posts = []
    player_posts = []

    for post in thread_posts:
        cleaned_content = clean_forum_text(post.get('content', ''))
        post_data = {
            "timestamp": post.get('timestamp', 'N/A'),
            "author": post.get('username', 'Unknown'),
            "content": cleaned_content,
            "raw_length": len(cleaned_content)
        }
        if post.get('username') == moderator:
            mod_posts.append(post_data)
        else:
            player_posts.append(post_data)

    # 3. Detect Phase Boundaries and Event Markers in Mod Posts
    opening_post = mod_posts[0] if mod_posts else {"content": ""}
    endgame_post = None
    has_explicit_closing = False
    closing_posts = []

    # Check for Endgame Reveal in the last 3 mod posts
    for mp in reversed(mod_posts[-4:]):
        c = mp['content'].lower()
        if any(term in c for term in ['good game', 'the crew win', 'town win', 'mafia win', 'game over', 'sole survivor', 'roles revealed', 'player list']):
            endgame_post = mp
            has_explicit_closing = True
            break

    # If no explicit keyword, check if the last mod post wraps up the game
    if not endgame_post and mod_posts:
        endgame_post = mod_posts[-1]
        has_explicit_closing = False

    # 4. Extract Vote Counts & Phase Stories from Mod Posts
    phase_stories = []
    lynch_events = []
    night_deaths = []

    for mp in mod_posts:
        c = mp['content']
        c_lower = c.lower()

        # Detect Vote Tally
        if 'vote count' in c_lower or 'final vote' in c_lower or 'tally' in c_lower:
            phase_stories.append({
                "type": "vote_tally",
                "timestamp": mp['timestamp'],
                "text": c
            })

        # Detect Night Story / Day Start
        elif any(k in c_lower for k in ['night phase', 'day phase', 'the sun rises', 'murdered', 'killed night', 'conspirators', 'serial killer snuck']):
            phase_stories.append({
                "type": "narrative_resolution",
                "timestamp": mp['timestamp'],
                "text": c
            })

    # 5. Extract High-Signal Player Discourse (claims, accusations, notable arguments)
    # Filter player posts to those with significant analysis or claims (> 150 chars or containing 'vote' / 'cop' / 'doctor')
    high_signal_player_posts = []
    for p in player_posts:
        c_lower = p['content'].lower()
        if any(term in c_lower for term in ['vote:', 'claim', 'cop', 'doctor', 'mafia', 'scum', 'innocent', 'guilty', 'suspect']) or p['raw_length'] > 200:
            high_signal_player_posts.append(p)

    return {
        "moderator": moderator,
        "total_posts": len(thread_posts),
        "total_mod_posts": len(mod_posts),
        "total_player_posts": len(player_posts),
        "has_explicit_closing": has_explicit_closing,
        "needs_inference": not has_explicit_closing,
        "opening_theme": opening_post['content'],
        "phase_stories": phase_stories,
        "endgame_post": endgame_post['content'] if endgame_post else "",
        "mod_posts_full": mod_posts,
        "high_signal_player_posts": high_signal_player_posts[:30] # Limit to top 30 key posts to manage tokens
    }

if __name__ == "__main__":
    posts = get_posts_for_thread("203868")
    segmented = segment_game_thread(posts)
    print(f"Mod: {segmented['moderator']}")
    print(f"Mod Posts: {segmented['total_mod_posts']}")
    print(f"Has Explicit Closing: {segmented['has_explicit_closing']}")
    print(f"Phase Stories Found: {len(segmented['phase_stories'])}")
