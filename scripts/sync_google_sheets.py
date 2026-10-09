"""
scripts/sync_google_sheets.py
Syncs all Mafia game data (Historic Forum, Historic Discourse, Discord Bot, Discord Manual),
along with unified Games, Players, and Analytics (PEU skill metrics) into Google Sheets.
"""
import os
import sys
import json
import re
import logging
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SheetsSync")

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "data")
WEBSITE_DIR = os.path.join(ROOT_DIR, "Website")
DB_DIR = os.path.join(WEBSITE_DIR, "database")
if not os.path.exists(DB_DIR):
    DB_DIR = os.path.join(DATA_DIR, "database")
WEBSITE_DATA_DIR = os.path.join(WEBSITE_DIR, "data")

try:
    from oauth2client.service_account import ServiceAccountCredentials
    import gspread
except ImportError:
    logger.error("Required packages (gspread, oauth2client) not found. Run in the virtual environment (.venv).")
    gspread = None

DEFAULT_CREDS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE") or os.path.join(DATA_DIR, "ic-mafia-bot-41a41f61e757.json")
DEFAULT_SHEET_ID = os.getenv("GOOGLE_SHEET_ID") or "1MCFL0Q0bgBdb8JUP-n1fo0EHLw3imdj_SKzjfqheslM"

def get_sheets_client(creds_path=DEFAULT_CREDS_FILE):
    if not os.path.exists(creds_path):
        raise FileNotFoundError(f"Credentials file not found at {creds_path}")
    scope = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
    client = gspread.authorize(creds)
    return client

def load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def sync_worksheet(sheet, title, headers, rows):
    """Safely updates or creates a worksheet, resizing if necessary."""
    try:
        ws = sheet.worksheet(title)
    except gspread.WorksheetNotFound:
        logger.info(f"Creating new worksheet '{title}'...")
        ws = sheet.add_worksheet(title=title, rows=max(100, len(rows) + 50), cols=max(15, len(headers) + 2))
    
    total_needed_rows = len(rows) + 5  # Include header and safety buffer
    if ws.row_count < total_needed_rows:
        rows_to_add = total_needed_rows - ws.row_count + 50
        logger.info(f"Resizing worksheet '{title}': adding {rows_to_add} rows...")
        ws.add_rows(rows_to_add)
        
    if ws.col_count < len(headers):
        cols_to_add = len(headers) - ws.col_count + 5
        logger.info(f"Resizing worksheet '{title}': adding {cols_to_add} columns...")
        ws.add_cols(cols_to_add)

    ws.clear()
    payload = [headers] + rows
    ws.update(range_name='A1', values=payload)
    logger.info(f"✅ Synced tab '{title}' ({len(rows)} rows, {len(headers)} cols)")

POWER_ROLE_KEYWORDS = {
    "cop", "doctor", "doc", "detective", "vigilante", "vig", "godfather",
    "tracker", "watcher", "hooker", "roleblocker", "rb", "assassin",
    "investigator", "mason", "jailer", "bodyguard", "leader"
}

def is_power_role(role_name):
    if not role_name:
        return "FALSE"
    rn = role_name.lower()
    if any(k in rn for k in POWER_ROLE_KEYWORDS):
        return "TRUE"
    return "FALSE"

