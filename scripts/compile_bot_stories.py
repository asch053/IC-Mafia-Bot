"""
scripts/compile_bot_stories.py
Extracts and builds rich story_as_written markdown files for all 54 Discord Bot games
and saves them to Website/stories/{tid}_story.md.
"""

import os
import glob
import json
import re
from datetime import datetime

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBSITE_DIR = os.path.join(ROOT_DIR, "Website")
STORIES_DIR = os.path.join(WEBSITE_DIR, "stories")
DB_DIR = os.path.join(WEBSITE_DIR, "database")
STATS_DIR = os.path.join(ROOT_DIR, "stats")
DISCORD_HISTORY_PATH = os.path.join(ROOT_DIR, "Other Projects", "Mafia History Project", "output", "new_discord_history.jsonl")

def load_json(path, default=None):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def get_stats_story_map():
    stats_stories = glob.glob(os.path.join(STATS_DIR, "**", "game_*_story.md"), recursive=True)
    # Prefer Production over Alpha_Testing
    story_map = {}
    for p in stats_stories:
        fname = os.path.basename(p)
        gid = fname.replace("game_", "").replace("_story.md", "")
        if gid not in story_map or "Production" in p:
            story_map[gid] = p
    return story_map

def get_summary_map():
    summaries = glob.glob(os.path.join(STATS_DIR, "**", "*_summary.json"), recursive=True)
    summ_map = {}
    for p in summaries:
        fname = os.path.basename(p)
        gid = fname.replace("_summary.json", "")
        if gid not in summ_map or "Production" in p:
            summ_map[gid] = p
    return summ_map

def get_prompts_map():
    prompts = glob.glob(os.path.join(STATS_DIR, "**", "*_ai_prompts.json"), recursive=True)
    p_map = {}
    for p in prompts:
        fname = os.path.basename(p)
        gid = fname.replace("_ai_prompts.json", "")
        if gid not in p_map or "Production" in p:
            p_map[gid] = p
    return p_map

