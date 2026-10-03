import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def filter_games_by_time(games: list, days: int = None) -> list:
    """Filters a list of games, returning only those that ended within the last X days."""
    if not days:
        return games
    logger.debug(f"Filtering games that ended within the last {days} days.")    
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    filtered_games = []
    logger.debug(f"Cutoff date for filtering: {cutoff_date.isoformat()}")
    for game in games:
        end_str = game.get('game_summary', {}).get('end_date_utc')
        logger.debug(f"Checking game with end date: {end_str}")
        if end_str:
            try:
                # Parse the ISO format string stored by your bot
                end_date = datetime.fromisoformat(end_str)
                if end_date > cutoff_date:
                    filtered_games.append(game)
                    logger.debug(f"Game added to filtered list: {game}")
                logger.debug(f"Game end date {end_date.isoformat()} is not within the last {days} days.")
            except ValueError:
                logger.warning(f"Could not parse date string: {end_str}")
                logger.debug(f"Game data: {game}")
        logger.debug(f"Game end date {end_str} is not valid or not present.")
    logger.debug(f"Filtered games: {filtered_games}")
    return filtered_games