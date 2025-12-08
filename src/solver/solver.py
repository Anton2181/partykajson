from ortools.sat.python import cp_model
from src.solver.penalties import SolverPenalties
import math

class SolutionPrinter(cp_model.CpSolverSolutionCallback):
    def __init__(self):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.__solution_count = 0

    def OnSolutionCallback(self):
        self.__solution_count += 1
        print(f'Solution {self.__solution_count}, time = {self.WallTime():.2f} s, objective = {self.ObjectiveValue()}')

class SATSolver:
    def __init__(self, groups, team_members):
        self.groups = groups
        self.team_members = team_members
        self.member_map = {m['name']: m for m in team_members}
        self.group_map = {g['id']: g for g in groups}
        
        # Define Rules for Ladder
        # 1. Unassigned (Highest)
        # 2. Underworked (Effort < 8)
        # 3. Multi-Day Weekdays (First Rule)
        # 4. Min Tasks/Day
        # 5. Multi-Day General (Third Rule - Mixed)
        # Define Rules for Ladder
        # Loaded from data/penalty_config.json
        import json
        from pathlib import Path
        
        config_path = Path(__file__).parent.parent.parent / 'data' / 'penalty_config.json'
        with open(config_path, 'r') as f:
            t = json.load(f)
            self.rule_definitions = t['ladder'] # User said ladder is the sorted subsection
            self.time_limit = t.get('time_limit_seconds', 30.0)
            self.penalty_ratio = t.get('penalty_ratio', 10)
            
            # Or should I pass the full implemented_rules? 
            # SolverPenalties usually takes the ladder (the rules that determine cost).
            # The "implemented_rules" is likely for UI or validation.
            # I will use 'ladder' as the active rules list.
            
        self.penalties = SolverPenalties(self.rule_definitions, self.penalty_ratio)
        
        # Initialize model and variables here, as they are used across methods
        # and need to be reset if solve is called multiple times.
        # However, the instruction implies moving model creation to solve,
        # so we'll follow that and ensure other variables are also initialized there.
        self.model = None
        self.assignments = {} # (group_id, person_name) -> BoolVar
        self.unassigned_vars = {} # group_id -> BoolVar
        self.effort_vars = {} # person_name -> IntVar (Scaled x10)
        self.underworked_vars = {} # person_name -> BoolVar

    def solve(self):
        self.model = cp_model.CpModel()
        
        # ----------------------
        # 1. Variables
        # ----------------------
        
        # Reset variables for a new solve call
        self.assignments = {}
        self.unassigned_vars = {}
        self.effort_vars = {}
        self.underworked_vars = {}
        self.debug_vars = {'unassigned': {}} # Initialize debugging structure

        self.debug_vars = {'unassigned': {}} # Initialize debugging structure

        # Filter persons: Only include those who are candidates in at least one group
        # This excludes members with 0 task availability from "Underworked" and other checks.
        active_candidates = set()
        for group in self.groups:
            active_candidates.update(self.get_group_candidates(group))
            
        all_persons = {m['name'] for m in self.team_members if m['name'] in active_candidates}
        
        # Assignment Variables
        for group in self.groups:
            candidates = self.get_group_candidates(group)
            for person in candidates:
                self.assignments[(group['id'], person)] = self.model.NewBoolVar(f"x_{group['id']}_{person}")
            
            self.unassigned_vars[group['id']] = self.model.NewBoolVar(f"unassigned_{group['id']}")

        # Effort Variables (Scaled x10)
        # Calculate dynamic upper bound based on total available effort
        total_effort = sum(group.get('effort', 0) for group in self.groups)
        max_scaled_effort = int(math.ceil(total_effort * 10))
        
        for person in all_persons:
            self.effort_vars[person] = self.model.NewIntVar(0, max_scaled_effort, f"effort_{person}")
            self.underworked_vars[person] = self.model.NewBoolVar(f"underworked_{person}")

        # 2. Constraints (Hard)
        
        # Coverage & Hard Priority
        for group in self.groups:
            g_id = group['id']
            priority_list = group.get('filtered_priority_candidates_list', [])
            all_candidates = self.get_group_candidates(group)
            
            # Constraint: Sum(Assignees) + Unassigned == 1
            possible_vars = [self.assignments[(g_id, p)] for p in all_candidates if (g_id, p) in self.assignments]
            if not possible_vars:
                self.model.Add(self.unassigned_vars[g_id] == 1)
            else:
                self.model.Add(sum(possible_vars) + self.unassigned_vars[g_id] == 1)
            
            # Hard Priority Rule
            # If priority candidates exist, we MUST pick one of them (OR be unassigned).
            # We cannot pick a non-priority candidate.
            
            # EXCEPTION: If manually assigned, do not enforce this (Manual overrides Priority).
            manual_assignee = group.get('assignee')
            
            if priority_list and not manual_assignee:
                # Identify non-priority candidates
                non_priority = [p for p in all_candidates if p not in priority_list]
                for np in non_priority:
                     if (g_id, np) in self.assignments:
                         # Force non-priority to 0
                         self.model.Add(self.assignments[(g_id, np)] == 0)

        # Mutual Exclusion
        group_map = {g['id']: g for g in self.groups}
        for group in self.groups:
            g_id = group['id']
            manual_assignee = group.get('assignee')
            
            if manual_assignee:
                 if (g_id, manual_assignee) in self.assignments:
                     self.model.Add(self.assignments[(g_id, manual_assignee)] == 1)
            
            for excl in group.get('exclusive_groups', []):
                excl_id = excl[0]
                if excl_id not in group_map: continue
                
                candidates_g = self.get_group_candidates(group)
                candidates_e = self.get_group_candidates(group_map[excl_id])
                common = set(candidates_g).intersection(candidates_e)
                
                for p in common:
                    if (g_id, p) in self.assignments and (excl_id, p) in self.assignments:
                        self.model.Add(self.assignments[(g_id, p)] + self.assignments[(excl_id, p)] <= 1)

        # 3. Soft Constraints (Min Effort)
        
        # Calculate Effort per Person
        # scaled_effort = floor(effort * 10)
        for person in all_persons:
            contributions = []
            for group in self.groups:
                if (group['id'], person) in self.assignments:
                    g_effort_val = group.get('effort', 0)
                    scaled_val = int(round(g_effort_val * 10))
                    contributions.append(self.assignments[(group['id'], person)] * scaled_val)
            
            if contributions:
                self.model.Add(self.effort_vars[person] == sum(contributions))
            else:
                self.model.Add(self.effort_vars[person] == 0)
                
            # Define Underworked: Effort < 8.0 (80 scaled)
            # underworked => effort < 80
            # !underworked => effort >= 80
            TARGET_EFFORT = 80
            
            self.model.Add(self.effort_vars[person] < TARGET_EFFORT).OnlyEnforceIf(self.underworked_vars[person])
            self.model.Add(self.effort_vars[person] >= TARGET_EFFORT).OnlyEnforceIf(self.underworked_vars[person].Not())


        # 4. Objective Function & Penalty Tracking
        objective_terms = []
        
        P_UNASSIGNED = self.penalties.get_penalty_by_name("Unassigned Group")
        P_UNDERWORKED = self.penalties.get_penalty_by_name("Underworked Team Member (< 8 Effort)")
        
        # Term 1: Unassigned Groups
        if P_UNASSIGNED > 0:
            for group in self.groups:
                objective_terms.append(self.unassigned_vars[group['id']] * P_UNASSIGNED)
            
        # Term 2: Underworked People
        if P_UNDERWORKED > 0:
            for person in all_persons:
                objective_terms.append(self.underworked_vars[person] * P_UNDERWORKED)

        # Term 3: Multi-Day Weekdays (e.g. Tue+Wed) -> "First Rule"
        P_MULTI_WEEKDAY = self.penalties.get_penalty_by_name("Multi-Day Weekdays (e.g. Tue+Wed)")
        
        # Term 4: Min Daily Tasks (Efficiency)
        P_INEFFICIENT = self.penalties.get_penalty_by_name("Inefficient Day (< 2 Tasks)")
        
        # Term 5: Multi-Day General (e.g. Tue+Sun) -> "Third Rule"
        P_MULTI_GENERAL = self.penalties.get_penalty_by_name("Multi-Day General (Weekday+Sunday)")
        
        # Term 6: Cooldowns (New)
        P_INTRA_COOLDOWN = self.penalties.get_penalty_by_name("Intra-Week Cooldown (Same Week)")
        P_COOLDOWN = self.penalties.get_penalty_by_name("Cooldown (Adjacent Weeks)")
        
        # Term 7: Role Diversity
        P_DIVERSITY = self.penalties.get_penalty_by_name("Role Diversity (Assignments in each capable family)")

        # --- Role Diversity Logic ---
        # "For each defined family in groups we want each person to do at least one assignment 
        # (if they're marked as a candidate for any)"
        if P_DIVERSITY > 0:
            # 1. Group Groups by Family
            family_groups = {}
            family_candidates = {} # family -> set of persons capable
            
            for group in self.groups:
                fam = group.get('family', 'Unknown')
                if fam not in family_groups:
                    family_groups[fam] = []
                    family_candidates[fam] = set()
                family_groups[fam].append(group['id'])
                family_candidates[fam].update(self.get_group_candidates(group))
            
            # 2. Iterate Families and Candidates
            for fam, groups_ids in family_groups.items():
                # For each person capable of this family
                for person in family_candidates[fam]:
                    if person not in all_persons: continue # Skip if inactive
                    
                    # Gather assignment vars for this person in this family
                    fam_vars = []
                    for gid in groups_ids:
                        if (gid, person) in self.assignments:
                            fam_vars.append(self.assignments[(gid, person)])
                    
                    if fam_vars:
                        # Bool: Has at least one assignment in family
                        # We want to PENALIZE if sum(fam_vars) == 0
                        # i.e., NOT(OR(fam_vars))
                        
                        missed_diversity = self.model.NewBoolVar(f"missed_div_{fam}_{person}")
                        
                        # logic: missed <-> sum == 0
                        self.model.Add(sum(fam_vars) == 0).OnlyEnforceIf(missed_diversity)
                        self.model.Add(sum(fam_vars) > 0).OnlyEnforceIf(missed_diversity.Not())
                        
                        objective_terms.append(missed_diversity * P_DIVERSITY)
                        
                        # Store for reporting
                        if person not in self.debug_vars:
                             self.debug_vars[person] = {}
                        if 'diversity' not in self.debug_vars[person]:
                             self.debug_vars[person]['diversity'] = {}
                        self.debug_vars[person]['diversity'][fam] = missed_diversity


        # --- Cooldown Logic ---
        # 1. Build Cooldown Graph (Directed: Earlier -> Later)
        cooldown_graph = {} # id -> list of next_ids
        
        # We also need to keep the "Pairwise" penalty logic.
        # But we can iterate the graph effectively.
        
        # Capture pairwise vars for reporting
        self.cooldown_penalty_vars = {} # (person, rule_name) -> list of vars
        
        for group in self.groups:
            g_id = group['id']
            if g_id not in cooldown_graph: cooldown_graph[g_id] = []
            
            # Intra-Week Cooldowns (Handle separately as they are not "geometric" across weeks usually)
            if P_INTRA_COOLDOWN > 0:
                for target in group.get('intra_cooldown_groups', []):
                    t_id = target[0]
                    # Enforce ordering to avoid double counting
                    if g_id < t_id and t_id in self.group_map:
                         candidates_g = set(self.get_group_candidates(group))
                         candidates_t = set(self.get_group_candidates(self.group_map[t_id]))
                         common = candidates_g.intersection(candidates_t)
                         
                         for person in common:
                             # Exemption Check: If BOTH are exempt (Manual/Prepass), skip penalty
                             if self.is_exempt_assignment(group, person) and \
                                self.is_exempt_assignment(self.group_map[t_id], person):
                                 continue

                             var_g = self.assignments.get((g_id, person))
                             var_t = self.assignments.get((t_id, person))
                             
                             if var_g is not None and var_t is not None:
                                 penalty_var = self.model.NewBoolVar(f'intra_pool_{g_id}_{t_id}_{person}')
                                 self.model.AddBoolAnd([var_g, var_t]).OnlyEnforceIf(penalty_var)
                                 self.model.AddBoolOr([var_g.Not(), var_t.Not()]).OnlyEnforceIf(penalty_var.Not())
                                 objective_terms.append(penalty_var * P_INTRA_COOLDOWN)
                                 
                                 # Track
                                 if person not in self.debug_vars: self.debug_vars[person] = {}
                                 if 'intra_cooldown' not in self.debug_vars[person]: self.debug_vars[person]['intra_cooldown'] = []
                                 self.debug_vars[person]['intra_cooldown'].append({
                                     'var': penalty_var,
                                     'details': f" Intra-week: {group['name']} & {self.group_map[t_id]['name']}"
                                 })

            # General Cooldowns (Adjacent Weeks) -> Build Graph
            if P_COOLDOWN > 0:
                for target in group.get('cooldown_groups', []):
                    t_id = target[0]
                    if t_id in self.group_map:
                        # Directed Edge: Only add if g_id is "before" t_id (e.g. Week 15 -> Week 16)
                        # Assumes ID sorting respects time or explicit check
                        # We use ID check to ensure acyclic / uniqueness
                        if g_id < t_id:
                            cooldown_graph[g_id].append(t_id)
                            
                            # Add Base Pairwise Penalty (Length 2)
                            candidates_g = set(self.get_group_candidates(group))
                            candidates_t = set(self.get_group_candidates(self.group_map[t_id]))
                            common = candidates_g.intersection(candidates_t)
                            
                            for person in common:
                                # Exemption Check: If BOTH are exempt, skip penalty
                                if self.is_exempt_assignment(group, person) and \
                                   self.is_exempt_assignment(self.group_map[t_id], person):
                                    continue

                                var_g = self.assignments.get((g_id, person))
                                var_t = self.assignments.get((t_id, person))
                                
                                if var_g is not None and var_t is not None:
                                    penalty_var = self.model.NewBoolVar(f'pool_{g_id}_{t_id}_{person}')
                                    self.model.AddBoolAnd([var_g, var_t]).OnlyEnforceIf(penalty_var)
                                    self.model.AddBoolOr([var_g.Not(), var_t.Not()]).OnlyEnforceIf(penalty_var.Not())
                                    objective_terms.append(penalty_var * P_COOLDOWN)
                                    
                                    # Track
                                    if person not in self.debug_vars: self.debug_vars[person] = {}
                                    if 'cooldown' not in self.debug_vars[person]: self.debug_vars[person]['cooldown'] = []
                                    self.debug_vars[person]['cooldown'].append({
                                        'var': penalty_var,
                                        'cost': P_COOLDOWN,
                                        'details': f"{group['name']} (W{group['week']}) & {self.group_map[t_id]['name']} (W{self.group_map[t_id]['week']})"
                                    })

        # 2. Geometric Penalties (Streaks > 2)
        # Find paths of length 3, 4, 5
        # DFS to find chains
        if P_COOLDOWN > 0:
            def find_chains(current_id, current_chain):
                # current_chain contains [id1, id2, ..., current_id]
                # Try to extend
                next_ids = cooldown_graph.get(current_id, [])
                if not next_ids:
                    return

                for nid in next_ids:
                    new_chain = current_chain + [nid]
                    length = len(new_chain)
                    
                    # If length >= 3, add geometric penalty
                    if length >= 3:
                        # Determine penalty multiplier
                        # L=3 (A-B-C) -> +1*P (Total 2P for last link)
                        # L=4 -> +2*P (Total 4P for last link)
                        # L=5 -> +4*P (Total 8P for last link)
                        
                        multiplier = 2**(length - 3) 
                        extra_cost = P_COOLDOWN * multiplier
                        
                        # Apply constraint for this specific person on this chain
                        # Need intersection of candidates for ALL groups in chain
                        common = set(self.get_group_candidates(self.group_map[new_chain[0]]))
                        for cid in new_chain[1:]:
                             common.intersection_update(self.get_group_candidates(self.group_map[cid]))
                        
                        for person in common:
                            # Exemption Check: If ALL in chain are exempt, skip penalty
                            is_chain_exempt = True
                            for cid in new_chain:
                                if not self.is_exempt_assignment(self.group_map[cid], person):
                                    is_chain_exempt = False
                                    break
                            
                            if is_chain_exempt:
                                continue

                            # Verify vars exist
                            vars_in_chain = [self.assignments.get((cid, person)) for cid in new_chain]
                            if all(v is not None for v in vars_in_chain):
                                chain_var = self.model.NewBoolVar(f'streak_{length}_{new_chain[0]}_{new_chain[-1]}_{person}')
                                self.model.AddBoolAnd(vars_in_chain).OnlyEnforceIf(chain_var)
                                self.model.AddBoolOr([v.Not() for v in vars_in_chain]).OnlyEnforceIf(chain_var.Not())
                                
                                objective_terms.append(chain_var * extra_cost)
                                
                                # Track
                                if person not in self.debug_vars: self.debug_vars[person] = {}
                                if 'cooldown' not in self.debug_vars[person]: self.debug_vars[person]['cooldown'] = []
                                
                                # Format details
                                names = [f"W{self.group_map[cid]['week']}" for cid in new_chain]
                                chain_str = " -> ".join(names)
                                
                                self.debug_vars[person]['cooldown'].append({
                                    'var': chain_var,
                                    'cost': extra_cost,
                                    'details': f"Geometric Streak ({length} weeks): {chain_str}"
                                })

                    # Recurse (Upper bound 5 weeks)
                    if length < 5:
                        find_chains(nid, new_chain)

            # Initiate DFS from all nodes
            for start_node in cooldown_graph:
                find_chains(start_node, [start_node]) 
        for person in all_persons:
            if person not in self.debug_vars:
                self.debug_vars[person] = {}
            
            self.debug_vars[person]['multi_weekday'] = None
            self.debug_vars[person]['multi_general'] = None
            if 'diversity' not in self.debug_vars[person]:
                self.debug_vars[person]['diversity'] = {}

        # Optimization: Only calculate complex variables if penalty is active (>0)
        # However, "Unassigned" and "Underworked" are basic enough they are usually always tracked or easy.
        # But for these daily ones, let's be safe.
        
        # If ANY daily-based penalty is active, we need the day processing loop.
        if P_MULTI_WEEKDAY > 0 or P_INEFFICIENT > 0 or P_MULTI_GENERAL > 0:
            for person in all_persons:
                 # Gather days worked
                 days_worked_vars = []
                 weekdays_worked_vars = []
                 weekdays_by_week = {} # week_str -> list of vars
                 
                 # Group IDs by day for this person
                 person_day_groups = {}
                 for group in self.groups:
                     parts = group['id'].split('_')
                     if len(parts) >= 3:
                         day_key = f"{parts[0]}_{parts[1]}" # Week_Day
                     else:
                         continue
                         
                     if day_key not in person_day_groups:
                         person_day_groups[day_key] = []
                     person_day_groups[day_key].append(group['id'])

                 # Create Worked Day Vars
                 for day_key, g_ids in person_day_groups.items():
                     worked_var = self.model.NewBoolVar(f"worked_{person}_{day_key}")
                     day_assigns = [self.assignments[(gid, person)] for gid in g_ids if (gid, person) in self.assignments]
                     
                     if not day_assigns:
                         self.model.Add(worked_var == 0)
                     else:
                         self.model.Add(sum(day_assigns) > 0).OnlyEnforceIf(worked_var)
                         self.model.Add(sum(day_assigns) == 0).OnlyEnforceIf(worked_var.Not())
                         
                         if P_INEFFICIENT > 0:
                             inefficient_var = self.model.NewBoolVar(f"inefficient_{person}_{day_key}")
                             
                             # Count total tasks
                             total_tasks = sum(self.assignments[(gid, person)] * self.group_map[gid].get('task_count', 1) 
                                             for gid in g_ids if (gid, person) in self.assignments)
                             
                             is_low_tasks = self.model.NewBoolVar(f"is_low_tasks_{person}_{day_key}")
                             self.model.Add(total_tasks < 2).OnlyEnforceIf(is_low_tasks)
                             self.model.Add(total_tasks >= 2).OnlyEnforceIf(is_low_tasks.Not())
                             
                             self.model.AddBoolOr([inefficient_var, worked_var.Not(), is_low_tasks.Not()])
                             
                             objective_terms.append(inefficient_var * P_INEFFICIENT)
                     
                     days_worked_vars.append(worked_var)
                     
                     try:
                         d_num = int(day_key.split('_')[1])
                         if d_num != 7 and d_num != 0: # 7 is Sunday, 0 is Any/Null
                             weekdays_worked_vars.append(worked_var)
                             
                             # Per-Week Tracking
                             week_str = day_key.split('_')[0].replace('G', '')
                             if week_str not in weekdays_by_week:
                                 weekdays_by_week[week_str] = []
                             weekdays_by_week[week_str].append(worked_var)
                     except:
                         pass

                 if P_MULTI_WEEKDAY > 0:
                     self.debug_vars[person]['multi_weekday'] = []
                     
                     for w_str, vars_list in weekdays_by_week.items():
                         if len(vars_list) > 1: 
                             # Cascading Penalty: (N - 1) * P
                             # excess = max(0, sum(vars) - 1)
                             # Since we minimize, excess >= sum - 1 and excess >= 0 is sufficient.
                             
                             excess_var = self.model.NewIntVar(0, 7, f"multi_weekday_excess_{person}_{w_str}")
                             
                             # Constraints
                             self.model.Add(excess_var >= sum(vars_list) - 1)
                             self.model.Add(excess_var >= 0) # Implicit for IntVar(0,7) but good for clarity if range changed
                             
                             objective_terms.append(excess_var * P_MULTI_WEEKDAY)
                             
                             self.debug_vars[person]['multi_weekday'].append({
                                 'week': w_str,
                                 'var': excess_var
                             })
                     
                     # If no weeks had potential (len > 1), list remains empty, which is fine.

                 if P_MULTI_GENERAL > 0:
                     has_weekday = self.model.NewBoolVar(f"has_weekday_{person}")
                     self.model.Add(sum(weekdays_worked_vars) > 0).OnlyEnforceIf(has_weekday)
                     self.model.Add(sum(weekdays_worked_vars) == 0).OnlyEnforceIf(has_weekday.Not())
                     
                     sunday_vars = [v for v in days_worked_vars if v not in weekdays_worked_vars]
                     has_sunday = self.model.NewBoolVar(f"has_sunday_{person}")
                     if sunday_vars:
                         self.model.Add(sum(sunday_vars) > 0).OnlyEnforceIf(has_sunday)
                         self.model.Add(sum(sunday_vars) == 0).OnlyEnforceIf(has_sunday.Not())
                     else:
                         self.model.Add(has_sunday == 0)
                         
                     multi_general = self.model.NewBoolVar(f"multi_general_{person}")
                     self.model.AddBoolAnd([has_weekday, has_sunday]).OnlyEnforceIf(multi_general)
                     self.model.AddBoolOr([has_weekday.Not(), has_sunday.Not()]).OnlyEnforceIf(multi_general.Not())
                     
                     objective_terms.append(multi_general * P_MULTI_GENERAL)
                     self.debug_vars[person]['multi_general'] = multi_general
        
        self.model.Minimize(sum(objective_terms))

        # 5. Solve
        solver = cp_model.CpSolver()
        if self.time_limit > 0:
            solver.parameters.max_time_in_seconds = self.time_limit
        solution_printer = SolutionPrinter()
        status = solver.Solve(self.model, solution_printer)
        
        results = {}
        incurred_penalties = []
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            print(f"Solution Found! Status: {solver.StatusName(status)}")
            print(f"Objective Value: {solver.ObjectiveValue()}")
            
            # Collect Assignments
            for group in self.groups:
                g_id = group['id']
                assigned_person = None
                method = "unassigned"
                
                if solver.Value(self.unassigned_vars[g_id]) == 1:
                    assigned_person = None
                    method = "unassigned"
                    
                    incurred_penalties.append({
                        "group_id": g_id,
                        "group_name": group['name'],
                        "assignee": None,
                        "rule": self.penalties.get_rule_name(0),
                        "cost": P_UNASSIGNED
                    })
                else:
                    candidates = self.get_group_candidates(group)
                    for p in candidates:
                        if (g_id, p) in self.assignments:
                            if solver.Value(self.assignments[(g_id, p)]) == 1:
                                assigned_person = p
                                break
                    
                    if group.get('assignee') == assigned_person:
                        method = "manual"
                    else:
                        method = "automatic"
                
                results[g_id] = {
                    "group_name": group['name'],
                    "assignee": assigned_person,
                    "method": method
                }
                
            # Collect Person Penalties
            for person in all_persons:
                # Underworked
                if solver.Value(self.underworked_vars[person]) == 1:
                    actual_effort = solver.Value(self.effort_vars[person]) / 10.0
                    incurred_penalties.append({
                        "person_name": person,
                        "rule": self.penalties.get_rule_name(1),
                        "cost": P_UNDERWORKED,
                        "details": f"Total Effort: {actual_effort} < 8.0"
                    })
                    
                # New Rules
                # New Rules
                if person in self.debug_vars:
                    # Multi-Day Weekday
                    # Multi-Day Weekday (Cascading)
                    if 'multi_weekday' in self.debug_vars[person] and isinstance(self.debug_vars[person]['multi_weekday'], list):
                        total_excess = 0
                        weeks_details = []
                        for item in self.debug_vars[person]['multi_weekday']:
                            exc_val = solver.Value(item['var'])
                            if exc_val > 0:
                                total_excess += exc_val
                                weeks_details.append(f"W{item['week']}: {exc_val} extra days")
                        
                        if total_excess > 0:
                            cost = total_excess * P_MULTI_WEEKDAY
                            incurred_penalties.append({
                                "person_name": person,
                                "rule": "Multi-Day Weekdays (e.g. Tue+Wed)",
                                "cost": cost,
                                "details": f"Cascading Penalty (Total Excess: {total_excess}): " + ", ".join(weeks_details)
                            })
                    
                    # Multi-Day General
                    if self.debug_vars[person]['multi_general'] is not None and solver.Value(self.debug_vars[person]['multi_general']) == 1:
                        incurred_penalties.append({
                            "person_name": person,
                            "rule": "Multi-Day General (Weekday+Sunday)",
                            "cost": P_MULTI_GENERAL,
                            "details": "Worked on Weekday + Sunday"
                        })

                    # Role Diversity
                    if 'diversity' in self.debug_vars[person]:
                        for fam, var in self.debug_vars[person]['diversity'].items():
                            if solver.Value(var) == 1:
                                incurred_penalties.append({
                                    "person_name": person,
                                    "rule": "Role Diversity (Assignments in each capable family)",
                                    "cost": P_DIVERSITY,
                                    "details": f"Missed assignment in capable family: {fam}"
                                })

                    # Cooldowns (Geometric + Pairwise)
                    if 'cooldown' in self.debug_vars[person]:
                        for item in self.debug_vars[person]['cooldown']:
                            if solver.Value(item['var']) == 1:
                                incurred_penalties.append({
                                    "person_name": person,
                                    "rule": "Cooldown (Adjacent Weeks / Geometric Streak)",
                                    "cost": item['cost'],
                                    "details": item['details']
                                })

                    # Intra-Cooldowns
                    if 'intra_cooldown' in self.debug_vars[person]:
                        for item in self.debug_vars[person]['intra_cooldown']:
                            if solver.Value(item['var']) == 1:
                                incurred_penalties.append({
                                    "person_name": person,
                                    "rule": "Intra-Week Cooldown (Same Week)",
                                    "cost": P_INTRA_COOLDOWN,
                                    "details": item['details']
                                })
                        
                # Efficiency check (need to reconstruct context or store vars better)
                # Re-check logic simply via values for reporting
                # (Ideally we stored inefficient vars)

        else:
             print("No solution found.")
             
        return results, incurred_penalties

    def is_exempt_assignment(self, group, person):
        """
        Returns True if the assignment is effectively 'Prepass' or 'Manual'.
        - Manual: Explicitly assigned.
        - Prepass: Priority candidate or Single candidate (Forced).
        """
        # Manual
        if group.get('assignee') == person:
            return True
        
        # Priority
        # Use filtered priority list as that's what the solver sees as 'priority'
        if person in group.get('filtered_priority_candidates_list', []):
            return True
            
        # Forced (Single Candidate)
        candidates = self.get_group_candidates(group)
        if len(candidates) == 1 and candidates[0] == person:
            return True
            
        return False

    def get_group_candidates(self, group):
        """Helper to get all valid candidates for a group."""
        c = group.get('filtered_priority_candidates_list', []) + \
            group.get('filtered_candidates_list', [])
        s = list(set(c))
        
        m = group.get('assignee')
        if m and m not in s: 
            s.append(m)
        return s
