import os
import json
import re
from collections import Counter

WEBSITE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(WEBSITE_DIR, "data")

def load_json(filename, default=None):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return default
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def crawl_modern_games():
    stats_dir = os.path.join(WEBSITE_DIR, "..", "stats", "Production")
    modern_games = []
    
    if not os.path.exists(stats_dir):
        return modern_games
        
    for root, dirs, files in os.walk(stats_dir):
        for file in files:
            if file.endswith("_summary.json"):
                summary_path = os.path.join(root, file)
                story_path = summary_path.replace("_summary.json", "_story.md")
                
                with open(summary_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                summary = data.get("game_summary", {})
                player_data = data.get("player_data", [])
                vote_history = data.get("lynch_vote_history", [])
                
                if not summary:
                    continue
                    
                game_id = summary.get("game_id", "Unknown")
                era = "Discord"
                
                # Extract scenes and narrative chapters from story markdown
                story_scenes = {}
                narrative_chapters = []
                if os.path.exists(story_path):
                    with open(story_path, 'r', encoding='utf-8') as f:
                        story_content = f.read()
                    parts = story_content.split('========================================')
                    if len(parts) >= 3:
                        scene_block = parts[1]
                        phase_matches = re.split(r'\*\*---\s*([^-]+)\s*---\*\*', scene_block)
                        for i in range(1, len(phase_matches), 2):
                            ph_name = phase_matches[i].strip()
                            ph_text = phase_matches[i+1].strip()
                            story_scenes[ph_name] = ph_text
                            narrative_chapters.append(f"### {ph_name}\n\n{ph_text}")
                
                narrative = "\n\n".join(narrative_chapters) if narrative_chapters else f"Automated game {game_id} run on Discord."
                
                # Build chronological timeline
                all_phases = []
                for p in player_data:
                    dp = p.get("death_phase")
                    if dp and dp not in all_phases:
                        all_phases.append(dp)
                for v in vote_history:
                    vp = v.get("phase")
                    if vp and vp not in all_phases:
                        all_phases.append(vp)
                for sp in story_scenes.keys():
                    if sp not in all_phases:
                        all_phases.append(sp)

                def phase_sort_key(p):
                    nums = re.findall(r'\d+', p)
                    n = int(nums[0]) if nums else 0
                    is_day = 1 if 'day' in p.lower() else 0
                    return (n, is_day)

                all_phases = sorted(all_phases, key=phase_sort_key)
                
                timeline = []
                for ph in all_phases:
                    ph_deaths = [
                        {
                            "player": p.get("player_name"),
                            "role": p.get("role"),
                            "alignment": p.get("alignment"),
                            "cause": p.get("death_cause"),
                            "lynched_by": p.get("lynched_by_voters")
                        }
                        for p in player_data if p.get("death_phase") == ph
                    ]
                    ph_votes = [v for v in vote_history if v.get("phase") == ph]
                    final_votes = {}
                    for v in ph_votes:
                        final_votes[v["voter_name"]] = v["target_name"]
                    tally = dict(Counter(final_votes.values()))
                    
                    events = []
                    for d in ph_deaths:
                        ev_type = "Lynch" if "lynch" in (d.get("cause") or "").lower() else "Kill"
                        events.append({
                            "phase": ph,
                            "event": ev_type,
                            "target": d.get("player"),
                            "role": d.get("role"),
                            "alignment": d.get("alignment"),
                            "details": d.get("cause") or f"Eliminated in {ph}"
                        })
                        
                    timeline.append({
                        "phase": ph,
                        "type": "day" if "day" in ph.lower() else ("night" if "night" in ph.lower() else "other"),
                        "scene": story_scenes.get(ph, ""),
                        "events": events,
                        "eliminated": ph_deaths,
                        "vote_tally": tally,
                        "votes_cast": len(ph_votes)
                    })
                    
                roster = []
                for p in player_data:
                    roster.append({
                        "player": p.get("player_name"),
                        "role": p.get("role"),
                        "alignment": p.get("alignment"),
                        "survived": (p.get("status", "").lower() == "alive"),
                        "death_phase": p.get("death_phase"),
                        "death_cause": p.get("death_cause")
                    })
                
                winning_players = summary.get("winning_players", [])
                mvp = None
                if winning_players:
                    mvp = {
                        "player": winning_players[0],
                        "rationale": f"Secured the victory for {summary.get('winning_faction', 'their team')}."
                    }
                    
                modern_games.append({
                    "thread_id": game_id,
                    "era": era,
                    "title": f"Discord Game - {game_id}",
                    "narrative_chronicle": narrative,
                    "box_score": {
                        "winning_faction": summary.get("winning_faction", "Unknown"),
                        "mvp": mvp,
                        "roster": roster,
                        "timeline": timeline,
                        "notable_moments": [
                            f"Game completed in {summary.get('total_days', len(all_phases))} phases.",
                            f"Winning faction: {summary.get('winning_faction')}."
                        ]
                    }
                })
                
    return modern_games

def build_unified_stats():
    print("Building unified multi-era stats...")
    
    # Base historical games from the output
    raw_hist_path = os.path.join(WEBSITE_DIR, "..", "Other Projects", "Mafia History Project", "output", "history_archive.json")
    if os.path.exists(raw_hist_path):
        with open(raw_hist_path, 'r', encoding='utf-8') as f:
            history_archive = json.load(f)
    else:
        history_archive = load_json("history_archive.json", [])
        
    # Ensure every historical game has a rich timeline
    for g in history_archive:
        g["era"] = g.get("era", "Forum")
        box = g.setdefault("box_score", {})
        tl = box.get("timeline")
        if not tl or len(tl) == 0:
            # Synthesize timeline from roster
            roster = box.get("roster", [])
            syn_timeline = []
            for p in roster:
                dp = p.get("death_phase")
                if dp:
                    syn_timeline.append({
                        "phase": dp,
                        "event": "Elimination",
                        "target": p.get("player"),
                        "role": p.get("role"),
                        "alignment": p.get("alignment"),
                        "details": f"Eliminated in {dp} ({p.get('role', 'Unknown')})"
                    })
            if not syn_timeline:
                syn_timeline.append({
                    "phase": "Game Conclusion",
                    "event": "Overview",
                    "target": box.get("winning_faction", "All"),
                    "details": f"Game resolved with {box.get('winning_faction', 'Unknown')} victory condition."
                })
            box["timeline"] = syn_timeline
    
    # Modern games from the bot
    modern_games = crawl_modern_games()
    
    # Merge, keeping modern games unique
    existing_ids = {g.get("thread_id") for g in history_archive}
    for mg in modern_games:
        if mg["thread_id"] not in existing_ids:
            history_archive.append(mg)
            
    # Save the expanded history archive back so the website has it all
    out_history = os.path.join(DATA_DIR, "history_archive.json")
    with open(out_history, 'w', encoding='utf-8') as f:
        json.dump(history_archive, f, indent=4)
        
    user_map = load_json("master_user_map.json", {})
    
    player_stats = {}
    
    def get_player(p_id, p_name):
        if p_id not in player_stats:
            player_stats[p_id] = {
                "Player Name": p_name,
                "Games Played": 0,
                "Wins": 0,
                "Losses": 0,
                "Survival %": 0.0,
                "Skill Score": 0.0, # We'll just leave it at 0.0 for pure historic games for now unless we calculate PEU
                "Vote Accuracy %": 0.0,
                "Town Games": 0,
                "Mafia Games": 0,
                "Neutral/SK Games": 0,
                "Plain Town Games": 0,
                "Town Wins": 0,
                "Mafia Wins": 0,
                "Neutral/SK Wins": 0,
                "Times Lynched": 0,
                "D1 Lynches": 0,
                "Total Night Deaths": 0,
                "N1 Deaths": 0,
                "_survived_count": 0,
                "_p_score_sum": 0,
                "_e_score_sum": 0,
                "_u_score_sum": 0
            }
        return player_stats[p_id]

    # Process Historical Games
    game_stats = {"Total": 0, "Town": 0, "Mafia": 0, "Draw": 0, "Neutral": 0}
    
    for game in history_archive:
        box = game.get("box_score", {})
        if not box: continue
        
        roster = box.get("roster", [])
        winning_faction = box.get("winning_faction", "Unknown")
        
        # Game Stats
        game_stats["Total"] += 1
        wf_lower = winning_faction.lower()
        if "town" in wf_lower: game_stats["Town"] += 1
        elif "mafia" in wf_lower: game_stats["Mafia"] += 1
        elif "draw" in wf_lower: game_stats["Draw"] += 1
        else: game_stats["Neutral"] += 1
        
        for p in roster:
            raw_name = p.get("player", "Unknown")
            role = p.get("role", "Unknown")
            alignment = p.get("alignment", "Unknown")
            survived = p.get("survived", False)
            death_phase = p.get("death_phase", "")
            
            # Map Name to Canonical ID
            # If name is in user_map, use the first ID. Otherwise use a safe string.
            canonical_id = f"historic_{raw_name.lower().replace(' ', '_')}"
            canonical_name = raw_name
            
            mapped_ids = user_map.get(raw_name.lower())
            if mapped_ids and len(mapped_ids) > 0:
                canonical_id = str(mapped_ids[0])
                
            ps = get_player(canonical_id, canonical_name)
            
            ps["Games Played"] += 1
            if survived:
                ps["_survived_count"] += 1
                
            is_winner = (alignment == winning_faction)
            if is_winner:
                ps["Wins"] += 1
            else:
                ps["Losses"] += 1
                
            align_lower = alignment.lower() if isinstance(alignment, str) else "unknown"
            if "town" in align_lower:
                ps["Town Games"] += 1
                if is_winner: ps["Town Wins"] += 1
                if "plain" in role.lower() or "townie" in role.lower():
                    ps["Plain Town Games"] += 1
            elif "mafia" in align_lower:
                ps["Mafia Games"] += 1
                if is_winner: ps["Mafia Wins"] += 1
            else:
                ps["Neutral/SK Games"] += 1
                if is_winner: ps["Neutral/SK Wins"] += 1
                
            # Basic Death Analysis (rudimentary for historical data)
            if death_phase:
                dp_lower = death_phase.lower()
                if "lynch" in dp_lower or "day" in dp_lower:
                    ps["Times Lynched"] += 1
                    if "day 1" in dp_lower or "day one" in dp_lower:
                        ps["D1 Lynches"] += 1
                if "night" in dp_lower:
                    ps["Total Night Deaths"] += 1
                    if "night 1" in dp_lower or "night one" in dp_lower:
                        ps["N1 Deaths"] += 1

    # Finalize derived stats
    leaderboard = []
    for pid, ps in player_stats.items():
        if ps["Games Played"] > 0:
            ps["Survival %"] = (ps["_survived_count"] / ps["Games Played"]) * 100
        
        leaderboard.append(ps)
        
    # Write unified leaderboard.json
    out_leaderboard = os.path.join(DATA_DIR, "leaderboard.json")
    with open(out_leaderboard, 'w', encoding='utf-8') as f:
        json.dump(leaderboard, f, indent=4)
        
    # Update classic.json trend / gameStats
    classic_path = os.path.join(DATA_DIR, "classic.json")
    classic_data = load_json("classic.json", {})
    classic_data["gameStats"] = game_stats
    
    # Map leaderboard to classic format
    classic_leaderboard = []
    for ps in leaderboard:
        win_rate = (ps["Wins"] / ps["Games Played"] * 100) if ps["Games Played"] > 0 else 0
        classic_leaderboard.append({
            "name": ps["Player Name"],
            "skillScore": ps["Skill Score"],
            "p_score": ps.get("_p_score_sum", 0),
            "e_score": ps.get("_e_score_sum", 0),
            "u_score": ps.get("_u_score_sum", 0),
            "games": ps["Games Played"],
            "winRate": round(win_rate, 1),
            "n1Deaths": ps["N1 Deaths"],
            "d1Lynches": ps["D1 Lynches"]
        })
    classic_data["leaderboard"] = classic_leaderboard
    
    with open(classic_path, 'w', encoding='utf-8') as f:
        json.dump(classic_data, f, indent=4)
        
    print(f"Successfully unified {len(leaderboard)} player records into the Hall of Records!")
    
    # Also compile real Battle Royale stats
    build_battle_royale_stats()

def build_battle_royale_stats():
    br_dir = os.path.join(WEBSITE_DIR, "..", "stats", "Production", "Battle Royale")
    if not os.path.exists(br_dir):
        return
        
    br_games = 0
    combatant_stats = {}
    
    for root, dirs, files in os.walk(br_dir):
        for file in files:
            if file.endswith("_summary.json"):
                summary_path = os.path.join(root, file)
                with open(summary_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                summary = data.get("game_summary", {})
                player_data = data.get("player_data", [])
                if not summary:
                    continue
                    
                br_games += 1
                winning_players = [p.lower() for p in summary.get("winning_players", [])]
                winner_name = summary.get("winning_faction", "Draw")
                
                for p in player_data:
                    pname = p.get("player_name", "Unknown")
                    is_win = (pname.lower() in winning_players) or (p.get("is_winner") is True) or (pname.lower() == winner_name.lower())
                    is_survived = (p.get("status", "").lower() == "alive")
                    death_phase = p.get("death_phase") or ""
                    is_n1 = "night 1" in death_phase.lower()
                    
                    if pname not in combatant_stats:
                        combatant_stats[pname] = {
                            "name": pname,
                            "wins": 0,
                            "games": 0,
                            "_surv_count": 0,
                            "n1Deaths": 0
                        }
                    combatant_stats[pname]["games"] += 1
                    if is_win:
                        combatant_stats[pname]["wins"] += 1
                    if is_survived:
                        combatant_stats[pname]["_surv_count"] += 1
                    if is_n1:
                        combatant_stats[pname]["n1Deaths"] += 1

    br_leaderboard = []
    for name, cs in combatant_stats.items():
        win_rate = (cs["wins"] / cs["games"] * 100) if cs["games"] > 0 else 0
        surv_rate = (cs["_surv_count"] / cs["games"] * 100) if cs["games"] > 0 else 0
        br_leaderboard.append({
            "name": cs["name"],
            "wins": cs["wins"],
            "games": cs["games"],
            "winRate": round(win_rate, 1),
            "survRate": round(surv_rate, 1),
            "n1Deaths": cs["n1Deaths"]
        })
        
    br_leaderboard.sort(key=lambda x: (x["wins"], x["games"]), reverse=True)
    
    chart_labels = [p["name"] for p in br_leaderboard if p["wins"] > 0][:10]
    chart_values = [p["wins"] for p in br_leaderboard if p["wins"] > 0][:10]
    if not chart_labels:
        chart_labels = ["No Wins Recorded"]
        chart_values = [0]
        
    br_output = {
        "totalGames": br_games,
        "chart": {
            "labels": chart_labels,
            "values": chart_values
        },
        "leaderboard": br_leaderboard
    }
    
    out_br = os.path.join(DATA_DIR, "battle_royale.json")
    with open(out_br, 'w', encoding='utf-8') as f:
        json.dump(br_output, f, indent=4)
    print(f"Successfully compiled Battle Royale stats for {br_games} matches and {len(br_leaderboard)} combatants!")

if __name__ == "__main__":
    build_unified_stats()
