import logging
import os

logger = logging.getLogger(__name__)


async def load_cogs(bot):
    """Loads all modular cog extensions from the ./cogs directory and syncs commands."""
    logger.info("Loading cogs...")
    cogs_dir = os.path.join(os.path.dirname(__file__), "..", "cogs")
    for filename in sorted(os.listdir(cogs_dir)):
        if filename.endswith(".py") and not filename.startswith("__"):
            extension_name = f"cogs.{filename[:-3]}"
            try:
                await bot.load_extension(extension_name)
                logger.critical(f"Loaded cog: {filename}")
            except Exception as e:
                logger.error(f"Failed to load cog {filename}: {e}", exc_info=True)
    logger.info("Cogs loaded.")

    logger.info("Syncing commands globally...")
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} commands globally.")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}", exc_info=True)