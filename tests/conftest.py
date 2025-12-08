
import pytest
import pandas as pd
import json

@pytest.fixture
def sample_task_availability_csv(tmp_path):
    p = tmp_path / "task_availability.csv"
    p = tmp_path / "task_availability.csv"
    data = """Name,Role,Task1,Task2
Alice,Leader,Yes,No
Bob,Follower,Yes,Yes
Charlie,Leader,No,Yes
"""
    p.write_text(data, encoding='utf-8')
    return p

@pytest.fixture
def sample_calendar_availability_csv(tmp_path):
    # Mimic structure: 3 rows metadata, then weeks, dates, days
    # Row 3: Weeks
    # Row 4: Dates
    # Row 5: Days
    # Row 6+: Data
    # Col 0-3: Metadata
    p = tmp_path / "calendar_availability.csv"
    
    # Constructing a valid CSV string manually is tricky due to irregular structure.
    # Let's create a DataFrame and save it without header, 
    # but the reader expects header=None and explicit access.
    
    # 0,1,2,3 - metacolumns
    # 4,5 ... data columns
    
    data = [
        ["","","","","","",""], # 0
        ["","","","","","",""], # 1
        ["","","","","","",""], # 2
        ["","","","","Week 1","Week 1","Week 1"], # 3
        ["","","","","2026-01-01","2026-01-01","2026-01-01"], # 4
        ["","","","","Monday","Monday","Monday"], # 5
        # Row 6 is data start in code assumption (index 6, which is 7th row)
        # Cells must contain valid keys from PROPAGATION_MAP (e.g. "20-21", "20-22")
        ["t1","Alice","e1","L","20-21","","20-22"], # 6
        ["t2","Bob","e2","F","","21-22",""], # 7
    ]
    
    df = pd.DataFrame(data)
    df.to_csv(p, header=False, index=False)
    return p

@pytest.fixture
def sample_january_csv(tmp_path):
    p = tmp_path / "january_2026.csv"
    data = """Week,Day,Time,TODO,Assignee,EFFORT
1,Monday,20-21,Task1,,1.0
1,Monday,21-22,Task2,Bob,2.5
1,Tuesday,20-21,Task1,Alice,1.0
"""
    p.write_text(data, encoding='utf-8')
    return p

@pytest.fixture
def sample_tasks_list():
    return [
        {"id": "T1", "name": "Task A", "week": 1, "day": "Monday", "repeat_index": 1, "assignee": "Alice", "candidates": ["Alice", "Bob"], "effort": 1.0},
        {"id": "T2", "name": "Task B", "week": 1, "day": "Monday", "repeat_index": 1, "assignee": None, "candidates": ["Alice", "Bob"], "effort": 2.0},
        {"id": "T3", "name": "Task A", "week": 1, "day": "Monday", "repeat_index": 2, "assignee": None, "candidates": ["Alice", "Bob"], "effort": 1.0},
    ]

@pytest.fixture
def sample_task_families():
    return [
        {
            "name": "Family 1",
            "groups": [
                {
                    "name": "Group Alpha",
                    "tasks": ["Task A", "Task B"],
                    "leader-group-count": 1,
                    "follower-group-count": 0,
                    "any-group-count": 0,
                    "exclusive": [],
                    "PriorityAssignees": ["Alice"]
                }
            ]
        }
    ]

@pytest.fixture
def sample_team_members():
    return [
        {"name": "Alice", "role": "leader", "both": False},
        {"name": "Bob", "role": "follower", "both": True},
        {"name": "Charlie", "role": "leader", "both": True},
        {"name": "Dave", "role": "follower", "both": False},
    ]
