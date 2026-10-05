"""
scripts/sync_google_sheets.py
Syncs all Mafia game data (Historic Forum, Historic Discourse, Discord Bot, Discord Manual),
along with unified Games, Players, and Analytics (PEU skill metrics) into Google Sheets.
"""
import os
import sys
import json
import logging
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SheetsSync")

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "data")
DB_DIR = os.path.join(DATA_DIR, "database")
WEBSITE_DATA_DIR = os.path.join(ROOT_DIR, "Website", "data")

try:
    from oauth2client.service_account import ServiceAccountCredentials
    import gspread
except ImportError:
    logger.error("Required packages (gspread, oauth2client) not found. Run in the virtual environment (.venv).")
    gspread = None

DEFAULT_CREDS_FILE = os.path.join(DATA_DIR, "ic-mafia-bot-41a41f61e757.json")
DEFAULT_SHEET_ID = "1MCFL0Q0bgBdb8JUP-n1fo0EHLw3imdj_SKzjfqheslM"

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
        
    ws.clear()
    payload = [headers] + rows
    ws.update(range_name='A1', values=payload)
    logger.info(f"✅ Synced tab '{title}' ({len(rows)} rows, {len(headers)} cols)")

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
        "Game_ID", "Era", "Title", "Moderator", "Game_Type", "Winning_Faction", 
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
        "Game_ID", "Era", "Title", "Moderator", "Game_Type", "Winning_Faction", 
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
    for g in all_games:
        gid = str(g.get("thread_id", ""))
        era = str(g.get("era", "Unknown"))
        box = g.get("box_score") or {}
        roster = box.get("roster") or []
        wf = (box.get("winning_faction") or "").lower()
        for p in roster:
            p_name = p.get("player", "Unknown")
            role = p.get("role", "Unknown")
            align = p.get("alignment", "Unknown")
            survived = bool(p.get("survived", False))
            is_win = p.get("is_winner")
            if is_win is None:
                is_win = (align.lower() == wf) if wf else False
            master_player_rows.append([
                gid,
                era,
                str(p.get("player_id", "")),
                str(p_name),
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
        "Town Wins", "Mafia Wins", "Neutral/SK Wins"
    ]
    analytics_rows = []
    for p in leaderboard:
        games_played = int(p.get("Games Played", 0))
        wins = int(p.get("Wins", 0))
        losses = int(p.get("Losses", 0))
        win_rate = round((wins / games_played * 100), 1) if games_played > 0 else 0.0
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
            int(p.get("Neutral/SK Wins", 0))
        ])
    analytics_rows.sort(key=lambda r: (r[1], r[5]), reverse=True)
    sync_worksheet(sheet, "Analytics", analytics_headers, analytics_rows)

    logger.info("🎉 Multi-era Google Sheets sync successfully completed!")

if __name__ == "__main__":
    sync_all_to_sheets()
