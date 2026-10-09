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

import unittest

class TestRoleRandomness(unittest.TestCase):
    """
    Automated unit test suite verifying role distribution fairness and integrity.
    """
    def test_single_role_assignment_integrity(self):
        assignments = simulate_role_assignment()
        self.assertEqual(len(assignments), len(PLAYERS))
        self.assertEqual(set(assignments.keys()), set(PLAYERS))
        # Ensure role counts in a single game exactly match the defined setup
        assigned_role_counts = Counter(assignments.values())
        expected_role_counts = Counter(ROLES)
        self.assertEqual(assigned_role_counts, expected_role_counts)

    def test_role_distribution_uniformity(self):
        """
        Runs 1,000 simulation rounds and verifies that no player is starved of any role.
        """
        test_simulations = 1000
        results = {player: Counter() for player in PLAYERS}
        for _ in range(test_simulations):
            assignments = simulate_role_assignment()
            for player, role in assignments.items():
                results[player][role] += 1

        for player, role_counts in results.items():
            # Every player should have received every distinct role
            unique_roles = set(ROLES)
            self.assertEqual(set(role_counts.keys()), unique_roles, f"{player} missed some roles")
            # For 1-of roles (p=0.10), expected count = 100. Assert between 40 and 180.
            for role in unique_roles:
                count = role_counts[role]
                if role == "Townie":
                    # Townie has 3 copies (p=0.30), expected count = 300. Assert between 180 and 420.
                    self.assertGreater(count, 180, f"{player} received too few Townie roles ({count})")
                    self.assertLess(count, 420, f"{player} received too many Townie roles ({count})")
                else:
                    self.assertGreater(count, 40, f"{player} received too few {role} roles ({count})")
                    self.assertLess(count, 180, f"{player} received too many {role} roles ({count})")

if __name__ == "__main__":
    # To run this test, save it as a file (e.g., test_randomness.py)
    # and run `python test_randomness.py` from your terminal.
    run_test()

