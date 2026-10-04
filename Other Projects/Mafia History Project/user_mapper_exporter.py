import json
import os
import logging
import logging.handlers
import gspread
from datetime import datetime, timedelta, timezone

# --- 1. CONFIGURATION AND SETUP ---

CURRENT_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(os.path.dirname(CURRENT_SCRIPT_DIR))

# Use the Google Service Account
SERVICE_ACCOUNT_KEY_FILE = os.path.join(ROOT_DIR, "data", "ic-mafia-bot-41a41f61e757.json")
if not os.path.exists(SERVICE_ACCOUNT_KEY_FILE):
    SERVICE_ACCOUNT_KEY_FILE = os.path.join(ROOT_DIR, "ic-mafia-bot-41a41f61e757.json")

LOG_DIR = os.path.join(CURRENT_SCRIPT_DIR, "logs")
OUTPUT_DIR = os.path.join(CURRENT_SCRIPT_DIR, "output")

# The specific Google Sheet provided by the user
SPREADSHEET_ID = "1M-qcK4EW_phJ2MWKtzY4DOvTHstZOicyfsT8qH4RJCA"

# Local output file for the parsed mappings
OUTPUT_MAPPING_FILE = os.path.join(OUTPUT_DIR, "master_user_map.json")


# --- 2. LOGGING UTILITY FUNCTION ---

def setup_logging():
    formatter = logging.Formatter(
        '[{asctime}] [{levelname:<8}] {name} - {funcName}:{lineno}: {message}',
        datefmt='%Y-%m-%d %H:%M:%S',
        style='{'
    )
    
    logger = logging.getLogger() 
    logger.setLevel(logging.DEBUG) 
    
    now = datetime.now(timezone(timedelta(hours=12)))
    log_dir = os.path.join(LOG_DIR, now.strftime('%Y-%m-%d'))
    os.makedirs(log_dir, exist_ok=True)
    
    debug_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, f'{now.strftime("%Y-%m-%d")}_mapper_debug.log'),
        maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
    )
    debug_handler.setFormatter(formatter)
    debug_handler.setLevel(logging.DEBUG) 
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO) 
    
    if not logger.handlers:
        logger.addHandler(debug_handler)
        logger.addHandler(console_handler)
    
    return logging.getLogger('UserMapper')


# --- 3. CORE LOGIC: DATA UNIFICATION ---

def fetch_and_build_master_map(logger: logging.Logger):
    """
    Connects to the Master Mapping Google Sheet, parses the rows, explicitly splits
    comma-separated Discord IDs, and outputs a single JSON lookup dictionary.
    """
    logger.critical("## Starting Master Mapping Import from Google Sheets... ##")
    
    try:
        # Authenticate and connect
        gc = gspread.service_account(filename=SERVICE_ACCOUNT_KEY_FILE)
        spreadsheet = gc.open_by_key(SPREADSHEET_ID)
        
        # Grab the first worksheet
        worksheet = spreadsheet.sheet1
        all_records = worksheet.get_all_records()
        
        logger.info(f"Successfully fetched {len(all_records)} records from the Google Sheet.")
        
        master_map = {}
        processed_count = 0
        multiple_ids_count = 0
        
        for idx, row in enumerate(all_records):
            # Normalizing keys just in case the sheet headers slightly differ
            # Looking for any column that looks like a username (Forum, Discourse, etc)
            # and a column that looks like Discord ID.
            
            discord_id_raw = ""
            usernames = []
            
            for col_name, value in row.items():
                col_lower = str(col_name).lower()
                val_str = str(value).strip()
                if not val_str:
                    continue
                    
                if "id" in col_lower and "discord" in col_lower:
                    discord_id_raw = val_str
                elif "name" in col_lower or "handle" in col_lower or "user" in col_lower:
                    usernames.append(val_str)
                    
            # Skip if we couldn't find a discord ID
            if not discord_id_raw:
                continue
                
            # Split by comma and strip whitespace to support multiple accounts
            discord_ids = [did.strip() for did in discord_id_raw.split(",") if did.strip()]
            
            if len(discord_ids) > 1:
                multiple_ids_count += 1
                
            # Map every found username alias to the list of Discord IDs
            for alias in usernames:
                if alias:
                    # Lowercase mapping for case-insensitive lookup later
                    master_map[alias.lower()] = discord_ids
                    processed_count += 1
                    
        # Export to JSON
        with open(OUTPUT_MAPPING_FILE, 'w', encoding='utf-8') as f:
            json.dump(master_map, f, indent=4)
            
        logger.critical(f"SUCCESS: Exported {processed_count} aliases mapped to Discord IDs.")
        logger.info(f"Detected {multiple_ids_count} users with multiple comma-separated Discord IDs.")
        logger.critical(f"Master map saved locally to: {OUTPUT_MAPPING_FILE}")
        
    except Exception as e:
        logger.critical(f"FATAL ERROR during Google Sheets Import: {e}")
        logger.critical("Please ensure the service account email is invited as a Viewer/Editor to the sheet.")


# --- 4. MAIN EXECUTION ---

if __name__ == "__main__":
    os.makedirs(os.path.join(CURRENT_SCRIPT_DIR, "output"), exist_ok=True)
    os.makedirs(os.path.join(CURRENT_SCRIPT_DIR, "logs"), exist_ok=True)
    
    logger = setup_logging()
    
    try:
        logger.info("Starting User Mapping Import Pipeline...")
        fetch_and_build_master_map(logger)
        
    except Exception as e:
        logger.critical(f"Main execution failed: {e}", exc_info=True)