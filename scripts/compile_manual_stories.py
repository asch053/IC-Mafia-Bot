"""
scripts/compile_manual_stories.py
Enriches all 29 manual Discord mafia game stories (manual-998 through manual-1027)
with the original host posts from Discord (#stories, #voting-channel, #rules-and-roles)
combined with the phase-by-phase timeline from Google Sheets.
"""

import os
import glob
import json
import re

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBSITE_DIR = os.path.join(ROOT_DIR, "Website")
STORIES_DIR = os.path.join(WEBSITE_DIR, "stories")
DB_DIR = os.path.join(WEBSITE_DIR, "database")
DISCORD_HISTORY_PATH = os.path.join(ROOT_DIR, "Other Projects", "Mafia History Project", "output", "new_discord_history.jsonl")

def load_json(path, default=None):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def load_discord_manual_messages():
    print("Loading Discord archives for manual games (2019-08 to 2020-03)...")
    stories_msgs = []
    voting_msgs = []
    rules_msgs = []
    
    if os.path.exists(DISCORD_HISTORY_PATH):
        with open(DISCORD_HISTORY_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                    ts = obj.get("timestamp", "")
                    if not (ts.startswith("2019") or ts.startswith("2020")):
                        continue
                    sid = obj.get("source_id", "")
                    if "stories" in sid:
                        stories_msgs.append(obj)
                    elif "voting-channel" in sid:
                        voting_msgs.append(obj)
                    elif "rules-and-roles" in sid:
                        rules_msgs.append(obj)
                except Exception:
                    pass

    stories_msgs.sort(key=lambda x: x.get("timestamp", ""))
    voting_msgs.sort(key=lambda x: x.get("timestamp", ""))
    rules_msgs.sort(key=lambda x: x.get("timestamp", ""))
    print(f"Loaded {len(stories_msgs)} stories, {len(voting_msgs)} voting, and {len(rules_msgs)} rules messages.")
    return stories_msgs, voting_msgs, rules_msgs

def compile_all_manual_stories():
    manual_db_path = os.path.join(DB_DIR, "discord_manual.json")
    manual_games = load_json(manual_db_path, [])
    if not manual_games:
        print("No manual games found in database!")
        return

    stories_msgs, voting_msgs, rules_msgs = load_discord_manual_messages()
    os.makedirs(STORIES_DIR, exist_ok=True)

    print(f"Compiling rich stories for {len(manual_games)} Discord Manual games...")
    updated_count = 0

    for idx, g in enumerate(manual_games):
        gid = g.get("game_num") or g.get("game_id") or g.get("thread_id")
        clean_gid = str(gid).replace("manual-", "")
        start_date = g.get("start_date")
        title = g.get("title", f"Discord Mafia {clean_gid}")
        mod = g.get("moderator", "Game Master")
        win_faction = g.get("winning_faction", "Unknown")
        box = g.get("box_score", {})
        roster = box.get("roster", [])
        timeline = box.get("timeline", [])
        
        # Determine time window
        if idx + 1 < len(manual_games):
            next_start = manual_games[idx + 1].get("start_date")
        else:
            next_start = "2020-03-01"

        # 1. Filter matching messages from Discord channels
        matching_stories = [
            m for m in stories_msgs
            if start_date <= m.get("timestamp", "")[:10] < next_start
        ]
        matching_rules = [
            m for m in rules_msgs
            if start_date <= m.get("timestamp", "")[:10] < next_start
        ]
        # For voting channel, select mod announcements & phase updates
        matching_voting = [
            m for m in voting_msgs
            if start_date <= m.get("timestamp", "")[:10] < next_start
        ]
        mod_voting = [
            m for m in matching_voting
            if (mod and mod.lower() in (m.get("username") or "").lower()) or
               any(k in m.get("content", "").lower() for k in ["phase", "voting ends", "tally", "count:", "game over", "lynched"])
        ]

        # 2. Build Story Markdown
        md_lines = []
        md_lines.append(f"# {title}\n")
        md_lines.append(f"*Recorded & Moderated by Game Master **{mod}***\n")
        md_lines.append(f"- **Era:** Discord Historic Manual")
        md_lines.append(f"- **Start Date:** {start_date}")
        md_lines.append(f"- **Winning Faction:** **{win_faction}**")
        md_lines.append(f"- **Total Players:** {len(roster)}\n")
        md_lines.append("---\n")

        # Section A: Original Host Stories as Written (if available in #stories)
        if matching_stories:
            md_lines.append("## 📜 Original Host Chronicles & Stories as Written\n")
            for sm in matching_stories:
                ts_str = sm.get("timestamp", "")[:19].replace("T", " ")
                author = sm.get("username", mod)
                content = sm.get("content", "").strip()
                if content:
                    md_lines.append(f"### Update by {author} ({ts_str})\n\n{content}\n")
            md_lines.append("---\n")

        # Section B: Rules & Roles / Moderator Directives (if available)
        if matching_rules:
            md_lines.append("## 📋 Rules & Role Manifest\n")
            for rm in matching_rules:
                ts_str = rm.get("timestamp", "")[:19].replace("T", " ")
                author = rm.get("username", mod)
                content = rm.get("content", "").strip()
                if content:
                    md_lines.append(f"**[{ts_str}] {author}:**\n\n{content}\n")
            md_lines.append("---\n")

        # Section C: Moderator Phase Announcements & Voting Updates (if no #stories or to complement)
        if mod_voting and (not matching_stories or len(mod_voting) <= 15):
            md_lines.append("## 📢 Moderator Phase Announcements & Vote Directives\n")
            for vm in mod_voting[:15]:
                ts_str = vm.get("timestamp", "")[:19].replace("T", " ")
                author = vm.get("username", mod)
                content = vm.get("content", "").strip()
                if content:
                    md_lines.append(f"- **[{ts_str}] {author}:** {content}")
            md_lines.append("\n---\n")

        # Section D: Phase-by-Phase Tactical Timeline (From Sheet match records)
        md_lines.append("## ⚔️ Tactical Phase-by-Phase Timeline\n")
        if timeline:
            for ph in timeline:
                p_name = ph.get("phase", "Phase")
                md_lines.append(f"### {p_name}\n")
                events = ph.get("events", [])
                if events:
                    for ev in events:
                        target = ev.get("target", "Unknown")
                        role = ev.get("role", "Unknown")
                        align = ev.get("alignment", "Unknown")
                        details = ev.get("details", "")
                        ev_name = ev.get("event", "Event")
                        md_lines.append(f"- **{ev_name}:** **{target}** ({role} - {align}) — *{details}*")
                else:
                    md_lines.append("- No casualties recorded during this phase.")
                md_lines.append("")
        else:
            md_lines.append("_Phase events archived in primary match records._\n")

        # Section E: Cast of Characters
        md_lines.append("---\n")
        md_lines.append("## 👥 Roster & Final Standings\n")
        md_lines.append("| Player | Role | Alignment | Outcome |")
        md_lines.append("| :--- | :--- | :--- | :--- |")
        survivors = []
        for p in roster:
            pname = p.get("player") or p.get("name") or "Unknown"
            prole = p.get("role") or "Unknown"
            palign = p.get("alignment") or "Unknown"
            pdead = not p.get("survived", True)
            if pdead:
                dp = p.get("death_phase") or "Unknown"
                dc = p.get("death_cause") or "Eliminated"
                outcome = f"Dead ({dp} - {dc})"
            else:
                outcome = "Survived (Winner)" if p.get("is_winner") else "Survived"
                survivors.append(pname)
            md_lines.append(f"| **{pname}** | {prole} | {palign} | {outcome} |")

        md_lines.append("\n---\n")
        md_lines.append(f"### 🏆 Epilogue: Final Resolution\n")
        md_lines.append(f"When the conflict concluded, **{win_faction}** secured the victory!\n\n")
        if survivors:
            md_lines.append("Surviving combatants:\n" + "\n".join(f"- **{s}**" for s in survivors) + "\n")
        else:
            md_lines.append("No players survived the conflict.\n")

        final_story_md = "\n".join(md_lines)
        story_target_path = os.path.join(STORIES_DIR, f"manual-{clean_gid}_story.md")
        with open(story_target_path, "w", encoding="utf-8") as out_f:
            out_f.write(final_story_md)

        print(f"[{idx+1:2d}/29] manual-{clean_gid}: Compiled story ({len(final_story_md)} bytes, {len(matching_stories)} stories, {len(mod_voting)} mod voting msgs)")
        updated_count += 1

    print(f"Successfully compiled all {updated_count} manual Discord stories to Website/stories/!")

if __name__ == "__main__":
    compile_all_manual_stories()
