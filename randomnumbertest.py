# randonnumbertester.py

import random
import json
from collections import Counter
import time
import sys # Import the sys module to read command-line arguments

# --- Default Configuration ---
# These will be used if no arguments are provided
DEFAULT_NUM_PLAYERS = 9
DEFAULT_NUM_SIMULATIONS = 10000

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
    # Use .get() for safer access to the setups dictionary
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

def run_simulation(num_players):
    """Simulates one round of role assignment and returns the result."""
    player_ids = [f"Player {i+1}" for i in range(num_players)]
    roles_to_assign = generate_test_roles(num_players)
    
    # This is the core randomization logic
    random.shuffle(player_ids)
    random.shuffle(roles_to_assign)

    assignments = {player_ids[i]: roles_to_assign[i] for i in range(num_players)}
    return assignments

# --- Main Test Execution ---
if __name__ == "__main__":
    # Get parameters from command-line arguments, with defaults
    try:
        num_players = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_NUM_PLAYERS
        num_simulations = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_NUM_SIMULATIONS
    except (IndexError, ValueError):
        print("Usage: python randonnumbertester.py [num_players] [num_simulations]")
        print(f"Using defaults: {DEFAULT_NUM_PLAYERS} players, {DEFAULT_NUM_SIMULATIONS} simulations.")
        num_players = DEFAULT_NUM_PLAYERS
        num_simulations = DEFAULT_NUM_SIMULATIONS

    print(f"--- Running Role Assignment Randomness Test ---")
    print(f"Simulating a {num_players}-player game for {num_simulations} iterations...")
    print("-" * 45)

    results = {f"Player {i+1}": Counter() for i in range(num_players)}
    start_time = time.time()

    for _ in range(num_simulations):
        single_game_assignments = run_simulation(num_players)
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