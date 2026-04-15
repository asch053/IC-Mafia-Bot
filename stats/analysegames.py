import json
import os
import glob
import logging

logger = logging.getLogger('discord')

def load_all_game_data(self):
    """Loads all valid game summary JSON files from the stats directory."""
    all_games = []
    if not os.path.exists(self.stats_directory):
        logger.warning(f"Stats directory not found at: {self.stats_directory}")
        return all_games

    for root, _, files in os.walk(self.stats_directory):
        for file in files:
            if file.endswith("_summary.json"):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, "r", encoding='utf-8') as f:
                        data = json.load(f)
                        # Ensure the file has the necessary structure before adding
                        if "game_summary" in data and "player_data" in data:
                            all_games.append(data)
                        else:
                            logger.warning(f"Skipping malformed summary file: {filepath}")
                except json.JSONDecodeError:
                    logger.error(f"Could not decode JSON from file: {filepath}")
                except Exception as e:
                    logger.error(f"Error loading file {filepath}: {e}")
    return all_games

def calculate_win_rates(self, games):
    """Calculates win rates for each faction."""
    wins = Counter(game['game_summary']['winning_faction'] for game in games)
    total_games = len(games)
    if total_games == 0:
        return {}
    
    win_rates = {team: (count / total_games) * 100 for team, count in wins.items()}
    return win_rates

def calculate_player_stats(self, games):
    """Calculates alignment and role stats for each player."""
    player_stats = {}
    for game in games:
        for player in game['player_data']:
            player_name = player['player_name']
            if player_name not in player_stats:
                player_stats[player_name] = {
                    'alignments': Counter(),
                    'roles': Counter(),
                    'total_games': 0
                }
            
            player_stats[player_name]['alignments'][player['alignment']] += 1
            player_stats[player_name]['roles'][player['role']] += 1
            player_stats[player_name]['total_games'] += 1
    
    return player_stats

# Load all game data
all_game_data = load_all_game_data(".")
print(f"Total Games Loaded: {len(all_game_data)}")
print(f"Games loaded: {all_game_data}")

# Calculate win rates
win_rates = calculate_win_rates(all_game_data)
print(f"Win Rates: {win_rates}")

# Example: average game length in phases
total_phases = 0
for game in all_game_data:
    total_phases += game["total_phases"]
if all_game_data:
    average_phases = total_phases / len(all_game_data)
    print(f"Average Game Length (Phases): {average_phases:.2f}")
else:
    print("No game data found")

# Example: find all games won by Mafia
mafia_wins = [game for game in all_game_data if game["winner"] == "Mafia"]
print(f"Number of Mafia wins: {len(mafia_wins)}")

# Example: List all players who have played as Godfather
godfathers = set()  # Use a set to avoid duplicates
for game in all_game_data:
    for player in game["players"]:
        if player["role"] and player["role"]["name"] == "Godfather": #check role isn't none
            godfathers.add(player["display_name"])
print(f"Players who have been Godfather: {godfathers}")

