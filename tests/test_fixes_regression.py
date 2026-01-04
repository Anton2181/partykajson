import unittest
import json
import sys
import pathlib
import os

# Add src to path
current_dir = pathlib.Path(__file__).parent.resolve()
root_dir = current_dir.parent
sys.path.append(str(root_dir))

from src.step_03_aggregate_groups import ensure_family_consistency, resolve_priority_deadlocks, process_groups

class TestFixesRegression(unittest.TestCase):

    def test_exclusion_propagation(self):
        """Test that ensure_family_consistency makes exclusions bidirectional."""
        families = [
            {
                "name": "Family A",
                "groups": [
                    {"name": "Group A", "exclusive": ["Group B"]}
                ]
            },
            {
                "name": "Family B",
                "groups": [
                    {"name": "Group B", "exclusive": []} # Missing "Group A"
                ]
            }
        ]
        
        changed = ensure_family_consistency(families)
        self.assertTrue(changed)
        
        group_b = families[1]['groups'][0]
        self.assertIn("Group A", group_b['exclusive'])
        
        # Run again, should be stable
        changed = ensure_family_consistency(families)
        self.assertFalse(changed)

    def test_priority_deadlock_resolution(self):
        """Test Pigeonhole deadlock resolution logic."""
        # Case 1: Deadlock (2 slots, 1 candidate)
        groups = [
            {
                "week": 1, "day": "Monday", "name": "Test Group",
                "assignee": None,
                "filtered_priority_candidates_list": ["Alice"],
                "filtered_candidates_list": ["Alice", "Bob", "Charlie"], # Standard list is broader
                "note": ""
            },
            {
                "week": 1, "day": "Monday", "name": "Test Group",
                "assignee": None,
                "filtered_priority_candidates_list": ["Alice"],
                "filtered_candidates_list": ["Alice", "Bob", "Charlie"],
                "note": ""
            }
        ]
        
        resolve_priority_deadlocks(groups)
        
        # Should be relaxed
        self.assertEqual(groups[0]['filtered_priority_candidates_list'], ["Alice", "Bob", "Charlie"])
        self.assertIn("Priority constraint relaxed", groups[0]['note'])
        
        # Case 2: No Deadlock (2 slots, 2 candidates: Alice, Bob) - distinct lists
        groups_valid = [
            {
                "week": 1, "day": "Tuesday", "name": "Test Group 2",
                "assignee": None,
                "filtered_priority_candidates_list": ["Alice", "Bob"],
                "filtered_candidates_list": ["Alice", "Bob", "Charlie"],
                "note": ""
            },
            {
                "week": 1, "day": "Tuesday", "name": "Test Group 2",
                "assignee": None,
                "filtered_priority_candidates_list": ["Bob"], # Even if this is tight
                "filtered_candidates_list": ["Alice", "Bob", "Charlie"],
                "note": ""
            }
        ]
        # Unique Candidates: Alice, Bob (2). Slots: 2. No Deadlock.
        
        resolve_priority_deadlocks(groups_valid)
        
        # Should NOT be relaxed
        self.assertEqual(groups_valid[1]['filtered_priority_candidates_list'], ["Bob"])

    def test_manual_split_and_role_logic(self):
        """Test manual split handling and role counts enforcement."""
        
        # Setup
        # Family: 1 Leader, 1 Follower. 
        # Tasks: T1, T2 (Instance 1), T3, T4 (Instance 2)
        task_families = [{
            "name": "Family Test",
            "groups": [{
                "name": "Group Test",
                "tasks": ["Task A", "Task B"],
                "leader-group-count": 1,
                "follower-group-count": 1,
                "any-group-count": 0
            }]
        }]
        
        team_members = [
            {"name": "LeaderGuy", "role": "leader", "both": False},
            {"name": "FollowerGirl", "role": "follower", "both": False}
        ]
        
        # Case A: Manual Split (User validation check)
        # LeaderGuy takes Task A. FollowerGirl takes Task B.
        # This is 1 Instance. LeaderGuy makes it Leader instance.
        # FollowerGirl is invalid for Leader. Should be swapped to LeaderGuy (or TBD).
        tasks_case_a = [
            {"id": "t1", "name": "Task A", "week": 1, "day": "Monday", "repeat_index": 1, "candidates": ["LeaderGuy", "FollowerGirl"], "assignee": "LeaderGuy", "effort": 1.0},
            {"id": "t2", "name": "Task B", "week": 1, "day": "Monday", "repeat_index": 1, "candidates": ["LeaderGuy", "FollowerGirl"], "assignee": "FollowerGirl", "effort": 1.0}
        ]
        
        groups_a = process_groups(tasks_case_a, task_families, team_members)
        
        # Expect 2 groups (split). 
        # Both should be Leader role (Instance level).
        # Group with FollowerGirl should be reassigned to LeaderGuy (valid leader in instance).
        
        self.assertEqual(len(groups_a), 2)
        g1 = next(g for g in groups_a if g['tasks'][0][1] == "Task A")
        g2 = next(g for g in groups_a if g['tasks'][0][1] == "Task B")
        
        self.assertEqual(g1['role'], 'leader')
        self.assertEqual(g1['assignee'], 'LeaderGuy')
        
        self.assertEqual(g2['role'], 'leader')
        # g2 assignee: FollowerGirl is INVALID for 'leader'. 
        # Logic tries to find replacement in instance assignees (LeaderGuy).
        self.assertEqual(g2['assignee'], 'LeaderGuy')
        
        
        # Case B: Count Enforcement
        # Repeated twice. 1L, 1F available.
        # LeaderGuy takes Instance 1 (T1, T2).
        # LeaderGuy takes Instance 2 (T3, T4).
        # Instance 1 gets L. Instance 2 forced to F.
        # Instance 2 assignee (LeaderGuy) invalid for F. Stripped.
        tasks_case_b = [
            {"id": "t1", "name": "Task A", "week": 2, "day": "Monday", "repeat_index": 1, "candidates": ["LeaderGuy"], "assignee": "LeaderGuy", "effort": 1.0},
            {"id": "t2", "name": "Task B", "week": 2, "day": "Monday", "repeat_index": 1, "candidates": ["LeaderGuy"], "assignee": "LeaderGuy", "effort": 1.0},
            {"id": "t3", "name": "Task A", "week": 2, "day": "Monday", "repeat_index": 2, "candidates": ["LeaderGuy"], "assignee": "LeaderGuy", "effort": 1.0},
            {"id": "t4", "name": "Task B", "week": 2, "day": "Monday", "repeat_index": 2, "candidates": ["LeaderGuy"], "assignee": "LeaderGuy", "effort": 1.0}
        ]
        
        groups_b = process_groups(tasks_case_b, task_families, team_members)
        self.assertEqual(len(groups_b), 2) # Not split, just full groups
        
        g_inst1 = next(g for g in groups_b if g['repeat_index'] == 1)
        g_inst2 = next(g for g in groups_b if g['repeat_index'] == 2)
        
        # Instance 1 should satisfy Leader count
        self.assertEqual(g_inst1['role'], 'leader')
        self.assertEqual(g_inst1['assignee'], 'LeaderGuy')
        
        # Instance 2 forced to Follower
        self.assertEqual(g_inst2['role'], 'follower')
        # LeaderGuy invalid for Follower. Stripped.
        self.assertIsNone(g_inst2['assignee']) 

if __name__ == '__main__':
    unittest.main()
