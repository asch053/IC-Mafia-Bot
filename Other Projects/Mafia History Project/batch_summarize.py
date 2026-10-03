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

# 3 Selected Representative Classic Games
SELECTED_GAMES = [
    {
        "thread_id": "203868",
        "title": "Mafia 54: USS Ziusudra",
        "era": "Forum (2012–2020)",
        "theme": "Sci-Fi Generation Ship"
    },
    {
        "thread_id": "181405",
        "title": "Mafia 38: Gotham City",
        "era": "Forum (2012–2020)",
        "theme": "Superhero / Batman"
    },
    {
        "thread_id": "183598",
        "title": "Mafia 42: Shaken Not Stirred",
        "era": "Forum (2012–2020)",
        "theme": "James Bond 007 Espionage"
    }
]

def run_batch():
    print(f"=== Starting Historic Game Summarization Batch for {len(SELECTED_GAMES)} Games ===")
    summaries = []

    for game in SELECTED_GAMES:
        tid = game["thread_id"]
        title = game["title"]
        print(f"\nProcessing {title} (Thread ID: {tid})...")
        try:
            summary = summarize_historic_game(tid, game)
            output_file = os.path.join(SUMMARIES_DIR, f"game_{tid}_summary.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            print(f"Saved summary to {output_file}")
            summaries.append(summary)
        except Exception as e:
            print(f"Error processing {title}: {e}")

    # Compile into test web portal history archive
    portal_archive_file = os.path.join(OUTPUT_DIR, "history_archive.json")
    with open(portal_archive_file, 'w', encoding='utf-8') as f:
        json.dump(summaries, f, indent=2, ensure_ascii=False)
    print(f"\nSuccessfully compiled {len(summaries)} games into {portal_archive_file}!")

if __name__ == "__main__":
    run_batch()
