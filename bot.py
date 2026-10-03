import logging
import discord
import asyncio
from discord.ext import commands
import config
import setup.loggersetup as loggersetup
import setup.cogsetup as cogsetup
import setup.startbot as startbot

# --- 1. Setup logging ---
loggersetup.setup_logging()
logger = logging.getLogger(__name__)
logger.critical("Logging is set up and ready to go.")

# --- 2. Bot Intents and Initialization ---
logger.critical("Defining intents and creating bot instance...")
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix=config.BOT_PREFIX, intents=intents, owner_id=config.OWNER_ID)
bot.game_instance = None  # Single source of truth for active game
logger.critical("Bot instance created.")

# --- 3. Setup Hook to Load Cogs and Sync Commands ---
async def setup_hook():
    logger.critical("Bot setup hook running: Loading cogs and syncing commands...")
    await cogsetup.load_cogs(bot)
    logger.critical("All cogs loaded and commands synced.")

bot.setup_hook = setup_hook

# --- 4. Run the Bot ---
@bot.event
async def on_ready():
    logger.critical(f"Bot is ready. Logged in as {bot.user} (ID: {bot.user.id})")
    logger.critical("Bot is now running.")

# --- 5. Start the Bot ---
if __name__ == "__main__":
    asyncio.run(startbot.main(bot))