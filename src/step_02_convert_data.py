
import pandas as pd
import json
from pathlib import Path
import numpy as np


def process_task_availability(task_df):
    tasks_data = []
    
    # Fix missing "Name" column if it was read as "Unnamed: 0" or similar
    if "Name" not in task_df.columns:
        # Assuming the first column is the Name column
        task_df.rename(columns={task_df.columns[0]: "Name"}, inplace=True)

    # Columns 0 (Name) and 1 (Role) are metadata. The rest are tasks.
    name_col = "Name"
    
    # Identify task columns (skip Name and Role)
    # Be robust if header is different or if Role column is missing? 
    # Assuming fixed structure based on previous code: 3rd column onwards.
    if len(task_df.columns) > 2:
        task_columns = task_df.columns[2:]
    else:
        return []

    for task in task_columns:
        # Filter for candidates who said "Yes"
        candidates = task_df[task_df[task] == "Yes"][name_col].tolist()
        tasks_data.append({
            "name": task,
            "candidates": candidates
        })
    return tasks_data

def process_calendar_availability(cal_df):
    # Extract header rows
    weeks_row = cal_df.iloc[3]
    dates_row = cal_df.iloc[4]
    days_row = cal_df.iloc[5]
    
    # Extract data part (from row 7 onwards)
    data_df = cal_df.iloc[6:].reset_index(drop=True)
    
    calendar_data = {}
    
    # Propagation Logic
    PROPAGATION_MAP = {
        "All": ["All", "19-00", "19-22", "20-22", "21-00", "19-21", "19-20", "20-21", "21-22", "22-00"],
        "19-00": ["19-00", "19-22", "20-22", "21-00", "19-21", "19-20", "20-21", "21-22", "22-00"],
        "19-22": ["19-22", "19-21", "20-22", "19-20", "20-21", "21-22"],
        "19-21": ["19-21", "19-20", "20-21"],
        "19-20": ["19-20"],
        "20-22": ["20-22", "20-21", "21-22"],
        "21-00": ["21-00", "21-22", "22-00"],
        "20-21": ["20-21"],
        "21-22": ["21-22"],
        "22-00": ["22-00"],
    }

    col_start_index = 4
    num_cols = cal_df.shape[1]
    
    current_week = None
    
    for col_idx in range(col_start_index, num_cols):
        # Get metadata for this column
        week_val = weeks_row.iloc[col_idx]
        if pd.notna(week_val):
            current_week = week_val
            
        date_val = dates_row.iloc[col_idx]
        if pd.notna(date_val):
            date_val = pd.to_datetime(date_val).strftime('%Y-%m-%d')
        day_val = days_row.iloc[col_idx]
        
        # Skip if no valid week/day info
        if not current_week or pd.isna(day_val):
            continue
            
        # Initialize structure
        if current_week not in calendar_data:
            calendar_data[current_week] = {}
        
        if day_val not in calendar_data[current_week]:
            calendar_data[current_week][day_val] = {
                "date": date_val,
                "time_slots": {}
            }
            
        # Collect candidates for this slot
        for _, row in data_df.iterrows():
            candidate_name = row[1] # Name column
            availability = row[col_idx]
            
            if pd.isna(availability):
                continue
                
            # Normalize availability string
            raw_slot = str(availability).strip()
            
            # Get propagated slots
            target_slots = PROPAGATION_MAP.get(raw_slot, [])
            if not target_slots:
                continue

            for slot in target_slots:
                if slot not in calendar_data[current_week][day_val]["time_slots"]:
                     calendar_data[current_week][day_val]["time_slots"][slot] = []
                calendar_data[current_week][day_val]["time_slots"][slot].append(candidate_name)
    
    # Sort time slots for consistency
    for week_key in calendar_data:
        for day_key in calendar_data[week_key]:
            slots = calendar_data[week_key][day_key]["time_slots"]
            # Sort keys: "All" first/last or just alphabetical? 
            # Alphabetical: 20-21, 20-22, 21-00, 21-22, 22-00, All
            # This seems consistent.
            sorted_slots = dict(sorted(slots.items()))
            calendar_data[week_key][day_key]["time_slots"] = sorted_slots

    return calendar_data

