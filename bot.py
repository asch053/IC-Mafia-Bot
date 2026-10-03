import logging
import discord
import asyncio
from discord.ext import commands
from discord import app_commands
import config
import setup.loggersetup as loggersetup
import setup.cogsetup as cogsetup
import setup.startbot as startbot

# --- 1. Setup logging ---
loggersetup.setup_logging()
logger = logging.getLogger(__name__)
logger.info("Logging is set up and ready to go.")

# --- 2. Bot Intents and Initialization ---
logger.info("Defining intents and creating bot instance...")
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix=config.BOT_PREFIX, intents=intents, owner_id=config.OWNER_ID)
bot.game_instance = None  # Single source of truth for active game
loggersetup.set_bot(bot)
logger.info("Bot instance created.")

# --- Global Application Command Error Handler ---
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """
    Global error handler for slash commands ensuring graceful, user-friendly responses
    without crashing the bot or hanging Discord interactions.
    """
    if isinstance(error, app_commands.CheckFailure):
        msg = "⚠️ You cannot use this command right now (e.g., no active game or command not permitted in this context)."
    elif isinstance(error, app_commands.CommandOnCooldown):
        msg = f"⏳ This command is on cooldown. Try again in {error.retry_after:.1f}s."
    else:
        logger.error(
            f"Unhandled slash command error in {interaction.command.name if interaction.command else 'command'}: {error}",
            exc_info=True
        )
        msg = "⚠️ An unexpected error occurred while executing this command. Please try again later."

    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception as send_err:
        logger.error(f"Failed to send slash command error response to user: {send_err}")

# --- 3. Setup Hook to Load Cogs and Sync Commands ---
async def setup_hook():
    logger.info("Bot setup hook running: Loading cogs and syncing commands...")
    await cogsetup.load_cogs(bot)
    logger.info("All cogs loaded and commands synced.")

bot.setup_hook = setup_hook

# --- 4. Run the Bot ---
@bot.event
async def on_ready():
    logger.info(f"Bot is ready. Logged in as {bot.user} (ID: {bot.user.id})")
    logger.info("Bot is now running.")

# --- 5. Start the Bot ---
if __name__ == "__main__":
    asyncio.run(startbot.main(bot))