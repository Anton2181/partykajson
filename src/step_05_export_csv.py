import pandas as pd
import json
from pathlib import Path
import numpy as np

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def export_csv_for_month(month="january", year="2026"):
    # Use CWD-relative data path
    base_dir = Path(".")
    data_dir = base_dir / "data"
    results_dir = data_dir / "results"
    raw_dir = data_dir / "raw"
    processed_dir = data_dir / "processed" # Needed? groups_path uses it.

    # 1. Determine Prefix
    penalty_config_path = data_dir / "penalty_config.json"
    source_prefix = None
    
    if penalty_config_path.exists():
        config = load_json(penalty_config_path)
        if not source_prefix:
            scope = config.get("scope", {})
            if "month" in scope and "year" in scope:
                source_prefix = f"{scope['month'].lower()}_{scope['year']}"
            else:
                source_prefix = scope.get("prefix", "january_2026")
    else:
        if not source_prefix:
             source_prefix = "january_2026"

    print(f"Exporting for prefix: {source_prefix}")

    # 2. Load Input Data
    # A. Raw CSV (Source of Truth for ordering/structure)
    raw_csv_path = raw_dir / f"{source_prefix}.csv"
    if not raw_csv_path.exists():
        print(f"Error: Raw CSV not found at {raw_csv_path}")
        return

    jan_df = pd.read_csv(raw_csv_path, encoding='utf-8')
    
    # B. Groups Definition (Maps Task ID <-> Group)
    groups_path = processed_dir / f"{source_prefix}_groups.json"
    groups = load_json(groups_path)
    
    # C. Assignments (Maps Group <-> Assignee)
    assignments_path = results_dir / f"{source_prefix}_assignments.json"
    if not assignments_path.exists():
        print(f"Error: Assignments file not found at {assignments_path}. Run solver first.")
        return
        
    assignments = load_json(assignments_path)

    # 3. Build Assignment Map (Task ID -> Assignee)
    task_id_to_assignee = {}
    
    # Map Group ID -> Assignee
    # The assignments JSON is {GroupID: AssigneeName} or {GroupID: {assignee: ..., method: ...}}
    # Let's inspect the structure from previous steps. 
    # Based on previous output: "G15_7_1_1": {"group_name": "...", "assignee": "Name", ...}
    
    for group in groups:
        g_id = group['id']
        
        # Determine Assignee
        assigned_person = None
        
        # Check solver output first
        if g_id in assignments:
            val = assignments[g_id]
            if isinstance(val, dict):
                assigned_person = val.get('assignee')
            else:
                # Fallback if simple key-value (older versions?)
                assigned_person = val
        
        # Fallback to group definition (Manual assignments)
        if not assigned_person:
            assigned_person = group.get('assignee')
            
        if assigned_person:
            # Propagate to all tasks in this group
            for task_ref in group['tasks']:
                 # task_ref is [id, name]
                 t_id = task_ref[0]
                 task_id_to_assignee[t_id] = assigned_person

    print(f"Mapped {len(task_id_to_assignee)} tasks to assignees.")

    # 4. Process CSV and Fill
    # Logic copied from step_02_convert_data.py to recreate Task IDs
    
    # helper structures for ID generation
    daily_task_registry = {} 
    DAY_NUM_MAP = {
        "Monday": 1, "Tuesday": 2, "Wednesday": 3, "Thursday": 4,
        "Friday": 5, "Saturday": 6, "Sunday": 7
    }
    occurrence_tracker = {}
    
    # Prepare Output Columns
    # We want to fill 'Assignee' column. Ensure it exists.
    if 'Assignee' not in jan_df.columns:
        jan_df['Assignee'] = None
        
    # Iterate and Fill
    # Using index to update directly
    for idx, row in jan_df.iterrows():
        # --- ID Generation Logic (MUST BE EXACT MATCH TO STEP 02) ---
        week = row.get('Week')
        day = row.get('Day')
        time_slot = row.get('Time')
        name = row.get('TODO')
        
        # Skip empty names/breaklines
        if pd.isna(name): continue
        
        # Clean week
        if pd.notna(week) and isinstance(week, float) and week.is_integer():
             week_num = int(week)
        elif pd.notna(week) and str(week).strip() != "":
             try:
                week_num = int(week)
             except:
                week_num = 0
        else:
             week_num = 0

        day_num = DAY_NUM_MAP.get(day, 0)
        
        # Determine Task Num
        context_key = (week_num, day_num)
        if context_key not in daily_task_registry:
            daily_task_registry[context_key] = {}
        
        task_norm_name = str(name).strip()
        
        if task_norm_name not in daily_task_registry[context_key]:
            daily_task_registry[context_key][task_norm_name] = len(daily_task_registry[context_key]) + 1
            
        task_num = daily_task_registry[context_key][task_norm_name]

        # Key for repetition tracking
        # key = (week, day, time_slot, name) - Watch generic types in pandas (NaN != None)
        # step_02 used: key = (week, day, time_slot, name) directly from row.get
        # But we need to be careful about equality checks.
        
        key = (week, day, time_slot, name)
        
        if key not in occurrence_tracker:
            occurrence_tracker[key] = 0
        occurrence_tracker[key] += 1
        
        repeat_index = occurrence_tracker[key]
        
        task_id = f"T{week_num}_{day_num}_{task_num}_{repeat_index}"
        
        # --- Fill Logic ---
        if task_id in task_id_to_assignee:
            jan_df.at[idx, 'Assignee'] = task_id_to_assignee[task_id]

    # 5. Sanitize Output (Remove newlines that break simple parsers)
    # Replace \n and \r with spaces in all object (string) columns
    print("Sanitizing output (removing newlines)...")
    for col in jan_df.columns:
        if jan_df[col].dtype == 'object':
            # Use regex to replace newlines/carriage returns
            jan_df[col] = jan_df[col].replace(r'[\r\n]+', ' ', regex=True)

    # 6. Save Output
    output_path = results_dir / f"{source_prefix}_filled.csv"
    
    # Use standard CSV settings
    jan_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"Exported filled CSV to {output_path}")

if __name__ == "__main__":
    export_csv_for_month()
