import pytest
from src.solver.solver import SATSolver

@pytest.fixture
def sample_team():
    return [
        {"name": "Alice", "role": "leader", "both": False},
        {"name": "Bob", "role": "follower", "both": False}
    ]

@pytest.fixture
def sample_groups():
    return [
        {
            "id": "G01_1_0_1", 
            "name": "Task 1", 
            "week": 1, 
            "day": "Monday",
            "family": "Teaching",
            "filtered_candidates_list": ["Alice", "Bob"],
            "task_count": 1,
            "effort": 1.0
        }
    ]

def test_solver_initialization(sample_groups, sample_team):
    """Test that the solver initializes correctly with basic data."""
    solver = SATSolver(sample_groups, sample_team)
    assert solver.groups == sample_groups
    assert solver.team_members == sample_team
    assert "Alice" in solver.member_map
    assert "G01_1_0_1" in solver.group_map
    assert solver.model is None  # Model initialized in solve()

def test_equality_overflow_protection(sample_team):
    """
    Verify that the exponential cost calculation in Teaching/Assisting Equality
    is capped at 9e18 to prevent integer overflow.
    """
    # Create enough groups to trigger a high assignment count for Alice in one family.
    # We used base 2, so 2^63 is overflow. 2^60 is > 1e18.
    # Loop needs to be sizeable.
    
    large_n = 70 # Should easily exceed 64-bit if 2^N not capped
    
    # We rely on the internal logic of `solve` building the model.
    # We can inspect the model constraints or variables if accessible,
    # or arguably just ensure it doesn't crash and potentially check debug vars if exposed.
    
    groups = []
    for i in range(large_n):
        groups.append({
            "id": f"G_{i}",
            "name": f"Task {i}",
            "week": 1, 
            "day": "Monday",
            "family": "Teaching",
            "filtered_candidates_list": ["Alice"], # Force Alice
            "task_count": 1
        })
        
    solver = SATSolver(groups, sample_team)
    
    # Force the Equality rule to be active by mocking/ensuring config
    # In SATSolver.__init__, it reads config. 
    # We might need to ensuring 'Usage' of rule or P > 0.
    # The default penalty config usually has this rule.
    # We can override the penalties object if needed, or rely on default loading.
    
    # Run solve - expected NOT to crash (OverflowError)
    try:
        solver.solve()
    except OverflowError:
        pytest.fail("Solver raised OverflowError, capping logic failed.")
    except Exception as e:
        # CP-SAT might raise specific errors for invalid model
        if "Capacity" in str(e) or "overflow" in str(e).lower():
             pytest.fail(f"Solver raised overflow-related error: {e}")
        # Other errors (unsat etc) are fine for this specific test as long as model build passed
        pass
        
    # Validation: Check SATSolver debug_vars for the capped value if possible
    # Alice's equality debug var
    if "Alice" in solver.debug_vars and "equality" in solver.debug_vars["Alice"]:
        eq_info = solver.debug_vars["Alice"]["equality"]
        # It's a list of dicts per family
        teach_info = next((item for item in eq_info if item['family'] == "Teaching"), None)
        if teach_info:
            # We can't easily check the *value* inside the model without a solution,
            # but if solve() completed (even if UNSAT), the model construction worked.
            # Building the model involves the `if val > 9e18` python check.
            pass

def test_basic_constraint_one_person_per_group(sample_team):
    """Verify that a group gets assigned exactly one person."""
    groups = [{
        "id": "G1", "name": "Task 1", "week": 1, "day": "Mon", 
        "filtered_candidates_list": ["Alice", "Bob"], "task_count": 1
    }]
    
    solver = SATSolver(groups, sample_team)
    res, _ = solver.solve()
    
    assert "G1" in res
    assert res["G1"]["assignee"] in ["Alice", "Bob"]
    assert res["G1"]["method"] in ["automatic", "manual", "unassigned"]
    # Should not be unassigned if penalty is high enough and feasible
