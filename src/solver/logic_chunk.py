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
            # Group by Context: Name, Week, Day
            # Note: We need to handle potential missing keys safely
            w = g.get('week')
            d = g.get('day')
            n = g.get('name')
            # Only consider context where all 3 are present to avoid grouping 'None'
            if w is None or d is None or n is None:
                continue
                
            key = (n, w, d)
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
            
            # Iterate potential people (sanity check: intersection with team_members)
            # Actually we just map what IS forced.
            
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
                    is_forced = True
                
                if is_forced:
                    self.forced_assignment_map[(g_id, person)] = True

    def _is_forced(self, group_id, person_name):
        return self.forced_assignment_map.get((group_id, person_name), False)
