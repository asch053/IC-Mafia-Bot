# cogs/exportcogs/sheets_client.py
import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import config

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def get_sheets_client():
    """Initializes Google Sheets client credentials and connection."""
    scope = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    try:
        creds_file = getattr(config, 'GOOGLE_CREDENTIALS_FILE', 'credentials.json')
        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_file, scope)
        client = gspread.authorize(creds)
        logger.info("Successfully authenticated with Google Sheets API.")
        return creds, client
    except Exception as e:
        logger.error(f"Failed to authenticate with Google Sheets: {e}")
        return None, None


def connect_to_sheet(creds, client):
    """Helper to reconnect/get the sheet object safely."""
    try:
        if creds and getattr(creds, 'access_token_expired', False):
            client.login()

        sheet = None
        if hasattr(config, 'GOOGLE_SHEET_ID'):
            try:
                sheet = client.open_by_key(config.GOOGLE_SHEET_ID)
                logger.info(f"✅ Connected by ID. Target Sheet: '{sheet.title}'")
            except gspread.SpreadsheetNotFound:
                logger.error(f"❌ Config has GOOGLE_SHEET_ID ({config.GOOGLE_SHEET_ID}) but sheet was not found.")
                raise
        else:
            logger.warning("⚠️ GOOGLE_SHEET_ID not found in config. Falling back to Name search.")
            sheet = client.open("IC Mafia Bot Results")
            logger.info(f"✅ Connected by Name. Target Sheet: '{sheet.title}'")

        return sheet
    except Exception as e:
        logger.error(f"Could not connect to Google Sheet: {e}")
        raise e


RULES_SHEET_HEADERS = [
    "Game_ID",
    "Scheduled_At_UTC",
    "Scheduled_By",
    "Game_Type",
    "Story_Type",
    "Start_Time_UTC",
    "Phase_Hours",
    "Mafia_Ratio",
    "Town_Cop_Req",
    "Town_Doctor_Req",
    "Town_RB_Req",
    "Mafia_RB_Req",
    "SK_Player_Count",
    "GF_Investigatable",
    "SK_Investigatable",
    "GF_Night_Immune",
    "SK_Night_Immune",
    "BR_Skip_Day"
]


def log_game_setup_to_sheets_sync(setup_data: dict) -> bool:
    """
    Synchronously appends or updates a game's rule setup to the Rules Setup tab on Google Sheets.
    Creates the tab and headers if not present.
    """
    creds, client = get_sheets_client()
    if not client:
        logger.warning("Could not log game setup to Google Sheets: Client authentication failed.")
        return False

    try:
        sheet = connect_to_sheet(creds, client)
        tab_name = getattr(config, 'GOOGLE_SHEET_RULES_TAB', 'Rules Setup')

        try:
            ws = sheet.worksheet(tab_name)
        except gspread.WorksheetNotFound:
            logger.info(f"Worksheet '{tab_name}' not found. Creating worksheet...")
            ws = sheet.add_worksheet(title=tab_name, rows=100, cols=len(RULES_SHEET_HEADERS))
            ws.append_row(RULES_SHEET_HEADERS)

        existing_values = ws.get_all_values()
        if not existing_values:
            ws.append_row(RULES_SHEET_HEADERS)
            existing_values = [RULES_SHEET_HEADERS]
        elif not any(existing_values[0]) or len(existing_values[0]) < len(RULES_SHEET_HEADERS):
            ws.update(range_name='A1', values=[RULES_SHEET_HEADERS])

        def format_choice(val):
            if isinstance(val, bool):
                return "Yes" if val else "No"
            if isinstance(val, str):
                return "Yes" if val.lower() in ("yes", "true", "1") else "No"
            return "No"

        def format_dt(val):
            if hasattr(val, 'isoformat'):
                return val.isoformat()
            return str(val) if val else ""

        game_id = str(setup_data.get("game_id", ""))
        row = [
            game_id,
            format_dt(setup_data.get("scheduled_at_utc", "")),
            str(setup_data.get("scheduled_by", "")),
            str(setup_data.get("game_type", "")),
            str(setup_data.get("story_type", "")),
            format_dt(setup_data.get("start_time_utc", "")),
            setup_data.get("phase_hours", ""),
            setup_data.get("mafia_ratio", ""),
            setup_data.get("town_cop_req", ""),
            setup_data.get("town_doctor_req", ""),
            setup_data.get("town_rb_req", ""),
            setup_data.get("mafia_rb_req", ""),
            setup_data.get("sk_player_count", ""),
            format_choice(setup_data.get("gf_investigate", False)),
            format_choice(setup_data.get("sk_investigate", False)),
            format_choice(setup_data.get("gf_night_immune", True)),
            format_choice(setup_data.get("sk_night_immune", True)),
            format_choice(setup_data.get("br_skip_day", False))
        ]

        # Check if game_id already exists in tab (to update instead of duplicate)
        existing_row_index = None
        for idx, r in enumerate(existing_values[1:], start=2):
            if r and r[0] == game_id:
                existing_row_index = idx
                break

        if existing_row_index:
            cell_range = f"A{existing_row_index}:{chr(ord('A') + len(RULES_SHEET_HEADERS) - 1)}{existing_row_index}"
            ws.update(range_name=cell_range, values=[row])
            logger.info(f"Updated existing game rules setup for Game ID '{game_id}' in Google Sheet tab '{tab_name}'.")
        else:
            ws.append_row(row)
            logger.info(f"Appended new game rules setup for Game ID '{game_id}' to Google Sheet tab '{tab_name}'.")

        return True
    except Exception as e:
        logger.error(f"Failed to log game setup to Google Sheets: {e}", exc_info=True)
        return False


async def log_game_setup_to_sheets(setup_data: dict) -> bool:
    """
    Asynchronously logs the game's rules setup to Google Sheets in an executor.
    """
    import asyncio
    return await asyncio.to_thread(log_game_setup_to_sheets_sync, setup_data)


