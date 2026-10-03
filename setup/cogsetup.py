import logging
import os

import bot

# Import logging from the main bot file to ensure consistent logging configuration
logger = logging.getLogger(__name__)

# Load cogs
async def load_cogs(bot):
    logger.info("Loading cogs...")
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            try:
                bot.load_extension(f"cogs.{filename[:-3]}")
                logger.critical(f"Loaded cog: {filename}")
            except Exception as e:
                logger.error(f"Failed to load cog {filename}: {e}")
    logger.info("Cogs loaded.")
    # ensure all commands are synced globally with Discord
    logger.info("Syncing commands globally...")
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} commands globally.")
        logger.info("Commands synced globally.")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")