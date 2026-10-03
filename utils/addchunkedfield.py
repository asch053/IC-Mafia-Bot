import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def add_chunked_field(embed, name, text, chunk_size=1000):
        """
        Helper: Splits long text into multiple fields to avoid Discord API errors.
        """
        logger.debug(f"Adding chunked field '{name}' to embed. Total length: {len(text)} characters, chunk size: {chunk_size}.")
        if not text:
            logger.warning(f"No text provided for embed field '{name}'. Skipping.")
            return
        # Split content into a list of strings
        logger.debug(f"Adding chunked field '{name}' to embed. Total length: {len(text)} characters.")
        chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
        for i, chunk in enumerate(chunks):
            # If there's only one chunk, just use the name; otherwise, add (Part X)
            field_name = name if len(chunks) == 1 else f"{name} (Part {i + 1})"
            embed.add_field(name=field_name, value=chunk, inline=False)
            logger.info(f"Added field '{field_name}' with {len(chunk)} characters to embed.")