DISC_55_65_TITLES = {
    "55": "IC Mafia 2.1 - The return",
    "56": "IC Mafia 56: Fire and Blood",
    "57": "IC Mafia 57 : Avenging the EndGame",
    "58": "Mafia 58 New Sanguine",
    "59": "IC Mafia 59: The uprising",
    "60": "IC Mafia 60: Welcome to the Wild West",
    "61": "IC Mafia 61: The Testament of the Watchers",
    "62": "IC Mafia 62: Can I see your ticket?",
    "63": "IC Mafia 63: Bad Romans",
    "64": "IC Mafia: Capricorn Round 1: Moderators vs. IC Players",
    "65": "IC Mafia 65- NYC remastered"
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

DISC_55_65_DATES = {
    "55": "2019-04-30",
    "56": "2019-05-19",
    "57": "2019-05-30",
    "58": "2019-06-08",
    "59": "2019-06-20",
    "60": "2019-06-30",
    "61": "2019-07-08",
    "62": "2019-07-17",
    "63": "2019-07-25",
    "64": "2019-08-03",
    "65": "2019-08-11"
}

MANUAL_START_DATES = {
    "998": "2019-08-04",
    "999": "2019-08-11",
    "1001": "2019-08-18",
    "1002": "2019-08-25",
    "1003": "2019-09-01",
    "1004": "2019-09-08",
    "1005": "2019-09-15",
    "1006": "2019-09-22",
    "1007": "2019-09-29",
    "1008": "2019-10-06",
    "1009": "2019-10-13",
    "1010": "2019-10-20",
    "1011": "2019-10-27",
    "1012": "2019-11-03",
    "1013": "2019-11-10",
    "1014": "2019-11-17",
    "1015": "2019-11-24",
    "1016": "2019-12-01",
    "1017": "2019-12-08",
    "1018": "2019-12-15",
    "1019": "2019-12-22",
    "1020": "2019-12-29",
    "1021": "2020-01-05",
    "1022": "2020-01-12",
    "1023": "2020-01-19",
    "1024": "2020-01-26",
    "1025": "2020-02-02",
    "1026": "2020-02-09",
    "1027": "2020-02-16"
}

def get_useful_name(gid):
    gid_clean = str(gid).strip()
    if gid_clean in DISC_55_65_TITLES:
        return DISC_55_65_TITLES[gid_clean]
    if gid_clean in MANUAL_THEMES:
        return MANUAL_THEMES[gid_clean]
    return f"Mafia Game {gid_clean}"

def get_start_date(gid):
    gid_clean = str(gid).strip().replace("manual-", "")
    if gid_clean in DISC_55_65_DATES:
        return DISC_55_65_DATES[gid_clean]
    if gid_clean in MANUAL_START_DATES:
        return MANUAL_START_DATES[gid_clean]
    return ""

def generate_pbp_rows_for_games(games_list, headers, header_col_map):
    generated_rows = []
    
    for g in games_list:
        gid = str(g.get("thread_id", ""))
        gname = str(g.get("title") or f"Mafia Game {gid}")
        gdate = str(g.get("start_date") or get_start_date(gid))
        box = g.get("box_score", {})
        roster = box.get("roster", [])
        if not roster:
            continue
            
        wf = str(box.get("winning_faction") or g.get("winning_faction") or "Town")
        timeline = box.get("timeline", [])
        votes = g.get("lynch_vote_history", [])
        
        tl_death_map = {}
        for ev in timeline:
            tgt = ev.get("target")
            ev_type = ev.get("event", "")
            ph = ev.get("phase", "")
            det = ev.get("details", "")
            if tgt and (ev_type in ["Kill", "Lynch", "Elimination"] or "killed" in det.lower() or "lynch" in det.lower()):
                tl_death_map[tgt.lower()] = (ph, ev_type, det)
                
        max_day = 1
        for p in roster:
            dp = str(p.get("death_phase") or "").lower()
            m = re.findall(r'\d+', dp)
            if m: max_day = max(max_day, int(m[0]))
        for ev in timeline:
            ph = str(ev.get("phase") or "").lower()
            m = re.findall(r'\d+', ph)
            if m: max_day = max(max_day, int(m[0]))
        for v in votes:
            vp = str(v.get("phase") or "").lower()
            m = re.findall(r'\d+', vp)
            if m: max_day = max(max_day, int(m[0]))
            
        max_day = min(11, max(1, max_day))
        total_phases = max_day * 2
        
        res_row = [""] * len(headers)
        res_row[0] = gid
        res_row[1] = gname
        res_row[2] = gdate
        res_row[3] = str(total_phases)
        res_row[4] = "Completed"
        res_row[5] = "Result"
        for d in range(1, max_day + 1):
            n_col = f"Night {d}"
            d_col = f"Day {d}"
            if n_col in header_col_map: res_row[header_col_map[n_col]] = "Death"
            if d_col in header_col_map: res_row[header_col_map[d_col]] = "Death"
        generated_rows.append(res_row)
        
        player_votes = {}
        for v in votes:
            voter = str(v.get("voter_name") or "")
            target = str(v.get("target_name") or "")
            ph = str(v.get("phase") or "")
            m = re.findall(r'\d+', ph)
            if m and voter:
                d_num = int(m[0])
                if voter not in player_votes: player_votes[voter] = {}
                player_votes[voter][d_num] = target
                
        eliminated_by_day = {}
        for p in roster:
            dp = str(p.get("death_phase") or "")
            if 'day' in dp.lower():
                m = re.findall(r'\d+', dp)
                if m: eliminated_by_day[int(m[0])] = p.get("player")
                
        for p in roster:
            pname = p.get("player", "Unknown")
            survived = bool(p.get("survived", False))
            role = p.get("role") or "Townie"
            if role in ["N/A", "Unknown", None]:
                role = "Townie" if "town" in str(p.get("alignment")).lower() else "Mob"
                
            align = str(p.get("alignment") or "Town")
            align_lower = align.lower()
            
            if "town" in align_lower:
                fact = "Town"
            elif any(x in align_lower for x in ["mafia", "mob"]):
                fact = "Mob"
            elif any(x in align_lower for x in ["sk", "serial"]):
                fact = "SK"
            else:
                fact = "Neutral"
                
            wf_lower = wf.lower()
            if "draw" in wf_lower:
                fact_status = "Draw"
            elif (fact == "Town" and "town" in wf_lower) or (fact == "Mob" and any(x in wf_lower for x in ["mob", "mafia"])) or (fact == "SK" and "sk" in wf_lower):
                fact_status = "Win"
            else:
                fact_status = "Loss"
                
            dp = str(p.get("death_phase") or "")
            dc = str(p.get("death_cause") or "")
            if not dp or dp.upper() in ["N/A", "NONE"]:
                if pname.lower() in tl_death_map:
                    dp, tl_ev, tl_det = tl_death_map[pname.lower()]
                    if not dc: dc = tl_det or tl_ev
            
            if survived or dp.upper() in ["N/A", "NONE"]:
                survived = True
                lasted = total_phases
                surv_depth = 100.0
                dtype = ""
            else:
                m = re.findall(r'\d+', dp)
                d_num = min(11, int(m[0]) if m else 1)
                if 'night' in dp.lower():
                    lasted = max(0, (d_num * 2) - 1)
                else:
                    lasted = max(1, d_num * 2)
                surv_depth = round((lasted / total_phases) * 100.0, 2) if total_phases > 0 else 0.0
                
                dc_lower = dc.lower()
                if "lynch" in dc_lower or "day" in dp.lower():
                    dtype = "Lynched"
                elif "sk" in dc_lower or "serial" in dc_lower:
                    dtype = "by SK"
                elif "mob" in dc_lower or "mafia" in dc_lower:
                    dtype = "by Mob"
                else:
                    dtype = "by Mob" if "night" in dp.lower() else "Lynched"
                    
            p_v = player_votes.get(pname, {})
            if p_v:
                correct_votes = sum(1 for d_idx, tgt in p_v.items() if d_idx in eliminated_by_day and eliminated_by_day[d_idx] == tgt)
                vote_acc = f"{(correct_votes / len(p_v) * 100.0):.2f}%"
            else:
                vote_acc = ""
                
            prow = [""] * len(headers)
            prow[0] = gid
            prow[1] = gname
            prow[2] = gdate
            prow[3] = str(total_phases)
            prow[4] = "Completed"
            prow[5] = pname
            prow[6] = "Alive" if survived else "Dead"
            prow[7] = fact
            prow[8] = fact_status
            prow[9] = is_power_role(role)
            prow[10] = dtype
            prow[11] = str(lasted)
            prow[12] = f"{surv_depth:.2f}%"
            prow[13] = vote_acc
            
            for d_idx, tgt in p_v.items():
                if d_idx <= 11:
                    v_col = f"{d_idx}.0 Vote"
                    if v_col in header_col_map:
                        prow[header_col_map[v_col]] = tgt
                        
            if not survived and dp:
                m = re.findall(r'\d+', dp)
                d_num = min(11, int(m[0]) if m else 1)
                target_col = f"Night {d_num}" if 'night' in dp.lower() else f"Day {d_num}"
                if target_col in header_col_map:
                    prow[header_col_map[target_col]] = f"Killed - {role} - {dtype}"
            elif survived:
                last_day_col = f"Day {max_day}"
                if last_day_col in header_col_map:
                    prow[header_col_map[last_day_col]] = f"Winner - {role}" if fact_status == "Win" else f"Alive - {role}"
                    
            generated_rows.append(prow)
            
    return generated_rows

def build_phase_by_phase_dataset():
    """
    Builds the complete 97-column Phase by Phase table across all eras,
    including the 'Game Name' column for thread titles & thematic bot names:
    1. Forum Era Games (historic_forum.json)
    2. Discourse Era Games (55-65 from source sheet, 65+ from historic_discourse.json)
    3. Discord Manual Games (998-1027 from source sheet)
    4. Discord Bot Games (discord_bot.json)
    """
    cache_path = os.path.join(WEBSITE_DATA_DIR, "phase_by_phase_source.json")
    if not os.path.exists(cache_path):
        cache_path = os.path.join(WEBSITE_DIR, "data", "phase_by_phase_source.json")
        
    headers = []
    raw_source_rows = []
    
    if os.path.exists(cache_path):
        with open(cache_path, 'r', encoding='utf-8') as f:
            src = json.load(f)
            old_headers = src.get("headers", [])
            headers = [old_headers[0], "Game Name", "Start Date"] + old_headers[1:]
            raw_rows = src.get("rows", [])
            raw_source_rows = raw_rows[1:] if len(raw_rows) > 1 else []
            
    if not headers:
        logger.warning("No Phase by Phase source headers found; skipping Phase_By_Phase sync.")
        return None, None
        
    header_col_map = {h: i for i, h in enumerate(headers)}
    
    # 1. Forum Era Games
    forum_games = load_json(os.path.join(DB_DIR, "historic_forum.json"), [])
    forum_rows = generate_pbp_rows_for_games(forum_games, headers, header_col_map)
    
    # 2. Discourse Era Games: 55-65 from sheet, 65+ generated
    disc_55_65_ids = {'55', '56', '57', '58', '59', '60', '61', '62', '63', '64', '65'}
    disc_source_rows = []
    for r in raw_source_rows:
        if r and r[0] in disc_55_65_ids:
            disc_source_rows.append([r[0], get_useful_name(r[0]), get_start_date(r[0])] + r[1:])
    
    disc_games = load_json(os.path.join(DB_DIR, "historic_discourse.json"), [])
    disc_55_65_tids = {'6053', '6219', '6347', '6452', '6556', '6631', '6680', '6772', '6825', '6871', '6913'}
    disc_65_plus_games = [g for g in disc_games if str(g.get('thread_id')) not in disc_55_65_tids]
    disc_65_plus_rows = generate_pbp_rows_for_games(disc_65_plus_games, headers, header_col_map)
    
    # 3. Discord Manual Games: 998-1027 from sheet
    manual_source_rows = []
    for r in raw_source_rows:
        if r and r[0] in MANUAL_THEMES:
            manual_source_rows.append([r[0], get_useful_name(r[0]), get_start_date(r[0])] + r[1:])
    
    # 4. Modern Discord Bot Games
    bot_games = load_json(os.path.join(DB_DIR, "discord_bot.json"), [])
    bot_rows = generate_pbp_rows_for_games(bot_games, headers, header_col_map)
    
    all_combined_rows = forum_rows + disc_source_rows + disc_65_plus_rows + manual_source_rows + bot_rows
    logger.info(
        f"Compiled Phase_By_Phase dataset: {len(all_combined_rows)} rows across all eras "
        f"({len(forum_rows)} Forum, {len(disc_source_rows)} Discourse 55-65, {len(disc_65_plus_rows)} Discourse 65+, "
        f"{len(manual_source_rows)} Discord Manual, {len(bot_rows)} Discord Bot)."
    )
    
    # Save local cache
    all_cache_path = os.path.join(WEBSITE_DATA_DIR, "phase_by_phase_all.json")
    with open(all_cache_path, 'w', encoding='utf-8') as f:
        json.dump({"headers": headers, "rows": [headers] + all_combined_rows}, f, ensure_ascii=False)
        
    return headers, all_combined_rows

def sync_all_to_sheets(sheet_id=DEFAULT_SHEET_ID, creds_path=DEFAULT_CREDS_FILE):
    client = get_sheets_client(creds_path)
    sheet = client.open_by_key(sheet_id)
    logger.info(f"Connected to Google Spreadsheet: '{sheet.title}' (ID: {sheet_id})")

    # 1. Load the 4 Modular Databases
    forum_games = load_json(os.path.join(DB_DIR, "historic_forum.json"), [])
    discourse_games = load_json(os.path.join(DB_DIR, "historic_discourse.json"), [])
    discord_bot_games = load_json(os.path.join(DB_DIR, "discord_bot.json"), [])
    discord_manual_games = load_json(os.path.join(DB_DIR, "discord_manual.json"), [])

    # 2. Compile era-specific game rows
    era_headers = [
        "Game_ID", "Era", "Title", "Start_Date", "Moderator", "Game_Type", "Winning_Faction", 
        "Total_Players", "Total_Posts", "MVP_Player", "MVP_Rationale", "Summary_File", "Story_File"
    ]

    def build_era_rows(games_list, default_era):
        rows = []
        for g in games_list:
            box = g.get("box_score") or {}
            mvp = box.get("mvp") or {}
            roster = box.get("roster") or []
            rows.append([
                str(g.get("thread_id", "")),
                str(g.get("era", default_era)),
                str(g.get("title", "")),
                str(g.get("start_date", "")),
                str(g.get("moderator", "")),
                str(g.get("game_type", "classic")),
                str(box.get("winning_faction", g.get("winning_faction", "Unknown"))),
                len(roster),
                g.get("total_posts", 0) or 0,
                str(mvp.get("player", "") if isinstance(mvp, dict) else ""),
                str(mvp.get("rationale", "") if isinstance(mvp, dict) else ""),
                str(g.get("summary_file", "")),
                str(g.get("story_file", ""))
            ])
        return rows

    forum_rows = build_era_rows(forum_games, "Forum")
    discourse_rows = build_era_rows(discourse_games, "Discourse")
    bot_rows = build_era_rows(discord_bot_games, "Discord")
    manual_rows = build_era_rows(discord_manual_games, "Discord_Manual")

    # Sync Modular Database Tabs
    sync_worksheet(sheet, "Forum_Historic", era_headers, forum_rows)
    sync_worksheet(sheet, "Discourse_Historic", era_headers, discourse_rows)
    sync_worksheet(sheet, "Discord_Bot", era_headers, bot_rows)
    sync_worksheet(sheet, "Discord_Manual", era_headers, manual_rows)

    # 3. Master Games Tab
    all_games = forum_games + discourse_games + discord_bot_games + discord_manual_games
    master_game_headers = [
        "Game_ID", "Era", "Title", "Start_Date", "Moderator", "Game_Type", "Winning_Faction", 
        "Total_Players", "Total_Posts", "MVP_Player", "Summary_File", "Story_File"
    ]
    master_game_rows = []
    for g in all_games:
        box = g.get("box_score") or {}
        mvp = box.get("mvp") or {}
        roster = box.get("roster") or []
        master_game_rows.append([
            str(g.get("thread_id", "")),
            str(g.get("era", "Unknown")),
            str(g.get("title", "")),
            str(g.get("start_date", "")),
            str(g.get("moderator", "")),
            str(g.get("game_type", "classic")),
            str(box.get("winning_faction", g.get("winning_faction", "Unknown"))),
            len(roster),
            g.get("total_posts", 0) or 0,
            str(mvp.get("player", "") if isinstance(mvp, dict) else ""),
            str(g.get("summary_file", "")),
            str(g.get("story_file", ""))
        ])
    sync_worksheet(sheet, "Games", master_game_headers, master_game_rows)

    # 4. Master Players Tab
    master_player_headers = [
        "Game_ID", "Era", "Player_ID", "Player_Name", "Role", "Alignment", 
        "Is_Winner", "Survived", "Death_Phase", "Death_Cause"
    ]
    master_player_rows = []
    user_map = load_json(os.path.join(WEBSITE_DATA_DIR, "master_user_map.json"), {})
    
    try:
        from Website.build_unified_leaderboard import resolve_player_identity
    except ImportError:
        def resolve_player_identity(name, pid, umap):
            return str(pid or f"historic_{name.lower().replace(' ', '_')}"), name

    for g in all_games:
        gid = str(g.get("thread_id", ""))
        era = str(g.get("era", "Unknown"))
        box = g.get("box_score") or {}
        roster = box.get("roster") or []
        wf = (box.get("winning_faction") or "").lower()
        for p in roster:
            raw_name = p.get("player", "Unknown")
            role = p.get("role", "Unknown")
            align = p.get("alignment", "Unknown")
            survived = bool(p.get("survived", False))
            is_win = p.get("is_winner")
            if is_win is None:
                is_win = (align.lower() == wf) if wf else False
            
            canonical_id, canonical_name = resolve_player_identity(raw_name, p.get("player_id"), user_map)
            master_player_rows.append([
                gid,
                era,
                str(canonical_id),
                str(canonical_name),
                str(role),
                str(align),
                "TRUE" if is_win else "FALSE",
                "TRUE" if survived else "FALSE",
                str(p.get("death_phase") or ""),
                str(p.get("death_cause") or "")
            ])
    sync_worksheet(sheet, "Players", master_player_headers, master_player_rows)

    # 5. Master Votes Tab
    master_vote_headers = [
        "Game_ID", "Era", "Phase", "Voter_ID", "Voter_Name", "Target_ID", "Target_Name"
    ]
    master_vote_rows = []
    for g in all_games:
        gid = str(g.get("thread_id", ""))
        era = str(g.get("era", "Unknown"))
        for v in g.get("lynch_vote_history", []):
            master_vote_rows.append([
                gid,
                era,
                str(v.get("phase", "")),
                str(v.get("voter_id", "")),
                str(v.get("voter_name", "")),
                str(v.get("target_id", "")),
                str(v.get("target_name", ""))
            ])
    if master_vote_rows:
        sync_worksheet(sheet, "Votes", master_vote_headers, master_vote_rows)

    # 6. Analytics Tab (Unified PEU scores across all players)
    leaderboard = load_json(os.path.join(WEBSITE_DATA_DIR, "leaderboard.json"), [])
    analytics_headers = [
        "Player Name", "Skill Score", "Persuasion (P)", "Elusiveness (E)", "Understanding (U)",
        "Games Played", "Wins", "Losses", "Win Rate %", "Survival %", 
        "Times Lynched", "D1 Lynches", "Total Night Deaths", "N1 Deaths", 
        "Vote Accuracy %", "Town Games", "Mafia Games", "Neutral/SK Games", "Plain Town Games",
        "Town Wins", "Mafia Wins", "Neutral/SK Wins", "Known Aliases"
    ]
    analytics_rows = []
    for p in leaderboard:
        games_played = int(p.get("Games Played", 0))
        wins = int(p.get("Wins", 0))
        losses = int(p.get("Losses", 0))
        win_rate = round((wins / games_played * 100), 1) if games_played > 0 else 0.0
        aliases_str = ", ".join(p.get("Aliases", []))
        analytics_rows.append([
            str(p.get("Player Name", "")),
            float(p.get("Skill Score", 0.0)),
            float(p.get("p_score", 0.0)),
            float(p.get("e_score", 0.0)),
            float(p.get("u_score", 0.0)),
            games_played,
            wins,
            losses,
            win_rate,
            float(p.get("Survival %", 0.0)),
            int(p.get("Times Lynched", 0)),
            int(p.get("D1 Lynches", 0)),
            int(p.get("Total Night Deaths", 0)),
            int(p.get("N1 Deaths", 0)),
            float(p.get("Vote Accuracy %", 0.0)),
            int(p.get("Town Games", 0)),
            int(p.get("Mafia Games", 0)),
            int(p.get("Neutral/SK Games", 0)),
            int(p.get("Plain Town Games", 0)),
            int(p.get("Town Wins", 0)),
            int(p.get("Mafia Wins", 0)),
            int(p.get("Neutral/SK Wins", 0)),
            aliases_str
        ])
    analytics_rows.sort(key=lambda r: (r[1], r[5]), reverse=True)
    sync_worksheet(sheet, "Analytics", analytics_headers, analytics_rows)

    # 7. Phase_By_Phase Tab (Universal 96-column ledger across eras)
    pbp_headers, pbp_rows = build_phase_by_phase_dataset()
    if pbp_headers and pbp_rows:
        sync_worksheet(sheet, "Phase_By_Phase", pbp_headers, pbp_rows)

    logger.info("🎉 Multi-era Google Sheets sync successfully completed!")

if __name__ == "__main__":
    sync_all_to_sheets()
