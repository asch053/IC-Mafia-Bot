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
logger.critical("Bot instance created.")

# --- 3. Load Cogs ---
@bot.event
async def setuphook():
    logger.critical(f"Bot is ready. Logged in as {bot.user} (ID: {bot.user.id})")
    await cogsetup.load_cogs(bot)
    logger.critical("All cogs loaded and commands synced.")

# --- 4. Run the Bot ---
@bot.event
async def on_ready():
    logger.critical(f"Bot is ready. Logged in as {bot.user} (ID: {bot.user.id})")
    logger.critical("Bot is now running.")

# --- 5. Start the Bot ---
asyncio.run(startbot.main(bot))