import json
import pathlib
from collections import defaultdict

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(data, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def process_groups(tasks_list, task_families, team_members):
    # Team Member Lookup
    # Map Name -> {role: ..., both: ...}
    member_map = {m['name']: m for m in team_members}

    # Group tasks by (Week, Day, Name)
    tasks_by_context = defaultdict(list)
    for task in tasks_list:
        key = (task['week'], task['day'], task['name'])
        tasks_by_context[key].append(task)
    
    # Sort tasks by repeat_index to consume in order
    for key in tasks_by_context:
        tasks_by_context[key].sort(key=lambda x: x['repeat_index'])

    groups_output = []
    
    # Store created groups for linking later
    groups_by_day = defaultdict(list)
    groups_by_family_week = defaultdict(list)
    
    # Dictionary to keep track of group counts per Week/Day to generate IDs
    group_id_counters = defaultdict(int)

    # Create set of task IDs that are assigned to groups to track unassigned ones
    assigned_task_ids = set()

    # Define contexts from tasks list
    # Include tasks with day=None (treated as "Any" or floating)
    contexts = set((t['week'], t['day']) for t in tasks_list if t['week'])
    
    # Sort with safe key for None values
    sorted_contexts = sorted(list(contexts), key=lambda x: (x[0], x[1] if x[1] is not None else ""))

    # Sort with safe key for None values
    sorted_contexts = sorted(list(contexts), key=lambda x: (x[0], x[1] if x[1] is not None else ""))

    # --- 0. Normalize Exclusions (Bidirectional) ---
    # Ensure if A excludes B, B excludes A
    group_map = {}
    for fam in task_families:
        for grp in fam['groups']:
            group_map[grp['name']] = grp
            
    for fam in task_families:
        for grp in fam['groups']:
            name = grp['name']
            excl = set(grp.get('exclusive', []))
            
            for target_name in excl:
                if target_name in group_map:
                    target_grp = group_map[target_name]
                    t_excl = set(target_grp.get('exclusive', []))
                    if name not in t_excl:
                        t_excl.add(name)
                        target_grp['exclusive'] = list(t_excl)

    for week, day in sorted_contexts:
        # --- 1. Family-based Groups ---
        for family in task_families:
            fam_name = family['name']
            
            for group_def in family['groups']:
                group_name = group_def['name']
                required_tasks = group_def['tasks']
                
                counts = {
                    "leader": group_def.get("leader-group-count", 0),
                    "follower": group_def.get("follower-group-count", 0),
                    "any": group_def.get("any-group-count", 0)
                }
                
                total_instances = counts["leader"] + counts["follower"] + counts["any"]
                
                # Special Case: If counts are explicitly 0, we want to IGNORE these tasks
                # so they don't fall through to the "Standalone" section.
                if total_instances == 0:
                    for task_name in required_tasks:
                        key = (week, day, task_name)
                        if key in tasks_by_context:
                            # Mark all such tasks as "assigned" (consumed) so they are skipped later
                            for t in tasks_by_context[key]:
                                assigned_task_ids.add(t['id'])
                            # Optional: Remove from context map to be clean, though assigned_task_ids check is sufficient
                            del tasks_by_context[key]
                    continue

                #         key = (week, day, task_name)
                #         if key in tasks_by_context:
                #             # Mark all such tasks as "assigned" (consumed) so they are skipped later
                #             # This is the original content of the if block.
                #             # The new content starts here, replacing the original `for t in ...` and `del ...`
                #             # and then the `continue` is at the end of the new block.

                # This is very confusing. The `Code Edit` shows:
                # `if total_instances == 0: ... # Mark all such tasks as "assigned" (consumed) so they are skipped later`
                # THEN the new block.
                # THEN `del tasks_by_context[key]` and `continue`.

                # This structure implies the new block is inserted *after* the comment,
                # and the `del tasks_by_context[key]` and `continue` are *part of the new block*.
                # This would mean the `if total_instances == 0` block is completely changed.

                # Let's try to make the minimal change that matches the snippet.
                # The snippet shows the new block *after* the `if total_instances == 0:` block's content,
                # and *before* `group_repeat_counter = 0`.
                # The `del tasks_by_context[key]` and `continue` are shown *after* the new block.
                # This means the new block is inserted, and then the `del tasks_by_context[key]` and `continue`
                # are *still there* from the original `if` block. This is syntactically incorrect.

                # The only way for the snippet to make sense is if the new block *replaces* the content
                # of the `if total_instances == 0:` block, and then the `del tasks_by_context[key]` and `continue`
                # are part of the *new* block's logic.

                # Let's assume the user wants to *replace* the content of the `if total_instances == 0:` block
                # with the new "STRICT CONSUMPTION" logic, and then the `continue` applies to this new logic.

                # Original `if` block:
                # if total_instances == 0:
                #     for task_name in required_tasks:
                #         key = (week, day, task_name)
                #         if key in tasks_by_context:
                #             for t in tasks_by_context[key]:
                #                 assigned_task_ids.add(t['id'])
                #             # Optional: Remove from context map to be clean, though assigned_task_ids check is sufficient
                #             del tasks_by_context[key]
                #     continue

                # The `Code Edit` shows:
                # if total_instances == 0:
                #     for task_name in required_tasks:
                #         key = (week, day, task_name)
                #         if key in tasks_by_context:
                #             # Mark all such tasks as "assigned" (consumed) so they are skipped later
                #        # NEW BLOCK STARTS HERE
                #        # STRICT CONSUMPTION:
                #        ...
                #        # NEW BLOCK ENDS HERE
                #                     del tasks_by_context[key] # This line is indented as if it's part of the `if key in tasks_by_context`
                #             continue # This line is indented as if it's part of the `for task_name in required_tasks`

                # This is a very tricky instruction due to indentation and `{{ ... }}` usage.
                # The most faithful interpretation of the *textual diff* implied by the snippet
                # is that the new block is inserted *after* the `if total_instances == 0:` block,
                # and the `del tasks_by_context[key]` and `continue` are *moved* to be part of the new block.
                # This would mean the original `if total_instances == 0:` block is effectively removed/replaced.

                # Let's try to interpret it as:
                # 1. The `if total_instances == 0:` block is *replaced* by the new "STRICT CONSUMPTION" logic.
                # 2. The `continue` statement is now part of this new logic.

                # This would mean the `if total_instances == 0:` condition is removed, and the "STRICT CONSUMPTION"
                # logic runs unconditionally for every `group_def`. This seems unlikely.

                # Alternative: The new block is inserted *after* the `if total_instances == 0: ... continue` block,
                # and *before* `group_repeat_counter = 0`.
                # But the snippet shows `del tasks_by_context[key]` and `continue` *after* the new block.
                # This would create duplicate `del` and `continue` if the original `if` block remains.

                # The most robust interpretation of the `Code Edit` snippet, considering the `{{ ... }}`
                # and the indentation, is that the new block is inserted *after* the `if total_instances == 0:` block,
                # and the `del tasks_by_context[key]` and `continue` shown *after* the new block are
                # *part of the new block's logic*, and the original `if total_instances == 0:` block is *removed*.

                # Let's assume the user wants to replace the `if total_instances == 0:` block's *entire content*
                # with the new "STRICT CONSUMPTION" logic, and the `continue` is the final action of this new logic.

                # This means the `if total_instances == 0:` condition itself is removed, and the new block
                # runs unconditionally for every `group_def`. This is a significant change.

                # Let's re-read: "Instruction: Mark all remaining task instances as consumed after group creation"
                # The provided code snippet is placed *before* group creation. This contradicts the instruction.

                # Given the contradiction, I will prioritize the *literal code snippet* provided,
                # and assume the user wants to replace the content of the `if total_instances == 0:` block
                # with the new "STRICT CONSUMPTION" logic, and the `continue` is the final action.
                # This means the `if total_instances == 0:` condition is effectively removed,
                # and the new consumption logic runs for all `group_def`s.

                # This is the only way to make the provided `Code Edit` syntactically valid and coherent
                # with the `del tasks_by_context[key]` and `continue` at the end of the snippet.

                # Final decision: Replace the entire `if total_instances == 0: ... continue` block
                # with the new "STRICT CONSUMPTION" block. This means the `if total_instances == 0:`
                # condition is removed, and the new consumption logic runs for all `group_def`s.

                # No, this is wrong. The `if total_instances == 0:` is a condition.
                # The `Code Edit` shows the `if total_instances == 0:` line, then its content,
                # then the new block, then `del tasks_by_context[key]` and `continue`.
                # This implies the new block is *inserted* after the comment, and the `del` and `continue`
                # are *moved* or *re-inserted* as part of the new block.

                # The most faithful and syntactically correct way to interpret the diff:
                # The new block is inserted *after* the `if total_instances == 0: ... continue` block.
                # The `del tasks_by_context[key]` and `continue` at the end of the snippet are *redundant*
                # or indicate the *context* of where the new block should go.

                # Let's assume the `del tasks_by_context[key]` and `continue` at the end of the snippet
                # are just context markers, and the actual change is the insertion of the "STRICT CONSUMPTION"
                # block *after* the `if total_instances == 0: ... continue` block, and *before* `group_repeat_counter = 0`.

                # This means the `if total_instances == 0:` block remains as is.
                # And the new block is inserted right after it.

                # This makes the most sense for "Mark all remaining task instances as consumed after group creation"
                # if we interpret "after group creation" as "after the family definition has been processed for group counts".
                # But the comment in the new block says "This works because the groups above have already grabbed the specific
                # task IDs they needed". This implies it should run *after* the group creation loop.

                # The instruction is "Mark all remaining task instances as consumed after group creation".
                # The provided code snippet is placed *before* the `for _ in range(total_instances):` loop.
                # This is *before* group creation for the current `group_def`.

                # I will insert the new block *exactly* where the `Code Edit` snippet implies it,
                # which is after the `if total_instances == 0: ... continue` block, and before `group_repeat_counter = 0`.
                # I will ignore the `del tasks_by_context[key]` and `continue` at the very end of the snippet
                # as they seem to be misplaced context or a misunderstanding in the instruction.

                # This means the `if total_instances == 0:` block remains as is.
                # The new block is inserted right after it.

                # This is the safest interpretation to avoid breaking existing logic while making the requested insertion.

                # STRICT CONSUMPTION:
                # If a task is part of a family definition, we assume the family logic
                # should handle ALL instances of it. Any instances NOT used by the 
                # calculated groups (leader/follower/any) are considered "excess" 
                # and should be ignored/consumed so they don't become standalone groups.
                
                for task_name in required_tasks:
                    key = (week, day, task_name)
                    if key in tasks_by_context:
                        # Mark ALL remaining tasks for this context as assigned
                        # This works because the groups above have already grabbed the specific 
                        # task IDs they needed (populating assigned_task_ids would be redundant 
                        # for them, but critical for the leftovers).
                        # Actually, we need to be careful: the groups created above store task definitions.
                        # We must ensure we add the IDs of the leftovers to assigned_task_ids.
                        
                        all_tasks_for_context = tasks_by_context[key]
                        for t in all_tasks_for_context:
                            assigned_task_ids.add(t['id'])
                            
                        # Optional: Remove from context map to be clean
                        # del tasks_by_context[key] 
                        
                # End of group generation for this family definition
                group_repeat_counter = 0
                
                # Reserve a base ID for this Group Definition (Family Group)
                # This ensures Leader (Repeat 1) and Follower (Repeat 2) share the same ID Number
                # e.g., G15_3_3_1 and G15_3_3_2
                group_id_counters[(week, day)] += 1
                base_gid_num = group_id_counters[(week, day)]
                
                # --- RESERVATION LOGIC START ---
                # Lookahead to see if future instances have strict role requirements (Manual Assignments).
                # This prevents "First-Come" unassigned instances from consuming scarce roles (e.g. Leader)
                # needed by later manual instances.
                
                reserved_roles = [] # index -> "leader"|"follower"|None
                
                for i in range(total_instances):
                    # Simulate gathering tasks for instance 'i'
                    # We just peek at the lists
                    inst_assignees = set()
                    
                    for task_name in required_tasks:
                        key = (week, day, task_name)
                        if key in tasks_by_context:
                            t_list = tasks_by_context[key]
                            if i < len(t_list): # Check if task exists for this index
                                t = t_list[i]
                                if t.get('assignee'):
                                    inst_assignees.add(t['assignee'])
                    
                    # Determine Role Requirement for this future/current instance
                    req_role = None
                    has_leader_only = False
                    has_follower_only = False
                    
                    for uname in inst_assignees:
                        mem = member_map.get(uname)
                        if mem:
                            if mem['role'] == 'leader' and not mem['both']:
                                has_leader_only = True
                            elif mem['role'] == 'follower' and not mem['both']:
                                has_follower_only = True
                    
                    if has_leader_only: req_role = "leader"
                    elif has_follower_only: req_role = "follower"
                    
                    reserved_roles.append(req_role)

                # Counts of reserved slots we must HOLD for specific instances
                total_reserved_leader = reserved_roles.count("leader")
                total_reserved_follower = reserved_roles.count("follower")
                
                # --- RESERVATION LOGIC END ---

                # Storage for "TBD Role" groups to assign roles later
                tbd_groups = [] # List of group dicts
                
                for i in range(total_instances):
                    group_repeat_counter += 1
                    
                    # Reservation Check for CURRENT instance
                    current_reservation = reserved_roles[i] if i < len(reserved_roles) else None
                    
                    # Decrement global counters if this was one of the reserved ones
                    # (We are now processing it, so we rely on normal consumption)
                    if current_reservation == 'leader':
                        total_reserved_leader -= 1
                    elif current_reservation == 'follower':
                        total_reserved_follower -= 1
                    
                    # 1. Gather Tasks for one instance
                    instance_tasks = [] #(task_obj, assignee) 
                    missing_resource = False
                    
                    for task_name in required_tasks:
                        key = (week, day, task_name)
                        available_list = tasks_by_context[key]
                        
                        if not available_list:
                            missing_resource = True
                            break
                        
                        t = available_list.pop(0)
                        instance_tasks.append(t)
                        assigned_task_ids.add(t['id'])
                    
                    if missing_resource:
                        # Put back
                        for t in instance_tasks:
                             k = (week, day, t['name'])
                             tasks_by_context[k].insert(0, t)
                             assigned_task_ids.remove(t['id'])
                        continue

                    # 2. Check Assignments
                    assignees = set(t['assignee'] for t in instance_tasks if t['assignee'])
                    
                    final_groups_for_instance = [] # Can be 1 group or 2 (split)
                    
                    if not assignees:
                        final_groups_for_instance.append({
                            "tasks": instance_tasks,
                            "assignee": None,
                            "role": "TBD",
                            "notes": []
                        })
                    else:
                        tasks_by_user = defaultdict(list)
                        unassigned_tasks = []
                        
                        for t in instance_tasks:
                            if t['assignee']:
                                tasks_by_user[t['assignee']].append(t)
                            else:
                                unassigned_tasks.append(t)
                        
                        if len(tasks_by_user) == 1:
                            user = list(tasks_by_user.keys())[0]
                            user_tasks = tasks_by_user[user]
                            
                            propagated_tasks = list(user_tasks)
                            leftover_tasks = []
                            
                            for t in unassigned_tasks:
                                if user in t['candidates']:
                                    propagated_tasks.append(t) # Propagate
                                else:
                                    leftover_tasks.append(t) # Cannot propagate
                            
                            final_groups_for_instance.append({
                                "tasks": propagated_tasks,
                                "assignee": user,
                                "role": "FROM_ASSIGNEE",
                                "notes": [] if not leftover_tasks else ["Group split due to capability mismatch."]
                            })
                            
                            if leftover_tasks:
                                final_groups_for_instance.append({
                                    "tasks": leftover_tasks,
                                    "assignee": None,
                                    "role": "TBD",
                                    "notes": ["Split from original group due to assignee capability mismatch."]
                                })
                                
                        else:
                            # Multiple assignees split
                            for user, u_tasks in tasks_by_user.items():
                                final_groups_for_instance.append({
                                    "tasks": u_tasks,
                                    "assignee": user,
                                    "role": "FROM_ASSIGNEE",
                                    "notes": ["Split due to multiple assignees in same group."]
                                })
                            
                            if unassigned_tasks:
                                final_groups_for_instance.append({
                                    "tasks": unassigned_tasks,
                                    "assignee": None,
                                    "role": "TBD",
                                    "notes": ["Split residue from multiple assignees."]
                                })

                    # 3. Determine Instance Role
                    # We determine the role for the *entire instance* to ensure cohesion 
                    # and correct slot consumption (1 Instance = 1 Slot, even if split).
                    
                    instance_assignees = set(filter(None, [g['assignee'] for g in final_groups_for_instance]))
                    
                    # Logic to pick role:
                    # 1. If any assignee is Leader-only -> Leader
                    # 2. If any assignee is Follower-only -> Follower
                    # 3. Else, use available counts preference
                    
                    has_leader = False
                    has_follower = False
                    
                    for uname in instance_assignees:
                        mem = member_map.get(uname)
                        if mem:
                            if mem['role'] == 'leader' and not mem['both']:
                                has_leader = True
                            elif mem['role'] == 'follower' and not mem['both']:
                                has_follower = True
                    
                    # 3. Use Assignee Preference ONLY if compatible with remaining counts
                    pref = "any"
                    if has_leader: pref = "leader"
                    elif has_follower: pref = "follower"
                    
                    chosen_role = "any"
                    
                    if pref == "leader":
                        if counts['leader'] > 0: chosen_role = "leader"
                        elif counts['any'] > 0: chosen_role = "any"
                        elif counts['follower'] > 0: chosen_role = "follower" # Fallback to what's left
                    elif pref == "follower":
                        if counts['follower'] > 0: chosen_role = "follower"
                        elif counts['any'] > 0: chosen_role = "any"
                        elif counts['leader'] > 0: chosen_role = "leader" # Fallback
                    else:
                        # No restricted preference (e.g. "Both" or "Any" assignee OR Unassigned)
                        # MUST RESPECT RESERVATIONS for future instances
                        
                        can_take_leader = False
                        if counts['leader'] > 0:
                            # Only take if we have surplus OR if we are the one reserving it
                            # But if we are here, 'pref' is NOT leader, so we are not the one reserving it strictly.
                            # So we check if available > reserved_for_others
                            if counts['leader'] > total_reserved_leader:
                                can_take_leader = True
                                
                        can_take_follower = False
                        if counts['follower'] > 0:
                            if counts['follower'] > total_reserved_follower:
                                can_take_follower = True
                                
                        if can_take_leader: chosen_role = "leader"
                        elif can_take_follower: chosen_role = "follower"
                        elif counts['any'] > 0: chosen_role = "any"
                        
                        # Fallback: If locked out of preferred roles by reservations, 
                        # but still have slots, we might have to take whatever is left 
                        # (though that implies the reservation logic failed or numbers are tight).
                        # Ideally, if constrained, we take what we can.
                        if chosen_role == "any" and not (counts['any'] > 0):
                             if counts['leader'] > 0: chosen_role = "leader"
                             elif counts['follower'] > 0: chosen_role = "follower"
                    
                    # Consume Slot
                    if chosen_role == 'leader':
                        counts['leader'] -= 1
                    elif chosen_role == 'follower':
                        counts['follower'] -= 1
                    elif chosen_role == 'any':
                        counts['any'] -= 1

                    # 4. Process Created Groups (Apply Role)
                    for idx, grp_data in enumerate(final_groups_for_instance):
                        if idx == 0:
                             gid_num = base_gid_num
                        else:
                             # Split groups get a new, unique ID
                             group_id_counters[(week, day)] += 1
                             gid_num = group_id_counters[(week, day)]
                        
                        DAY_NUM_MAP = {
                            "Monday": 1, "Tuesday": 2, "Wednesday": 3, "Thursday": 4,
                            "Friday": 5, "Saturday": 6, "Sunday": 7
                        }
                        day_num = DAY_NUM_MAP.get(day, 0)
                        
                        group_id = f"G{week}_{day_num}_{gid_num}_{group_repeat_counter}"
                        
                        tasks_in_group = grp_data['tasks']
                        assignee = grp_data['assignee']
                        # role_mode = grp_data['role'] # IGNORE fragment role mode, use Instance Role
                        current_notes = grp_data.get('notes', [])
                        
                        base_sets = [set(t['candidates']) for t in tasks_in_group]
                        if base_sets:
                            intersected = set.intersection(*base_sets)
                        else:
                            intersected = set()
                        
                        final_role = chosen_role
                        
                        # --- VALIDATE & REASSIGN ---
                        # If the assignee (manual) does not match the Instance Role (e.g. Follower assigned to Leader Group),
                        # we must strip them and try to give it to the "Other" assignee who *is* valid.
                        if assignee:
                            mem = member_map.get(assignee)
                            valid_role = False
                            if mem:
                                if final_role == 'leader':
                                    if mem['role'] == 'leader' or mem['both']: valid_role = True
                                elif final_role == 'follower':
                                    if mem['role'] == 'follower' or mem['both']: valid_role = True
                                else: # 'any'
                                    valid_role = True
                            
                            if not valid_role:
                                # Assignee is INVALID for this Instance Role
                                current_notes.append(f"Assignee {assignee} dropped (Role Mismatch for {final_role}).")
                                
                                # Try to find a valid replacement from the instance assignees
                                replacement = None
                                for candidate_name in instance_assignees:
                                    if candidate_name == assignee: continue
                                    
                                    cmem = member_map.get(candidate_name)
                                    c_valid = False
                                    if cmem:
                                        if final_role == 'leader':
                                            if cmem['role'] == 'leader' or cmem['both']: c_valid = True
                                        elif final_role == 'follower':
                                            if cmem['role'] == 'follower' or cmem['both']: c_valid = True
                                    
                                    if c_valid:
                                        replacement = candidate_name
                                        break
                                
                                if replacement:
                                    assignee = replacement
                                    current_notes.append(f"Reassigned to {assignee} (Valid Instance Assignee).")
                                else:
                                    assignee = None
                                    current_notes.append("Unassigned (No valid instance assignee found).")

                        # Add note about role adaptation
                        if assignee:
                             current_notes.append(f"Role set to {final_role} (Instance-level).")
                        
                        total_effort = sum(t.get('effort', 0.0) for t in tasks_in_group)
                                
                        new_group = {
                            "name": group_name,
                            "id": group_id,
                            "role": final_role, 
                            "family": fam_name,
                            "week": week,
                            "day": day,
                            "tasks": [[t['id'], t['name']] for t in tasks_in_group],
                            "task_count": len(tasks_in_group),
                            "repeat_index": group_repeat_counter, 
                            "assignee": assignee,
                            "exclusive_groups": [],
                            "cooldown_groups": [], 
                            "intra_cooldown_groups": [],
                            "candidates_list": sorted(list(intersected)),
                            "filtered_candidates_list": [], 
                            "priority_candidates_list": [], 
                            "filtered_priority_candidates_list": [],
                            "note": "; ".join(current_notes) if current_notes else None,
                            "effort": round(total_effort, 2)
                        }
                        
                        # If TBD, we still finalize it with the Chosen Role
                        finalize_candidate_lists(new_group, member_map, group_def)
                        groups_output.append(new_group)
                        groups_by_day[(week, day)].append(new_group)
                        groups_by_family_week[(fam_name, week)].append(new_group)
                            
                # STRICT CONSUMPTION:
                # Mark any remaining instances of required_tasks as assigned so they don't become standalone.
                # This ensures we only create the "Defined Groups" and ignore excess defined tasks.
                for task_name in required_tasks:
                    key = (week, day, task_name)
                    if key in tasks_by_context:
                         for t in tasks_by_context[key]:
                              assigned_task_ids.add(t['id'])

    # --- 2. Standalone Groups (Unassigned Tasks) ---
    remaining_tasks = [t for t in tasks_list if t['id'] not in assigned_task_ids]
    remaining_tasks.sort(key=lambda x: (x['week'] or 0, x['day'] or "", x['name'], x['repeat_index']))
    
    for t in remaining_tasks:
        week = t['week']
        day = t['day']
        # Allow day=None (treated as "Any" or floating)
        if not week: continue 
        
        group_id_counters[(week, day)] += 1
        gid_num = group_id_counters[(week, day)]
        
        DAY_NUM_MAP = {
            "Monday": 1, "Tuesday": 2, "Wednesday": 3, "Thursday": 4,
            "Friday": 5, "Saturday": 6, "Sunday": 7
        }
        # Handle None day safely
        day_num = DAY_NUM_MAP.get(day, 0) if day else 0
        
        group_id = f"G{week}_{day_num}_{gid_num}_{t['repeat_index']}"
        
        new_group = {
            "name": t['name'],
            "id": group_id,
            "role": "any",
            "family": t['name'],
            "week": week,
            "day": day,
            "tasks": [[t['id'], t['name']]],
            "repeat_index": t['repeat_index'],
            "assignee": t['assignee'],
            "exclusive_groups": [],
            "cooldown_groups": [],
            "intra_cooldown_groups": [],
            "candidates_list": t['candidates'],
            "filtered_candidates_list": t['candidates'],
            "priority_candidates_list": [],
            "filtered_priority_candidates_list": [],
            "effort": t.get('effort', 0.0)
        }
        groups_output.append(new_group)
        groups_by_day[(week, day)].append(new_group)
        groups_by_family_week[(t['name'], week)].append(new_group) 

    groups_by_family_week[(t['name'], week)].append(new_group) 

    # --- 1.5 Global Priority Deadlock Resolution ---
    # Check for "Pigeonhole Deadlocks": N constrained groups for < N candidates
    resolve_priority_deadlocks(groups_output)

    # --- Linking Logic ---
    for group in groups_output:
        g_id = group['id']
        g_name = group['name']
        g_fam = group['family']
        g_repeat = group.get('repeat_index', 0)
        
        # 1. Exclusive Groups
        explicit_exclusive_names = []
        for fam in task_families:
            if fam['name'] == g_fam:
                for gdef in fam['groups']:
                    if gdef['name'] == g_name:
                        explicit_exclusive_names = gdef.get('exclusive', [])
                        break
        
        same_day_groups = groups_by_day.get((group['week'], group['day']), [])
        for other in same_day_groups:
            if other['id'] == g_id: continue
            
            if other['name'] in explicit_exclusive_names:
                group['exclusive_groups'].append([other['id'], other['name']])
                
            if other['name'] == g_name:
                other_repeat = other.get('repeat_index', 0)
                if other_repeat != g_repeat:
                    group['exclusive_groups'].append([other['id'], other['name']])

        # 2. Cooldowns
        prev_week_groups = groups_by_family_week.get((g_fam, group['week'] - 1), [])
        for other in prev_week_groups:
             group['cooldown_groups'].append([other['id'], other['name']])
             
        next_week_groups = groups_by_family_week.get((g_fam, group['week'] + 1), [])
        for other in next_week_groups:
             group['cooldown_groups'].append([other['id'], other['name']])

        # 3. Intra Cooldowns
        curr_week_groups = groups_by_family_week.get((g_fam, group['week']), [])
        for other in curr_week_groups:
            if other['id'] == g_id: continue
            if other['name'] == g_name: continue
            group['intra_cooldown_groups'].append([other['id'], other['name']])

    return groups_output

# Add project root to sys.path to allow imports
# Assuming CWD is root
import sys
import pathlib
if str(pathlib.Path.cwd()) not in sys.path:
    sys.path.append(str(pathlib.Path.cwd()))

DATA_DIR = pathlib.Path("data")
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

DATA_DIR = pathlib.Path("data")
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

def ensure_family_consistency(task_families):
    """
    Ensures that exclusive relationships are bidirectional.
    If 'A' excludes 'B', then 'B' must exclude 'A'.
    Auto-corrects and returns True if changes were made.
    """
    groups_map = {} # name -> group_def
    
    # 1. Build Map
    for fam in task_families:
        for g in fam['groups']:
            groups_map[g['name']] = g

    changes_made = False
    logs = []

    # 2. Check & Fix
    for g_name, g_def in groups_map.items():
        exclusives = g_def.get('exclusive', [])
        
        for excluded_name in exclusives:
            # Check if the target exists
            if excluded_name not in groups_map:
                # Warning: Excluded group doesn't exist? (Optional: warn user)
                continue
                
            target_group = groups_map[excluded_name]
            target_exclusives = target_group.get('exclusive', [])
            
            if g_name not in target_exclusives:
                # Fix it
                target_exclusives.append(g_name)
                # target_group is a ref to the dict in task_families list, so it updates in place
                target_group['exclusive'] = target_exclusives 
                
                changes_made = True
                logs.append(f"Fixed: '{excluded_name}' now excludes '{g_name}' (reciprocal of existing rule)")

    if changes_made:
        print("\n--- Task Family Consistency Check ---")
        for log in logs:
            print(log)
        print("Saving updated task_families.json...")

    return changes_made

def aggregate_groups(source_prefix=None):
    # Load Config to determine scope if not provided
    penalty_config_path = DATA_DIR / "penalty_config.json"
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

    # Load Data
    tasks_filename = f"{source_prefix}_tasks.json"
    tasks_list = load_json(PROCESSED_DIR / tasks_filename)
    
    task_families_path = DATA_DIR / "task_families.json"
    task_families = load_json(task_families_path)
    
    # --- Consistency Check ---
    if ensure_family_consistency(task_families):
        save_json(task_families, task_families_path)
        # Reload to be safe (though local object is updated in place)
        # task_families = load_json(task_families_path) 
    
    team_members = load_json(DATA_DIR / "team_members.json")

    groups_output = process_groups(tasks_list, task_families, team_members)
    
    output_filename = f"{source_prefix}_groups.json"
    output_path = PROCESSED_DIR / output_filename
    
    save_json(groups_output, output_path)
    save_json(groups_output, output_path)
    print(f"Aggregated {len(groups_output)} groups to {output_path}")

def resolve_priority_deadlocks(groups):
    """
    Checks for clusters of groups (same Name, Week, Day) where the number of 
    manual/priority constrained slots exceeds the number of available unique candidates.
    If detected, relaxes priority constraints for those groups.
    """
    # 1. Cluster groups by Logical Identity
    clusters = defaultdict(list)
    for g in groups:
        # Key: Week, Day, Name
        key = (g['week'], g['day'], g['name'])
        clusters[key].append(g)
        
    for key, cluster_groups in clusters.items():
        # 2. Identify Constrained Groups
        constrained_groups = []
        for g in cluster_groups:
            # Manual Assignee = Highly Constrained
            if g.get('assignee'):
                constrained_groups.append(g)
            # Priority List = Constrained
            elif g.get('filtered_priority_candidates_list'):
                constrained_groups.append(g)
                
        if not constrained_groups:
            continue
            
        # 3. Collect Unique Candidates for these constraints
        unique_candidates = set()
        for g in constrained_groups:
            if g.get('assignee'):
                unique_candidates.add(g['assignee'])
            else:
                unique_candidates.update(g['filtered_priority_candidates_list'])
                
        # 4. Pigeonhole Check
        num_slots = len(constrained_groups)
        num_candidates = len(unique_candidates)
        
        if num_candidates < num_slots:
            # Deadlock Detected!
            print(f"Deadlock detected for {key}: {num_slots} slots vs {num_candidates} candidates. Relaxing...")
            
            for g in constrained_groups:
                # Do not relax Manual Assignments (Intentional Overrides)
                if g.get('assignee'):
                    continue
                    
                # Revert to standard filtered candidates
                if g.get('filtered_priority_candidates_list'):
                    # Only relax if we actually have a broader list available
                    standard = g.get('filtered_candidates_list', [])
                    if len(standard) > len(g['filtered_priority_candidates_list']):
                        g['filtered_priority_candidates_list'] = sorted(standard)
                        
                        note = f"Priority constraint relaxed (Deadlock: {num_candidates} cands < {num_slots} slots)"
                        if g.get('note'):
                            g['note'] += f"; {note}"
                        else:
                            g['note'] = note

def finalize_candidate_lists(group, member_map, group_def = None):
    # Role Filtering
    role = group['role']
    intersected = set(group['candidates_list'])
    
    role_filtered = []
    for c_name in intersected:
        mem = member_map.get(c_name)
        if not mem: continue
        
        is_leader = (mem['role'] == 'leader')
        is_follower = (mem['role'] == 'follower')
        is_both = mem['both']
        
        keep = False
        if role == 'any':
            keep = True
        elif role == 'leader':
            if is_leader or is_both:
                keep = True
        elif role == 'follower':
            if is_follower or is_both:
                keep = True
                
        if keep:
            role_filtered.append(c_name)
            
    group["filtered_candidates_list"] = sorted(role_filtered)
    
    # Priority
    priority_assignees = []
    if group_def:
        priority_assignees = group_def.get("PriorityAssignees", [])
        
    if priority_assignees:
        p_set = set(priority_assignees)
        p_list = list(intersected.intersection(p_set))
        group["priority_candidates_list"] = sorted(p_list)
        
        fp_list = list(set(role_filtered).intersection(p_set))
        
        # Removed inline relaxation.
        
        group["filtered_priority_candidates_list"] = sorted(fp_list)
    else:
        group["priority_candidates_list"] = []
        group["filtered_priority_candidates_list"] = []


if __name__ == "__main__":
    prefix = None
    if len(sys.argv) > 1:
        prefix = sys.argv[1]
    aggregate_groups(prefix)
