
import pytest
import pandas as pd
from src.step_02_convert_data import process_task_availability, process_calendar_availability, process_schedule

def test_process_task_availability(sample_task_availability_csv):
    df = pd.read_csv(sample_task_availability_csv)
    result = process_task_availability(df)
    
    assert len(result) == 2
    t1 = next(t for t in result if t['name'] == 'Task1')
    assert set(t1['candidates']) == {'Alice', 'Bob'}
    
    t2 = next(t for t in result if t['name'] == 'Task2')
    assert set(t2['candidates']) == {'Bob', 'Charlie'}

def test_process_calendar_availability(sample_calendar_availability_csv):
    df = pd.read_csv(sample_calendar_availability_csv, header=None)
    result = process_calendar_availability(df)
    
    assert "Week 1" in result
    assert "Monday" in result["Week 1"]
    
    slots = result["Week 1"]["Monday"]["time_slots"]
    # Alice: 20-22 -> 20-21, 21-22
    # Also 20-21 explicitly Yes
    
    # Bob: 21-22 Yes
    
    # 20-21 should have Alice
    assert "Alice" in slots["20-21"]
    
    # 21-22 should have Alice (from 20-22) and Bob
    assert "Alice" in slots["21-22"]
    assert "Bob" in slots["21-22"]

def test_process_schedule_basic():
    # Mock Inputs
    jan_df = pd.DataFrame([
        {"Week": 1, "Day": "Monday", "Time": "20-21", "TODO": "Task A", "Assignee": None, "EFFORT": 1.5},
        {"Week": 1, "Day": "Monday", "Time": "20-21", "TODO": "Task A", "Assignee": "Bob", "EFFORT": 2.2}
    ])
    
    tasks_data = [{"name": "Task A", "candidates": ["Alice", "Bob"]}]
    
    calendar_data = {
        "Week 1": {
            "Mon": { 
                 "time_slots": {
                     "20-21": ["Alice"]
                 }
            }
        }
    }
    
    result = process_schedule(jan_df, tasks_data, calendar_data)
    
    assert len(result) == 2
    
    # First task: No assignee. Candidate intersection.
    # Capable: Alice, Bob. Available: Alice.
    # Result: Alice.
    t1 = result[0]
    assert t1['candidates'] == ['Alice']
    assert t1['effort'] == 1.5
    
    # Second task: Assignee Bob.
    t2 = result[1]
    t2['assignee'] == 'Bob' 
    t2['effort'] == 2.2

def test_convert_data_dynamic_args(tmp_path, monkeypatch):
    """Verify convert_data creates files with the correct prefix."""
    from src.step_02_convert_data import convert_data
    import sys
    import os
    
    # Setup Dirs
    (tmp_path / "data" / "raw").mkdir(parents=True)
    (tmp_path / "data" / "processed").mkdir(parents=True)
    
    # Create input CSV
    target_prefix = "february_2026"
    csv_path = tmp_path / "data" / "raw" / f"{target_prefix}.csv"
    csv_path.write_text("Week,Day,Time,TODO,Assignee,EFFORT\n1,Monday,20-21,TaskA,,1.0", encoding='utf-8')

    # Create dummy Task Availability
    (tmp_path / "data" / "raw" / "task_availability.csv").write_text("Name,Role,TaskA\nAlice,Leader,Yes\nBob,Follower,Yes", encoding='utf-8')
    
    # Create dummy Calendar Availability
    # Needs specific structure to pass process_calendar_availability check
    # Row 3: Weeks, Row 4: Dates, Row 5: Days
    # Row 6+: Data
    # Create dummy Calendar Availability
    # Needs specific structure to pass process_calendar_availability check
    # Row 3: Weeks, Row 4: Dates, Row 5: Days
    # Row 6+: Data
    # 5 dummy columns + 1 data column at index 5 ? 
    # Logic: col_start_index = 4. 
    # Col 0,1,2,3 ignored/metadata? 
    # Col 4 is first data col.
    # Let's make 10 cols to be safe.
    
    cal_content = (
        ",,,,,,,,,\n" * 3 + # 0, 1, 2
        ",,,,Week 1,,,,,\n" + # 3 (Weeks)
        ",,,,2026-01-01,,,,,\n" + # 4 (Dates)
        ",,,,Monday,,,,,\n" + # 5 (Days)
        "Name,Role,Other,Col3,Col4,,,,,\n" # 6 (Header) 
        ",Alice,Leader,,All,,,,,\n"
    )
    (tmp_path / "data" / "raw" / "calendar_availability.csv").write_text(cal_content, encoding='utf-8')
    
    # Change CWD to tmp_path so "Path('.')" works there.
    monkeypatch.chdir(tmp_path)
    
    convert_data(target_month=target_prefix)
         
    # Check output
    output_path = tmp_path / "data" / "processed" / f"{target_prefix}_tasks.json"
    assert output_path.exists(), f"File not found at {output_path}"


def test_process_schedule_manual_override_unavailability():
    # Scenario: Alice is NOT available in calendar, but manually assigned to Task A.
    
    # Mock Schedule: Alice assigned
    jan_df = pd.DataFrame([
        {"Week": 1, "Day": "Monday", "Time": "20-21", "TODO": "Task A", "Assignee": "Alice", "EFFORT": 1.0}
    ])
    
    # Task Def: Alice is capable
    tasks_data = [{"name": "Task A", "candidates": ["Alice", "Bob"]}]
    
    # Calendar: Alice NOT available (only Bob is)
    calendar_data = {
        "Week 1": {
            "Mon": { 
                 "time_slots": {
                     "20-21": ["Bob"] # Alice missing
                 }
            }
        }
    }
    
    result = process_schedule(jan_df, tasks_data, calendar_data)
    
    assert len(result) == 1
    t = result[0]
    
    assert t['assignee'] == "Alice"
    # CRITICAL CHECK: Alice must be in 'candidates' list for the solver to respect the assignment
    # currently this likely fails (Alice filtered out because not in calendar)
    assert "Alice" in t['candidates'], "Manual assignee Alice should be in candidates list even if unavailable"