def process_schedule(jan_df, tasks_data, calendar_data):
    jan_tasks_data = []
    occurrence_tracker = {}
    
    # helper structures for ID generation
    # key: (week, day) -> value: {task_name: task_num}
    daily_task_registry = {} 
    
    # Map strict day names to numbers
    DAY_NUM_MAP = {
        "Monday": 1, "Tuesday": 2, "Wednesday": 3, "Thursday": 4,
        "Friday": 5, "Saturday": 6, "Sunday": 7
    }

    # Day mapping (Full to Short) for Calendar Lookup
    DAY_SHORT_MAP = {
        "Monday": "Mon", "Tuesday": "Tue", "Wednesday": "Wed", "Thursday": "Thu",
        "Friday": "Fri", "Saturday": "Sat", "Sunday": "Sun"
    }

    # Create a map for quick task capability lookup
    task_candidate_map = {t['name']: set(t['candidates']) for t in tasks_data}

    for _, row in jan_df.iterrows():
        # Clean data
        week = row.get('Week')
        if pd.notna(week) and isinstance(week, float) and week.is_integer():
            week = int(week)
            
        day = row.get('Day')
        time_slot = row.get('Time')
        name = row.get('TODO')
        assignee = row.get('Assignee')
        effort_val = row.get('EFFORT')
        
        # Handle NaNs
        if pd.isna(assignee): assignee = None
        if pd.isna(day): day = None
        if pd.isna(time_slot): time_slot = None
        
        effort = 0.0
        if pd.notna(effort_val):
            try:
                effort = float(effort_val)
            except ValueError:
                effort = 0.0
            
        # Skip empty task names
        if pd.isna(name): continue
        
        # --- ID Generation Logic ---
        week_num = int(week) if (week is not None and week != "") else 0
        day_num = DAY_NUM_MAP.get(day, 0)
        
        # Determine Task Num for this (Week, Day) context
        context_key = (week_num, day_num)
        if context_key not in daily_task_registry:
            daily_task_registry[context_key] = {}
        
        task_norm_name = str(name).strip()
        
        if task_norm_name not in daily_task_registry[context_key]:
            daily_task_registry[context_key][task_norm_name] = len(daily_task_registry[context_key]) + 1
            
        task_num = daily_task_registry[context_key][task_norm_name]

        # Key for repetition tracking
        key = (week, day, time_slot, name)
        
        if key not in occurrence_tracker:
            occurrence_tracker[key] = 0
        occurrence_tracker[key] += 1
        
        repeat_index = occurrence_tracker[key]
        
        # Generate ID String: T{Week}_{Day}_{TaskNum}_{Repeat}
        task_id = f"T{week_num}_{day_num}_{task_num}_{repeat_index}"

        # --- Candidates Intersection Logic ---
        eligible_candidates = []
        
        # 1. Get candidates capable of doing this task
        capable_candidates = task_candidate_map.get(task_norm_name, set())
        
        if day is None:
             eligible_candidates = list(capable_candidates)
             eligible_candidates.sort()
        else:
            # 2. Get candidates available at this time
            available_candidates = set()
            
            if week and time_slot:
                week_key = f"Week {week}"
                short_day = DAY_SHORT_MAP.get(day, day)
                
                if week_key in calendar_data:
                    week_data = calendar_data[week_key]
                    if short_day in week_data:
                        day_data = week_data[short_day]
                        if "time_slots" in day_data:
                             normalized_slot = str(time_slot).strip()
                             if normalized_slot in day_data["time_slots"]:
                                 available_candidates = set(day_data["time_slots"][normalized_slot])
            
            # 3. Intersect
            if capable_candidates and available_candidates:
                eligible_candidates = list(capable_candidates.intersection(available_candidates))
                eligible_candidates.sort()
            elif not capable_candidates:
                 pass
            elif not available_candidates:
                 pass

        task_entry = {
            "id": task_id,
            "name": name,
            "repeat_index": repeat_index,
            "week": week,
            "day": day,
            "time_slot": time_slot,
            "assignee": assignee,
            "candidates": eligible_candidates,
            "effort": effort
        }
        jan_tasks_data.append(task_entry)
        
    return jan_tasks_data

import sys

def convert_data(target_month=None):
    base_dir = Path(".")
    raw_dir = base_dir / "data" / "raw"
    processed_dir = base_dir / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    # Determine Target Month
    if target_month is None:
        if len(sys.argv) > 1:
            target_month = sys.argv[1].lower().replace(" ", "_")
        else:
             target_month = "january_2026" # Default
             
    print(f"Target Month: {target_month}")

    # --- Process Task Availability ---
    print("Processing Task Availability...")
    task_df = pd.read_csv(raw_dir / "task_availability.csv", encoding='utf-8')
    tasks_data = process_task_availability(task_df)

    # Save tasks.json
    tasks_output_path = processed_dir / "tasks.json"
    with open(tasks_output_path, "w", encoding='utf-8') as f:
        json.dump(tasks_data, f, indent=4, ensure_ascii=False)
    print(f"Saved tasks to {tasks_output_path}")

    # --- Process Calendar Availability ---
    print("Processing Calendar Availability...")
    cal_df = pd.read_csv(raw_dir / "calendar_availability.csv", header=None, encoding='utf-8')
    calendar_data = process_calendar_availability(cal_df)
    
    # Save calendar.json
    calendar_output_path = processed_dir / "calendar.json"
    with open(calendar_output_path, "w", encoding='utf-8') as f:
        json.dump(calendar_data, f, indent=4, ensure_ascii=False)
        
    print(f"Saved calendar to {calendar_output_path}")

    # --- Process Target Schedule ---
    print(f"Processing {target_month} Schedule...")
    input_csv = raw_dir / f"{target_month}.csv"
    
    if not input_csv.exists():
        print(f"[ERROR] Input file not found: {input_csv}")
        # Identify what files ARE there to be helpful
        found = list(raw_dir.glob("*_20*.csv"))
        if found:
            print(f"Found similar files: {[f.name for f in found]}")
        return

    jan_df = pd.read_csv(input_csv, encoding='utf-8')
    jan_tasks_data = process_schedule(jan_df, tasks_data, calendar_data)

    # Save
    yan_output_path = processed_dir / f"{target_month}_tasks.json"
    with open(yan_output_path, "w", encoding='utf-8') as f:
        json.dump(jan_tasks_data, f, indent=4, ensure_ascii=False)
    print(f"Saved monthly schedule to {yan_output_path}")

if __name__ == "__main__":
    convert_data()
