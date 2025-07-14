import discord
from discord.ext import commands
import asyncio
import logging
import logging.handlers
import os
import config  # Import the config module directly
from datetime import datetime, timedelta, timezone

# --- 1. Logging Setup ---
def setup_logging():
    """Configures logging for the bot."""
    log_dir = os.path.join(".", "logs")
    os.makedirs(log_dir, exist_ok=True)
    dt_fmt = '%Y-%m-%d %H:%M:%S'
    formatter = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}', dt_fmt, style='{')

    logger = logging.getLogger('discord')
    logger.setLevel(logging.DEBUG)

    # File handler
    file_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, 'mafiabot.log'),
        encoding='utf-8',
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO) # Only show INFO and above in console
    logger.addHandler(console_handler)
    
    return logger

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
    # Sync the slash commands to your specific test server for instant updates
    try:
        # Create a discord.Object for your guild
        guild = discord.Object(id=config.SERVER_ID)
        # Sync to this specific guild only
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        logger.info(f"Synced {len(synced)} slash command(s) to guild {config.SERVER_ID}.")
    except Exception as e:
        logger.error("Failed to sync slash commands.", exc_info=True)


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