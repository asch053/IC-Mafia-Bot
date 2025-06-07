import discord
from discord.ext import commands
import asyncio
import json
import logging
import logging.handlers
import os
import mafiaconfig  # Import the config module directly
from datetime import datetime, timedelta, timezone

# --- Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=mafiaconfig.BOT_PREFIX, intents=intents, owner_id=mafiaconfig.OWNER_ID)

# --- Logging Setup ---
def setup_logging():
    """Configures logging for the bot."""
    log_dir = os.path.join(".", "logs")
    os.makedirs(log_dir, exist_ok=True)

    dt_fmt = '%Y-%m-%d %H:%M:%S'
    formatter = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}', dt_fmt, style='{')

    # Debug log handler
    debug_log_file = os.path.join(log_dir, f"{datetime.now(timezone(timedelta(hours=12))).strftime('%Y-%m-%d')}_debug.log")
    debug_handler = logging.handlers.RotatingFileHandler(
        debug_log_file,
        encoding='utf-8',
        maxBytes=10 * 1024 * 1024,  # 10 MiB
        backupCount=5,  # Rotate through 5 files
    )
    debug_handler.setFormatter(formatter)
    debug_handler.setLevel(logging.DEBUG)

    # Error log handler
    error_log_file = os.path.join(log_dir, f"{datetime.now(timezone(timedelta(hours=12))).strftime('%Y-%m-%d')}_error.log")
    error_handler = logging.handlers.RotatingFileHandler(
        error_log_file,
        encoding='utf-8',
        maxBytes=10 * 1024 * 1024,  # 10 MiB
        backupCount=5,  # Rotate through 5 files
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    logger = logging.getLogger('discord')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(debug_handler)
    logger.addHandler(error_handler)
    logger.addHandler(console_handler)

    return logger, debug_handler  # Return the main handler

logger, main_handler = setup_logging()

# --- Bot Event ---
@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user.name}")
    try:
        await bot.load_extension("cogs.game")
        await bot.load_extension("cogs.admin")
        await bot.load_extension("cogs.info")
        #await bot.load_extension("cogs.stats")
        logger.info("Cogs loaded successfully.")
    except Exception as e:
        logger.exception(f"Failed to load cogs: {e}")

async def main():
  async with bot:
    await bot.start(mafiaconfig.BOT_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())