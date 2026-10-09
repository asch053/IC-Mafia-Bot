import os
import json
import re
import sys
import math
from collections import Counter, defaultdict

WEBSITE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(WEBSITE_DIR, "data")
ROOT_DIR = os.path.dirname(WEBSITE_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
DB_DIR = os.path.join(WEBSITE_DIR, "database")
if not os.path.exists(DB_DIR):
    alt_db = os.path.join(ROOT_DIR, "data", "database")
    if os.path.exists(alt_db): DB_DIR = alt_db

STORIES_DIR = os.path.join(WEBSITE_DIR, "stories")
if not os.path.exists(STORIES_DIR):
    alt_stories = os.path.join(ROOT_DIR, "data", "stories")
    if os.path.exists(alt_stories): STORIES_DIR = alt_stories

CANONICAL_NAMES = {
    "225405842235719680": "You_Fool",
    "139146807472160768": "Jets",
    "294464443570454528": "Jets",
    "479362336264683520": "MrBlonde",
    "479197632074612736": "The_Unknown",
    "98260473664790528": "Walking Corpse",
    "211933902225408010": "KT",
    "566633524585824266": "Player1",
    "220666545544626177": "Arby3",
    "336188557561430017": "Melvin85",
    "750562540282445884": "Tishxo",
    "549657242170032154": "Goddess",
    "386804810617323531": "melsfreefallin",
    "220142891027136512": "Panda",
    "216918396539764737": "Ordos",
    "undeath": "Undeath",
    "risingdown": "RisingDown",
    "wildflowersoul": "WildFlowerSoul",
    "a10": "A10",
    "einstein": "Einstein",
    "HydroP": "Hydro"
}

ID_ALIASES = {
    "294464443570454528": "139146807472160768"
}

def load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def phase_str_to_int(phase_str):
    if not phase_str: return 0
    p = str(phase_str).lower().strip()
    nums = re.findall(r'\d+', p)
    n = int(nums[0]) if nums else 1
    if 'night' in p:
        return max(1, (n * 2) - 1)
    elif 'day' in p:
        return max(2, n * 2)
    return 2

def get_game_total_phases(game):
    box = game.get('box_score', {})
    roster = box.get('roster', [])
    max_p = 1
    for p in roster:
        dp = p.get('death_phase')
        if dp:
            max_p = max(max_p, phase_str_to_int(dp))
    for ev in box.get('timeline', []):
        tp = ev.get('phase')
        if tp:
            max_p = max(max_p, phase_str_to_int(tp))
    return max(2, max_p)

def resolve_player_identity(raw_name, raw_pid, user_map):
    # 1. Resolve raw_pid if known
    if raw_pid:
        pid_str = str(raw_pid).strip()
        if pid_str in ID_ALIASES:
            pid_str = ID_ALIASES[pid_str]
        if pid_str in CANONICAL_NAMES:
            return pid_str, CANONICAL_NAMES[pid_str]
        if pid_str in user_map and len(user_map[pid_str]) > 0:
            cid = str(user_map[pid_str][0])
            cid = ID_ALIASES.get(cid, cid)
            return cid, CANONICAL_NAMES.get(cid, raw_name)
            
    # 2. Resolve raw_name with multiple normalization forms
    clean_lower = str(raw_name).lower().strip()
    candidates = [
        clean_lower,
        clean_lower.replace(" ", "_"),
        clean_lower.replace("_", " "),
        clean_lower.replace(" ", "").replace("_", "")
    ]
    for c in candidates:
        if c in user_map and len(user_map[c]) > 0:
            cid = str(user_map[c][0])
            cid = ID_ALIASES.get(cid, cid)
            cname = CANONICAL_NAMES.get(cid, raw_name)
            return cid, cname

    cid = f"historic_{clean_lower.replace(' ', '_')}"
    cname = CANONICAL_NAMES.get(cid, raw_name)
    return cid, cname

def sync_new_production_games():
    stats_dir = os.path.join(ROOT_DIR, "stats", "Production")
    bot_db_path = os.path.join(DB_DIR, "discord_bot.json")
    bot_games = load_json(bot_db_path, [])
    existing_ids = {str(g.get("thread_id")) for g in bot_games}
    
    if not os.path.exists(stats_dir):
        return bot_games

    added = 0
    for root, dirs, files in os.walk(stats_dir):
        for file in files:
            if file.endswith("_summary.json"):
                summary_path = os.path.join(root, file)
                story_path = summary_path.replace("_summary.json", "_story.md")
                
                try:
                    with open(summary_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except Exception:
                    continue
                    
                summary = data.get("game_summary", {})
                player_data = data.get("player_data", [])
                vote_history = data.get("lynch_vote_history", [])
                
                if not summary:
                    continue
                    
                game_id = summary.get("game_id")
                if not game_id or str(game_id) in existing_ids:
                    continue
                    
                existing_ids.add(str(game_id))
                added += 1
                
                story_scenes = {}
                narrative_chapters = []
                full_raw_story = ""
                if os.path.exists(story_path):
                    with open(story_path, 'r', encoding='utf-8') as f:
                        story_content = f.read()
                    if "\n## Chat Transcript" in story_content:
                        story_content = story_content.split("\n## Chat Transcript")[0].strip()
                    full_raw_story = story_content
                    parts = story_content.split('========================================')
                    if len(parts) >= 3:
                        scene_block = parts[1]
                        phase_matches = re.split(r'\*\*---\s*([^-]+)\s*---\*\*', scene_block)
                        for i in range(1, len(phase_matches), 2):
                            ph_name = phase_matches[i].strip()
                            ph_text = phase_matches[i+1].strip()
                            story_scenes[ph_name] = ph_text
                            narrative_chapters.append(f"### {ph_name}\n\n{ph_text}")
                
                story_as_written = full_raw_story or ("\n\n".join(narrative_chapters) if narrative_chapters else f"Automated game {game_id} run on Discord.")
                winning_faction = summary.get("winning_faction", "Unknown")
                winning_players_str = ", ".join(summary.get("winning_players", [])) if summary.get("winning_players") else "None"
                narrative_summary = (
                    f"### 📋 Match Overview\n"
                    f"- **Game ID:** `{game_id}`\n"
                    f"- **Era:** Discord Modern Bot\n"
                    f"- **Game Type:** {summary.get('game_type', 'Classic')}\n"
                    f"- **Winning Faction:** **{winning_faction}**\n"
                    f"- **Victors:** {winning_players_str}\n"
                    f"- **Total Players:** {len(player_data)} (Town: {summary.get('player_counts', {}).get('town', 0)}, Mafia: {summary.get('player_counts', {}).get('mafia', 0)}, Neutral: {summary.get('player_counts', {}).get('neutral', 0)})\n"
                    f"- **Total Duration:** {summary.get('total_days', 0)} phases\n\n"
                    f"### ⚔️ Tactical Summary\n"
                    f"Automated match hosted on Discord. The game proceeded across strategic phases, culminating in a decisive **{winning_faction}** victory."
                )

                os.makedirs(STORIES_DIR, exist_ok=True)
                with open(os.path.join(STORIES_DIR, f"{game_id}_summary.md"), "w", encoding="utf-8") as sf:
                    sf.write(narrative_summary)
                with open(os.path.join(STORIES_DIR, f"{game_id}_story.md"), "w", encoding="utf-8") as stf:
                    stf.write(story_as_written)

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
                winning_players_lower = [w.lower() for w in summary.get("winning_players", [])]
                for p in player_data:
                    p_name = p.get("player_name", "Unknown")
                    is_win = (p.get("is_winner") is True) or (p_name.lower() in winning_players_lower) or (p.get("alignment", "").lower() == winning_faction.lower())
                    roster.append({
                        "player": p_name,
                        "player_id": p.get("player_id"),
                        "role": p.get("role"),
                        "alignment": p.get("alignment"),
                        "survived": (p.get("status", "").lower() == "alive"),
                        "is_winner": is_win,
                        "death_phase": p.get("death_phase"),
                        "death_cause": p.get("death_cause")
                    })
                
                winning_players = summary.get("winning_players", [])
                mvp = None
                if winning_players:
                    mvp = {
                        "player": winning_players[0],
                        "rationale": f"Secured the victory for {winning_faction}."
                    }
                    
                bot_games.append({
                    "thread_id": str(game_id),
                    "era": "Discord",
                    "title": f"Discord Game - {game_id}",
                    "moderator": "IC Mafia Bot",
                    "game_type": summary.get("game_type", "classic"),
                    "total_posts": 0,
                    "winning_faction": winning_faction,
                    "summary_file": f"stories/{game_id}_summary.md",
                    "story_file": f"stories/{game_id}_story.md",
                    "box_score": {
                        "winning_faction": winning_faction,
                        "game_type": summary.get("game_type", "classic"),
                        "mvp": mvp,
                        "roster": roster,
                        "timeline": timeline,
                        "notable_moments": [
                            f"Game completed in {summary.get('total_days', len(all_phases))} phases.",
                            f"Winning faction: {winning_faction}."
                        ]
                    },
                    "lynch_vote_history": vote_history
                })

    if added > 0:
        with open(bot_db_path, "w", encoding="utf-8") as f:
            json.dump(bot_games, f, indent=2, ensure_ascii=False)
        print(f"Appended {added} new production games to discord_bot.json.")
        
    return bot_games

def load_markdown_file(rel_or_abs_path):
    if not rel_or_abs_path:
        return ""
    if os.path.isabs(rel_or_abs_path):
        target = rel_or_abs_path
    else:
        target = os.path.join(WEBSITE_DIR, rel_or_abs_path)
        if not os.path.exists(target):
            clean_name = os.path.basename(rel_or_abs_path)
            target = os.path.join(STORIES_DIR, clean_name)
        if not os.path.exists(target):
            clean_name = os.path.basename(rel_or_abs_path)
            target = os.path.join(STORIES_DIR, "ineligible games", clean_name)
        
    if os.path.exists(target):
        try:
            with open(target, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception:
            return ""
    return ""

def compute_player_leaderboard(games_list, user_map):
    player_stats = {}
    def get_player(p_id, p_name):
        if p_id not in player_stats:
            player_stats[p_id] = {
                "Player Name": p_name,
                "Games Played": 0,
                "Wins": 0,
                "Losses": 0,
                "Games Won": 0,
                "Survival %": 0.0,
                "Skill Score": 0.0,
                "p_score": 0.0,
                "e_score": 0.0,
                "u_score": 0.0,
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
                "_w_surv": 0.0,
                "_w_total_phases": 0.0,
                "_p_scores": [],
                "_u_faction_games": defaultdict(int),
                "_u_faction_wins": defaultdict(int),
                "_accurate_votes": 0,
                "_total_end_phase_votes": 0,
                "_aliases": set(),
                "_games": []
            }
        return player_stats[p_id]

    for game in games_list:
        box = game.get("box_score", {})
        if not box: continue
        
        roster = box.get("roster", [])
        winning_faction = box.get("winning_faction", "Unknown")
        total_phases = get_game_total_phases(game)
        vote_history = game.get("lynch_vote_history", [])
        wf_lower = winning_faction.lower() if isinstance(winning_faction, str) else "unknown"

        for p in roster:
            raw_name = p.get("player", "Unknown")
            raw_pid = p.get("player_id")
            role = p.get("role", "Unknown")
            alignment = p.get("alignment", "Unknown")
            survived = bool(p.get("survived", False))
            death_phase = p.get("death_phase", "") or ""
            death_cause = (p.get("death_cause") or "").lower()
            
            canonical_id, canonical_name = resolve_player_identity(raw_name, raw_pid, user_map)
            ps = get_player(canonical_id, canonical_name)
            if canonical_id in CANONICAL_NAMES:
                ps["Player Name"] = CANONICAL_NAMES[canonical_id]
            
            ps["Games Played"] += 1
            if survived:
                ps["_survived_count"] += 1
                
            is_winner = p.get("is_winner")
            if is_winner is None:
                is_winner = (alignment.lower() == wf_lower) if wf_lower else False
                
            if is_winner:
                ps["Wins"] += 1
                ps["Games Won"] += 1
            else:
                ps["Losses"] += 1

            ps["_aliases"].add(raw_name)
            ps["_games"].append({
                "thread_id": str(game.get("thread_id", "")),
                "game_id": str(game.get("game_id", "")),
                "era": game.get("era", "Unknown"),
                "title": game.get("title", "Mafia Game"),
                "role": role,
                "alignment": alignment,
                "result": "Win" if is_winner else "Loss",
                "survived": survived,
                "death_phase": death_phase if death_phase else ("Survived" if survived else "Dead")
            })
                
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
                
            dp_lower = death_phase.lower()
            if death_phase:
                if "lynch" in dp_lower or "day" in dp_lower or "lynch" in death_cause:
                    ps["Times Lynched"] += 1
                    if "day 1" in dp_lower or "day one" in dp_lower:
                        ps["D1 Lynches"] += 1
                if "night" in dp_lower or "night" in death_cause:
                    ps["Total Night Deaths"] += 1
                    if "night 1" in dp_lower or "night one" in dp_lower:
                        ps["N1 Deaths"] += 1

            # 1. Elusiveness (E)
            if survived:
                lived = total_phases
            elif death_phase:
                lived = max(0, phase_str_to_int(death_phase) - 1)
            else:
                lived = max(1, total_phases // 2)
                
            ps["_w_surv"] += (lived * (lived + 1)) / 2
            ps["_w_total_phases"] += (total_phases * (total_phases + 1)) / 2
            
            # 2. Understanding (U)
            cutoff = math.floor(total_phases * 0.25)
            if lived > cutoff or is_winner:
                u_align = 'Town' if 'town' in align_lower else ('Mafia' if 'mafia' in align_lower else 'Neutral')
                ps["_u_faction_games"][u_align] += 1
                if is_winner:
                    ps["_u_faction_wins"][u_align] += 1
                    
            # 3. Persuasion (P)
            my_votes = []
            if vote_history:
                p_id_str = str(p.get("player_id", ""))
                my_votes = [
                    v for v in vote_history 
                    if str(v.get("voter_name", "")).lower() == raw_name.lower() or 
                       (p_id_str and str(v.get("voter_id", "")) == p_id_str) or
                       (str(v.get("voter_id", "")) == canonical_id)
                ]
                
            if my_votes:
                w_correct = 0
                w_total_vote = 0
                total_switches = 0
                votes_by_phase = defaultdict(list)
                for v in my_votes:
                    if v.get("phase"):
                        votes_by_phase[v["phase"]].append(v)
                        
                for ph, v_list in votes_by_phase.items():
                    if len(v_list) > 1:
                        for idx in range(1, len(v_list)):
                            if v_list[idx-1].get("target_id") != v_list[idx].get("target_id") or \
                               v_list[idx-1].get("target_name") != v_list[idx].get("target_name"):
                                total_switches += 1
                    p_num = phase_str_to_int(ph)
                    if p_num > 0 and p_num % 2 == 0:
                        w_total_vote += p_num
                        lynched_name = None
                        for cand in roster:
                            if cand.get("death_phase") == ph and "lynch" in (cand.get("death_cause") or "").lower():
                                lynched_name = cand.get("player")
                                break
                        final_targ = v_list[-1].get("target_name") or v_list[-1].get("target_id")
                        if lynched_name and final_targ and str(final_targ).lower() == str(lynched_name).lower():
                            w_correct += p_num
                            
                    final_targ_name = (v_list[-1].get("target_name") or "").lower()
                    target_cand = next((cand for cand in roster if cand.get("player", "").lower() == final_targ_name), None)
                    if target_cand:
                        ps["_total_end_phase_votes"] += 1
                        if "mafia" in (target_cand.get("alignment") or "").lower():
                            ps["_accurate_votes"] += 1
                            
                p_base = (w_correct / w_total_vote) if w_total_vote > 0 else 0.5
                p_decis = 1.0 - (total_switches / len(my_votes)) if len(my_votes) > 0 else 1.0
                ps["_p_scores"].append(min(5.0, p_base * p_decis * 5.0))
            else:
                if "day 1" in dp_lower and ("lynch" in dp_lower or "lynch" in death_cause):
                    ps["_p_scores"].append(0.5)
                elif "day 2" in dp_lower and ("lynch" in dp_lower or "lynch" in death_cause):
                    ps["_p_scores"].append(1.5)
                elif "lynch" in dp_lower or "lynch" in death_cause:
                    ps["_p_scores"].append(2.5)
                elif "night" in dp_lower or lived < total_phases:
                    ps["_p_scores"].append(4.0 if is_winner else 2.0)
                else:
                    ps["_p_scores"].append(4.8 if is_winner else 2.5)

    result_dict = {}
    for pid, ps in player_stats.items():
        if ps["Games Played"] > 0:
            ps["Survival %"] = round((ps["_survived_count"] / ps["Games Played"]) * 100, 1)
            
            # Elusiveness (E)
            if ps["_w_total_phases"] > 0:
                ps["e_score"] = round(min(5.0, (ps["_w_surv"] / ps["_w_total_phases"]) * 5.0), 1)
            else:
                ps["e_score"] = 0.0
                
            # Understanding (U)
            w_map = {'Town': 0.10, 'Mafia': 0.35, 'Neutral': 0.55}
            rates = sum((ps["_u_faction_wins"][f] / ps["_u_faction_games"][f]) * w_map[f] for f in ps["_u_faction_games"] if ps["_u_faction_games"][f] > 0)
            w_sum = sum(w_map[f] for f in ps["_u_faction_games"] if ps["_u_faction_games"][f] > 0)
            ps["u_score"] = round(min(5.0, (rates / w_sum * 5.0)), 1) if w_sum > 0 else 0.0
            
            # Persuasion (P)
            if ps["_p_scores"]:
                ps["p_score"] = round(min(5.0, sum(ps["_p_scores"]) / len(ps["_p_scores"])), 1)
            else:
                ps["p_score"] = 0.0
                
            final_skill = (ps["p_score"] + ps["e_score"] + ps["u_score"]) / 3.0
            ps["Skill Score"] = round(min(5.0, max(0.0, final_skill)), 2)
            
            if ps["_total_end_phase_votes"] > 0:
                ps["Vote Accuracy %"] = round((ps["_accurate_votes"] / ps["_total_end_phase_votes"]) * 100, 1)
            else:
                win_ratio = ps["Wins"] / ps["Games Played"]
                d1_ratio = ps["D1 Lynches"] / ps["Games Played"]
                est_acc = min(100.0, max(0.0, 40.0 + (35.0 * win_ratio) - (15.0 * d1_ratio)))
                ps["Vote Accuracy %"] = round(est_acc, 1)
        clean_ps = {k: v for k, v in ps.items() if not k.startswith("_")}

        # Enrich aliases from master_user_map.json
        user_map_aliases = set(ps["_aliases"])
        for k, v in user_map.items():
            if not k.isdigit() and str(pid) in [str(x) for x in v]:
                user_map_aliases.add(k)

        seen_aliases = {}
        for a in user_map_aliases:
            a_str = str(a).strip()
            if not a_str or a_str.isdigit(): continue
            low = a_str.lower()
            if low not in seen_aliases or (a_str != low and seen_aliases[low] == low):
                seen_aliases[low] = a_str

        clean_ps["Aliases"] = sorted(list(seen_aliases.values()), key=lambda x: (x.lower(), x))
        clean_ps["Games"] = ps["_games"]
        result_dict[pid] = clean_ps
    return result_dict

FORUM_GAME_ID_MAP = {
    "844": "11",
    "6880": "12",
    "9921": "13",
    "35451": "14",
    "38590": "15",
    "39258": "15.1",
    "44647": "16",
    "50496": "17",
    "54849": "18",
    "58647": "19",
    "80385": "20",
    "82572": "21",
    "84210": "22",
    "85134": "23",
    "93305": "24",
    "139357": "25",
    "140972": "26",
    "142153": "27",
    "145042": "28",
    "153449": "29",
    "174143": "30",
    "175063": "31",
    "176810": "32",
    "177411": "33",
    "178353": "34",
    "179654": "35",
    "180235": "36",
    "180756": "37",
    "181405": "38",
    "181955": "39",
    "182698": "40",
    "183110": "41",
    "183598": "42",
    "184133": "43",
    "184555": "44",
    "184809": "45",
    "185122": "46",
    "185333": "47",
    "185552": "48",
    "185734": "49",
    "186100": "50",
    "186442": "51",
    "186801": "52",
    "189576": "53",
    "203868": "54",
}

DISCOURSE_GAME_ID_MAP = {
    "6053": "55",
    "6219": "56",
    "6347": "57",
    "6452": "58",
    "6556": "59",
    "6631": "60",
    "6680": "61",
    "6772": "62",
    "6825": "63",
    "6871": "64",
    "6906": "65",
    "6913": "65.1",
    "6930": "66",
    "6954": "67",
    "7043": "68",
    "7077": "70",
    "7107": "71",
    "7130": "72",
    "7164": "73",
    "7187": "74",
    "7235": "75",
    "7275": "76",
    "7321": "77",
    "7347": "78",
    "7419": "79",
    "7475": "80",
    "7513": "81",
    "7552": "82",
    "7703": "84",
    "7879": "86",
    "8118": "88"
}

def get_canonical_game_id(era, tid, title=""):
    clean_tid = str(tid).replace("manual-", "").strip()
    if era == "Forum":
        return FORUM_GAME_ID_MAP.get(clean_tid, clean_tid)
    elif era == "Discourse":
        return DISCOURSE_GAME_ID_MAP.get(clean_tid, clean_tid)
    elif era == "Discord_Manual":
        return clean_tid
    elif "Discord" in era:
        m = re.search(r'(Classic\s*#?\d+|Battle\s*Royale\s*#?\d+)', title, re.IGNORECASE)
        if m:
            clean = m.group(1).replace('Battle Royale', 'BR').replace('Battle royale', 'BR')
            return clean
        return clean_tid
    return clean_tid

def build_unified_stats(sync_sheets=False):
    print("Building unified multi-era stats from modular databases...")
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(DB_DIR, exist_ok=True)
    os.makedirs(STORIES_DIR, exist_ok=True)

    sync_new_production_games()

    forum_games = load_json(os.path.join(DB_DIR, "historic_forum.json"), [])
    discourse_games = load_json(os.path.join(DB_DIR, "historic_discourse.json"), [])
    discord_bot_games = load_json(os.path.join(DB_DIR, "discord_bot.json"), [])
    discord_manual_games = load_json(os.path.join(DB_DIR, "discord_manual.json"), [])

    print(f"Loaded: {len(forum_games)} Forum, {len(discourse_games)} Discourse, {len(discord_bot_games)} Discord Bot, {len(discord_manual_games)} Discord Manual games.")

    all_source_games = forum_games + discourse_games + discord_bot_games + discord_manual_games
    history_archive = []
    
    for g in all_source_games:
        if g.get("eligible") is False:
            continue
        tid = str(g.get("thread_id", "unknown"))
        era = g.get("era", "Forum")
        
        summary_file = g.get("summary_file") or f"stories/{tid}_summary.md"
        story_file = g.get("story_file") or f"stories/{tid}_story.md"
        
        narrative_chronicle = load_markdown_file(summary_file)
        story_as_written = load_markdown_file(story_file)
        
        box = g.get("box_score") or {}
        if not box.get("timeline"):
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

        game_id = get_canonical_game_id(era, tid, g.get("title", ""))
        game_entry = {
            "game_id": game_id,
            "thread_id": tid,
            "era": era,
            "title": g.get("title", f"{era} Game {tid}"),
            "start_date": g.get("start_date", ""),
            "moderator": g.get("moderator", "Game Host"),
            "author": g.get("author") or g.get("moderator", "Game Host"),
            "game_type": g.get("game_type", "classic"),
            "total_posts": g.get("total_posts"),
            "narrative_chronicle": narrative_chronicle,
            "story_as_written": story_as_written,
            "summary_file": summary_file,
            "story_file": story_file,
            "box_score": box,
            "lynch_vote_history": g.get("lynch_vote_history", [])
        }
        history_archive.append(game_entry)

    def parse_archive_sort_key(g):
        sd = g.get("start_date") or "1970-01-01"
        gid = str(g.get("game_id", ""))
        nums = re.findall(r"\d+(?:\.\d+)?", gid)
        val = float(nums[0]) if nums else 0.0
        return (sd, val)

    history_archive.sort(key=parse_archive_sort_key)

    out_history = os.path.join(DATA_DIR, "history_archive.json")
    with open(out_history, 'w', encoding='utf-8') as f:
        json.dump(history_archive, f, indent=4, ensure_ascii=False)
    print(f"Saved {len(history_archive)} games to {out_history}.")

    user_map = load_json(os.path.join(DATA_DIR, "master_user_map.json"), {})
    
    # Separate Classic Games (excluding Battle Royale) for Mafia Classic stats and leaderboard
    classic_games = [g for g in history_archive if g.get("game_type", "classic").lower() != "battle_royale"]
    print(f"Isolated {len(classic_games)} Classic games (excluding {len(history_archive) - len(classic_games)} Battle Royale games) for Classic Mode analytics.")

    game_stats = {"Total": 0, "Town": 0, "Mafia": 0, "Draw": 0, "Neutral": 0}
    for game in classic_games:
        box = game.get("box_score", {})
        if not box: continue
        winning_faction = box.get("winning_faction", "Unknown")
        game_stats["Total"] += 1
        wf_lower = winning_faction.lower() if isinstance(winning_faction, str) else "unknown"
        if "town" in wf_lower: game_stats["Town"] += 1
        elif "mafia" in wf_lower or "mob" in wf_lower: game_stats["Mafia"] += 1
        elif "draw" in wf_lower or wf_lower in ["n/a", "unknown"]: game_stats["Draw"] += 1
        else: game_stats["Neutral"] += 1

    # 1. Calculate All-Time Career Leaderboard (Classic Mode Only)
    all_players_dict = compute_player_leaderboard(classic_games, user_map)

    # 2. Calculate Era-Specific Leaderboards (Classic Mode Only)
    eras = ["Forum", "Discourse", "Discord_Manual", "Discord"]
    era_leaderboards = {}
    for era in eras:
        era_games = [g for g in classic_games if g.get("era") == era]
        era_leaderboards[era] = compute_player_leaderboard(era_games, user_map)

    # 3. Attach era_stats to each player in all_players_dict
    for pid, ps in all_players_dict.items():
        ps["era_stats"] = {}
        for era in eras:
            if pid in era_leaderboards[era]:
                # Exclude nested Games/Aliases to keep leaderboard.json compact
                sub = {k: v for k, v in era_leaderboards[era][pid].items() if k not in ["Games", "Aliases", "era_stats"]}
                ps["era_stats"][era] = sub

    leaderboard = list(all_players_dict.values())
        
    out_leaderboard = os.path.join(DATA_DIR, "leaderboard.json")
    with open(out_leaderboard, 'w', encoding='utf-8') as f:
        json.dump(leaderboard, f, indent=4, ensure_ascii=False)
        
    classic_path = os.path.join(DATA_DIR, "classic.json")
    classic_data = load_json(classic_path, {})
    classic_data["gameStats"] = game_stats
    
    classic_leaderboard = []
    for ps in leaderboard:
        win_rate = (ps["Wins"] / ps["Games Played"] * 100) if ps["Games Played"] > 0 else 0
        classic_leaderboard.append({
            "name": ps["Player Name"],
            "skillScore": ps["Skill Score"],
            "p_score": ps.get("p_score", 0.0),
            "e_score": ps.get("e_score", 0.0),
            "u_score": ps.get("u_score", 0.0),
            "games": ps["Games Played"],
            "winRate": round(win_rate, 1),
            "survRate": round(ps.get("Survival %", 0.0), 1),
            "n1Deaths": ps["N1 Deaths"],
            "d1Lynches": ps["D1 Lynches"]
        })
    classic_leaderboard.sort(key=lambda x: (x["skillScore"], x["games"]), reverse=True)
    classic_data["leaderboard"] = classic_leaderboard
    
    # Calculate Meta History Trend across Classic games chronologically
    sorted_games = sorted(classic_games, key=lambda g: g.get("start_date") or "1970-01-01")
    cum_town = 0
    cum_mafia = 0
    cum_neutral = 0
    cum_draw = 0
    trend = []

    era_labels = {
        "Forum": "Forum Era",
        "Discourse": "Discourse Era",
        "Discord_Manual": "Discord Manual",
        "Discord": "Discord Bot"
    }

    era_stats = {
        "Forum": {"Total": 0, "Town": 0, "Mafia": 0, "Draw": 0, "Neutral": 0, "label": "Forum Era"},
        "Discourse": {"Total": 0, "Town": 0, "Mafia": 0, "Draw": 0, "Neutral": 0, "label": "Discourse Era"},
        "Discord_Manual": {"Total": 0, "Town": 0, "Mafia": 0, "Draw": 0, "Neutral": 0, "label": "Discord Manual"},
        "Discord": {"Total": 0, "Town": 0, "Mafia": 0, "Draw": 0, "Neutral": 0, "label": "Discord Bot"}
    }

    for i, g in enumerate(sorted_games, 1):
        box = g.get("box_score", {}) or {}
        wf = box.get("winning_faction", "Unknown")
        wf_lower = wf.lower() if isinstance(wf, str) else "unknown"
        era_raw = g.get("era") or "Unknown"
        era_label = era_labels.get(era_raw, era_raw)

        if era_raw not in era_stats:
            era_stats[era_raw] = {"Total": 0, "Town": 0, "Mafia": 0, "Draw": 0, "Neutral": 0, "label": era_label}

        era_stats[era_raw]["Total"] += 1

        if "town" in wf_lower:
            cum_town += 1
            era_stats[era_raw]["Town"] += 1
        elif "mafia" in wf_lower or "mob" in wf_lower:
            cum_mafia += 1
            era_stats[era_raw]["Mafia"] += 1
        elif "draw" in wf_lower or wf_lower in ["n/a", "unknown"]:
            cum_draw += 1
            era_stats[era_raw]["Draw"] += 1
        else:
            cum_neutral += 1
            era_stats[era_raw]["Neutral"] += 1

        t_pct = round((cum_town / i) * 100, 1)
        m_pct = round((cum_mafia / i) * 100, 1)
        n_pct = round((cum_neutral / i) * 100, 1)
        d_pct = round(max(0.0, 100.0 - t_pct - m_pct - n_pct), 1)

        sd = g.get("start_date") or "Unknown"
        title = g.get("title") or f"Game {i}"
        trend.append({
            "gameNum": i,
            "gameId": g.get("game_id", ""),
            "date": sd,
            "title": title,
            "era": era_raw,
            "eraLabel": era_label,
            "winningFaction": wf,
            "label": f"Game {i}: {title} [{era_label}] ({sd})",
            "townPct": t_pct,
            "mafiaPct": m_pct,
            "neutralPct": n_pct,
            "drawPct": d_pct
        })

    classic_data["trend"] = trend
    classic_data["eraStats"] = era_stats
    
    with open(classic_path, 'w', encoding='utf-8') as f:
        json.dump(classic_data, f, indent=4, ensure_ascii=False)
        
    print(f"Successfully unified {len(leaderboard)} player records into the Hall of Records!")
    
    build_battle_royale_stats()

    if sync_sheets:
        try:
            from scripts.sync_google_sheets import sync_all_to_sheets
            sync_all_to_sheets()
        except Exception as e:
            print(f"Warning: Google Sheets sync failed: {e}")

def build_battle_royale_stats():
    prod_dir = os.path.join(ROOT_DIR, "stats", "Production")
    if not os.path.exists(prod_dir):
        return
        
    user_map = load_json(os.path.join(DATA_DIR, "master_user_map.json"), {})
    br_games = 0
    combatant_stats = {}
    seen_gids = set()
    
    for root, dirs, files in os.walk(prod_dir):
        for file in files:
            if file.endswith("_summary.json"):
                summary_path = os.path.join(root, file)
                try:
                    with open(summary_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except Exception:
                    continue
                    
                summary = data.get("game_summary", {})
                player_data = data.get("player_data", [])
                if not summary:
                    continue
                    
                gid = summary.get("game_id")
                if not gid or gid in seen_gids:
                    continue
                gtype = summary.get("game_type", "")
                if gtype != "battle_royale" and "Battle Royale" not in root:
                    continue
                seen_gids.add(gid)
                
                br_games += 1
                winning_players = [resolve_player_identity(p, None, user_map)[1].lower() for p in summary.get("winning_players", [])]
                _, winner_name = resolve_player_identity(summary.get("winning_faction", "Draw"), None, user_map)
                
                for p in player_data:
                    raw_name = p.get("player_name", "Unknown")
                    _, pname = resolve_player_identity(raw_name, p.get("player_id"), user_map)
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
        json.dump(br_output, f, indent=4, ensure_ascii=False)
    print(f"Successfully compiled Battle Royale stats for {br_games} matches and {len(br_leaderboard)} combatants!")

if __name__ == "__main__":
    sync = "--sync-sheets" in sys.argv
    build_unified_stats(sync_sheets=sync)
