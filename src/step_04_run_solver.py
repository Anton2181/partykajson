
import json
import pathlib
import sys

# Add project root to sys.path to allow running as script
root_dir = str(pathlib.Path(__file__).parent.parent)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from src.solver.solver import SATSolver

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def run_solver(source_prefix=None):
    base_dir = pathlib.Path(__file__).parent.parent
    processed_dir = base_dir / "data" / "processed"
    data_dir = base_dir / "data"
    results_dir = base_dir / "data" / "results"
    
    # Ensure results directory exists
    results_dir.mkdir(parents=True, exist_ok=True)
    
    # Load Config to determine scope if not provided
    penalty_config_path = data_dir / "penalty_config.json"
    if penalty_config_path.exists():
        config = load_json(penalty_config_path)
        if not source_prefix:
            scope = config.get("scope", {})
            if "month" in scope and "year" in scope:
                source_prefix = f"{scope['month'].lower()}_{scope['year']}"
                print(f"Generated source prefix from config: {source_prefix}")
            else:
                source_prefix = scope.get("prefix", "january_2026")
                print(f"Using scope prefix from config: {source_prefix}")
    else:
        if not source_prefix:
             source_prefix = "january_2026"
             print("Config not found, defaulting to january_2026")

    groups_file = processed_dir / f"{source_prefix}_groups.json"
    team_file = data_dir / "team_members.json"

    print(f"Loading groups from {groups_file}...")
    groups = load_json(groups_file)
    team_members = load_json(team_file)

    print("Initializing Solver...")
    solver = SATSolver(groups, team_members)
    
    print("Solving...")
    assignments, penalties = solver.solve()
    
    # Sort penalties: Cost (Desc) -> Rule (Asc)
    penalties.sort(key=lambda x: (-x['cost'], x['rule']))

    output_path = results_dir / f"{source_prefix}_assignments.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(assignments, f, indent=4, ensure_ascii=False)
        
    penalties_path = results_dir / f"{source_prefix}_penalties.json"
    with open(penalties_path, 'w', encoding='utf-8') as f:
        json.dump(penalties, f, indent=4, ensure_ascii=False)
        
    print(f"Assignments saved to {output_path}")
    print(f"Penalties saved to {penalties_path}")
    
    # Generate Person Report
    person_report_path = results_dir / f"{source_prefix}_assignments_by_person.json"
    save_person_report(assignments, penalties, groups, person_report_path)
    print(f"Person report saved to {person_report_path}")

    # Generate Effort Chart
    chart_path = results_dir / f"{source_prefix}_effort_chart.png"
    generate_effort_chart(assignments, groups, chart_path)
    print(f"Effort chart saved to {chart_path}")

def save_person_report(assignments, penalties, groups, output_path):
    # assignments: dict of group_id -> {assignee, method, ...}
    # penalties: list of {person_name, rule, cost, details, ...}
    
    group_map = {g['id']: g for g in groups}
    person_data = {}
    
    # 1. Map Assignments to People
    for g_id, res in assignments.items():
        person = res.get('assignee')
        if not person: continue
        
        if person not in person_data:
            person_data[person] = {
                "assignments": [],
                "penalties": []
            }
            
        group = group_map.get(g_id)
        if not group: continue
        
        person_data[person]["assignments"].append({
            "week": group.get('week'),
            "day": group.get('day'),
            "group_name": group.get('name'),
            "family": group.get('family'),
            "role": group.get('role'),
            "group_id": g_id
        })
        
    # 2. Map Penalties to People
    for p in penalties:
        # Some penalties are group-based (Unassigned), skip those here unless we want to list them under "Unassigned" person?
        # User asked for "person-week-day-groups-rule broken". "Unassigned" isn't a person.
        person = p.get('person_name')
        if not person: continue # Skip group penalties
        
        if person not in person_data:
            person_data[person] = {
                "assignments": [],
                "penalties": []
            }
            
        person_data[person]["penalties"].append({
            "rule": p.get('rule'),
            "cost": p.get('cost'),
            "details": p.get('details')
        })
        
    # 3. Sort Assignments by Week/Day
    for person in person_data:
        # Sort assignments: Week (asc), Day (custom order if needed, but string comp Tue<Wed works or map)
        # Week is int. Day is string.
        # Simple tuple sort (week, day)
        person_data[person]["assignments"].sort(key=lambda x: (x.get('week', 0), x.get('day') or ''))
        
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(person_data, f, indent=4, ensure_ascii=False)

