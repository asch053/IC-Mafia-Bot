import random
import json
from collections import Counter
import time

# --- Configuration for the Test ---
NUM_PLAYERS = 9       # << CHANGE THIS to the player count you want to test
NUM_SIMULATIONS = 10000 # << Number of times to run the simulation for statistical accuracy

# --- Replicated GameRole Class and Data Loading ---
# We need these from your bot.py to run the test independently.

class GameRole:
    """A simple replicated GameRole class for testing purposes."""
    def __init__(self, name, alignment, **kwargs): # Using **kwargs to ignore extra fields
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
        print(f"{error_msg}: {filepath}")
        return {}
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {filepath}")
        return {}

mafia_setups = load_data("data/mafia_setups.json", "ERROR: mafia_setups.json not found!")

# --- Core Logic to Test ---

def generate_test_roles(num_players):
    """Generates a list of GameRole objects based on the setup file."""
    game_roles = []
    setups = mafia_setups.get(str(num_players))
    if not setups:
        raise ValueError(f"No setup found for {num_players} players in mafia_setups.json")

    setup = setups[0] # Use the first available setup for this player count
    for role_data in setup["roles"]:
        for _ in range(role_data["quantity"]):
            game_role = GameRole(
                name=role_data["name"],
                alignment=role_data["alignment"]
                # We don't need description, etc. for this test
            )
            game_roles.append(game_role)
    return game_roles

def run_simulation(num_players):
    """Simulates one round of role assignment and returns the result."""
    # 1. Create mock players
    # Using simple names like 'Player 1', 'Player 2' for clarity
    player_ids = [f"Player {i+1}" for i in range(num_players)]

    # 2. Generate the list of roles for this game size
    roles_to_assign = generate_test_roles(num_players)

    # 3. This is the core logic from your bot's assign_game_roles function
    # If you are seeding your random generator in your bot, that's the likely
    # cause of bias. This script does NOT seed, testing the raw shuffle.
    random.shuffle(player_ids)
    random.shuffle(roles_to_assign)

    # 4. "Assign" roles by pairing the shuffled lists
    assignments = {}
    for i, player_id in enumerate(player_ids):
        assignments[player_id] = roles_to_assign[i]

    return assignments

# --- Main Test Execution ---

if __name__ == "__main__":
    print(f"--- Running Role Assignment Randomness Test ---")
    print(f"Simulating a {NUM_PLAYERS}-player game for {NUM_SIMULATIONS} iterations...")
    print("-" * 45)

    # Initialize a structure to hold the results
    # e.g., {'Player 1': Counter({'Townie': 1100, 'Godfather': 300}), 'Player 2': ...}
    results = {f"Player {i+1}": Counter() for i in range(NUM_PLAYERS)}

    start_time = time.time()

    # Run the simulation many times
    for i in range(NUM_SIMULATIONS):
        # Optional: To test if seeding with a similar timestamp causes bias,
        # you could uncomment the following line. Notice how it would skew results.
        # random.seed(int(time.time()))

        single_game_assignments = run_simulation(NUM_PLAYERS)
        for player, role in single_game_assignments.items():
            results[player][role.name] += 1

    end_time = time.time()

    # --- Print the Results ---
    print("\n--- Results ---")
    game_roles_for_count = generate_test_roles(NUM_PLAYERS)
    role_counts = Counter(role.name for role in game_roles_for_count)

    for player, role_distribution in results.items():
        print(f"\nDistribution for {player}:")
        # Sort roles for consistent output
        sorted_roles = sorted(role_distribution.items(), key=lambda item: item[0])
        for role, count in sorted_roles:
            percentage = (count / NUM_SIMULATIONS) * 100
            expected_percentage = (role_counts[role] / NUM_PLAYERS) * 100
            print(f"  - {role:<20}: {count:>5} times ({percentage:.2f}%) "
                  f"(Expected: ~{expected_percentage:.2f}%)")

    print("-" * 45)
    print(f"Test finished in {end_time - start_time:.2f} seconds.")