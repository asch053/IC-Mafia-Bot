"""
scripts/ingest_manual_and_discourse_sheet.py
Ingests manual Discord mafia games (998, 999, 1001-1027) and enriches Discourse games (55-65)
from Google Spreadsheet 'Mafia Data' (1P6GhM7HBFGadZCx5yLgkvyP6H4BRkE_pf76sSM3KIH8).

Updates:
- Website/database/discord_manual.json (29 completed games)
- Website/database/historic_discourse.json (games 55-65 enriched with full rosters)
- Website/database/phase_by_phase_source.json (cached phase-by-phase rows for syncing)
- Website/stories/manual-{gid}_summary.md & manual-{gid}_story.md
"""

import os
import re
import json
import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("IngestSheet")

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "data")
WEBSITE_DIR = os.path.join(ROOT_DIR, "Website")
DB_DIR = os.path.join(WEBSITE_DIR, "database")
STORIES_DIR = os.path.join(WEBSITE_DIR, "stories")
SOURCE_SHEET_ID = "1P6GhM7HBFGadZCx5yLgkvyP6H4BRkE_pf76sSM3KIH8"
CREDS_FILE = os.path.join(DATA_DIR, "ic-mafia-bot-41a41f61e757.json")

# Discourse Game ID mapping to thread IDs in historic_discourse.json
DISCOURSE_ID_MAP = {
    "55": "6053",  # IC Mafia 2.1 - The return
    "56": "6219",  # IC Mafia 56: Fire and Blood
    "57": "6347",  # IC Mafia 57 : Avenging the EndGame
    "58": "6452",  # Mafia 58 New Sanguine
    "59": "6556",  # IC Mafia 59: The uprising
    "60": "6631",  # IC Mafia 60: Welcome to the Wild West
    "61": "6680",  # IC Mafia 61: The Testament of the Watchers
    "62": "6772",  # IC Mafia 62: Can I see your ticket?
    "63": "6825",  # IC Mafia 63: Bad Romans
    "64": "6871",  # IC Mafia: Capricorn Round 1: Moderators vs. IC Players
    "65": "6913"   # IC Mafia 65- NYC remastered
}

MANUAL_THEMES = {
    "998": "Discord Mafia 998: Street Fighter",
    "999": "Discord Mafia 999: Hydro's Syndicate",
    "1001": "Discord Mafia 1001: Goddess of War",
    "1002": "Discord Mafia 1002: Gamzee's Carnage",
    "1003": "Discord Mafia 1003: Arby's Crossfire",
    "1004": "Discord Mafia 1004: Blonde's Reservoir",
    "1005": "Discord Mafia 1005: TBO's Reckoning",
    "1006": "Discord Mafia 1006: Schnipel's Slasher",
    "1007": "Discord Mafia 1007: Schnipel's Mystery",
    "1008": "Discord Mafia 1008: Goddess's Domain",
    "1009": "Discord Mafia 1009: sCriv's Underworld",
    "1010": "Discord Mafia 1010: Gamzee's Chaos",
    "1011": "Discord Mafia 1011: Arby's Gambit",
    "1012": "Discord Mafia 1012: Jets' Jetstream",
    "1013": "Discord Mafia 1013: Schniepel's Return",
    "1014": "Discord Mafia 1014: Puny Penguin's Arctic",
    "1015": "Discord Mafia 1015: Nolio's Court",
    "1016": "Discord Mafia 1016: Nolio's Vendetta",
    "1017": "Discord Mafia 1017: Nolio's Shadows",
    "1018": "Discord Mafia 1018: Schneipel's Trap",
    "1019": "Discord Mafia 1019: Genesis's Creation",
    "1020": "Discord Mafia 1020: Goddess's Wrath",
    "1021": "Discord Mafia 1021: Arby's Finale",
    "1022": "Discord Mafia 1022: TBO's Stand",
    "1023": "Discord Mafia 1023: Goddess's Triumph",
    "1024": "Discord Mafia 1024: Genesis's Reckoning",
    "1025": "Discord Mafia 1025: Gwynedd's Revival",
    "1026": "Discord Mafia 1026: Genesis's End",
    "1027": "Discord Mafia 1027: Hydro's Last Call"
}

