"""
Extract Databases and Stories Script
Converts the monolithic history_archive.json into:
1. data/database/historic_forum.json (Forum games)
2. data/database/historic_discourse.json (Discourse games)
3. data/database/discord_bot.json (Discord Bot games)
4. data/database/discord_manual.json (Manual Discord games)
5. data/stories/{thread_id}_summary.md (Narrative chronicle / summary per game)
6. data/stories/{thread_id}_story.md (Stories as written per game)
"""
import os
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "data")
WEBSITE_DIR = os.path.join(ROOT_DIR, "Website")
DB_DIR = os.path.join(WEBSITE_DIR, "database")
STORIES_DIR = os.path.join(WEBSITE_DIR, "stories")
WEBSITE_DATA_DIR = os.path.join(WEBSITE_DIR, "data")

def run_extraction():
    os.makedirs(DB_DIR, exist_ok=True)
    os.makedirs(STORIES_DIR, exist_ok=True)
    
    archive_path = os.path.join(WEBSITE_DATA_DIR, "history_archive.json")
    if not os.path.exists(archive_path):
        logging.error(f"Archive not found at {archive_path}")
        return

    with open(archive_path, "r", encoding="utf-8") as f:
        games = json.load(f)

    forum_games = []
    discourse_games = []
    discord_bot_games = []

    for g in games:
        era = g.get("era", "Forum")
        tid = str(g.get("thread_id", "unknown"))

        # Extract markdown files
        chronicle = (g.get("narrative_chronicle") or "").strip()
        story = (g.get("story_as_written") or "").strip()

        summary_filename = f"{tid}_summary.md"
        story_filename = f"{tid}_story.md"

        summary_path = os.path.join(STORIES_DIR, summary_filename)
        story_path = os.path.join(STORIES_DIR, story_filename)

        with open(summary_path, "w", encoding="utf-8") as sf:
            sf.write(chronicle)

        with open(story_path, "w", encoding="utf-8") as stf:
            stf.write(story)

        clean_g = {
            "thread_id": tid,
            "era": era,
            "title": g.get("title", f"{era} Game {tid}"),
            "moderator": g.get("moderator", "Game Host"),
            "game_type": g.get("game_type", "classic"),
            "total_posts": g.get("total_posts"),
            "winning_faction": (g.get("box_score", {}) or {}).get("winning_faction", "Unknown"),
            "summary_file": f"stories/{summary_filename}",
            "story_file": f"stories/{story_filename}",
            "box_score": g.get("box_score", {}),
            "lynch_vote_history": g.get("lynch_vote_history", [])
        }

        if era == "Forum":
            clean_g["era"] = "Forum"
            forum_games.append(clean_g)
        elif era == "Discourse":
            clean_g["era"] = "Discourse"
            discourse_games.append(clean_g)
        else:
            clean_g["era"] = "Discord"
            discord_bot_games.append(clean_g)

    forum_path = os.path.join(DB_DIR, "historic_forum.json")
    discourse_path = os.path.join(DB_DIR, "historic_discourse.json")
    bot_path = os.path.join(DB_DIR, "discord_bot.json")
    manual_path = os.path.join(DB_DIR, "discord_manual.json")

    with open(forum_path, "w", encoding="utf-8") as f:
        json.dump(forum_games, f, indent=2, ensure_ascii=False)

    with open(discourse_path, "w", encoding="utf-8") as f:
        json.dump(discourse_games, f, indent=2, ensure_ascii=False)

    with open(bot_path, "w", encoding="utf-8") as f:
        json.dump(discord_bot_games, f, indent=2, ensure_ascii=False)

    if not os.path.exists(manual_path):
        sample_manual = [
            {
                "thread_id": "manual-example-01",
                "era": "Discord_Manual",
                "title": "Manual Community Game 1",
                "moderator": "CommunityHost",
                "game_type": "classic",
                "total_posts": 0,
                "winning_faction": "Town",
                "summary_file": "stories/manual-example-01_summary.md",
                "story_file": "stories/manual-example-01_story.md",
                "box_score": {
                    "winning_faction": "Town",
                    "game_type": "classic",
                    "mvp": {
                        "player": "Alice",
                        "rationale": "Leading the Town to victory with accurate reads."
                    },
                    "roster": [
                        {
                            "player": "Alice",
                            "player_id": "10001",
                            "role": "Detective",
                            "alignment": "Town",
                            "survived": True,
                            "is_winner": True,
                            "death_phase": None,
                            "death_cause": None
                        },
                        {
                            "player": "Bob",
                            "player_id": "10002",
                            "role": "Godfather",
                            "alignment": "Mafia",
                            "survived": False,
                            "is_winner": False,
                            "death_phase": "Day 2",
                            "death_cause": "Lynched by Town"
                        }
                    ],
                    "timeline": [
                        {
                            "phase": "Day 1",
                            "type": "day",
                            "scene": "The town gathers in the square to begin discussions.",
                            "events": [],
                            "eliminated": [],
                            "vote_tally": {},
                            "votes_cast": 0
                        },
                        {
                            "phase": "Day 2",
                            "type": "day",
                            "scene": "Bob was accused and eliminated by vote.",
                            "events": [
                                {
                                    "phase": "Day 2",
                                    "event": "Lynch",
                                    "target": "Bob",
                                    "role": "Godfather",
                                    "alignment": "Mafia",
                                    "details": "Eliminated in Day 2 (Godfather)"
                                }
                            ],
                            "eliminated": [
                                {
                                    "player": "Bob",
                                    "role": "Godfather",
                                    "alignment": "Mafia",
                                    "cause": "Lynch",
                                    "lynched_by": ["Alice"]
                                }
                            ],
                            "vote_tally": { "Bob": 1 },
                            "votes_cast": 1
                        }
                    ],
                    "notable_moments": [
                        "Alice identified Bob on Day 2.",
                        "Flawless Town victory."
                    ]
                },
                "lynch_vote_history": [
                    {
                        "phase": "Day 2",
                        "voter_name": "Alice",
                        "voter_id": "10001",
                        "target_name": "Bob",
                        "target_id": "10002"
                    }
                ]
            }
        ]
        with open(manual_path, "w", encoding="utf-8") as f:
            json.dump(sample_manual, f, indent=2, ensure_ascii=False)
            
        # Also create sample stories for manual-example-01
        with open(os.path.join(STORIES_DIR, "manual-example-01_summary.md"), "w", encoding="utf-8") as f:
            f.write("### 📋 Match Overview\n- **Game ID:** `manual-example-01`\n- **Era:** Discord Manual\n- **Winner:** Town\n\n### ⚔️ Tactical Summary\nCommunity manual game demonstrating flawless Town play.")
        with open(os.path.join(STORIES_DIR, "manual-example-01_story.md"), "w", encoding="utf-8") as f:
            f.write("## 📜 Opening Briefing\nThe town square was quiet as the investigation began...\n\n## ⚔️ Day 2\nBob was uncovered as the Godfather and brought to justice.")

    logging.info(f"Successfully created:")
    logging.info(f"- {forum_path} ({len(forum_games)} games)")
    logging.info(f"- {discourse_path} ({len(discourse_games)} games)")
    logging.info(f"- {bot_path} ({len(discord_bot_games)} games)")
    logging.info(f"- {manual_path} (manual discord template)")
    logging.info(f"- {STORIES_DIR} ({len(os.listdir(STORIES_DIR))} markdown stories/summaries)")

if __name__ == "__main__":
    run_extraction()
