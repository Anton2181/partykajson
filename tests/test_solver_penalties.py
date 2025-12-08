
import pytest
from src.solver.solver import SATSolver

def test_cascading_multi_day_penalty(sample_team_members):
    # Setup: Alice works on 3 days in Week 1 -> Penalty should be (3-1)*P = 2P
    
    # Define simplified groups
    # We need Monday, Tuesday, Wednesday
    # IDs format: G{Week}_{DayNum}_{...}
    # Day mapping: Mon=1, Tue=2, Wed=3
    
    groups = [
        {"id": "G01_1_0_1", "name": "Task Mon", "week": 1, "day": "Monday", "filtered_candidates_list": ["Alice"], "family": "FamA", "task_count": 1},
        {"id": "G01_2_0_1", "name": "Task Tue", "week": 1, "day": "Tuesday", "filtered_candidates_list": ["Alice"], "family": "FamA", "task_count": 1},
        {"id": "G01_3_0_1", "name": "Task Wed", "week": 1, "day": "Wednesday", "filtered_candidates_list": ["Alice"], "family": "FamA", "task_count": 1},
    ]
    
    # Alice is the only candidate, she MUST be assigned to all 3.
    # Note: Ensure she has valid capacity or ignore capacity?
    # SATSolver normally uses penalties, so assignments are feasible if unassigned penalty is high properly ?
    # Actually, candidate list is strict.
    
    solver = SATSolver(groups, sample_team_members)
    # Mock config / Force params if needed? 
    # SATSolver reads config from disk. Assumes P_MULTI_WEEKDAY > 0.
    
    # Solve
    results, incurred_penalties = solver.solve()
    
    # Check results
    # Expect "Alice" to have "Role Diversity" (maybe) and "Multi-Day Weekdays"
    
    penalties = [p for p in incurred_penalties if p['person_name'] == "Alice"]
    
    # Find Multi-Day penalty
    md_penalty = next((p for p in penalties if "Multi-Day Weekdays" in p['rule']), None)
    
    assert md_penalty is not None, "Cascading Multi-Day Penalty not triggered"
    
    # Check Cost
    # We don't know exact 'P' from here easily without reading config, but check logic details
    assert "Cascading Penalty" in md_penalty['details']
    assert "Total Excess: 2" in md_penalty['details'] # 3 days - 1 = 2 excess

