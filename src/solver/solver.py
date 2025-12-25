from ortools.sat.python import cp_model
from src.solver.penalties import SolverPenalties
import math
from collections import defaultdict

class SolutionPrinter(cp_model.CpSolverSolutionCallback):
    def __init__(self, penalty_vars=None, callback=None):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.__solution_count = 0
        self.penalty_vars = penalty_vars if penalty_vars else []
        self.callback = callback

    def OnSolutionCallback(self):
        self.__solution_count += 1
        
        active_penalties = 0
        if self.penalty_vars:
            # Count how many penalty variables (bool or int > 0) are triggered
            for var in self.penalty_vars:
                if self.Value(var) > 0:
                    active_penalties += 1
        
        print(f'Solution {self.__solution_count}, time = {self.WallTime():.2f} s, objective = {int(self.ObjectiveValue())}, penalties = {active_penalties}', flush=True)
        
        if self.callback:
            self.callback(self)

class SATSolver:
    # ... (init and methods remain) ...

    def extract_solution(self, provider):
        """
        Extracts the current solution using a provider (either a Solver object or a Callback object).
        provider must have a .Value(var) method.
        """
        results = {}
        incurred_penalties = []
        
        P_UNASSIGNED = self.penalties.get_penalty_by_name("Unassigned Group")
        P_UNDERWORKED = self.penalties.get_penalty_by_name("Underworked Team Member (< Threshold)")
        P_MULTI_GENERAL = self.penalties.get_penalty_by_name("Multi-Day General (Weekday+Sunday)")
        P_INTRA_COOLDOWN = self.penalties.get_penalty_by_name("Intra-Week Cooldown (Same Week)")
        TARGET_EFFORT_SCALED = int(self.effort_threshold * 10)
        
        all_persons = sorted(self.team_members, key=lambda x: x['name'])
        all_persons = [p['name'] for p in all_persons]

        # Collect Assignments
        for group in self.groups:
            g_id = group['id']
            assigned_person = None
            method = "unassigned"
            
            if provider.Value(self.unassigned_vars[g_id]) == 1:
                assigned_person = None
                method = "unassigned"
                
                incurred_penalties.append({
                    "group_id": g_id,
                    "group_name": group['name'],
                    "assignee": None,
                    "rule": "Unassigned Group",
                    "cost": P_UNASSIGNED,
                    "details": f"Group: {group['name']}"
                })
            else:
                candidates = self.get_group_candidates(group)
                for p in candidates:
                    if (g_id, p) in self.assignments:
                        if provider.Value(self.assignments[(g_id, p)]) == 1:
                            assigned_person = p
                            break
                
                if self._is_forced(g_id, assigned_person):
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
            if person not in self.effort_vars: continue

            # Underworked
            if person in self.underworked_vars and provider.Value(self.underworked_vars[person]) == 1:
                actual_effort = provider.Value(self.effort_vars[person]) / 10.0
                incurred_penalties.append({
                    "person_name": person,
                    "rule": self.penalties.get_rule_name(1),
                    "cost": P_UNDERWORKED,
                    "details": f"Total Effort: {actual_effort} < {self.effort_threshold}"
                })
                
            if person in self.debug_vars:
                # Multi-Day Weekday (Cascading)
                if 'multi_weekday' in self.debug_vars[person] and isinstance(self.debug_vars[person]['multi_weekday'], list):
                    total_cost = 0
                    weeks_details = []
                    for item in self.debug_vars[person]['multi_weekday']:
                        c_val = provider.Value(item['cost_var'])
                        if c_val > 0:
                            count_val = provider.Value(item['count_var'])
                            total_cost += c_val
                            weeks_details.append(f"W{item['week']}: {count_val} days ({c_val} cost)")
                    
                    if total_cost > 0:
                        incurred_penalties.append({
                            "person_name": person,
                            "rule": "Multi-Day Weekdays (e.g. Tue+Wed)",
                            "cost": total_cost,
                            "details": f"Geometric Penalty: " + ", ".join(weeks_details)
                        })
                
                # Multi-Day General
                if self.debug_vars[person].get('multi_general') is not None and provider.Value(self.debug_vars[person]['multi_general']) == 1:
                    incurred_penalties.append({
                        "person_name": person,
                        "rule": "Multi-Day General (Weekday+Sunday)",
                        "cost": P_MULTI_GENERAL,
                        "details": "Worked on Weekday + Sunday"
                    })

                # Role Diversity
                if 'diversity_cost_var' in self.debug_vars[person]:
                        cost_val = provider.Value(self.debug_vars[person]['diversity_cost_var'])
                        if cost_val > 0:
                            missed_fams = []
                            if 'diversity' in self.debug_vars[person]:
                                for fam, var in self.debug_vars[person]['diversity'].items():
                                    if provider.Value(var) == 1:
                                        missed_fams.append(fam)
                            
                            missed_count_val = provider.Value(self.debug_vars[person]['diversity_missed_count'])
                            incurred_penalties.append({
                                "person_name": person,
                                "rule": "Role Diversity (Cascading)",
                                "cost": cost_val,
                                "details": f"Missed {missed_count_val} families: {', '.join(missed_fams)}"
                            })

                # Cooldowns
                if 'cooldown' in self.debug_vars[person]:
                    for item in self.debug_vars[person]['cooldown']:
                        if provider.Value(item['var']) == 1:
                            incurred_penalties.append({
                                "person_name": person,
                                "rule": "Cooldown (Adjacent Weeks / Geometric Streak)",
                                "cost": item['cost'],
                                "details": item['details']
                            })

                # Intra-Cooldowns
                if 'intra_cooldown' in self.debug_vars[person]:
                    for item in self.debug_vars[person]['intra_cooldown']:
                        if provider.Value(item['var']) == 1:
                            incurred_penalties.append({
                                "person_name": person,
                                "rule": "Intra-Week Cooldown (Same Week)",
                                "cost": P_INTRA_COOLDOWN,
                                "details": item['details']
                            })
                    
                # Teaching/Assisting Preference
                if 'teach_pref' in self.debug_vars[person]:
                    info = self.debug_vars[person]['teach_pref']
                    cost_incurred = 0
                    details = ""
                    
                    if info['type'] == 'teacher':
                            if provider.Value(info['full_var']) == 1:
                                cost_incurred = info['cost_full']
                                details = "Teacher assigned neither Teaching nor Assisting"
                            elif provider.Value(info['half_var']) == 1:
                                cost_incurred = info['cost_half']
                                details = "Teacher assigned only Assisting (Preferred Teaching)"
                    elif info['type'] == 'assistant':
                            if provider.Value(info['full_var']) == 1:
                                cost_incurred = info['cost_full']
                                details = "Assistant assigned no Assisting tasks"
                    
                    if cost_incurred > 0:
                        incurred_penalties.append({
                            "person_name": person,
                            "rule": "Teaching/Assisting Preference",
                            "cost": cost_incurred,
                            "details": details
                        })

                # Teaching/Assisting Equality
                if 'equality' in self.debug_vars[person]:
                    for item in self.debug_vars[person]['equality']:
                        c_val = provider.Value(item['cost_var'])
                        if c_val > 0:
                            cnt = provider.Value(item['count_var'])
                            incurred_penalties.append({
                                "person_name": person,
                                "rule": "Teaching/Assisting Equality",
                                "cost": c_val,
                                "details": f"Hoarding {cnt} assignments in {item['family']}"
                            })

                # Effort Equalization
                if 'equalization' in self.debug_vars[person]:
                    info = self.debug_vars[person]['equalization']
                    p_val = info['cost'] 
                    
                    norm_cost = provider.Value(info['cost_var'])
                    total_penalty = norm_cost * p_val
                    
                    if total_penalty > 0:
                        effort_val = provider.Value(self.effort_vars[person])
                        scaled_diff = effort_val - TARGET_EFFORT_SCALED
                        sq_diff = scaled_diff * scaled_diff
                        
                        actual_diff = scaled_diff / 10.0
                        
                        incurred_penalties.append({
                            "person_name": person,
                            "rule": "Effort Equalization",
                            "cost": total_penalty,
                            "details": f"Deviation {actual_diff:.1f} from {self.effort_threshold} (SqDiff {sq_diff}, Norm {norm_cost})" 
                        })

        return results, incurred_penalties

    def _precalculate_forced_assignments(self):
        """
        Identify assignments that are effectively manual/forced:
        1. Explicit 'assignee' in data.
        2. Priority candidates (if person is in priority list).
        3. Single candidate available.
        4. N-for-N grouped dependency (e.g. 2 slots, 2 people available total).
        """
        self.forced_assignment_map = {}
        
        # N-for-N Logic
        context_groups = defaultdict(list)
        for g in self.groups:
            # Group by Context: Name, Week
            # Note: We need to handle potential missing keys safely
            w = g.get('week')
            n = g.get('name')
            
            if w is None or n is None:
                continue
                
            # Relaxed Key: Ignore Day to catch cross-day constraints in the same week
            key = (n, w)
            context_groups[key].append(g)
            
        forced_n_for_n_ids = set()
        for key, grps in context_groups.items():
            n_groups = len(grps)
            if n_groups == 0: continue
            
            all_candidates = set()
            for g in grps:
                # Prefer filtered list if present (solver usually gets this)
                cands = g.get('filtered_candidates_list')
                if not cands: 
                    cands = g.get('candidates_list', [])
                all_candidates.update(cands)
                
            # Logic: If N slots need filling and distinct candidates == N, they are locked.
            if len(all_candidates) == n_groups:
                for g in grps:
                    forced_n_for_n_ids.add(g['id'])

        # Build Map
        for group in self.groups:
            g_id = group['id']
            
            # Candidates to check
            p_list = group.get('filtered_priority_candidates_list')
            if not p_list: p_list = group.get('priority_candidates_list', [])
            
            cands = group.get('filtered_candidates_list')
            if not cands: cands = group.get('candidates_list', [])
            
            # Use intersection of candidates and team_members logic effectively
            # Iterate potential people who might be assigned
            
            possible_assignees = set(cands)
            if p_list: possible_assignees.update(p_list)
            if group.get('assignee'): possible_assignees.add(group['assignee'])
            
            for person in possible_assignees:
                is_forced = False
                
                # 1. Explicit
                if group.get('assignee') == person:
                    is_forced = True
                
                # 2. Priority
                # If person is a priority candidate, we deem it 'Manual/Prepass' intent
                elif p_list and person in p_list:
                    is_forced = True
                    
                # 3. Single Option
                elif len(cands) == 1 and person in cands:
                     is_forced = True
                    
                # 4. N-for-N
                elif g_id in forced_n_for_n_ids:
                    # If N-for-N is active, any valid candidate is forced
                    if person in cands:
                        is_forced = True
                
                if is_forced:
                    self.forced_assignment_map[(g_id, person)] = True

    def _is_forced(self, group_id, person_name):
        return self.forced_assignment_map.get((group_id, person_name), False)

    def solve(self, solution_callback=None):
        self.model = cp_model.CpModel()
        
        # ... (Variables and Constraints setup - same as before) ...
        # NOTE: I am not including the entire body here due to size limits in this tool,
        # but in a real edit I would keep the constraint setup logic.
        # Since I'm using MultiReplace or big Replace, I should be careful.
        # The tool input effectively replaces the extracted parts.
        
        # Wait, I cannot replace the *entire* solve method efficiently if I don't provide the body.
        # The instruction was "Update solve to use extract_solution".
        # I need to see exactly where to splice.
        pass
    def __init__(self, groups, team_members, config=None):
        self.groups = groups
        self.team_members = team_members
        self.member_map = {m['name']: m for m in team_members}
        self.group_map = {g['id']: g for g in groups}
        
        # Pre-calculate Forced Assignments for N-for-N detection and Priority
        self.forced_assignment_map = {}
        self._precalculate_forced_assignments()
        
        # Define Rules for Ladder
        self.disabled_rules = set()

        if config:
            ladder_raw = config.get('ladder', [])
            self.disabled_rules = set(config.get('disabled_rules', []))
            self.preferred_pairs = config.get('preferred_pairs', [])
            self.time_limit = config.get('time_limit_seconds', 30.0)
            self.effort_threshold = config.get('effort_threshold', 8.0)
            self.penalty_ratio = config.get('penalty_ratio', 10)
        else:
            # Loaded from data/penalty_config.json
            import json
            from pathlib import Path
            
            config_path = Path('data') / 'penalty_config.json'
            with open(config_path, 'r') as f:
                t = json.load(f)
                ladder_raw = t['ladder']
                self.disabled_rules = set(t.get('disabled_rules', []))
                self.preferred_pairs = t.get('preferred_pairs', [])
                self.time_limit = t.get('time_limit_seconds', 30.0)
                self.effort_threshold = t.get('effort_threshold', 8.0)
                self.penalty_ratio = t.get('penalty_ratio', 10)
        
        # Filter out disabled rules from the active ladder
        self.rule_definitions = [r for r in ladder_raw if r not in self.disabled_rules]
        
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

    def solve(self, solution_callback=None):
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
                
                excl_group = group_map[excl_id]
                
                candidates_g = self.get_group_candidates(group)
                candidates_e = self.get_group_candidates(excl_group)
                common = set(candidates_g).intersection(candidates_e)
                
                for p in common:
                    if (g_id, p) in self.assignments and (excl_id, p) in self.assignments:
                        # Check for Manual Override
                        # If the user manually assigned 'p' to BOTH groups, we allow it.
                        is_manual_g = (group.get('assignee') == p)
                        is_manual_e = (excl_group.get('assignee') == p)
                        
                        if is_manual_g and is_manual_e:
                            continue 
                            
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
                
            # Define Underworked: Effort < Threshold (scaled)
            # underworked => effort < threshold_scaled
            # !underworked => effort >= threshold_scaled
            TARGET_EFFORT = int(self.effort_threshold * 10)
            
            self.model.Add(self.effort_vars[person] < TARGET_EFFORT).OnlyEnforceIf(self.underworked_vars[person])
            self.model.Add(self.effort_vars[person] >= TARGET_EFFORT).OnlyEnforceIf(self.underworked_vars[person].Not())


        # 4. Objective Function & Penalty Tracking
        objective_terms = []
        all_cost_vars = [] # Track variables responsible for costs for live reporting
        
        P_UNASSIGNED = self.penalties.get_penalty_by_name("Unassigned Group")
        P_UNDERWORKED = self.penalties.get_penalty_by_name("Underworked Team Member (< Threshold)")
        
        # Term 1: Unassigned Groups
        if P_UNASSIGNED > 0:
            for group in self.groups:
                objective_terms.append(self.unassigned_vars[group['id']] * P_UNASSIGNED)
                all_cost_vars.append(self.unassigned_vars[group['id']])
            
        # Term 2: Underworked People
        if P_UNDERWORKED > 0:
            for person in all_persons:
                objective_terms.append(self.underworked_vars[person] * P_UNDERWORKED)
                all_cost_vars.append(self.underworked_vars[person])

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
        
        # Term 8: Teaching/Assisting Preference
        P_TEACH_PREF = self.penalties.get_penalty_by_name("Teaching/Assisting Preference")
        
        # Term 9: Teaching/Assisting Equality (Hoisted)
        P_TEACH_EQUALITY = self.penalties.get_penalty_by_name("Teaching/Assisting Equality")
        
        # --- Teaching/Assisting Preference Logic ---
        if P_TEACH_PREF > 0 or P_TEACH_EQUALITY > 0:
            # Shared: Identify Teaching/Assisting Groups and Candidates
            # 1. Group Classification
            teaching_groups_ids = []
            assisting_groups_ids = []
            
            # Map for capable sets
            capable_teaching = set()
            capable_assisting = set()
            
            for group in self.groups:
                fam = group.get('family', '')
                if fam == 'Teaching':
                    teaching_groups_ids.append(group['id'])
                    capable_teaching.update(self.get_group_candidates(group))
                elif fam == 'Assisting':
                    assisting_groups_ids.append(group['id'])
                    capable_assisting.update(self.get_group_candidates(group))

            # --- Teaching/Assisting Preference Logic ---
            if P_TEACH_PREF > 0:
                all_relevant = capable_teaching.union(capable_assisting)
                
                for person in all_relevant:
                    if person not in all_persons: continue
                    
                    teach_vars = [self.assignments[(gid, person)] for gid in teaching_groups_ids if (gid, person) in self.assignments]
                    assist_vars = [self.assignments[(gid, person)] for gid in assisting_groups_ids if (gid, person) in self.assignments]
                    
                    has_teaching = self.model.NewBoolVar(f"has_teaching_{person}")
                    if teach_vars:
                        # Optimization: sum(vars) > 0 <-> has_teaching
                        self.model.AddMaxEquality(has_teaching, teach_vars)
                    else:
                        self.model.Add(has_teaching == 0)
                        
                    has_assisting = self.model.NewBoolVar(f"has_assisting_{person}")
                    if assist_vars:
                        self.model.AddMaxEquality(has_assisting, assist_vars)
                    else:
                        self.model.Add(has_assisting == 0)
                    
                    # Apply Costs
                    if person in capable_teaching:
                        # P_TEACH_PREF * (1.0 * is_bad + 0.5 * is_ok_assist)
                        P_HALF = int(P_TEACH_PREF * 0.5)
                        
                        is_half_bad = self.model.NewBoolVar(f"teach_pref_half_{person}")
                        # (!T and A)
                        self.model.AddBoolAnd([has_teaching.Not(), has_assisting]).OnlyEnforceIf(is_half_bad)
                        self.model.AddBoolOr([has_teaching, has_assisting.Not()]).OnlyEnforceIf(is_half_bad.Not())
                        
                        is_full_bad = self.model.NewBoolVar(f"teach_pref_full_{person}")
                        # (!T and !A)
                        self.model.AddBoolAnd([has_teaching.Not(), has_assisting.Not()]).OnlyEnforceIf(is_full_bad)
                        self.model.AddBoolOr([has_teaching, has_assisting]).OnlyEnforceIf(is_full_bad.Not())
                        
                        objective_terms.append(is_half_bad * P_HALF)
                        objective_terms.append(is_full_bad * P_TEACH_PREF)
                        all_cost_vars.append(is_half_bad)
                        all_cost_vars.append(is_full_bad)
                        
                        # Debug logic remains similar but simplified context
                        if person not in self.debug_vars: self.debug_vars[person] = {}
                        self.debug_vars[person]['teach_pref'] = {
                            'type': 'teacher',
                            'half_var': is_half_bad,
                            'full_var': is_full_bad,
                            'cost_half': P_HALF,
                            'cost_full': P_TEACH_PREF
                        }

                    elif person in capable_assisting:
                        is_bad = self.model.NewBoolVar(f"assist_pref_bad_{person}")
                        # Not Assisting => Bad
                        self.model.Add(has_assisting == 0).OnlyEnforceIf(is_bad)
                        self.model.Add(has_assisting == 1).OnlyEnforceIf(is_bad.Not())
                        
                        objective_terms.append(is_bad * P_TEACH_PREF)
                        all_cost_vars.append(is_bad)
                        
                        if person not in self.debug_vars: self.debug_vars[person] = {}
                        self.debug_vars[person]['teach_pref'] = {
                            'type': 'assistant',
                            'full_var': is_bad,
                            'cost_full': P_TEACH_PREF
                        }

            # --- Teaching/Assisting Equality Logic ---
            if P_TEACH_EQUALITY > 0:
                fam_map_ids = {"Teaching": teaching_groups_ids, "Assisting": assisting_groups_ids}
                
                for person in all_persons:
                     for fam_name, gids in fam_map_ids.items():
                         if not gids: continue

                         # Manual/Auto Detection
                         manual_vars = []
                         auto_vars = []
                         
                         # Optimization: Filter loop by assignments existence
                         person_gids = [gid for gid in gids if (gid, person) in self.assignments]
                         if not person_gids: continue

                         for gid in person_gids:
                             var = self.assignments[(gid, person)]
                             is_manual = self._is_forced(gid, person)
                             
                             if is_manual:
                                 manual_vars.append(var)
                             else:
                                 auto_vars.append(var)
                         
                         p_vars = manual_vars + auto_vars
                         
                         # Only create constraints if >1 assignment possible
                         # Actually we need it if >1 assignment is MADE. 
                         # We can optimistically create if len(p_vars) >= 2
                         if len(p_vars) >= 2:
                             total_count_var = self.model.NewIntVar(0, len(p_vars), f"equality_count_{fam_name}_{person}")
                             self.model.Add(total_count_var == sum(p_vars))
                             
                             costs = []
                             for i in range(len(p_vars) + 1):
                                 if i < 2:
                                     costs.append(0)
                                 else:
                                     multiplier = 3 ** (i - 2)
                                     val = P_TEACH_EQUALITY * multiplier
                                     if val > 9000000000000000000: val = 9000000000000000000
                                     costs.append(val)
                            
                             base_cost_var = self.model.NewIntVar(0, max(costs), f"equality_base_cost_{fam_name}_{person}")
                             self.model.AddElement(total_count_var, costs, base_cost_var)
                             
                             has_auto = self.model.NewBoolVar(f"equality_has_auto_{fam_name}_{person}")
                             if auto_vars:
                                 self.model.AddMaxEquality(has_auto, auto_vars)
                             else:
                                 self.model.Add(has_auto == 0)
                                 
                             final_cost_var = self.model.NewIntVar(0, max(costs), f"equality_final_cost_{fam_name}_{person}")
                             self.model.AddMultiplicationEquality(final_cost_var, [base_cost_var, has_auto])
                             objective_terms.append(final_cost_var)
                             all_cost_vars.append(final_cost_var)
                             
                             if person not in self.debug_vars: self.debug_vars[person] = {}
                             if 'equality' not in self.debug_vars[person]: self.debug_vars[person]['equality'] = []
                             self.debug_vars[person]['equality'].append({
                                 'family': fam_name,
                                 'count_var': total_count_var,
                                 'cost_var': final_cost_var,
                                 'has_auto': has_auto
                             })

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
            
            # 2. Collect Missed Families per Person
            person_missed_vars = {} # person -> list of bool vars (one per family)
            
            for fam, groups_ids in family_groups.items():
                # For each person capable of this family
                for person in family_candidates[fam]:
                    if person not in all_persons: continue # Skip if inactive
                    
                    if person not in person_missed_vars:
                        person_missed_vars[person] = []
                    
                    # Gather assignment vars for this person in this family
                    fam_vars = []
                    for gid in groups_ids:
                        if (gid, person) in self.assignments:
                            fam_vars.append(self.assignments[(gid, person)])
                    
                    if fam_vars:
                        # Bool: Has at least one assignment in family
                        # We want to PENALIZE if sum(fam_vars) == 0
                        
                        missed_diversity = self.model.NewBoolVar(f"missed_div_{fam}_{person}")
                        
                        # logic: missed <-> sum == 0
                        self.model.Add(sum(fam_vars) == 0).OnlyEnforceIf(missed_diversity)
                        self.model.Add(sum(fam_vars) > 0).OnlyEnforceIf(missed_diversity.Not())
                        
                        person_missed_vars[person].append(missed_diversity)
                        
                        # Store for reporting (individual details)
                        if person not in self.debug_vars:
                             self.debug_vars[person] = {}
                        if 'diversity' not in self.debug_vars[person]:
                             self.debug_vars[person]['diversity'] = {}
                        self.debug_vars[person]['diversity'][fam] = missed_diversity

            # 3. Apply Cascading Penalty per Person
            for person, missed_vars in person_missed_vars.items():
                if missed_vars:
                    # Calculate total missed families
                    missed_count = self.model.NewIntVar(0, len(missed_vars), f"missed_count_{person}")
                    self.model.Add(missed_count == sum(missed_vars))
                    
                    # Create Cost Table: 0 -> 0, 1 -> P, 2 -> 2P, 3 -> 4P, 4 -> 8P ...
                    # Formula: Cost = P * 2^(N-1) for N >= 1, else 0
                    costs = [0]
                    for i in range(1, len(missed_vars) + 1):
                         val = P_DIVERSITY * (3**(i-1))
                         if val > 9000000000000000000: val = 9000000000000000000
                         costs.append(val)
                    
                    div_cost_var = self.model.NewIntVar(0, max(costs), f"div_cost_{person}")
                    self.model.AddElement(missed_count, costs, div_cost_var)
                    
                    objective_terms.append(div_cost_var)
                    all_cost_vars.append(div_cost_var)
                    
                    # Save for debug reporting (override the dict logic partly or augment it?)
                    # We still keep 'diversity' dict for details, but maybe store cost var too
                    self.debug_vars[person]['diversity_cost_var'] = div_cost_var
                    self.debug_vars[person]['diversity_missed_count'] = missed_count


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
                                 all_cost_vars.append(penalty_var)
                                 
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
                                    all_cost_vars.append(penalty_var)
                                    
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
                        # Multipliers derived to match geometric totals (100, 300, 900, 2700):
                        # L=3: Tot=300 (2 Pairs + 1 Streak). S3=100 (1x).
                        # L=4: Tot=900 (3 Pairs + 2 S3 + 1 Streak). S4=400 (4x).
                        # L=5: Tot=2700 (4 Pairs + 3 S3 + 2 S4 + 1 Streak). S5=1200 (12x).
                        
                        multiplier = 1
                        if length == 4: multiplier = 4
                        elif length == 5: multiplier = 12
                        
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
                                all_cost_vars.append(chain_var)
                                
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
            # Hoist: Build Day -> Group Map ONCE
            day_to_group_ids = {} # day_key -> list of gids
            
            for group in self.groups:
                 parts = group['id'].split('_')
                 if len(parts) >= 3:
                     day_key = f"{parts[0]}_{parts[1]}" # Week_Day
                     if day_key not in day_to_group_ids:
                         day_to_group_ids[day_key] = []
                     day_to_group_ids[day_key].append(group['id'])

            for person in all_persons:
                 # Gather days worked
                 days_worked_vars = []
                 weekdays_worked_vars = []
                 weekdays_by_week = {} # week_str -> list of vars
                 
                 # Optimization: Use Shared Map
                 
                 # Create Worked Day Vars
                 for day_key, g_ids in day_to_group_ids.items():
                     worked_var = self.model.NewBoolVar(f"worked_{person}_{day_key}")
                     
                     # Only consider groups this person is actually a candidate for (exists in assignments)
                     day_assigns = [self.assignments[(gid, person)] for gid in g_ids if (gid, person) in self.assignments]
                     
                     if not day_assigns:
                         self.model.Add(worked_var == 0)
                     else:
                         # sum > 0 <-> worked
                         self.model.AddMaxEquality(worked_var, day_assigns)
                         
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
                             all_cost_vars.append(inefficient_var)
                     
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
                         if len(vars_list) >= 2: 
                             # Geometric Cascading Penalty: 
                             # 2 days -> 1x
                             # 3 days -> 3x
                             # 4 days -> 9x
                             # Formula: P * 3^(count - 2) for count >= 2
                             
                             # 1. Count Total Weekdays Assigned
                             count_var = self.model.NewIntVar(0, len(vars_list), f"multi_weekday_count_{person}_{w_str}")
                             self.model.Add(count_var == sum(vars_list))
                             
                             # 2. Build Cost Table
                             # Index i corresponds to count=i
                             costs = []
                             for i in range(len(vars_list) + 1):
                                 if i < 2:
                                     costs.append(0)
                                 else:
                                     # i=2 -> 3^(0) = 1
                                     # i=3 -> 3^(1) = 3
                                     multiplier = 3 ** (i - 2)
                                     val = P_MULTI_WEEKDAY * multiplier
                                     if val > 9000000000000000000: val = 9000000000000000000
                                     costs.append(val)
                             
                             cost_var = self.model.NewIntVar(0, max(costs), f"multi_weekday_cost_{person}_{w_str}")
                             self.model.AddElement(count_var, costs, cost_var)
                             
                             objective_terms.append(cost_var)
                             all_cost_vars.append(cost_var)
                             
                             self.debug_vars[person]['multi_weekday'].append({
                                 'week': w_str,
                                 'count_var': count_var,
                                 'cost_var': cost_var
                             })
                     
                     # If no weeks had potential (len < 2), list remains empty.

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
                     all_cost_vars.append(multi_general)
                     self.debug_vars[person]['multi_general'] = multi_general
        
                     self.debug_vars[person]['multi_general'] = multi_general
        
        # Term 10: Effort Equalization
        P_EQUALIZATION = self.penalties.get_penalty_by_name("Effort Equalization")
        
        if P_EQUALIZATION > 0:
            TARGET_EFFORT_SCALED = int(self.effort_threshold * 10)
            
            # Pre-compute cost table for all possible effort values
            # Domain of effort_var is [0, max_scaled_effort]
            cost_table = []
            for e in range(max_scaled_effort + 1):
                diff = e - TARGET_EFFORT_SCALED
                sq = diff * diff
                norm = sq // 100 # Normalize by 100
                cost_table.append(norm)
                
            for person in all_persons:
                # No exemption: All users (Manual/Priority/Auto) are subject to equalization
                # regarding their TOTAL consolidated effort.
                
                effort_var = self.effort_vars[person]
                 
                # Optimization: Table Lookup instead of Quadratic Math constraints
                # Cost = cost_table[effort_var]
                
                cost_var = self.model.NewIntVar(0, max(cost_table), f"effort_cost_{person}")
                self.model.AddElement(effort_var, cost_table, cost_var)
                
                objective_terms.append(cost_var * P_EQUALIZATION)
                all_cost_vars.append(cost_var)
                
                # Debug
                if person not in self.debug_vars: self.debug_vars[person] = {}
                self.debug_vars[person]['equalization'] = {
                    'cost_var': cost_var,
                    'cost': P_EQUALIZATION
                }

        # Term 11: Preferred Pair Split (Separate Rungs of same Ladder)
        # Goal: If preferred pair members are assigned to SAME Logical Group (Name, Week, Day),
        # but in different repeats, that is GOOD.
        # User: "incentivize them being assigned to different repeats of the same group"
        # Implies: If A is in G_1 (Rep 1) and B is NOT in any G (Rep 1..N) of same type -> ?
        # Or: Group them together.
        # Let's interpret "Separate Rungs" as: They should appear in the set of assignees for the Logical Group.
        # Logic: For each Logical Group (Name, Week, Day):
        #   If (A is present) XOR (B is present) -> Penalty.
        #   If A and B both present -> Good.
        #   If neither -> Good (Neutral).
        # "Preferred Pair" (Renamed from Split)
        # logic: if pair_pref=True for (p1,p2), then if both assigned to same Group, GOOD.
        # If assigned to incompatible groups (split) -> BAD.
        # BUT logic in code: check if assigned to different groups at same time?
        # Actually solver likely checks `is_preferred_pair_split`.
        P_PAIR_SPLIT = self.penalties.get_penalty_by_name("Preferred Pair")
        
        if P_PAIR_SPLIT > 0 and self.preferred_pairs:
            # 1. Group IDs by Logical Group (Name, Week, Day)
            logical_groups = {} # (Name, Week, Day) -> [GroupIDs]
            for g in self.groups:
                # Assuming standard group naming/ID structure isn't needed if we use attributes
                key = (g['name'], g['week'], g['day'])
                if key not in logical_groups:
                    logical_groups[key] = []
                logical_groups[key].append(g['id'])
            
            # 2. Iterate Pairs and Logical Groups
            for p1_name, p2_name in self.preferred_pairs:
                # Verify names exist to avoid errors
                if p1_name not in self.member_map or p2_name not in self.member_map:
                    print(f"Warning: Preferred pair [{p1_name}, {p2_name}] contains unknown members.")
                    continue
                    
                for key, g_ids in logical_groups.items():
                    # Create presence vars for this logical group
                    # is_p1_present = OR(assignments[g_id, p1])
                    # is_p2_present = OR(assignments[g_id, p2])
                    
                    p1_vars = []
                    p2_vars = []
                    
                    for gid in g_ids:
                        if (gid, p1_name) in self.assignments:
                            p1_vars.append(self.assignments[(gid, p1_name)])
                        if (gid, p2_name) in self.assignments:
                            p2_vars.append(self.assignments[(gid, p2_name)])
                            
                    if not p1_vars and not p2_vars:
                        continue
                        
                    p1_present = self.model.NewBoolVar(f"pair_{p1_name}_{key}")
                    p2_present = self.model.NewBoolVar(f"pair_{p2_name}_{key}")
                    
                    if p1_vars:
                        self.model.AddBoolOr(p1_vars).OnlyEnforceIf(p1_present)
                        self.model.AddBoolAnd([v.Not() for v in p1_vars]).OnlyEnforceIf(p1_present.Not())
                    else:
                        self.model.Add(p1_present == 0)

                    if p2_vars:
                        self.model.AddBoolOr(p2_vars).OnlyEnforceIf(p2_present)
                        self.model.AddBoolAnd([v.Not() for v in p2_vars]).OnlyEnforceIf(p2_present.Not())
                    else:
                        self.model.Add(p2_present == 0)
                        
                    # 3. Penalty if XOR (One present, other missing)
                    # split_var = p1_present != p2_present
                    split_var = self.model.NewBoolVar(f"split_{p1_name}_{p2_name}_{key}")
                    self.model.Add(p1_present != p2_present).OnlyEnforceIf(split_var)
                    self.model.Add(p1_present == p2_present).OnlyEnforceIf(split_var.Not())
                    
                    objective_terms.append(split_var * P_PAIR_SPLIT)
                    all_cost_vars.append(split_var)
                    
                    # Debug logic (attach to P1 for visibility)
                    if p1_name not in self.debug_vars: self.debug_vars[p1_name] = {}
                    # Accumulate if multiple splits? Complex to show in flat dict.
                    # Just showing last for now or unique key
                    # self.debug_vars[p1_name][f'split_{p2_name}'] = split_var

        self.model.Minimize(sum(objective_terms))

        # 5. Solve
        solver = cp_model.CpSolver()
        if self.time_limit > 0:
            solver.parameters.max_time_in_seconds = self.time_limit
            
        solution_printer = SolutionPrinter(all_cost_vars, callback=solution_callback)
        status = solver.Solve(self.model, solution_printer)
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            print(f"Solution Found! Status: {solver.StatusName(status)}")
            print(f"Objective Value: {int(solver.ObjectiveValue())}")
            return self.extract_solution(solver)
        else:
             print("No solution found.")
             return {}, []

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
        """Helper to get all valid candidates for a group.
        
        Optimization: If 'assignee' is set, return ONLY that person.
        Optimization: If 'filtered_priority_candidates_list' exists and is not empty, use ONLY that.
        Otherwise, use 'filtered_candidates_list'.
        """
        # 1. Manual Assignment (Highest Priority)
        m = group.get('assignee')
        if m:
            return [m]
        
        # 2. Filtered Priority List (Strict)
        # Note: If this list exists, we ignore standard candidates completely.
        # This prunes the search space significantly.
        priority_candidates = group.get('filtered_priority_candidates_list', [])
        if priority_candidates:
            return list(set(priority_candidates))
            
        # 3. Standard Candidates
        return list(set(group.get('filtered_candidates_list', [])))
