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

