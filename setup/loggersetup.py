import logging
import config
import os
import logging.handlers
from datetime import datetime

# Setup logging
def setup_logging():
    """Sets up logging for the bot, creating a log directory and a rotating file handler."""
    # 1. Define the formatter
    formatter = logging.Formatter(
        '[{asctime}] [{levelname:<8}] {name} - {funcName}:{lineno}: {message}',
        datefmt='%Y-%m-%d %H:%M:%S',
        style='{'
    )
    # 2. Create a rotating file handler

    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"bot_log_{datetime.now().strftime('%Y-%m-%d')}.log")

    # Create a rotating file handler
    handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5*1024*1024, backupCount=5
    )
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)

    # Get the root logger and set its level and handler
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