def load_discord_bot_stories_and_chat():
    print("Loading Discord history for bot games (stories and talky-talky)...")
    stories_by_msg = []
    talky_by_msg = []
    
    if os.path.exists(DISCORD_HISTORY_PATH):
        with open(DISCORD_HISTORY_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                    sid = obj.get("source_id", "")
                    ts = obj.get("timestamp", "")
                    if not ts.startswith("2025"):
                        continue
                    if "stories" in sid:
                        stories_by_msg.append(obj)
                    elif "talky-talky" in sid and "community" not in sid:
                        talky_by_msg.append(obj)
                except Exception:
                    pass

    stories_by_msg.sort(key=lambda x: x.get("timestamp", ""))
    talky_by_msg.sort(key=lambda x: x.get("timestamp", ""))
    print(f"Loaded {len(stories_by_msg)} stories messages and {len(talky_by_msg)} talky-talky messages.")
    return stories_by_msg, talky_by_msg

def build_cast_markdown(player_data):
    if not player_data:
        return ""
    lines = [
        "## Cast of Characters\n",
        "| Player | Role | Alignment | Status |",
        "| :--- | :--- | :--- | :--- |"
    ]
    for p in player_data:
        name = p.get("player_name") or p.get("name") or "Unknown"
        role = p.get("role") or "Unknown"
        align = p.get("alignment") or "Unknown"
        is_alive = (p.get("status", "").lower() == "alive") or (p.get("is_alive") is True)
        if is_alive:
            status = "Alive"
        else:
            dp = p.get("death_phase") or "Unknown"
            dc = p.get("death_cause") or "Eliminated"
            status = f"Dead ({dp} - {dc})"
        lines.append(f"| **{name}** | {role} | {align} | {status} |")
    return "\n".join(lines) + "\n\n"

def build_chat_transcript_markdown(chat_logs):
    if not chat_logs:
        return "\n## Chat Transcript\n\n_No chat log recorded for this match._\n"
    
    lines = [
        "\n## Chat Transcript\n",
        "Timestamp | Channel | Phase | Player Name | Message",
        ":--- | :--- | :--- | :--- | :---"
    ]
    for entry in chat_logs:
        ts = entry.get("timestamp_utc") or entry.get("timestamp") or ""
        ts_clean = ts[:19].replace("T", " ") if ts else ""
        ch = entry.get("channel_name") or entry.get("source_id", "talky-talky").split("-")[0]
        ph = entry.get("phase") or ""
        ph_num = entry.get("phase_number")
        phase_str = f"{ph} {ph_num}".strip() if ph_num is not None else ph
        if not phase_str:
            phase_str = "-"
        name = entry.get("username") or "Unknown"
        msg = entry.get("content", "").replace("\n", " ").replace("|", "\\|")
        lines.append(f"**[{ts_clean}]** | {ch} | {phase_str} | **{name}** | {msg}")
    
    return "\n".join(lines) + "\n"

def compile_all_bot_stories():
    bot_db_path = os.path.join(DB_DIR, "discord_bot.json")
    bot_games = load_json(bot_db_path, [])
    if not bot_games:
        print("No bot games found in database!")
        return

    stats_story_map = get_stats_story_map()
    summary_map = get_summary_map()
    prompts_map = get_prompts_map()
    stories_msgs, talky_msgs = load_discord_bot_stories_and_chat()

    print(f"Compiling stories for {len(bot_games)} Discord Bot games...")
    os.makedirs(STORIES_DIR, exist_ok=True)

    updated_count = 0

    for idx, g in enumerate(bot_games):
        tid = g.get("thread_id")
        start_date = g.get("start_date")
        game_title = g.get("title", f"Discord Game {tid}")
        game_type = g.get("game_type", "classic")
        winning_faction = g.get("winning_faction", "Unknown")
        
        story_target_path = os.path.join(STORIES_DIR, f"{tid}_story.md")
        
        # Next game start date or limit
        if idx + 1 < len(bot_games):
            next_start = bot_games[idx + 1].get("start_date")
        else:
            next_start = "2026-12-31"

        final_story_md = ""

        # Case 1: In stats/ with game_{tid}_story.md
        if tid in stats_story_map:
            stats_p = stats_story_map[tid]
            with open(stats_p, "r", encoding="utf-8") as sf:
                final_story_md = sf.read().strip()
            if "\n## Chat Transcript" in final_story_md:
                final_story_md = final_story_md.split("\n## Chat Transcript")[0].strip()
            print(f"[{idx+1:2d}/54] {tid}: Using rich stats story log ({len(final_story_md)} bytes) from {os.path.basename(stats_p)}")

        # Case 2: In stats/ with ai_prompts.json (e.g. 20260421-220000)
        elif tid in prompts_map:
            pr_path = prompts_map[tid]
            su_path = summary_map.get(tid)
            su_data = load_json(su_path, {}) if su_path else {}
            pr_data = load_json(pr_path, {})
            
            g_summ = su_data.get("game_summary", {})
            p_data = su_data.get("player_data", [])
            
            header = (
                f"# Game Story Log\n"
                f"**Game ID:** {tid}\n"
                f"**Start date (UTC):** {g_summ.get('start_date_utc', start_date)}\n"
                f"**End date (UTC):** {g_summ.get('end_date_utc', 'N/A')}\n"
                f"Game Type: {g_summ.get('game_type', game_type)}\n"
                f"Number of players: {len(p_data)}\n"
                f"Total days: {g_summ.get('total_days', 'N/A')}\n"
                f"**Winning Team:** {g_summ.get('winning_faction', winning_faction)}\n\n"
                f"**Winning Players:** {g_summ.get('winning_players', [])}\n\n"
            )
            cast_md = build_cast_markdown(p_data)
            
            # Phase stories
            story_chapters = ["========================================\n"]
            for phase_key, p_info in pr_data.items():
                if isinstance(p_info, dict) and p_info.get("final_story"):
                    ch_name = phase_key.split(" - ")[0].strip()
                    story_chapters.append(f"### {ch_name}\n\n{p_info['final_story'].strip()}\n")
            
            final_story_md = (header + cast_md + "\n".join(story_chapters)).strip()
            print(f"[{idx+1:2d}/54] {tid}: Reconstructed from ai_prompts.json ({len(final_story_md)} bytes)")

        # Case 3: Early games in Discord archives (games 1 to 18, 2025-08 to 2025-11)
        elif tid.startswith("2025") and int(tid[:8]) < 20251130:
            su_path = summary_map.get(tid)
            su_data = load_json(su_path, {}) if su_path else {}
            g_summ = su_data.get("game_summary", {})
            p_data = su_data.get("player_data", [])
            
            # Filter Discord #stories messages for this game window
            game_stories_msgs = [
                m for m in stories_msgs
                if start_date <= m.get("timestamp", "")[:10] <= next_start
            ]
            
            # If game over message found, narrow down
            end_ts = None
            for m in game_stories_msgs:
                if "game over" in m.get("content", "").lower() or "game ended" in m.get("content", "").lower():
                    end_ts = m.get("timestamp")
                    break
            
            if end_ts:
                game_stories_msgs = [m for m in game_stories_msgs if m.get("timestamp") <= end_ts]

            header = (
                f"# Game Story Log\n"
                f"**Game ID:** {tid}\n"
                f"**Start date (UTC):** {g_summ.get('start_date_utc', start_date)}\n"
                f"**End date (UTC):** {end_ts or g_summ.get('end_date_utc', 'N/A')}\n"
                f"Game Type: {g_summ.get('game_type', game_type)}\n"
                f"Number of players: {len(p_data)}\n"
                f"Total days: {g_summ.get('total_days', 'N/A')}\n"
                f"**Winning Team:** {g_summ.get('winning_faction', winning_faction)}\n\n"
                f"**Winning Players:** {g_summ.get('winning_players', [])}\n\n"
            )
            cast_md = build_cast_markdown(p_data)
            
            # Formulate Stories section from actual Discord posts
            narrative_blocks = ["========================================\n", "## The Story as Written (Discord Bot Announcements)\n"]
            for sm in game_stories_msgs:
                ts_str = sm.get("timestamp", "")[:19].replace("T", " ")
                content = sm.get("content", "").strip()
                # Skip pure 1-hour / 10-minute reminders for cleaner reading
                if content.startswith("**Reminder:**") and "left in the phase" in content:
                    continue
                narrative_blocks.append(f"{content}\n")
            
            final_story_md = (header + cast_md + "\n".join(narrative_blocks)).strip()
            print(f"[{idx+1:2d}/54] {tid}: Compiled from Discord #stories ({len(game_stories_msgs)} posts) -> {len(final_story_md)} bytes")

        # Case 4: Other games with summary.json (games 42 to 48)
        else:
            su_path = summary_map.get(tid)
            su_data = load_json(su_path, {}) if su_path else {}
            g_summ = su_data.get("game_summary", {})
            p_data = su_data.get("player_data", [])
            lvh = su_data.get("lynch_vote_history", [])
            
            header = (
                f"# Game Story Log\n"
                f"**Game ID:** {tid}\n"
                f"**Start date (UTC):** {g_summ.get('start_date_utc', start_date)}\n"
                f"**End date (UTC):** {g_summ.get('end_date_utc', 'N/A')}\n"
                f"Game Type: {g_summ.get('game_type', game_type)}\n"
                f"Number of players: {len(p_data)}\n"
                f"Total days: {g_summ.get('total_days', 'N/A')}\n"
                f"**Winning Team:** {g_summ.get('winning_faction', winning_faction)}\n\n"
                f"**Winning Players:** {g_summ.get('winning_players', [])}\n\n"
            )
            cast_md = build_cast_markdown(p_data)
            
            # Build phase narrative based on player deaths and lynch history
            phases = []
            for p in p_data:
                dp = p.get("death_phase")
                if dp and dp not in phases:
                    phases.append(dp)
            for v in lvh:
                vp = v.get("phase")
                if vp and vp not in phases:
                    phases.append(vp)
            
            narrative_blocks = ["========================================\n", "## Game Chronicle & Tactical Executions\n"]
            for ph in phases:
                narrative_blocks.append(f"### {ph}\n")
                ph_deaths = [p for p in p_data if p.get("death_phase") == ph]
                if ph_deaths:
                    for d in ph_deaths:
                        narrative_blocks.append(f"- **{d.get('player_name')}** ({d.get('role')} - {d.get('alignment')}) was eliminated: *{d.get('death_cause')}*.\n")
                else:
                    narrative_blocks.append("No casualties recorded during this phase.\n")
            
            final_story_md = (header + cast_md + "\n".join(narrative_blocks)).strip()
            print(f"[{idx+1:2d}/54] {tid}: Compiled from summary.json -> {len(final_story_md)} bytes")

        # Save compiled story
        with open(story_target_path, "w", encoding="utf-8") as out_f:
            out_f.write(final_story_md)
        updated_count += 1

    print(f"Successfully compiled all {updated_count} bot stories to Website/stories/!")

if __name__ == "__main__":
    compile_all_bot_stories()
