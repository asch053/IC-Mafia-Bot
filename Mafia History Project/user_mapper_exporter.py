import json
import os
import csv
from collections import defaultdict
import gspread 
import pandas as pd 
import logging
import logging.handlers
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

# --- 1. CONFIGURATION AND SETUP ---

# Define the script's own directory (e.g., F:\IC Mafia Bot\Mafia History Project)
CURRENT_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# *** FIX: Go up one level to the parent (root) directory for the key file. ***
ROOT_DIR = os.path.dirname(CURRENT_SCRIPT_DIR)
SERVICE_ACCOUNT_KEY_FILE = os.path.join(ROOT_DIR, "ic-mafia-bot-41a41f61e757.json")

# Define paths relative to the script's directory
LOG_DIR = os.path.join(CURRENT_SCRIPT_DIR, "logs")
OUTPUT_DIR = os.path.join(CURRENT_SCRIPT_DIR, "output")

# --- PLACEHOLDERS (UPDATE THESE) ---
SPREADSHEET_NAME = "Mafia Historical Data Master Sheet" 
WORKSHEET_TITLE = "User_Mapping_Template"

# --- INPUT AND OUTPUT FILES ---
# List of all harvested JSONL files to be merged:
INPUT_FILES = [
    os.path.join(OUTPUT_DIR, "extracted_history.jsonl"), # Old forum
    os.path.join(OUTPUT_DIR, "discourse_history.jsonl"), # New Discourse
    os.path.join(OUTPUT_DIR, "old_discord_history.jsonl"), # Old Discord
    os.path.join(OUTPUT_DIR, "live_discord_history.jsonl") # Live Discord
]
# Local output file for the mapping template (in the output folder)
OUTPUT_MAPPING_FILE = os.path.join(OUTPUT_DIR, "username_mapping_template.csv")


# --- 2. LOGGING UTILITY FUNCTION ---

def setup_logging():
    """Configures logging: DEBUG to file, INFO+ to console, using script's absolute path."""
    
    formatter = logging.Formatter(
        '[{asctime}] [{levelname:<8}] {name} - {funcName}:{lineno}: {message}',
        datefmt='%Y-%m-%d %H:%M:%S',
        style='{'
    )
    
    logger = logging.getLogger() 
    logger.setLevel(logging.DEBUG) 
    
    # Create the absolute, date-stamped directory
    now = datetime.now(timezone(timedelta(hours=12)))
    log_dir = os.path.join(LOG_DIR, now.strftime('%Y-%m-%d'))
    os.makedirs(log_dir, exist_ok=True)
    
    # File Handler (Captures everything: DEBUG and above)
    debug_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, f'{now.strftime("%Y-%m-%d")}_mapper_debug.log'),
        maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
    )
    debug_handler.setFormatter(formatter)
    debug_handler.setLevel(logging.DEBUG) 
    
    # Console Handler (Shows INFO and above for startup/progress)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO) 
    
    if not logger.handlers:
        logger.addHandler(debug_handler)
        logger.addHandler(console_handler)
    
    return logging.getLogger('UserMapper')


# --- 3. CORE LOGIC: DATA UNIFICATION ---

