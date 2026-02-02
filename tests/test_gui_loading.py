
import sys
import unittest
from unittest.mock import MagicMock, patch
import json
from pathlib import Path
import tempfile
import os

# Mock PyQt6 before importing src.gui
sys.modules["PyQt6"] = MagicMock()
sys.modules["PyQt6.QtWidgets"] = MagicMock()
sys.modules["PyQt6.QtCore"] = MagicMock()
sys.modules["PyQt6.QtGui"] = MagicMock()
sys.modules["PyQt6.QtSvg"] = MagicMock()
sys.modules["pyqtgraph"] = MagicMock()

# define a base class for QDialog so we don't inherit from MagicMock
class MockQDialog:
    def __init__(self, parent=None):
        pass
    def setWindowTitle(self, title):
        pass
    def resize(self, w, h):
        pass
    def setMinimumWidth(self, w):
        pass

sys.modules["PyQt6.QtWidgets"].QDialog = MockQDialog
sys.modules["PyQt6.QtWidgets"].QWidget = MockQDialog

# Ensure we can import src
sys.path.append(os.getcwd())
# Check if src is importable, otherwise we might need to rely on PYTHONPATH=.
try:
    from src.gui import TaskFamiliesOverlay
except ImportError:
    # If run via python3 tests/..., cwd is root.
    pass

from src.gui import TaskFamiliesOverlay

class TestOverlay(TaskFamiliesOverlay):
    def __init__(self, data_path):
        # Skip super().__init__ to avoid QDialog/UI stuff
        self.data_path = data_path
        self.families_data = [] 
        self.all_tasks = set()
    
    def populate_tree(self):
        pass
        
    def enable_editor(self, enabled):
        pass

class TestTaskFamiliesOverlay(unittest.TestCase):
    def test_load_data_includes_tasks_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            
            # Create processed/tasks.json
            processed_dir = tmp_path / "processed"
            processed_dir.mkdir()
            tasks_json = processed_dir / "tasks.json"
            
            expected_task = "New Unassigned Task"
            with open(tasks_json, 'w') as f:
                json.dump([{"name": expected_task}], f)
                
            # Create task_families.json
            families_json = tmp_path / "task_families.json"
            with open(families_json, 'w') as f:
                json.dump([], f)
                
            # Patch DATA_DIR in src.gui
            with patch("src.gui.DATA_DIR", tmp_path):
                overlay = TestOverlay(families_json)
                overlay.load_data()
                
                self.assertIn(expected_task, overlay.all_tasks)

if __name__ == "__main__":
    unittest.main()
