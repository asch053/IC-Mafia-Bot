import logging


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def send_chunked_message(bot, channel, message: str, chunk_size: int = 1900):
    """Sends a long message in chunks."""
    logger.debug(f"Sending message in chunks to channel {channel.id}. Total length: {len(message)} characters, chunk size: {chunk_size}.")
    for i in range(0, len(message), chunk_size):
        await channel.send(message[i:i+chunk_size])
        logger.debug(f"Sent chunk {i//chunk_size + 1}: {message[i:i+chunk_size]}")