def test_cascading_role_diversity_penalty(sample_team_members):
    # Setup: Alice behaves, but misses families.
    # Families: A, B, C, D.
    # Alice capable of all.
    # Alice assigned ONLY to A.
    # Missed: B, C, D (3 families).
    # Expected Cost: Base * 2^(3-1) = Base * 4.
    
    groups = [
        {"id": "G01_1_0_1", "name": "Task A", "family": "FamA", "filtered_candidates_list": ["Alice"], "task_count": 1},
        {"id": "G01_1_0_2", "name": "Task B", "family": "FamB", "filtered_candidates_list": ["Alice"], "task_count": 1}, # Overlapping ID? use diff suffix
        {"id": "G01_1_0_3", "name": "Task C", "family": "FamC", "filtered_candidates_list": ["Alice"], "task_count": 1},
        {"id": "G01_1_0_4", "name": "Task D", "family": "FamD", "filtered_candidates_list": ["Alice"], "task_count": 1},
    ]
    
    # To ensure Alice works ONLY on A, we can manipulate candidates or just make other groups unassignable?
    # Or simpler: Alice Only candidate for A. But "capable" depends on 'candidates' list in group usually?
    # "Assignments in each capable family": checks if person IS CAPABLE (in candidates list).
    # So Alice must be in candidates list for A, B, C, D.
    # But we want her assigned only to A.
    # How? Maybe B, C, D have another candidate "Bob" who is cheaper/better? 
    # Or force assignments via manual property if solver supports it?
    # Solver supports 'assignee' key in group for pre-assignment?
    # Let's check solver code: "if group.get('assignee') == assigned_person: method = manual"
    # But does it ENFORCE it?
    # Yes, typically pre-assigned groups are fixed variables.
    # Let's try specifying assignee.
    
    groups[0]['assignee'] = "Alice" # Assigned A
    groups[1]['assignee'] = None    # B Unassigned (Or assigned to Bob)
    groups[1]['candidates'] = ["Bob"] # Wait, if Alice is not candidate for B, she isn't penalized for missing it!
    # Correct. Rule: "Assignments in each capable family"
    # So Alice MUST be in candidates of B, C, D.
    
    # Force Bob to take B, C, D
    groups[1]['candidates'] = ["Alice", "Bob"]
    groups[1]['assignee'] = "Bob"
    
    groups[2]['candidates'] = ["Alice", "Bob"]
    groups[2]['assignee'] = "Bob"
    
    groups[3]['candidates'] = ["Alice", "Bob"]
    groups[3]['assignee'] = "Bob"
    
    # Alice assignment to A
    groups[0]['assignee'] = "Alice"
    
    # IMPORTANT: "Assignee" in input group dict usually acts as a mandatory constraint in this solver?
    # I need to verify if SATSolver respects `group['assignee']`.
    # Code snippet viewed earlier: "if solver.Value(self.unassigned_vars[g_id]) == 1... else ... assigned_person = p"
    # It doesn't explicitly look for `group['assignee']` to FIX the var, unless `aggregate_groups` handled it?
    # `step_04` passes `groups` list.
    # Let's assume for this test we can force it by stripping Alice from candidates effectively? 
    # NO, if she is not candidate, no penalty.
    
    # Better strategy: Rely on unassigned penalty being lower than diversity penalty? 
    # Or make Bob the only candidate for B,C,D? NO, then Alice not capable.
    
    # Alternative: Use "Exclusive Groups" to prevent Alice from taking B,C,D?
    # Or simpler: Alice only works 1 day. B,C,D are on same day/time and she can't do parallel?
    # "id" implies time. 
    # Use same time for A, B, C, D?
    # If A, B, C, D are concurrent, Alice can only pick one (A).
    # Triggering misses for B, C, D.
    
    groups = [
        {"id": "G01_1_0_1", "name": "Task A", "week": 1, "day": "Monday", "family": "FamA", "candidates": ["Alice"], "task_count": 1},
        {"id": "G01_1_0_2", "name": "Task B", "week": 1, "day": "Monday", "family": "FamB", "candidates": ["Alice", "Bob"], "task_count": 1},
        {"id": "G01_1_0_3", "name": "Task C", "week": 1, "day": "Monday", "family": "FamC", "candidates": ["Alice", "Bob"], "task_count": 1},
        {"id": "G01_1_0_4", "name": "Task D", "week": 1, "day": "Monday", "family": "FamD", "candidates": ["Alice", "Bob"], "task_count": 1},
    ]
    
    # To force Alice to A:
    # Maybe leave Bob out of A. 
    # Bob takes B, C, D (if he can? concurrent?). 
    # Actually, if they are concurrent, Bob can only take 1 too.
    # We need Bob, Charlie, Dave to cover B, C, D.
    
    team = [
        {"name": "Alice", "role": "leader", "both": False},
        {"name": "Bob", "role": "leader", "both": False},
        {"name": "Charlie", "role": "leader", "both": False},
        {"name": "Dave", "role": "leader", "both": False},
    ]
    
    groups[0]['filtered_candidates_list'] = ["Alice"] # Only Alice
    groups[1]['filtered_candidates_list'] = ["Alice", "Bob"] # Alice capable, but Bob takes it
    groups[2]['filtered_candidates_list'] = ["Alice", "Charlie"] 
    groups[3]['filtered_candidates_list'] = ["Alice", "Dave"]
    
    # Bob, Charlie, Dave will take B, C, D respectively because Alice is busy with A (same time/day conflict?).
    # Wait, does solver infer time conflict from ID or explicit data?
    # ID splitting: G{Week}_{Day}_{Hour?}_{...}
    # Standard format: `G15_0_6_2`.
    # Code splits parts[0], parts[1].
    # parts[1] is DayNum?
    # Code ignores time overlap logic unless `exclusive` lists are provided?
    # Typically strict conflict logic isn't in basic SATSolver unless added.
    # BUT, `P_INTRA_COOLDOWN` checks distinct groups in same week if linked.
    
    # Let's rely on `exclusive` list.
    # Mutually exclusive: A, B, C, D.
    all_excl = [["G01_1_0_1", "Task A"], ["G01_1_0_2", "Task B"], ["G01_1_0_3", "Task C"], ["G01_1_0_4", "Task D"]]
    for g in groups:
        g['exclusive_groups'] = [e for e in all_excl if e[0] != g['id']] 
    
    solver = SATSolver(groups, team)
    results, incurred_penalties = solver.solve()
    
    # Filter penalties for Alice
    penalties = [p for p in incurred_penalties if p.get('person_name') == "Alice"]
    div_penalty = next((p for p in penalties if "Role Diversity" in p['rule']), None)
    
    assert div_penalty is not None
    assert "Cascading Penalty" in div_penalty['rule'] or "Role Diversity (Cascading)" in div_penalty['rule']
    assert "Missed 3 families" in div_penalty['details']
    
