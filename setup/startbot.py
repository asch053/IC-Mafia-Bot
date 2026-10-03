import config
import logging
import asyncio


logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)

async def main(bot=None):
    if bot is None:
        from bot import bot as default_bot
        bot = default_bot

    try:
        logger.info("Starting the bot...")
        async with bot:
            await bot.start(config.BOT_TOKEN)
    except Exception as e:
        logger.critical(f"Bot encountered a fatal error: {e}", exc_info=True)
    finally:
        if not bot.is_closed():
            logger.info("Bot is shutting down.")
            await bot.close()
        else:
            logger.info("Bot has already been closed.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot is shutting down.")
    except Exception as e:
        logger.critical(f"Unexpected error occurred: {e}", exc_info=True)