
import pytest
import json
from pathlib import Path
from src.solver.solver import SATSolver

def test_penalty_config_loading(sample_team_members):
    sample_groups = [] # Empty list is checking config loading, shouldn't crash __init__
    # Determine path to expected config
    config_path = Path(__file__).parent.parent / 'data' / 'penalty_config.json'
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    expected_ladder = config['ladder']
    
    # Initialize Solver
    solver = SATSolver(sample_groups, sample_team_members)
    
    # Check if loaded rules match
    assert solver.rule_definitions == expected_ladder
    
    # Check if time limit loaded
    assert solver.time_limit == config.get('time_limit_seconds', 30.0)

    # Check if penalty ratio loaded
    assert solver.penalty_ratio == config.get('penalty_ratio', 10)
    
    # Check if SolverPenalties was initialized with these rules
    # SolverPenalties maps rule string to index/cost
    # We can check if get_penalty_by_name works for the last rule
    last_rule = expected_ladder[-1]
    # Cost should be > 0 (assuming exponential decay doesn't hit 0)
    # Actually SolverPenalties logic is 1000 * (0.5)^i or something
    cost = solver.penalties.get_penalty_by_name(last_rule)
    assert cost > 0
    assert cost <= solver.penalties.get_penalty_by_name(expected_ladder[0])
