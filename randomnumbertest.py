# randomnumbertest.py

import random
import json
from collections import Counter
import time
import sys
import argparse # Import the argparse module

# --- Replicated GameRole Class and Data Loading ---
class GameRole:
    """A simple replicated GameRole class for testing purposes."""
    def __init__(self, name, alignment, **kwargs):
        self.name = name
        self.alignment = alignment
    def __repr__(self):
        return self.name

def load_data(filepath, error_msg):
    """Loads JSON data from a file."""
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: {error_msg}: {filepath}")
        sys.exit(1) # Exit if the required data file is not found
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {filepath}")
        sys.exit(1)

mafia_setups = load_data("data/mafia_setups.json", "mafia_setups.json not found!")

# --- Core Logic to Test ---
def generate_test_roles(num_players):
    """Generates a list of GameRole objects based on the setup file."""
    game_roles = []
    setup_data = mafia_setups.get(str(num_players))
    if not setup_data:
        raise ValueError(f"No setup found for {num_players} players in mafia_setups.json")

    setup = setup_data[0] # Use the first available setup for this player count
    for role_data in setup["roles"]:
        for _ in range(role_data.get("quantity", 0)):
            game_roles.append(
                GameRole(name=role_data["name"], alignment=role_data["alignment"])
            )
    return game_roles

def run_simulation(player_names):
    """Simulates one round of role assignment using the provided player names."""
    num_players = len(player_names)
    local_player_list = list(player_names) # Create a copy to shuffle
    roles_to_assign = generate_test_roles(num_players)
    
    random.shuffle(local_player_list)
    random.shuffle(roles_to_assign)

    assignments = {local_player_list[i]: roles_to_assign[i] for i in range(num_players)}
    return assignments

# --- Main Test Execution ---
if __name__ == "__main__":
    # --- New Argument Parsing ---
    parser = argparse.ArgumentParser(description="Test randomness of Mafia role assignments.")
    parser.add_argument(
        "-s", "--simulations",
        type=int,
        default=10000,
        help="The number of simulations to run."
    )
    parser.add_argument(
        'player_names',
        nargs='+', # This means it will accept one or more player names
        help="A list of player names, separated by spaces."
    )
    args = parser.parse_args()

    num_players = len(args.player_names)
    num_simulations = args.simulations
    # --- End New Argument Parsing ---

    print(f"--- Running Role Assignment Randomness Test ---")
    print(f"Simulating a {num_players}-player game for {num_simulations} iterations...")
    print(f"Players: {', '.join(args.player_names)}")
    print("-" * 45)

    results = {player_name: Counter() for player_name in args.player_names}
    start_time = time.time()

    for _ in range(num_simulations):
        single_game_assignments = run_simulation(args.player_names)
        for player, role in single_game_assignments.items():
            results[player][role.name] += 1

    end_time = time.time()

    # --- Print the Results ---
    print("\n--- Results ---")
    game_roles_for_count = generate_test_roles(num_players)
    role_counts = Counter(role.name for role in game_roles_for_count)

    for player, role_distribution in results.items():
        print(f"\nDistribution for {player}:")
        sorted_roles = sorted(role_distribution.items())
        for role, count in sorted_roles:
            percentage = (count / num_simulations) * 100
            expected_percentage = (role_counts.get(role, 0) / num_players) * 100
            print(f"  - {role:<20}: {count:>6} times ({percentage:6.2f}%) "
                  f"(Expected: ~{expected_percentage:.2f}%)")

    print("-" * 45)
    print(f"Test finished in {end_time - start_time:.2f} seconds.")