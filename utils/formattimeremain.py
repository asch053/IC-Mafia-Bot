import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def format_time_remaining(target) -> str:
    """Formats the time remaining from now until target (datetime or timedelta)."""
    logger.debug(f"Calculating time remaining for target: {target}.")
    if target is None:
        return "N/A"
    if isinstance(target, datetime):
        # Ensure UTC comparison
        now = datetime.now(timezone.utc)
        delta = target - now
        logger.debug(f"Target is a datetime. Current time: {now}, Delta: {delta}")
    else:
        delta = target
        logger.debug(f"Target is a timedelta. Delta: {delta}")
    logger.debug(f"Calculating time remaining for target: {target}, current time: {datetime.now(timezone.utc)}, delta: {delta}")
    seconds = int(delta.total_seconds())
    if seconds < 0:
        logger.debug("Time is up!")
        return "Time is up!"
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    logger.debug(f"Formatted time remaining: {hours}h {minutes}m {seconds}s")
    return f"{hours}h {minutes}m {seconds}s"