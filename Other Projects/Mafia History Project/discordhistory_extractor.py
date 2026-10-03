import discord
from discord.ext import commands
import asyncio
import json
import logging
import logging.handlers
import os
import historybot_config as config # Assuming you add the new token/IDs to config.py
from datetime import datetime, timezone, timedelta

# --- CONFIGURATION (Customize these) ---
HARVESTER_BOT_TOKEN = config.BOT_TOKEN
SERVER_ID = config.SERVER_ID # ID of the old Mafia server
OUTPUT_FILE = "new_discord_history.jsonl"
# List of Channel IDs to target in the OLD server
CHANNEL_IDS_TO_SCRAPE = [
    config.TALKY_TALKY_CHANNEL_ID, # talky-talky channel ID
    config.COMMUNITY_TALKY_CHANNEL_ID, # community talky-talky channel ID
    config.STORIES_CHANNEL_ID,     # stories channel ID
    config.VOTING_CHANNEL_ID,   # voting channel ID
    config.RULES_AND_ROLES_CHANNEL_ID, # rules-and-roles channel ID
]
CURRENT_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# --- LOGGING SETUP ---
def setup_logging():
    """Configures logging: DEBUG to file, INFO+ to file, CRITICAL+ to console."""
    # 1. Define the formatter
    formatter = logging.Formatter(
        '[{asctime}] [{levelname:<8}] {name} - {funcName}:{lineno}: {message}',
        datefmt='%Y-%m-%d %H:%M:%S',
        style='{'
    )
    
    # *** CRITICAL FIX: Target the Root Logger ***
    logger = logging.getLogger() # Target the Root Logger (name='')
    logger.setLevel(logging.DEBUG) # Root logger must be lowest level
    
    # 2. Create the date-stamped directory
    now = datetime.now(timezone(timedelta(hours=12)))
    # We must assume BASE_LOG_FOLDER is defined before this call
    base_log_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    log_dir = os.path.join(base_log_folder, now.strftime('%Y-%m-%d'))
    os.makedirs(log_dir, exist_ok=True)
    
    # 3. Handlers
    
    # Debug/All Handler
    debug_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, f'{now.strftime("%Y-%m-%d")}_debug.log'),
        maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
    )
    debug_handler.setFormatter(formatter)
    debug_handler.setLevel(logging.DEBUG) 
    
    # Info/Error Handler
    info_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, f'{now.strftime("%Y-%m-%d")}_error.log'),
        maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
    )
    info_handler.setFormatter(formatter)
    info_handler.setLevel(logging.INFO)
    
    # *** CRITICAL FIX: Console Handler Level for Visibility ***
    # Console Handler now shows INFO+ to see startup/progress messages
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO) 
    
    # 4. Attach Handlers (only if none exist)
    if not logger.handlers:
        logger.addHandler(debug_handler)
        logger.addHandler(info_handler)
        logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()

# --- CORE EXTRACTION LOGIC ---
async def extract_channel_history(bot: commands.Bot, channel_id: int) -> int:
    # Get the channel object
    channel = bot.get_channel(channel_id)
    # Check if the channel exists
    if not channel:
        logger.error(f"Channel ID {channel_id} not found.")
        return 0
    # Start extracting messages
    records_extracted = 0
    logger.info(f"Starting extraction from #{channel.name}...")
    # Use limit=None to automatically handle pagination and fetch all messages
    async for message in channel.history(limit=None, oldest_first=True):
        record = {
            "timestamp": message.created_at.isoformat(),
            "source_type": "Discord-Archive",
            "source_id": f"{channel.name}-{channel.id}",
            "user_id": message.author.id,
            "username": message.author.display_name,
            "content": message.content
        }
        
        with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
        
        records_extracted += 1
        logger.info(f"Extracted message #{records_extracted} from {channel.name} by {message.author.display_name} at {message.created_at.isoformat()}")
        logger.debug(f" Record generated: {json.dumps(record, indent=None)}")
        
    logger.info(f"Finished #{channel.name}. Extracted {records_extracted} records.")
    return records_extracted

# --- MAIN EXECUTION ---
async def main():
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix='!', intents=intents)

    @bot.event
    async def on_ready():
        logger.critical(f"Harvester Bot connected as {bot.user}.")
        total_records = 0
        logger.critical(f"----- STARTING DISCORD ARCHIVE EXTRACTION -----")
        # This loop executes the extraction for all specified channels
        for chan_id in CHANNEL_IDS_TO_SCRAPE:
            logger.critical(f"----- EXTRACTING CHANNEL ID: {chan_id} -----")    
            total_records += await extract_channel_history(bot, chan_id)
            logger.critical(f"----- COMPLETED CHANNEL ID: {chan_id} -----")
        logger.critical(f"----- ALL DISCORD ARCHIVE EXTRACTIONS COMPLETE -----")
        logger.critical(f"TOTAL RECORDS WRITTEN: {total_records}")
        await bot.close()

    async with bot:
        await bot.start(HARVESTER_BOT_TOKEN)

if __name__ == "__main__":
    # Ensure logging is set up and run the main function
    logger = logging.getLogger(__name__) # Use a simple logger for this one-off script
    asyncio.run(main())