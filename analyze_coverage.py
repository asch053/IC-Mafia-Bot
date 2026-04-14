import ast
import os
import json

def get_functions_and_classes(filepath):
    if not os.path.exists(filepath):
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        try:
            tree = ast.parse(f.read(), filename=filepath)
        except Exception as e:
            return [{"error": str(e)}]
    
    items = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            items.append({
                "type": "function",
                "name": node.name,
                "args": [arg.arg for arg in node.args.args]
            })
        elif isinstance(node, ast.ClassDef):
            methods = []
            for item in node.body:
                if isinstance(item, ast.FunctionDef) or isinstance(item, ast.AsyncFunctionDef):
                    methods.append({
                        "name": item.name,
                        "args": [arg.arg for arg in item.args.args]
                    })
            items.append({
                "type": "class",
                "name": node.name,
                "methods": methods
            })
    return items

source_files = [
    "game/actions.py", "game/engine.py", "game/narration_ai.py",
    "game/narration_static.py", "game/narration.py", "game/player.py",
    "game/roles.py", "game/setup_generator.py", "cogs/admin.py",
    "cogs/export.py", "cogs/game.py", "cogs/info.py", "cogs/stats.py",
    "game/statistics/fame.py"
]

test_files = [
    "tests/test_0_logging.py", "tests/test_1_engine.py", "tests/test_2_action.py",
    "tests/test_4_narration.py", "tests/test_5_statistics.py",
    "tests/test_6_utilities.py", "tests/test_randomness.py"
]

report = {
    "sources": {},
    "tests": {}
}

for sf in source_files:
    report["sources"][sf] = get_functions_and_classes(sf)

for tf in test_files:
    report["tests"][tf] = get_functions_and_classes(tf)

with open("analysis_report.json", "w", encoding='utf-8') as f:
    json.dump(report, f, indent=2)
