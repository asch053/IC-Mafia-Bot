import logging


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def send_chunked_message(bot, channel, message: str, chunk_size: int = 1900):
    """Sends a long message in chunks, splitting on line breaks where possible."""
    logger.debug(f"Sending message in chunks to channel {channel.id}. Total length: {len(message)} characters, chunk size: {chunk_size}.")
    text = message
    chunk_num = 1
    while text:
        if len(text) <= chunk_size:
            await channel.send(text)
            logger.debug(f"Sent final chunk {chunk_num} ({len(text)} chars).")
            break

        # Attempt to split on newline within chunk_size
        split_idx = text.rfind('\n', 0, chunk_size)
        if split_idx == -1 or split_idx == 0:
            # Fallback: attempt to split on whitespace
            split_idx = text.rfind(' ', 0, chunk_size)
            if split_idx == -1 or split_idx == 0:
                split_idx = chunk_size

        chunk = text[:split_idx].rstrip()
        if chunk:
            await channel.send(chunk)
            logger.debug(f"Sent chunk {chunk_num} ({len(chunk)} chars).")
            chunk_num += 1
        text = text[split_idx:].lstrip('\n')