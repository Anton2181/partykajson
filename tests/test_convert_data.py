
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
    assert t2['assignee'] == 'Bob' 
    assert t2['effort'] == 2.2
