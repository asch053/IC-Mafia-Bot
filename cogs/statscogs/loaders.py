# cogs/statscogs/loaders.py
import os
import json
import logging
from collections import defaultdict
import config

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def load_game_file(file_path: str) -> dict | None:
    """Loads a single JSON game file and returns its data."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Error loading game file {file_path}: {e}")
    return None


def load_and_group_games() -> dict:
    """
    Loads all game logs and groups them by game mode.
    Returns: {'classic': [game1, game2], 'battle_royale': [game3]}
    """
    games_by_mode = defaultdict(list)
    stats_dir = getattr(config, 'data_save_path', 'data/stats')
    abs_path = os.path.abspath(stats_dir)
    logger.info(f"Searching for game logs in: {abs_path}")

    if not os.path.exists(stats_dir):
        logger.warning(f"Stats directory not found at: {abs_path}")
        return {}

    for root, dirs, files in os.walk(stats_dir):
        for file in files:
            if file.endswith("_summary.json"):
                file_path = os.path.join(root, file)
                game_data = load_game_file(file_path)
                if game_data:
                    game_summary = game_data.get('game_summary', {})
                    mode = game_summary.get('game_type', 'classic').lower().replace(' ', '_')
                    games_by_mode[mode].append(game_data)

    logger.info(f"Loaded games by mode: {', '.join([f'{k}: {len(v)}' for k, v in games_by_mode.items()])}")
    return dict(games_by_mode)


def get_player_games(games_by_mode: dict, player_id: int) -> dict:
    """Filters the grouped games to only include games where player participated."""
    player_games = defaultdict(list)
    for mode, games in games_by_mode.items():
        for game in games:
            if any(p.get('player_id') == player_id for p in game.get('player_data', [])):
                player_games[mode].append(game)
    return dict(player_games)

