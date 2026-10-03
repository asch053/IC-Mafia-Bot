import config
import logging
import asyncio


logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)

async def main(bot):
    try:
        logger.critical("Starting the bot...")
        async with bot:
            await bot.start(config.BOT_TOKEN)
    except Exception as e:
        logger.critical(f"Bot encountered an error: {e}")
    finally:
        if not bot.is_closed():
            logger.critical("Bot is shutting down.")
            await bot.close()
        else:
            logger.critical("Bot has already been closed.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.critical("Bot is shutting down.")
    except Exception as e:
        logger.critical(f"Unexpected error occurred: {e}")