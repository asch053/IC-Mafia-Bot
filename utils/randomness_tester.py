import random
import logging
from collections import Counter

# Get the same logger instance as in mafiabot.py
logger = logging.getLogger('discord')

# This file contains the logic for simulating role assignments to test for fairness.
def test_role_distribution(player_names: list, role_names: list, num_simulations: int = 10000):
    """
    Simulates role assignments and returns a high-level summary and a detailed text breakdown.
    Args:
        player_names (list): A list of display names for the players in the game.
        role_names (list): A list of role names to be assigned.
        num_simulations (int): The number of times to run the simulation.
    Returns:
        A tuple containing (summary_string, detailed_string).
    """
    if not player_names or not role_names or len(player_names) != len(role_names):
        # Return an error message and a placeholder for the detailed string
        logger.error("Player and role counts do not match or are empty.")
        return ("Error: Player and role counts do not match.", "Cannot run test.")
    # --- Simulation ---
    logger.info(f"Running role assignment randomness test for {len(player_names)} players and {len(role_names)} roles over {num_simulations:,} simulations.")
    results = {player: Counter() for player in player_names}
    for _ in range(num_simulations):
        shuffled_players = random.sample(player_names, len(player_names))
        shuffled_roles = random.sample(role_names, len(role_names))
        for i, player_name in enumerate(shuffled_players):
            assigned_role = shuffled_roles[i]
            results[player_name][assigned_role] += 1
    # --- Detailed Breakdown String (for the .txt file) ---
    logger.info("Simulations completed, generating detailed breakdown of role assignments.")
    total_roles = len(role_names)
    role_type_counts = Counter(role_names)
    expected_percentages = {role: (count / total_roles) * 100 for role, count in role_type_counts.items()}
    detailed_string = (
        f"--- Running Role Assignment Randomness Test ---\n"
        f"Simulating a {len(player_names)}-player game for {num_simulations:,} iterations...\n"
        f"Players: {', '.join(player_names)}\n"
        f"---------------------------------------------\n\n"
        f"--- Results ---\n"
    )
    for player_name, role_counts in results.items():
        detailed_string += f"\nDistribution for {player_name}:\n"
        sorted_roles = sorted(role_counts.items())
        for role, count in sorted_roles:
            percentage = (count / num_simulations) * 100
            expected = expected_percentages.get(role, 0)
            detailed_string += f"  - {role:<20}: {count:>6} times ({percentage:>6.2f}%) (Expected: ~{expected:.2f}%)\n"
    # --- High-Level Summary String (for the Discord message) ---
    logger.info("Generating high-level summary of the test results.")
    max_deviation = 0
    for player_name in player_names:
        for role_name in role_names:
            count = results[player_name].get(role_name, 0)
            percentage = (count / num_simulations) * 100
            expected = expected_percentages.get(role_name, 0)
            deviation = abs(percentage - expected)
            if deviation > max_deviation:
                max_deviation = deviation
    summary_string = (
        f"Ran **{num_simulations:,}** simulated role assignments for **{len(player_names)}** players.\n"
        f"• **Maximum Deviation Observed:** {max_deviation:.2f}%\n"
    )
    logger.info(f"Maximum deviation observed: {max_deviation:.2f}%")
    logger.info("Generating final summary string for Discord message.")
    if max_deviation > 2.0:
        summary_string += "• **Result:** ⚠️ High deviation detected. The distribution may be less random than expected.\n"
    else:
        summary_string += "• **Result:** ✅ Distribution appears to be fair and random.\n"
    summary_string += "\n*A detailed breakdown has been attached as a text file.*"
    logger.info("Role assignment randomness test completed successfully.")
    # Return both the summary and detailed strings
    return (summary_string, detailed_string)