def get_sheets_client(creds_path=CREDS_FILE):
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
    return gspread.authorize(creds)

def parse_phase_outcome_cell(cell_val, faction, is_power=False):
    cell_val = (cell_val or "").strip()
    val_lower = cell_val.lower()
    is_dead = any(k in val_lower for k in ['killed', 'dead', 'lynched', 'suicide', 'inactive', 'mod killed'])
    is_survivor = any(k in val_lower for k in ['winner', 'survived', 'alive'])
    
    parts = [p.strip() for p in cell_val.split('-') if p.strip()]
    extracted_role = None
    death_cause = None

    if len(parts) >= 3:
        extracted_role = parts[1]
        death_cause = parts[2]
    elif len(parts) == 2:
        if is_survivor:
            extracted_role = parts[1]
        else:
            if any(k in parts[1].lower() for k in ['lynched', 'by mob', 'by sk', 'inactive', 'mod killed', 'suicide', 'tie']):
                death_cause = parts[1]
                extracted_role = None
            else:
                extracted_role = parts[1]
    elif len(parts) == 1:
        if is_survivor:
            extracted_role = parts[0]
        else:
            death_cause = parts[0]

    if extracted_role and extracted_role.lower() in ['true', 'false', 'result', '']:
        extracted_role = None

    if not extracted_role:
        if faction == 'Town':
            extracted_role = 'Town Power' if is_power else 'Plain Town'
        elif faction == 'Mob':
            extracted_role = 'Mob Power' if is_power else 'Plain Mob'
        elif faction == 'SK':
            extracted_role = 'Serial Killer'
        else:
            extracted_role = faction or 'Vanilla'

    return is_dead, is_survivor, extracted_role, death_cause

