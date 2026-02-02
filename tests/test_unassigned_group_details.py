
import pytest
from src.solver.solver import SATSolver

def test_unassigned_group_details_include_id():
    # Setup: Group with no candidates -> Guaranteed Unassigned
    group_id = "G_TEST_ID_123"
    group_name = "Test Group"
    
    groups = [
        {
            "id": group_id,
            "name": group_name,
            "week": 1,
            "day": "Monday",
            "family": "TestFam",
            "task_count": 1,
            "candidates_list": [], # No candidates
            "filtered_candidates_list": []
        }
    ]
    
    team = [
        {"name": "Alice", "role": "leader"}
    ]
    
    solver = SATSolver(groups, team)
    
    # Solve
    results, incurred_penalties = solver.solve()
    
    # Find Unassigned Penalty
    penalty = next((p for p in incurred_penalties if p['rule'] == "Unassigned Group"), None)
    
    assert penalty is not None, "Expected 'Unassigned Group' penalty not found."
    
    # Verify ID is in details
    # We expect something like "Group: Test Group (ID: G_TEST_ID_123)"
    print(f"DEBUG: Penalty Details: {penalty['details']}")
    assert f"(ID: {group_id})" in penalty['details'], \
        f"Group ID {group_id} not found in penalty details: '{penalty['details']}'"
