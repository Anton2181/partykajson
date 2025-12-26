import unittest
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from step_02_convert_data import process_calendar_availability

class TestTimePropagation(unittest.TestCase):
    def test_propagation_map_integrity(self):
        """Verify that the propagation map covers expected scenarios."""
        # Use reflection to access the internal map if possible, 
        # or mock the input dataframe to test behavior.
        # Since PROPAGATION_MAP is local to process_calendar_availability, 
        # we can't access it directly without modifying the code or using a mock.
        # However, checking the processing result is better.
        
        # We'll construct a mock Calendar DF
        import pandas as pd
        
        # Row structure: 
        # 0-3: Header garbage/metadata
        # 3: Weeks
        # 4: Dates
        # 5: Days
        # 6-N: Candidates
        
        # Create minimal DF
        # Cols: Metadata (0-3), Data (4)
        
        header_rows = [
            ["", "", "", ""], # 0
            ["", "", "", ""], # 1
            ["", "", "", ""], # 2
            ["", "", "", "", "Week 1"], # 3 (Weeks)
            ["", "", "", "", "2026-01-01"], # 4 (Dates)
            ["", "", "", "", "Monday"], # 5 (Days)
        ]
        
        # Candidate Availability
        # Candidate A: 19-00
        # Candidate B: 19-21
        # Candidate C: 19-20
        # Candidate D: 21-00
        
        candidates = [
            ["", "Candidate A", "Role", "Group", "19-00"],
            ["", "Candidate B", "Role", "Group", "19-21"],
            ["", "Candidate C", "Role", "Group", "19-20"],
            ["", "Candidate D", "Role", "Group", "21-00"],
        ]
        
        all_data = header_rows + candidates
        df = pd.DataFrame(all_data)
        
        result = process_calendar_availability(df)
        
        # Check Week 1 -> Monday -> time_slots
        slots = result["Week 1"]["Monday"]["time_slots"]
        
        # Candidate A (19-00) should appear in 19-20, 19-21, 19-22, 20-21, 20-22, 21-00, 21-22, 22-00
        self.assertIn("Candidate A", slots.get("19-20", []))
        self.assertIn("Candidate A", slots.get("21-00", []))
        
        # Candidate B (19-21) should appear in 19-20, 20-21, 19-21
        self.assertIn("Candidate B", slots.get("19-20", []))
        self.assertIn("Candidate B", slots.get("20-21", []))
        self.assertNotIn("Candidate B", slots.get("21-22", [])) # Should NOT be here
        
        # Candidate C (19-20) should appear only in 19-20
        self.assertIn("Candidate C", slots.get("19-20", []))
        self.assertNotIn("Candidate C", slots.get("20-21", []))
        
        print("Propagation Logic Verified Successfully.")

if __name__ == '__main__':
    unittest.main()
