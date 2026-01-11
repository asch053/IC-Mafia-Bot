import json
import itertools

# Define the Factors and Levels
factors = {
    "Factor_A_Mafia_Smart": [0.1, 0.2],
    "Factor_B_Town_Smart": [0.6,0.6],
    "Factor_C_Base_Intuition": [0.65, 0.75],
    "Factor_D_Hard_Bandwagon": [0.65, 0.75],
    "Factor_E_Soft_Bandwagon": [0.45, 0.55],
    "Factor_F_Curious_Bandwagon": [0.1, 0.1]
}

# Generate all combinations (Cartesian product)
keys = list(factors.keys())
values = list(factors.values())
combinations = list(itertools.product(*values))

doe_suite = []

for i, combo in enumerate(combinations, 1):
    scenario = {
        "Scenario_ID": f"Scenario_{i:02d}",  # e.g., Scenario_01
        "Parameters": {
            "PROBABILITY_MAFIA_SMART": combo[0],
            "PROBABILITY_TOWN_SMART": combo[1],
            "BASE_INTUITION": combo[2],
            "PROBABILITY_HARD_BANDWAGON": combo[3],
            "PROBABILITY_SOFT_BANDWAGON": combo[4],
            "PROBABILITY_CURIOUS_BANDWAGON": combo[5]
        }
    }
    doe_suite.append(scenario)

# Write to JSON file
filename = "mafia_doe_scenarios.json"
with open(filename, "w") as f:
    json.dump(doe_suite, f, indent=4)

print(f"Successfully created '{filename}' with {len(doe_suite)} scenarios.")