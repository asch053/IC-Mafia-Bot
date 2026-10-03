# setup/loggersetup.py
import sys
import asyncio
import logging
import os
import logging.handlers
from datetime import datetime, timezone
import discord
import config


class DiscordCriticalHandler(logging.Handler):
    """
    Custom logging handler that intercepts logging.CRITICAL records
    and dispatches a formatted alert embed to the admin/mod channel (config.MOD_CHANNEL_ID).
    Includes rate-limiting/cooldown to prevent Discord API flooding during repeated failures.
    """
    _bot = None
    _recent_alerts = {}  # (location, message_snippet): timestamp

    @classmethod
    def set_bot(cls, bot):
        cls._bot = bot

    @classmethod
    def get_bot(cls):
        return cls._bot

    def __init__(self, level=logging.CRITICAL, cooldown_seconds: float = 30.0):
        super().__init__(level)
        self.cooldown_seconds = cooldown_seconds
        self._is_sending = False

    def emit(self, record: logging.LogRecord):
        if record.levelno < logging.CRITICAL:
            return
        if not self._bot:
            return
        if self._is_sending:
            return

        # Deduplication / Cooldown check
        now = datetime.now(timezone.utc).timestamp()
        key = (record.name, record.getMessage())
        last_sent = self._recent_alerts.get(key, 0.0)
        if (now - last_sent) < self.cooldown_seconds:
            return
        self._recent_alerts[key] = now

        # Prune old cache entries
        if len(self._recent_alerts) > 50:
            self._recent_alerts = {k: ts for k, ts in self._recent_alerts.items() if (now - ts) < self.cooldown_seconds * 2}

        bot = self._bot
        if not hasattr(bot, 'loop') or bot.loop is None or bot.loop.is_closed():
            return

        async def _dispatch_alert():
            if self._is_sending:
                return
            self._is_sending = True
            try:
                mod_channel_id = getattr(config, 'MOD_CHANNEL_ID', None)
                if not mod_channel_id:
                    return

                channel = bot.get_channel(int(mod_channel_id))
                if channel is None:
                    try:
                        channel = await bot.fetch_channel(int(mod_channel_id))
                    except Exception:
                        channel = None

                if not channel:
                    return

                embed = discord.Embed(
                    title="🚨 CRITICAL SYSTEM ALERT",
                    description=f"A game-breaking or critical error occurred:\n```{record.getMessage()[:1500]}```",
                    color=discord.Color.red(),
                    timestamp=datetime.now(timezone.utc)
                )
                embed.add_field(name="Logger", value=f"`{record.name}`", inline=True)
                embed.add_field(name="Location", value=f"`{record.filename}:{record.lineno}`", inline=True)
                if record.funcName:
                    embed.add_field(name="Function", value=f"`{record.funcName}()`", inline=True)

                if record.exc_info:
                    import traceback
                    tb_str = "".join(traceback.format_exception(*record.exc_info))
                    if len(tb_str) > 1000:
                        tb_str = tb_str[:500] + "\n...[truncated]...\n" + tb_str[-450:]
                    embed.add_field(name="Traceback", value=f"```py\n{tb_str}\n```", inline=False)

                await channel.send(embed=embed)
            except Exception as e:
                sys.stderr.write(f"[DiscordCriticalHandler] Could not send alert to admin channel: {e}\n")
            finally:
                self._is_sending = False

        try:
            try:
                running_loop = asyncio.get_running_loop()
                running_loop.create_task(_dispatch_alert())
            except RuntimeError:
                if bot.loop.is_running():
                    asyncio.run_coroutine_threadsafe(_dispatch_alert(), bot.loop)
        except Exception as e:
            sys.stderr.write(f"[DiscordCriticalHandler] Error scheduling alert: {e}\n")


def set_bot(bot):
    """Sets the bot reference for DiscordCriticalHandler."""
    DiscordCriticalHandler.set_bot(bot)


def setup_logging():
    """Sets up logging for the bot, creating a log directory, a rotating file handler, and the critical alert handler."""
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"bot_log_{datetime.now().strftime('%Y-%m-%d')}.log")

    # 1. Create a rotating file handler (captures DEBUG and above)
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8'
    )
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)-8s] %(name)s - %(funcName)s:%(lineno)d: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    # 2. Create the Discord critical alert handler
    discord_handler = DiscordCriticalHandler()
    discord_handler.setFormatter(formatter)
    discord_handler.setLevel(logging.CRITICAL)

    # 3. Configure the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Avoid adding duplicate handlers if setup_logging is called multiple times
    has_file = any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root_logger.handlers)
    has_discord = any(isinstance(h, DiscordCriticalHandler) for h in root_logger.handlers)

    if not has_file:
        root_logger.addHandler(file_handler)
    if not has_discord:
        root_logger.addHandler(discord_handler)

    # Also configure discord logger to inherit DEBUG level
    discord_logger = logging.getLogger('discord')
    discord_logger.setLevel(logging.DEBUG)