def generate_user_data_and_export(logger: logging.Logger):
    """
    Consolidates data from all JSONL files, creates the mapping DataFrame,
    and exports it both locally and to Google Sheets.
    """
    # user_data structure: {username: {'posts': int, 'sources': set, 'discord_id': set}}
    # discord_id is a set to handle cases where a single username might resolve to multiple IDs over time
    user_data = defaultdict(lambda: {'posts': 0, 'sources': set(), 'discord_id': set()})
    
    logger.critical("##Starting data consolidation from all source files...##")
    
    # 1. Process and Tally Data from all sources
    for file_path in INPUT_FILES:
        if not os.path.exists(file_path):
            logger.warning(f"Input file not found: {os.path.basename(file_path)}. Skipping.")
            continue
        
        logger.info(f"Processing {os.path.basename(file_path)}...")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    record = json.loads(line)
                    username = record.get('username')
                    source_type = record.get('source_type')
                    user_id = record.get('user_id') # CRITICAL: Captured Discord ID
                    
                    if username:
                        user_data[username]['posts'] += 1
                        user_data[username]['sources'].add(source_type)
                        
                        # Only record the ID if it's present and not the 'N/A' placeholder from forum posts
                        if user_id and user_id != 'N/A':
                            user_data[username]['discord_id'].add(str(user_id))
                    logger.info(f" Tallying post by {username} from {source_type}")
                            
                except json.JSONDecodeError:
                    logger.error(f"Error decoding JSON in file: {os.path.basename(file_path)}. Skipping line.")
                
    # 2. CREATE PANDAS DATAFRAME for export
    mapping_list = []
    sorted_users = sorted(user_data.items(), key=lambda item: item[1]['posts'], reverse=True)
    # Build the mapping list
    for username, data in sorted_users:
        # Determine the Discord ID: use the found ID, or leave blank for manual mapping
        # This resolves if a user's display name maps to one or more known IDs.
        resolved_id = next(iter(data['discord_id']), '') if len(data['discord_id']) == 1 else ",".join(data['discord_id']) 
        logger.info(f"Preparing mapping entry for {username}: Sources={data['sources']}, Posts={data['posts']}, Resolved_ID={resolved_id}")
        mapping_list.append({
            'Source_Username': username,
            'Source_Platform(s)': ", ".join(sorted(list(data['sources']))),
            'Total_Posts': data['posts'],
            'Final_Discord_ID': resolved_id # Prefilled with captured Discord ID
        })
        logger.info(f"Added mapping entry for {username} to the list.")
        logger.debug(f" Current mapping list size: {len(mapping_list)} entries.")

    df = pd.DataFrame(mapping_list)
    
    # 3. EXPORT LOCALLY (CSV)
    df.to_csv(OUTPUT_MAPPING_FILE, index=False, encoding='utf-8')
    logger.critical(f"Local mapping template created: {os.path.basename(OUTPUT_MAPPING_FILE)}")
    
    # 4. EXPORT TO GOOGLE SHEETS
    logger.info("Attempting export to Google Sheets...")
    try:
        gc = gspread.service_account(filename=SERVICE_ACCOUNT_KEY_FILE)
        spreadsheet = gc.open(SPREADSHEET_NAME)
        try:
            worksheet = spreadsheet.worksheet(WORKSHEET_TITLE)
            worksheet.clear() 
        except gspread.WorksheetNotFound:
            logger.error(f"Worksheet '{WORKSHEET_TITLE}' not found. Creating a new one.")
            worksheet = spreadsheet.add_worksheet(title=WORKSHEET_TITLE, rows="1000", cols="4")
        
        data_to_upload = [df.columns.values.tolist()] + df.values.tolist()
        worksheet.update(range_name='A1', values=data_to_upload)
        
        logger.critical(f"SUCCESS: Data uploaded to Google Sheets worksheet: {WORKSHEET_TITLE}")

    except Exception as e:
        logger.critical(f"FATAL ERROR during Google Sheets Export: {e}")
        logger.critical("Please ensure the service account key is correct and the sheet is shared with the service account email.")


# --- 4. MAIN EXECUTION ---

if __name__ == "__main__":
    # Ensure output and log directories exist before logging setup
    os.makedirs(os.path.join(CURRENT_SCRIPT_DIR, "output"), exist_ok=True)
    os.makedirs(os.path.join(CURRENT_SCRIPT_DIR, "logs"), exist_ok=True)
    
    # Setup logging and run the main function
    logger = setup_logging()
    
    try:
        logger.info("Starting User Mapping and Export Pipeline...")
        generate_user_data_and_export(logger)
        
    except Exception as e:
        logger.critical(f"Main execution failed: {e}", exc_info=True)