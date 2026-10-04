# batch_summarize.py
"""
Batch Runner for Historic Mafia Game Summarization.
Runs the AI summarization pipeline across selected games and saves structured summaries.
"""

import os
import json
from summarize_historic_game import summarize_historic_game

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(CURRENT_DIR, "output")
SUMMARIES_DIR = os.path.join(OUTPUT_DIR, "summaries")
os.makedirs(SUMMARIES_DIR, exist_ok=True)

# Load all games and filter out signups/discussions
threads_file = os.path.join(OUTPUT_DIR, "mafia_threads.json")
SELECTED_GAMES = []
if os.path.exists(threads_file):
    with open(threads_file, "r", encoding="utf-8") as f:
        all_threads = json.load(f)
    for t in all_threads:
        title_lower = t.get("title", "").lower()
        if "signup" in title_lower or "sign up" in title_lower or "discussion" in title_lower or "rules" in title_lower:
            continue
        SELECTED_GAMES.append({
            "thread_id": t["thread_id"],
            "title": t["title"],
            "era": "Forum",
            "theme": "Historic"
        })
else:
    print("Warning: mafia_threads.json not found!")

def run_batch():
    print(f"=== Starting Historic Game Summarization Batch for {len(SELECTED_GAMES)} Games ===")
    import datetime
    
    summaries = []
    
    # Load user map if available
    user_map_path = os.path.join(OUTPUT_DIR, "master_user_map.json")
    master_user_map = {}
    if os.path.exists(user_map_path):
        with open(user_map_path, 'r', encoding='utf-8') as f:
            master_user_map = json.load(f)

    # Prepare modern bot format directory
    modern_bot_dir = os.path.join(OUTPUT_DIR, "modern_bot_format")
    os.makedirs(modern_bot_dir, exist_ok=True)

    import time
    for game in SELECTED_GAMES:
        tid = game["thread_id"]
        title = game["title"]
        output_file = os.path.join(SUMMARIES_DIR, f"game_{tid}_summary.json")
        
        print(f"\nProcessing {title} (Thread ID: {tid})...")
        
        # Skip if already exists (Resume capability)
        if os.path.exists(output_file):
            print(f"Skipping {title} - already processed.")
            with open(output_file, 'r', encoding='utf-8') as f:
                summaries.append(json.load(f))
            continue
            
        try:
            summary = summarize_historic_game(tid, game)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            print(f"Saved historic summary to {output_file}")
            
            # --- TRANSLATE TO MODERN BOT FORMAT ---
            box_score = summary.get("box_score", {})
            roster = box_score.get("roster", [])
            winning_faction = box_score.get("winning_faction", "Unknown")
            
            # Map Player IDs
            player_data = []
            player_counts = {"town": 0, "mafia": 0, "neutral": 0}
            winning_players = []
            
            for player in roster:
                name = player.get("player", "Unknown")
                role = player.get("role", "Unknown")
                alignment = player.get("alignment", "Unknown")
                survived = player.get("survived", False)
                death_phase = player.get("death_phase", "")
                
                # Update counts
                align_lower = alignment.lower() if isinstance(alignment, str) else "unknown"
                if "town" in align_lower: player_counts["town"] += 1
                elif "mafia" in align_lower: player_counts["mafia"] += 1
                else: player_counts["neutral"] += 1
                
                is_winner = (alignment == winning_faction)
                if is_winner:
                    winning_players.append(name)
                    
                # Map ID
                discord_ids = master_user_map.get(name.lower(), [])
                discord_id = discord_ids[0] if discord_ids else f"historic_user_{name}"
                
                player_data.append({
                    "player_id": str(discord_id),
                    "player_name": name,
                    "alignment": alignment,
                    "role": role,
                    "status": "Alive" if survived else "Dead",
                    "is_winner": is_winner,
                    "death_phase": death_phase,
                    "death_cause": "Unknown",
                    "death_phase_number": 0,
                    "lynched_by_voters": []
                })

            modern_summary = {
                "game_summary": {
                    "game_id": f"historic_{tid}",
                    "game_type": "historic",
                    "number_of_players": len(roster),
                    "player_counts": player_counts,
                    "start_date_utc": None,
                    "end_date_utc": None,
                    "total_days": len(box_score.get("timeline", [])),
                    "winning_faction": winning_faction,
                    "winning_players": winning_players
                },
                "player_data": player_data,
                "lynch_vote_history": [],
                "chat_activity_logs": []
            }
            
            # 1. Save modern summary JSON
            game_folder = os.path.join(modern_bot_dir, f"historic_{tid}")
            os.makedirs(game_folder, exist_ok=True)
            mod_sum_file = os.path.join(game_folder, f"historic_{tid}_summary.json")
            with open(mod_sum_file, 'w', encoding='utf-8') as f:
                json.dump(modern_summary, f, ensure_ascii=False, indent=4)
                
            # 2. Save modern story log Markdown
            story_file = os.path.join(game_folder, f"game_historic_{tid}_story.md")
            with open(story_file, 'w', encoding='utf-8') as f:
                f.write(f"# Game Story Log\n**Game ID:** historic_{tid}\n**Game Type:** historic\n")
                f.write(f"**Winning Team:** {winning_faction}\n\n## Cast of Characters\n\n| Player | Role | Status |\n| :--- | :--- | :--- |\n")
                for p in player_data:
                    f.write(f"| **{p['player_name']}** | {p['role']} | {p['status']} |\n")
                f.write("\n" + summary.get("narrative_chronicle", ""))
                
            print(f"Exported to modern bot format in {game_folder}")
            summaries.append(summary)
            
            # Sleep to prevent rate limits
            time.sleep(4)
            
        except Exception as e:
            print(f"Error processing {title}: {e}")

    # Compile into test web portal history archive
    portal_archive_file = os.path.join(OUTPUT_DIR, "history_archive.json")
    with open(portal_archive_file, 'w', encoding='utf-8') as f:
        json.dump(summaries, f, indent=2, ensure_ascii=False)
    print(f"\nSuccessfully compiled {len(summaries)} games into {portal_archive_file}!")

if __name__ == "__main__":
    run_batch()
