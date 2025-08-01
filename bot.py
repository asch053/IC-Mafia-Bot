import discord
from discord.ext import commands
import asyncio
import logging
import logging.handlers
import logging
import os
import config  # Import the config module directly
from datetime import datetime, timedelta, timezone

# Version without smart narration

# --- 1. Logging Setup ---
def setup_logging():
    """Configures logging into a date-stamped folder with separate files."""
    # 1. Define the formatter
    # Using a more detailed formatter for better debug info
    formatter = logging.Formatter(
        '[{asctime}] [{levelname:<8}] {name} - {funcName}:{lineno}: {message}',
        datefmt='%Y-%m-%d %H:%M:%S',
        style='{'
    )
    # 2. Get the main logger and set its level to the lowest (DEBUG)
    # This allows it to pass all messages to the handlers, which will do their own filtering.
    logger = logging.getLogger('discord')
    logger.setLevel(logging.DEBUG)
    # 3. Create the date-stamped directory (e.g., logs/2025-07-15/)
    # Using a fixed timezone as per your old code
    now = datetime.now(timezone(timedelta(hours=12)))
    log_dir = os.path.join("logs", now.strftime('%Y-%m-%d'))
    os.makedirs(log_dir, exist_ok=True)
    # 4. Create handler for ALL messages (debug.log)
    debug_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, f'{now.strftime("%Y-%m-%d")}_debug.log'),
        maxBytes=10*1024*1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    debug_handler.setFormatter(formatter)
    debug_handler.setLevel(logging.DEBUG) # This handler accepts everything.
    # 5. Create handler for INFO and up (error.log, as per your old naming)
    info_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, f'{now.strftime("%Y-%m-%d")}_error.log'),
        maxBytes=10*1024*1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    info_handler.setFormatter(formatter)
    info_handler.setLevel(logging.INFO) # This handler only accepts INFO, WARNING, ERROR, etc.
    # 6. Create console handler for INFO and up
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    # 7. Add all handlers to the main logger
    logger.addHandler(debug_handler)
    logger.addHandler(info_handler)
    logger.addHandler(console_handler)
    return logger
# This line at the bottom of the setup section remains the same
logger = setup_logging()

# --- 2. Bot Intents and Initialization ---
# REMOVED: The first, redundant bot and intents definition is gone.
logger.info("Defining intents and creating bot instance...")
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix=config.BOT_PREFIX, intents=intents, owner_id=config.OWNER_ID)


# --- 3. List of Cogs to Load ---
# This list is now correct with commas.
initial_extensions = [
    'Cogs.game',
    'Cogs.admin',
    'Cogs.info',
    # 'Cogs.stats'
]

# --- 4. Setup Hook (The ONLY place for loading cogs) ---
@bot.event
async def setup_hook():
    logger.info("Running setup hook...")
    # Load all cogs
    for extension in initial_extensions:
        try:
            await bot.load_extension(extension)
            logger.info(f"Successfully loaded extension: {extension}")
        except Exception as e:
            logger.error(f"Failed to load extension {extension}.", exc_info=True)
    # In your setup_hook function for the BETA BOT
    try:
        # This syncs commands globally to all servers and DMs
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} global slash command(s).")
    except Exception as e:
        logger.error("Failed to sync global slash commands.", exc_info=True)


# --- 5. on_ready Event (Simplified) ---
@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user.name} (ID: {bot.user.id})")
    # REMOVED: All cog loading logic is gone from here. It's not needed.


# --- 6. Main Entry Point ---
async def main():
    try:
        async with bot:
            await bot.start(config.BOT_TOKEN)
    finally:
        if not bot.is_closed():
            logger.critical("Shutting down the bot...")
            await bot.close()
            logger.info("Bot has been shut down.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.critical("Shutdown requested by user.")
