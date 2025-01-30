import os
import json


# --- load data files ---
def save_json_data(data, name, sub="game_data"):
    """
    Saves data to a JSON file in the specified subdirectory.
    Creates the subdirectory if it doesn't exist.

    Args:
        data: The data to save (must be JSON serializable, like a dictionary or list).
        filename: The name of the file (e.g., "game_1.json").
        subdirectory: The subdirectory within the "data" folder where the file should be saved.
    """
    filename = f"{name}.json"
    subdirectory = f"{sub}/{name}"
    # Create the subdirectory if it doesn't exist
    data_dir = os.path.join("stats", subdirectory)
    os.makedirs(data_dir, exist_ok=True)
    # Construct the full file path
    filepath = os.path.join(data_dir, filename)
    # Save the data to the JSON file
    with open(filepath, "w") as f:
           json.dump(data, f, indent=4)
    print(f"DEBUG: Data saved to {filepath}")

def load_data(filepath, error_msg):
    """Loads data from a JSON or TXT file, handling FileNotFoundError."""
    try:
        with open(filepath, "r") as f:
            if filepath.endswith(".json"):
                data = json.load(f)
            else:  # Assume it's a TXT file
                data = [line.strip() for line in f]
        return data
    except FileNotFoundError:
        print(error_msg)
        if filepath.endswith(".json"):
            # Create an empty JSON file if it doesn't exist
            if filepath == "data/game_data.json":
                with open(filepath, "w") as f:
                    json.dump([], f)
                return []
        return {} if filepath.endswith(".json") else []
    
    # --- Data Retention ---
def save_game_data(game_data):
    """Saves the game data to a JSON file."""
    try:
        with open("stats/testgames/game_data.json", "r") as f:
            all_games = json.load(f)
    except FileNotFoundError:
        all_games = []
    all_games.append(game_data)
    with open("stats/testgames/game_data.json", "w") as f:
        json.dump(all_games, f, indent=4)

def save_lynch_data(lynch_data):
    """Saves the game data to a JSON file."""
    try:
        with open("stats/testgames/lynch_data.json", "r") as f:
            all_games = json.load(f)
    except FileNotFoundError:
        all_games = []
    all_games.append(lynch_data)
    with open("stats/testgames/lynch_data.json", "w") as f:
        json.dump(all_games, f, indent=4)

