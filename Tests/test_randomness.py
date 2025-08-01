import random
from collections import Counter
import pprint # For pretty printing the results

# --- Simulation Parameters ---
# You can change these values to test different scenarios.

# Number of times to run the simulation for statistical significance.
NUM_SIMULATIONS = 100000
# A sample list of players for the test.
PLAYERS = [
    "PlayerA", "PlayerB", "PlayerC", "PlayerD", "PlayerE", 
    "PlayerF", "PlayerG", "PlayerH", "PlayerI", "PlayerJ"
]

# A sample list of roles for a 10-player game.
# This should match one of your setups in mafia_setups.json.
ROLES = [
    "Godfather", "Mafioso",
    "Town Cop", "Town Doctor",
    "Townie", "Townie", "Townie",
    "Serial Killer",
    "Jester",
    "Town Role Blocker"
]

def simulate_role_assignment():
    """
    Simulates a single round of assigning roles to players.
    This mimics the logic in your Game.assign_roles() method.
    """
    # In a real game, you shuffle the player IDs. Here, we shuffle the names.
    shuffled_players = random.sample(PLAYERS, len(PLAYERS))
    # The roles are also shuffled before assignment.
    shuffled_roles = random.sample(ROLES, len(ROLES))
    # Assign roles to players.
    assignments = {}
    for i, player_name in enumerate(shuffled_players):
        if i < len(shuffled_roles):
            assignments[player_name] = shuffled_roles[i] 
    return assignments

def run_test():
    """
    Runs the full simulation and prints the results.
    """
    # Initialize a dictionary to hold the results.
    # The structure will be: { "PlayerName": Counter({"RoleName": count}) }
    # e.g., { "PlayerA": Counter({"Townie": 100, "Mafia": 50}) }
    results = {player: Counter() for player in PLAYERS}
    print(f"--- Running {NUM_SIMULATIONS} role assignment simulations... ---")
    # Run the simulation loop
    for i in range(NUM_SIMULATIONS):
        # Get the role assignments for this single run
        assignments = simulate_role_assignment()
        # Update the main results counter
        for player, role in assignments.items():
            results[player][role] += 1
    print("--- Simulation Complete. Results: ---")
    # Print the results in a readable format
    for player, role_counts in results.items():
        print(f"\n--- {player}'s Role Distribution ---")
        # Sort roles by count for readability
        sorted_roles = role_counts.most_common()
        for role, count in sorted_roles:
            percentage = (count / NUM_SIMULATIONS) * 100
            print(f"  - {role:<20}: {count:>6} times ({percentage:.2f}%)")
    # --- Sanity Check ---
    # In a perfectly random distribution, each role should be assigned
    # roughly the same number of times overall.
    print("\n--- Overall Role Distribution (Sanity Check) ---")
    total_role_counts = Counter()
    for player_results in results.values():
        total_role_counts.update(player_results)
    sorted_total_roles = total_role_counts.most_common()
    for role, count in sorted_total_roles:
        # Each role should appear NUM_SIMULATIONS times in total
        percentage = (count / NUM_SIMULATIONS) * 100
        print(f"  - {role:<20}: {count:>6} times ({percentage:.2f}%)")

if __name__ == "__main__":
    # To run this test, save it as a file (e.g., test_randomness.py)
    # and run `python test_randomness.py` from your terminal.
    run_test()
