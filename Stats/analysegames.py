import json
import os
import glob

def load_all_game_data(directory="stats/testgames/game_data"):
    """Loads all game data from JSON files in the specified directory."""
    all_games = []
    # Use glob to find all json files in the directory
    for filepath in glob.glob(os.path.join(directory, "game_*.json")):
        try:
            with open(filepath, "r") as f:
                game_data = json.load(f)
                all_games.append(game_data)
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
    return all_games

def calculate_win_rates(games):
    """Calculates win rates for each team."""
    wins = {"Town": 0, "Mafia": 0, "Neutral": 0, "Draw":0}
    total_games = len(games)

    for game in games:
        winner = game["winner"]
        wins[winner] += 1

    win_rates = {}
    for team, count in wins.items():
        win_rates[team] = (count / total_games) * 100 if total_games >0 else 0

    return win_rates

# Load all game data
all_game_data = load_all_game_data()

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
            godfathers.add(player["name"])
print(f"Players who have been Godfather: {godfathers}")