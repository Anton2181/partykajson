import pytest
from src.solver.solver import SATSolver

def test_rule_reordering_affects_cost(sample_team_members):
    """
    Verify that changing the order of rules in the ladder changes their assigned costs.
    """
    groups = [] # No groups needed for initialization cost check
    
    # Config A: Rule 1 higher than Rule 2
    config_a = {
        "ladder": ["Rule1", "Rule2"],
        "disabled_rules": [],
        "preferred_pairs": [],
        "time_limit_seconds": 10,
        "penalty_ratio": 10,
        "scope": {"max_human_effort": 8.0}
    }
    
    solver_a = SATSolver(groups, sample_team_members, config=config_a)
    cost_a_1 = solver_a.penalties.get_penalty_by_name("Rule1")
    cost_a_2 = solver_a.penalties.get_penalty_by_name("Rule2")
    
    # Expect Cost(Rule1) > Cost(Rule2) because Rule1 is higher priority (lower index)
    assert cost_a_1 > cost_a_2
    
    # Config B: Rule 2 higher than Rule 1
    config_b = {
        "ladder": ["Rule2", "Rule1"],
        "disabled_rules": [],
        "preferred_pairs": [],
        "time_limit_seconds": 10,
        "penalty_ratio": 10,
        "scope": {"max_human_effort": 8.0}
    }
    
    solver_b = SATSolver(groups, sample_team_members, config=config_b)
    cost_b_1 = solver_b.penalties.get_penalty_by_name("Rule1")
    cost_b_2 = solver_b.penalties.get_penalty_by_name("Rule2")
    
    # Expect Cost(Rule2) > Cost(Rule1)
    assert cost_b_2 > cost_b_1
    
    # Also verify specific values if ratio is 10
    # Rule 1 (Index 0) -> Cost 1000
    # Rule 2 (Index 1) -> Cost 100
    # (Assuming base scaling logic in SolverPenalties)
    
    # Check SolverPenalties logic implicitly via inequality
    assert cost_a_1 == cost_b_2 # Both at index 0
    assert cost_a_2 == cost_b_1 # Both at index 1

def test_config_overrides(sample_team_members):
    """
    Verify that explicit config overrides default file loading.
    """
    groups = []
    
    custom_config = {
        "ladder": ["CustomRule"],
        "disabled_rules": ["DisabledRule"],
        "preferred_pairs": [["A", "B"]],
        "time_limit_seconds": 999,
        "penalty_ratio": 5,
        "effort_threshold": 5.0 # Custom threshold
    }
    
    solver = SATSolver(groups, sample_team_members, config=custom_config)
    
    assert solver.time_limit == 999
    assert solver.penalty_ratio == 5
    assert solver.effort_threshold == 5.0
    assert solver.rule_definitions == ["CustomRule"]
    assert "DisabledRule" in solver.disabled_rules
    assert solver.preferred_pairs == [["A", "B"]]