def generate_effort_chart(assignments, groups, output_path, args=None):
    import matplotlib.pyplot as plt
    import numpy as np

    # 1. Map Group ID -> Effort and Original Assignee
    # groups contains the INPUT state
    group_map = {g['id']: g for g in groups}
    
    # 2. Pre-calculate N-for-N Forced Groups
    # Group by (Name, Week, Day) context to find "N candidates for N repeats"
    from collections import defaultdict
    context_groups = defaultdict(list)
    for g in groups:
        # Use a tuple key: (name, week, day)
        # Note: day might be None for Planning, but that's handled in aggregation now
        key = (g['name'], g['week'], g['day'])
        context_groups[key].append(g)
        
    forced_n_for_n_ids = set()
    for key, grps in context_groups.items():
        n_groups = len(grps)
        # Get union of all candidates for these groups
        all_candidates = set()
        for g in grps:
            # Use filtered if available, else full list
            cands = g.get('filtered_candidates_list')
            if not cands: 
                cands = g.get('candidates_list', [])
            all_candidates.update(cands)
            
        # Condition: If N groups == N unique candidates, all are forced (1-to-1)
        if n_groups > 0 and len(all_candidates) == n_groups:
            for g in grps:
                forced_n_for_n_ids.add(g['id'])

    # 3. Aggregate Effort per Person (Manual vs Auto)
    manual_effort = {}
    auto_effort = {}
    
    # Track all people encountered
    all_people = set()

    for g_id, details in assignments.items():
        person = details.get('assignee')
        if not person:
            continue
            
        all_people.add(person)
        effort = group_map.get(g_id, {}).get('effort', 0.0)

        # Check if this group was pre-assigned or effectively forced
        original_group = group_map.get(g_id)
        is_manual = False
        
        if original_group:
            # A. Explicitly assigned
            if original_group.get('assignee'):
                is_manual = True
            else:
                # B. Priority Assignment
                # If the assigned person was a priority candidate
                p_cands = original_group.get('priority_candidates_list', [])
                if person in p_cands:
                    is_manual = True
                
                # C. Single Candidate (Only 1 option)
                candidates = original_group.get('filtered_candidates_list')
                if not candidates:
                    candidates = original_group.get('candidates_list', [])
                if candidates and len(candidates) == 1:
                    is_manual = True
                    
                # D. N-for-N Forced
                if g_id in forced_n_for_n_ids:
                    is_manual = True
        
        if is_manual:
            manual_effort[person] = manual_effort.get(person, 0.0) + effort
        else:
            auto_effort[person] = auto_effort.get(person, 0.0) + effort
            
    # 4. Sort by Total Effort (Rising)
    people_sorted = sorted(list(all_people), key=lambda p: manual_effort.get(p, 0) + auto_effort.get(p, 0))
    
    if not people_sorted:
        print("No assignments to plot.")
        return

    manual_vals = [manual_effort.get(p, 0.0) for p in people_sorted]
    auto_vals = [auto_effort.get(p, 0.0) for p in people_sorted]
    
    # 5. Plot (Vertical Stacked Bars)
    plt.figure(figsize=(12, 5))
    
    # Plot Manual (Blue)
    plt.bar(people_sorted, manual_vals, label="Manual/Prepass", color='tab:blue')
    # Plot Auto (Orange)
    plt.bar(people_sorted, auto_vals, bottom=manual_vals, label="Auto", color='tab:orange')
    
    plt.xticks(rotation=60, ha='right')
    plt.ylabel("Load (Effort)")
    plt.title("Per-person load (chosen model) — ascending, layered")
    plt.legend()
    
    # Add dashed line at y=8
    plt.axhline(y=8, color='black', linestyle='--')
    
    plt.tight_layout()
    # Save as SVG for infinite scalability/sharpness in GUI
    svg_path = output_path.with_suffix('.svg')
    plt.savefig(svg_path, format='svg')
    plt.close('all')

if __name__ == "__main__":
    run_solver()
