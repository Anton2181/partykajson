# Solver Architecture: Start to Finish

This document outlines the end-to-end process of the `SATSolver` class, from loading data to producing optimized assignments.

## 1. Initialization and Input Data
When `SATSolver(groups, team_members)` is initialized:
- **Groups**: A list of dictionaries representing tasks/shifts (e.g., `id`, `family`, `effort`, `candidate_list`).
- **Team Members**: A list of available people with their attributes.
- **Config**: The solver reads `data/penalty_config.json` to determine:
    - **Ladder**: The priority order of penalties.
    - **Ratio**: The geometric scaling factor (default 10).
    - **Effort Threshold**: The minimum effort required (default 8.0).

## 2. Variable Creation (The Search Space)
In `solve()`, the solver initializes the CP-SAT model and creates decision variables:

### A. Assignment Variables (`assignments`)
For every valid `(Group, Person)` pair, a boolean variable is created:
- `x_group_person = 1` implies Person is assigned to Group.
- `x_group_person = 0` implies Person is NOT assigned.
- **Filtering**: Variables are ONLY created if the person is a valid candidate for the group. This allows the UI to optimize the search space strictly.

### B. Unassigned Variables (`unassigned_vars`)
For every Group:
- `unassigned_group = 1` implies the group has NO assignee.

### C. Effort Variables (`effort_vars`)
For every Person:
- `effort_person` (Integer): The sum of effort from all assigned groups, scaled by 10 (e.g., 8.0 -> 80).

## 3. Constraints (The Rules of the Game)
The solver applies two types of constraints:

### A. Hard Constraints (Must be True)
1.  **Coverage**: Each group must have exactly ONE state: either 1 Assignee OR Unassigned = 1.
2.  **Mutual Exclusion**: A person cannot be assigned to two groups that clash (e.g., overlapping times).
3.  **Manual Overrides**: If the input JSON specifies an `assignee` for a group, the solver hard-codes that assignment to 1.

### B. Soft Constraints (Penalties)
These rules are added to the **Objective Function**. The solver tries to minimize the total cost.
- **See `PENALTIES.md`** for the full list of rules.
- **Implementation**: Each rule calculates a `cost_var` (e.g., "Is working Tuesday and Wednesday?").
- **Accumulation**: `Total Cost = Sum(RuleCost * PenaltyPrice)`.

## 4. The Solve Process
1.  **Model Building**: All variables and constraints are added to the `cp_model.CpModel`.
2.  **Objective**: `model.Minimize(sum(objective_terms))`.
3.  **Solving**: `cp_model.CpSolver().Solve(model)` runs the Google OR-Tools CP-SAT engine.
    - It searches for a feasible solution that satisfies all Hard Constraints.
    - It iteratively refines the solution to find lower Objective Values (lower penalties).
4.  **Callback**: Reference `SolutionPrinter`.
    - As the solver finds better solutions, it reports the `Objective Value` and `Penalties Count` to the console live.

## 5. Output Generation
Once `OPTIMAL` or `FEASIBLE` status is reached:
1.  **Extraction**: The solver reads the final values (`solver.Value(var)`) for all assignment variables.
2.  **Reporting**:
    - **Assignments JSON**: Which person goes to which group.
    - **Penalties JSON**: A detailed breakdown of *why* a penalty was incurred (e.g., "Missed Role Diversity in Family X").
    - **Stats**: Total effort, deviation, and fairness metrics.

## Key Optimizations
- **Candidate Filtering**: Only creating variables for valid candidates drastically reduces the search space $O(N \cdot M) \to O(\text{Candidates})$.
- **Shared Computations**: Rules that check similar things (e.g., "Teaching Preference" and "Teaching Equality") share intermediate boolean logic to avoid redundant work.
- **Table Lookups**: Complex math (like squared deviation) is pre-computed into array lookups (`AddElement`) for O(1) solver access.