def parse_game_data(gid, config_info, player_rows, headers):
    roster = []
    lynch_votes = []
    
    for r in player_rows:
        pname = r[3].strip()
        status = r[4].strip()
        faction = r[5].strip()
        fact_status = r[6].strip()
        is_power = (r[7].strip().upper() == 'TRUE')
        death_type = r[8].strip()
        phases_lasted = int(r[9]) if r[9].isdigit() else 0
        surv_depth = r[10].strip()
        vote_acc = r[11].strip()
        
        survived = (status.lower() == 'alive')
        is_winner = (fact_status.lower() == 'win')
        
        extracted_role = None
        death_phase = None
        death_cause = death_type if death_type else None
        
        for c in range(12, len(r)):
            if c >= len(headers):
                break
            col_name = headers[c]
            val = r[c].strip()
            if not val:
                continue
            
            if col_name.endswith('.0 Vote'):
                d_num = col_name.split('.')[0]
                lynch_votes.append({
                    "phase": f"Day {d_num}",
                    "voter_name": pname,
                    "target_name": val
                })
            
            if col_name.startswith('Night') or col_name.startswith('Day'):
                is_dead, is_survivor, cell_role, cell_cause = parse_phase_outcome_cell(val, faction, is_power)
                if is_dead:
                    death_phase = col_name
                    if cell_role and not extracted_role:
                        extracted_role = cell_role
                    if cell_cause and not death_cause:
                        death_cause = cell_cause
                elif is_survivor and cell_role and not extracted_role:
                    extracted_role = cell_role
        
        if not extracted_role:
            if faction == 'Town':
                extracted_role = 'Town Power' if is_power else 'Plain Town'
            elif faction == 'Mob':
                extracted_role = 'Mob Power' if is_power else 'Plain Mob'
            elif faction == 'SK':
                extracted_role = 'Serial Killer'
            else:
                extracted_role = faction or 'Vanilla'
                
        alignment = 'Town' if faction == 'Town' else ('Mafia' if faction == 'Mob' else faction)
        if not death_cause and not survived:
            death_cause = death_type or 'Eliminated'
            
        roster.append({
            "player": pname,
            "role": extracted_role,
            "alignment": alignment,
            "survived": survived,
            "is_winner": is_winner,
            "death_phase": death_phase,
            "death_cause": death_cause if not survived else None,
            "phases_lasted": phases_lasted,
            "survival_depth": surv_depth,
            "vote_accuracy": vote_acc
        })
        
    roster.sort(key=lambda x: (not x['survived'], x['player']))
    
    phases_found = set()
    for p in roster:
        if p.get('death_phase'):
            phases_found.add(p['death_phase'])
            
    def phase_sort_key(ph):
        nums = re.findall(r'\d+', ph)
        num = int(nums[0]) if nums else 0
        is_day = 'day' in ph.lower()
        return (num, 1 if is_day else 0)
        
    timeline = []
    for ph in sorted(list(phases_found), key=phase_sort_key):
        ph_deaths = [p for p in roster if p.get('death_phase') == ph]
        events = []
        eliminated = []
        for d in ph_deaths:
            cause = d.get('death_cause') or 'Eliminated'
            events.append({
                "phase": ph,
                "event": "Elimination",
                "target": d['player'],
                "role": d['role'],
                "alignment": d['alignment'],
                "details": f"{d['player']} ({d['role']}) died ({cause})"
            })
            eliminated.append({
                "player": d['player'],
                "role": d['role'],
                "alignment": d['alignment'],
                "cause": cause
            })
        timeline.append({
            "phase": ph,
            "type": "day" if "day" in ph.lower() else "night",
            "scene": f"Events of {ph}",
            "events": events,
            "eliminated": eliminated
        })
        
    total_phases = config_info.get('total_phases') or (len(timeline) if timeline else 1)
    win_faction = config_info.get('winning_faction', 'Town')
    title_str = MANUAL_THEMES.get(gid, f"Discord Manual Mafia {gid}")
    
    game_dict = {
        "thread_id": f"manual-{gid}",
        "era": "Discord_Manual",
        "title": title_str,
        "start_date": config_info.get('date_started', ''),
        "moderator": config_info.get('writer', 'Host'),
        "game_type": "classic",
        "total_posts": 0,
        "winning_faction": win_faction,
        "summary_file": f"stories/manual-{gid}_summary.md",
        "story_file": f"stories/manual-{gid}_story.md",
        "box_score": {
            "winning_faction": win_faction,
            "game_type": "classic",
            "roster": roster,
            "timeline": timeline,
            "notable_moments": [
                f"{win_faction} achieved victory after {total_phases} phases.",
                f"{sum(1 for p in roster if p['survived'])} players survived to the end."
            ]
        },
        "lynch_vote_history": lynch_votes
    }
    return game_dict

def generate_markdown_story(game):
    gid = game['thread_id'].replace("manual-", "")
    box = game['box_score']
    roster = box.get('roster', [])
    win_faction = game['winning_faction']
    mod = game['moderator']
    timeline = box.get('timeline', [])
    title = game.get('title', f"Discord Manual Mafia {gid}")
    
    survivors = [p['player'] for p in roster if p['survived']]
    
    summary_md = f"""# {title} Summary

**Era:** Discord Manual  
**Host / Game Master:** {mod}  
**Winning Faction:** **{win_faction}**  
**Total Players:** {len(roster)}  
**Survivors ({len(survivors)}):** {', '.join(survivors) if survivors else 'None'}  

---

## 📋 Full Game Roster & Box Score

| Player | Role | Alignment | Status | Death Phase | Death Cause | Phases Lasted | Survival Depth | Vote Accuracy |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""
    for p in roster:
        stat_badge = "🏆 Won" if p['is_winner'] else "❌ Lost"
        surv_badge = "✅ Survived" if p['survived'] else f"💀 {p.get('death_phase', 'Dead')}"
        cause_str = p.get('death_cause') or ("—" if p['survived'] else "Eliminated")
        summary_md += f"| **{p['player']}** | {p['role']} | {p['alignment']} | {surv_badge} ({stat_badge}) | {p.get('death_phase') or '—'} | {cause_str} | {p.get('phases_lasted', '—')} | {p.get('survival_depth', '—')} | {p.get('vote_accuracy', '—')} |\n"

    summary_md += f"""
