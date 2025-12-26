import json
import re
from pathlib import Path
import pprint

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
SRC_DIR = BASE_DIR / "src"

def load_json(filename):
    path = DATA_DIR / filename
    if not path.exists():
        print(f"Warning: {filename} not found.")
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def write_python_file(path, variable_name, data):
    content = f"{variable_name} = {pprint.pformat(data, indent=4, width=100)}\n"
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Updated {path.name}")

def update_gui_file(ladder, preferred_pairs):
    gui_path = SRC_DIR / "gui.py"
    with open(gui_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Update DEFAULT_LADDER
    ladder_str = pprint.pformat(ladder, indent=4)
    pattern_ladder = re.compile(r'DEFAULT_LADDER = \[.*?\]', re.DOTALL)
    new_ladder_def = f"DEFAULT_LADDER = {ladder_str}"
    
    if pattern_ladder.search(content):
        content = pattern_ladder.sub(new_ladder_def, content)
        print("Updated DEFAULT_LADDER in gui.py")
    else:
        print("Warning: DEFAULT_LADDER definition not found in gui.py")

    # Update DEFAULT_PREFERRED_PAIRS
    pairs_str = pprint.pformat(preferred_pairs, indent=4)
    # Regex to handle list of lists: matches outer brackets and content that includes inner brackets
    # Matches: DEFAULT_PREFERRED_PAIRS = [ (non-brackets OR inner [...])* ]
    pattern_pairs = re.compile(r'DEFAULT_PREFERRED_PAIRS\s*=\s*\[(?:[^\]]|\[.*?\])*\]', re.DOTALL)
    new_pairs_def = f"DEFAULT_PREFERRED_PAIRS = {pairs_str}"
    
    if pattern_pairs.search(content):
        content = pattern_pairs.sub(new_pairs_def, content)
        print("Updated DEFAULT_PREFERRED_PAIRS in gui.py")
    else:
        print("Warning: DEFAULT_PREFERRED_PAIRS definition not found in gui.py")

    with open(gui_path, 'w', encoding='utf-8') as f:
        f.write(content)

def main():
    print("--- Updating Default Files ---")
    
    # 1. Team Members
    team_data = load_json("team_members.json")
    if team_data:
        write_python_file(SRC_DIR / "default_team.py", "DEFAULT_TEAM", team_data)

    # 2. Task Families
    families_data = load_json("task_families.json")
    if families_data:
        write_python_file(SRC_DIR / "default_families.py", "DEFAULT_FAMILIES", families_data)

    # 3. Penalty Config (GUI Defaults)
    penalty_config = load_json("penalty_config.json")
    if penalty_config:
        ladder = penalty_config.get("ladder", [])
        preferred_pairs = penalty_config.get("preferred_pairs", [])
        update_gui_file(ladder, preferred_pairs)

    print("--- Update Complete ---")

if __name__ == "__main__":
    main()
