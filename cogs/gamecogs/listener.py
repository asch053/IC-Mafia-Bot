# cogs/gamecogs/listener.py
import logging
import discord
import config

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def handle_on_message(self, message: discord.Message):
    """
    Handles message events:
    1. UX Redirection: Guides users to slash commands in specific channels.
    2. Chat Logging: Records messages from the designated talk channel.
    """
    if message.author.bot or not message.guild:
        return

    game = getattr(self.bot, 'game_instance', None) or getattr(self, 'game', None)
    if not game:
        if message.channel.id == getattr(config, 'SIGN_UP_HERE_CHANNEL_ID', 0):
            await message.reply(
                f"Please use the slash command `/mafiajoin` to join, or discuss in <#{getattr(config, 'TALKY_TALKY_CHANNEL_ID', 0)}>."
            )
        return

    if message.channel.id == getattr(config, 'VOTING_CHANNEL_ID', 0):
        logger.info(f"Redirecting user {message.author.name} from chatting in voting channel.")
        await message.reply(
            f"Please do not chat in the voting channel. Use the slash command `/vote` to vote, or discuss in <#{getattr(config, 'TALKY_TALKY_CHANNEL_ID', 0)}>."
        )
        return

    talk_channel_id = getattr(config, 'TALKY_TALKY_CHANNEL_ID', 0)
    if message.channel.id != talk_channel_id:
        return

    if game.game_settings.get('current_phase', '').lower() == 'signup':
        return

    log_entry = {
        'user_id': message.author.id,
        'username': message.author.display_name,
        'timestamp_utc': message.created_at.isoformat(),
        'channel_name': message.channel.name,
        'message_id': message.id,
        'phase': game.game_settings.get('current_phase', 'N/A'),
        'phase_number': game.game_settings.get('phase_number', 0),
        'content': message.content
    }
    if hasattr(game, 'chat_log'):
        game.chat_log.append(log_entry)
        logger.debug(
            f"Chat Logged: Game={game.game_settings.get('game_id')} | Phase={log_entry['phase']} | User={message.author.name}"
        )