---

## 📜 Phase Timeline & Eliminations

"""
    if timeline:
        for t in timeline:
            summary_md += f"### {t['phase']}\n"
            if t.get('eliminated'):
                for e in t['eliminated']:
                    summary_md += f"- **Elimination**: **{e['player']}** ({e['role']}, *{e['alignment']}*) — *{e.get('cause', 'Eliminated')}*\n"
            else:
                summary_md += "- No deaths occurred this phase.\n"
            summary_md += "\n"
    else:
        summary_md += "Phase timeline reconstructed from roster records.\n"

    summary_md += f"""---
*Game concluded with a **{win_faction}** victory orchestrated under host {mod}.*
"""

    story_md = f"""# The Chronicle of {title}

*Recorded by Game Master {mod}*

---

### Prologue: The Assembly
In the historic manual era of the Discord Mafia community, **{len(roster)}** players entered the fray for Game {gid}. Factions formed in the shadows, alliances were forged in whisper channels, and the town prepared for what would become an intense tactical conflict.

### The Conflict
"""
    if timeline:
        for t in timeline:
            story_md += f"#### {t['phase']}\n"
            if t.get('eliminated'):
                for e in t['eliminated']:
                    story_md += f"The tension reached a breaking point as **{e['player']}**, who stood as **{e['role']}** for the **{e['alignment']}**, fell ({e.get('cause', 'eliminated')}).\n"
            else:
                story_md += "The town debated fervently, yet none fell in the clash this cycle.\n"
            story_md += "\n"
    else:
        story_md += f"Across consecutive day and night cycles, players cast crucial votes and made fateful nighttime decisions.\n"

    story_md += f"""
### Epilogue: Final Resolution
When the dust cleared, **{win_faction}** stood triumphant! 

Among the brave who lived to tell the tale:
{chr(10).join(f"- **{s}**" for s in survivors) if survivors else "- No survivors remained."}

The record of {title} is thus etched into the permanent chronicle.
"""

    return summary_md, story_md

def main():
    logger.info("Connecting to Google Sheets...")
    client = get_sheets_client()
    sheet = client.open_by_key(SOURCE_SHEET_ID)
    
    config_ws = sheet.worksheet("Config")
    config_rows = config_ws.get_all_values()
    config_by_id = {}
    for r in config_rows[1:]:
        if len(r) > 1 and r[1]:
            gid_clean = str(r[1]).strip()
            d_str = r[6] if len(r) > 6 else ''
            norm_date = ''
            if d_str:
                m_slash = re.search(r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})', d_str)
                if m_slash:
                    norm_date = f"{int(m_slash.group(3)):04d}-{int(m_slash.group(2)):02d}-{int(m_slash.group(1)):02d}"
                else:
                    norm_date = d_str
            config_by_id[gid_clean] = {
                'era': r[0] if len(r) > 0 else '',
                'game_id': gid_clean,
                'players': r[2] if len(r) > 2 else '',
                'date_started': norm_date,
                'status': r[8] if len(r) > 8 else '',
                'winning_faction': r[10] if len(r) > 10 else '',
                'writer': r[11] if len(r) > 11 else '',
                'total_phases': r[12] if len(r) > 12 else ''
            }
            
    pbp_ws = sheet.worksheet("Phase by Phase")
    headers = pbp_ws.row_values(1)
    all_pbp = pbp_ws.get_all_values()
    logger.info(f"Loaded {len(all_pbp)} rows from Phase by Phase ({len(headers)} columns).")
    
    cache_path = os.path.join(WEBSITE_DIR, "data", "phase_by_phase_source.json")
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump({"headers": headers, "rows": all_pbp}, f, ensure_ascii=False)
    logger.info(f"Cached Phase by Phase source data to {cache_path}")
    
    rows_by_gid = {}
    for r in all_pbp[1:]:
        if r and r[0]:
            gid = str(r[0]).strip()
            if gid not in rows_by_gid:
                rows_by_gid[gid] = []
            rows_by_gid[gid].append(r)
            
    manual_gids = [
        "998", "999", "1001", "1002", "1003", "1004", "1005", "1006", "1007", "1008",
        "1009", "1010", "1011", "1012", "1013", "1014", "1015", "1016", "1017", "1018",
        "1019", "1020", "1021", "1022", "1023", "1024", "1025", "1026", "1027"
    ]
    
    discord_manual_games = []
    os.makedirs(STORIES_DIR, exist_ok=True)
    
    for gid in manual_gids:
        if gid not in rows_by_gid:
            logger.warning(f"Manual Game {gid} not found in Phase by Phase rows!")
            continue
        grows = rows_by_gid[gid]
        player_rows = [r for r in grows if r[3] != 'Result']
        cfg = config_by_id.get(gid, {})
        
        parsed = parse_game_data(gid, cfg, player_rows, headers)
        discord_manual_games.append(parsed)
        
        summary_md, story_md = generate_markdown_story(parsed)
        with open(os.path.join(STORIES_DIR, f"manual-{gid}_summary.md"), 'w', encoding='utf-8') as f:
            f.write(summary_md)
        with open(os.path.join(STORIES_DIR, f"manual-{gid}_story.md"), 'w', encoding='utf-8') as f:
            f.write(story_md)
            
    out_manual_db = os.path.join(DB_DIR, "discord_manual.json")
    with open(out_manual_db, 'w', encoding='utf-8') as f:
        json.dump(discord_manual_games, f, indent=2, ensure_ascii=False)
    logger.info(f"✅ Successfully wrote {len(discord_manual_games)} manual Discord games to {out_manual_db}")
    
    discourse_db_path = os.path.join(DB_DIR, "historic_discourse.json")
    with open(discourse_db_path, 'r', encoding='utf-8') as f:
        discourse_games = json.load(f)
        
    discourse_by_tid = {str(g.get("thread_id")): g for g in discourse_games}
    enriched_count = 0
    
    for gid_num, tid in DISCOURSE_ID_MAP.items():
        if gid_num not in rows_by_gid:
            continue
        if tid not in discourse_by_tid:
            logger.warning(f"Discourse thread ID {tid} for game {gid_num} not found in historic_discourse.json!")
            continue
            
        target_game = discourse_by_tid[tid]
        grows = rows_by_gid[gid_num]
        player_rows = [r for r in grows if r[3] != 'Result']
        cfg = config_by_id.get(gid_num, {})
        
        parsed_game = parse_game_data(gid_num, cfg, player_rows, headers)
        
        target_game["winning_faction"] = parsed_game["winning_faction"]
        if cfg.get("writer"):
            target_game["moderator"] = cfg["writer"]
            
        box = target_game.setdefault("box_score", {})
        box["winning_faction"] = parsed_game["winning_faction"]
        box["roster"] = parsed_game["box_score"]["roster"]
        box["timeline"] = parsed_game["box_score"]["timeline"]
        
        if parsed_game.get("lynch_vote_history"):
            target_game["lynch_vote_history"] = parsed_game["lynch_vote_history"]
            
        enriched_count += 1
        logger.info(f"Enriched Discourse Game {gid_num} (Thread {tid}): roster expanded to {len(box['roster'])} players.")
        
    with open(discourse_db_path, 'w', encoding='utf-8') as f:
        json.dump(discourse_games, f, indent=2, ensure_ascii=False)
    logger.info(f"✅ Successfully enriched {enriched_count} Discourse games in {discourse_db_path}")

if __name__ == "__main__":
    main()
