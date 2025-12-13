import sys
import json
import subprocess
import time
import platform
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QComboBox, QPushButton, QListWidget, QListWidgetItem, 
    QAbstractItemView, QSpinBox, QCheckBox, QSplitter, QTextEdit, 
    QFrame, QGroupBox, QScrollArea, QSizePolicy, QTabWidget,
    QTreeWidget, QTreeWidgetItem, QDoubleSpinBox, QDialog, QTableWidget, 
    QTableWidgetItem, QHeaderView, QToolButton, QLineEdit, QMenu, QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QRectF, QTimer
from PyQt6.QtGui import QIcon, QFont, QColor, QPixmap, QPainter, QAction
from datetime import datetime, timedelta
from PyQt6.QtSvg import QSvgRenderer  # For sharp vector rendering

import pyqtgraph as pg
pg.setConfigOptions(antialias=True)

# --- Constants & Paths ---
# --- Constants & Paths ---
# --- Path Setup & Writability Check ---
import shutil
import os
try:
    from src.rule_descriptions import RULE_DESCRIPTIONS
except ImportError:
    from rule_descriptions import RULE_DESCRIPTIONS

try:
    from default_families import DEFAULT_FAMILIES
except ImportError:
    DEFAULT_FAMILIES = []

try:
    from default_team import DEFAULT_TEAM
except ImportError:
    DEFAULT_TEAM = []

DEFAULT_LADDER = [
    "Unassigned Group",
    "Underworked Team Member (< Threshold)",
    "Intra-Week Cooldown (Same Week)",
    "Teaching/Assisting Preference",
    "Multi-Day Weekdays (e.g. Tue+Wed)",
    "Teaching/Assisting Equality",
    "Role Diversity (Assignments in each capable family)",
    "Inefficient Day (< 2 Tasks)",
    "Multi-Day General (Weekday+Sunday)",
    "Cooldown (Adjacent Weeks)",
    "Preferred Pair",
    "Effort Equalization (Squared Deviation)"
]

def is_writable(path):
    if not path.exists():
        return False # Or try to create it?
    return os.access(path, os.W_OK)

def setup_paths():
    base_dir = None
    if getattr(sys, 'frozen', False):
        if platform.system() == "Darwin":
            candidate = Path(sys.executable).parent.parent.parent.parent
        else:
            candidate = Path(sys.executable).parent
    else:
        candidate = Path(__file__).parent.parent

    # Check Writability (Fix for Mac Read-Only / Translocation)
    # We try to create a temp file to verify true write access
    try:
        test_file = candidate / ".write_test"
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        base_dir = candidate
        # print(f"[Startup] Base Directory is Writable: {base_dir}")
    except Exception as e:
        print(f"[Startup] Base Directory READ-ONLY ({e}). Failure fallback.")
        # Fallback to User Documents
        docs_dir = Path.home() / "Documents" / "PartykaSolverSaves"
        docs_dir.mkdir(parents=True, exist_ok=True)
        base_dir = docs_dir
        print(f"[Startup] Switched to Documents: {base_dir}")

    # Set CWD
    os.chdir(base_dir)
    
    # Ensure Data Structure Exists
    data_dir = base_dir / "data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / "raw").mkdir(exist_ok=True)
    (data_dir / "processed").mkdir(exist_ok=True)
    (data_dir / "results").mkdir(exist_ok=True)

    # Initial Config Copy (If missing)
    # If we are frozen, we bundled defaults in _MEIPASS/data_defaults
    if getattr(sys, 'frozen', False):
        bundled_defaults = Path(sys._MEIPASS) / "data_defaults"
        if bundled_defaults.exists():
            for f in ["penalty_config.json", "team_members.json", "task_families.json"]:
                target = data_dir / f
                if not target.exists():
                    source = bundled_defaults / f
                    if source.exists():
                        shutil.copy2(source, target)
    
    return base_dir

BASE_DIR = setup_paths()

# Define Execution Python
if getattr(sys, 'frozen', False):
    VENV_PYTHON = sys.executable
else:
    # In source mode, we assume .venv is in the project root (parent of src)
    # NOT in the potentially redirected 'Documents' BASE_DIR
    PROJECT_ROOT = Path(__file__).parent.parent
    if platform.system() == "Windows":
        VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"

# --- Dispatcher for Subprocesses in Frozen Mode ---
# If arguments are passed, we might be trying to run a script
if len(sys.argv) > 1 and sys.argv[1] == "--dispatch":
    import runpy
    script_name = sys.argv[2]
    script_args = sys.argv[3:]
    
    # Locate script inside the bundle
    # Source code IS bundled in _MEIPASS
    bundle_src = Path(sys._MEIPASS) / "src"
    target_script = bundle_src / script_name
    
    # Fake argv so the script sees its own args
    sys.argv = [str(target_script)] + script_args
    # Preserve CWD as BASE_DIR so script can find data
    
    # Run
    print(f"Dispatching {script_name}...")
    try:
        runpy.run_path(str(target_script), run_name="__main__")
    except Exception as e:
        print(f"Execution Error: {e}")
    sys.exit(0)

# Paths relative to the verified writable BASE_DIR
DATA_DIR = BASE_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"
RESULTS_DIR = DATA_DIR / "results"
CONFIG_PATH = DATA_DIR / "penalty_config.json"
SRC_DIR = BASE_DIR / "src"
# If frozen, logic refers to SRC in bundle, but we don't use SRC_DIR much
# scripts use sys._MEIPASS logic usually.

# --- Styles ---
COLORS = {
    "bg": "#FDFCF8",
    "surface": "#FFFFFF",
    "surface_hover": "#FAFAFA",
    "text_primary": "#2D2A26",
    "text_secondary": "#6B665E",
    "border": "#EBE8E0",
    "accent_primary": "#E2B49A",
    "accent_secondary": "#A8C6A3",
    "accent_gold": "#DBCB96",
    "danger": "#E29A9A",
    "success": "#A8C6A3",
    "selection_bg": "#EBF8FF", 
    "selection_text": "#1565c0",
    "blue": "#4A90E2",
    "console_bg": "#FAFAFA",
    "chart_bg": "#FDFCF8",
    "axis_text": "#6B665E",
    "axis_text": "#6B665E",
    "axis_line": "#EBE8E0",
    "graph_obj": "#FF9F43", # Nice Orange
    "graph_pen": "#EE5253"  # Stronger Red
}

LIGHT_THEME = f"""
QMainWindow {{
    background-color: {COLORS["bg"]};
    color: {COLORS["text_primary"]};
}}
QWidget {{
    background-color: {COLORS["bg"]};
    color: {COLORS["text_primary"]};
    font-family: '.AppleSystemUIFont', 'Helvetica Neue', 'Arial', sans-serif;
    font-size: 14px;
}}
QGroupBox {{
    border: 1px solid {COLORS["border"]};
    border-radius: 12px;
    margin-top: 10px;
    font-weight: bold;
    background-color: {COLORS["surface"]};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: {COLORS["text_secondary"]};
}}
QPushButton {{
    background-color: {COLORS["accent_primary"]};
    color: {COLORS["text_primary"]};
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: bold;
}}
QPushButton:hover {{
    background-color: {COLORS["accent_gold"]};
}}
QPushButton:pressed {{
    background-color: {COLORS["accent_secondary"]};
}}
QPushButton:disabled {{
    background-color: {COLORS["border"]};
    color: {COLORS["text_secondary"]};
}}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QListWidget, QTextEdit, QTreeWidget {{
    background-color: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 8px;
    padding: 4px;
    color: {COLORS["text_primary"]};
    selection-background-color: {COLORS["selection_bg"]};
    selection-color: {COLORS["selection_text"]};
}}
QListWidget::item {{
    padding: 4px;
    border-bottom: 1px solid {COLORS["border"]};
}}
QListWidget::item:selected {{
    background-color: {COLORS["selection_bg"]};
    color: {COLORS["selection_text"]};
}}
QScrollBar:vertical {{
    background-color: {COLORS["bg"]};
    width: 12px;
}}
QScrollBar::handle:vertical {{
    background-color: {COLORS["border"]};
    border-radius: 6px;
}}
QMenu {{
    background-color: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 8px;
    padding: 5px;
}}
QMenu::item {{
    padding: 8px 16px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background-color: {COLORS["selection_bg"]};
    color: {COLORS["selection_text"]};
}}
QTabWidget::pane {{ 
    border: 1px solid {COLORS["border"]}; 
    background-color: {COLORS["surface"]};
}}
QTabBar::tab {{
    background: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-bottom: none;
    padding: 8px 16px;
    color: {COLORS["text_secondary"]};
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: {COLORS["bg"]};
    color: {COLORS["text_primary"]};
    font-weight: bold;
    border-bottom: 2px solid {COLORS["accent_primary"]};
}}
QHeaderView::section {{
    background-color: {COLORS["surface_hover"]};
    padding: 6px;
    border: 1px solid {COLORS["border"]};
    color: {COLORS["text_secondary"]};
    font-weight: bold;
}}
QTreeWidget {{
    background-color: {COLORS["surface"]};
    alternate-background-color: {COLORS["surface_hover"]};
}}
"""

# --- Solver Worker Thread ---
class ScriptWorker(QThread):
    progress_signal = pyqtSignal(str) # Raw output line
    data_signal = pyqtSignal(dict)    # Parsed data for graph
    finished_signal = pyqtSignal()
    
    def __init__(self, script_name, args=None, parse_output=False):
        super().__init__()
        self.script_name = script_name
        self.args = args or []
        self.parse_output = parse_output
        self.is_running = True
        self.process = None

    def run(self):
        # Force unbuffered output to get real-time updates
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        
        if getattr(sys, 'frozen', False):
            # Dispatch to internal script
            # VENV_PYTHON is the app executable
            # Add -u manually if dispatch doesn't automatically imply it (it implies python execution)
            # Actually, we can't easily pass -u to the *internal* python interpreter of a frozen app 
            # via argv unless we handle it in our dispatch logic. 
            # But PYTHONUNBUFFERED env var should work.
            cmd = [str(VENV_PYTHON), "--dispatch", self.script_name] + self.args
        else:
            # Normal python execution
            cmd = [str(VENV_PYTHON), "-u", str(SRC_DIR / self.script_name)] + self.args
        
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, # Merge stderr
                text=True,
                env=env, # Pass env with PYTHONUNBUFFERED
                cwd=BASE_DIR, # EXPLICITLY set CWD to the writable directory
                bufsize=0 # Unbuffered pipe
            )
            
            for line in self.process.stdout:
                if not self.is_running:
                    break
                    
                line = line.strip()
                self.progress_signal.emit(line)
                
                if self.parse_output:
                    self._parse_solver_line(line)
                    
            self.process.wait()
            
        except Exception as e:
            self.progress_signal.emit(f"Error: {e}")
        finally:
            self.finished_signal.emit()

    def _parse_solver_line(self, line):
        # Format: "Solution X, time = Y s, objective = Z, penalties = W"
        if "objective =" in line:
            parts = line.split(',')
            try:
                obj_part = [p for p in parts if "objective =" in p][0]
                time_part = [p for p in parts if "time =" in p][0]
                pen_part = [p for p in parts if "penalties =" in p]
                
                objective = float(obj_part.split('=')[1].strip())
                time_val = float(time_part.split('=')[1].strip().replace('s',''))
                penalties = 0
                if pen_part:
                    penalties = int(pen_part[0].split('=')[1].strip())
                    
                self.data_signal.emit({
                    "time": time_val,
                    "objective": objective,
                    "penalties": penalties
                })
            except:
                pass

    def stop(self):
        self.is_running = False
        if self.process:
            self.process.terminate()

        if self.process:
            self.process.terminate()

class SvgViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.renderer = QSvgRenderer()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Scale aspect ratio correctly (contain)
        if not self.renderer.isValid():
            return
            
        s = self.size()
        w, h = s.width(), s.height()
        
        view_box = self.renderer.viewBox()
        vb_w = view_box.width()
        vb_h = view_box.height()
        
        if vb_w == 0 or vb_h == 0:
            return
            
        # Aspect Ratio logic
        scale = min(w / vb_w, h / vb_h)
        target_w = vb_w * scale
        target_h = vb_h * scale
        
        x = (w - target_w) // 2
        y = (h - target_h) // 2
        
        target_rect = QRectF(float(x), float(y), float(target_w), float(target_h))
        self.renderer.render(painter, target_rect)
        painter.end()

    def load(self, filename):
        self.renderer.load(filename)
        self.update()

class PriorityOverlay(QDialog):
    def __init__(self, current_ladder, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Priorities")
        
        # Responsive sizing
        if parent:
            w = int(parent.width() * 0.8)
            h = int(parent.height() * 0.8)
            self.resize(w, h)
        else:
            self.resize(800, 600)
            
        self.setModal(True)
        # Apply parent's stylesheet if possible, or set consistent background
        self.setStyleSheet(parent.styleSheet() if parent else "")
        
        self.ladder = list(current_ladder)
        self.layout = QVBoxLayout(self)
        
        # Instruction
        self.layout.addWidget(QLabel("Drag and drop rows to reorder priorities (Highest priority at top)."))
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4) # [Rank, Name, Description, Actions]
        self.table.setHorizontalHeaderLabels(["Rank", "Rule Name", "Description", "Move"])
        
        # Col 0: Rank (Fixed small width)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 50) 
        
        # Col 1: Name (Size to content, but allow some flex)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        
        # Col 2: Desc (Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        # Col 3: Buttons (Fixed small width)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(3, 70)
        
        # Enable text wrapping and auto-row height
        self.table.setWordWrap(True)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        # Disable internal drag drop since we use buttons now (avoids conflict)
        self.table.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        
        self.populate_table()
        self.layout.addWidget(self.table)
        
        # Buttons
        btn_box = QHBoxLayout()
        restore_btn = QPushButton("Restore Defaults")
        restore_btn.clicked.connect(self.restore_defaults)
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        # Style buttons explicitly if needed, but inheriting theme should work
        btn_box.addWidget(restore_btn)
        btn_box.addStretch()
        btn_box.addWidget(cancel_btn)
        btn_box.addWidget(save_btn)
        self.layout.addLayout(btn_box)

    def restore_defaults(self):
        self.ladder = list(DEFAULT_LADDER)
        self.populate_table()

    def populate_table(self):
        self.table.setRowCount(0)
        for i, rule in enumerate(self.ladder):
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # 1. Rank
            rank_item = QTableWidgetItem(f"{i+1}.")
            rank_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            rank_item.setFlags(Qt.ItemFlag.ItemIsEnabled) # Read only
            self.table.setItem(row, 0, rank_item)
            
            # 2. Name
            name_item = QTableWidgetItem(rule)
            name_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(row, 1, name_item)
            
            # 3. Description
            desc = RULE_DESCRIPTIONS.get(rule, "No description available.")
            desc_item = QTableWidgetItem(desc)
            desc_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(row, 2, desc_item)

            # 4. Action Buttons
            cell_widget = QWidget()
            layout = QHBoxLayout(cell_widget)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(2)
            
            btn_up = QToolButton()
            btn_up.setText("▲")
            btn_up.setFixedSize(20, 20)
            btn_up.setToolTip("Move Up")
            # Use closure to capture current index
            btn_up.clicked.connect(lambda checked, idx=i: self.move_up(idx))
            
            btn_down = QToolButton()
            btn_down.setText("▼")
            btn_down.setFixedSize(20, 20)
            btn_down.setToolTip("Move Down")
            btn_down.clicked.connect(lambda checked, idx=i: self.move_down(idx))
            
            layout.addStretch()
            layout.addWidget(btn_up)
            layout.addWidget(btn_down)
            layout.addStretch()
            
            self.table.setCellWidget(row, 3, cell_widget)
            
    def move_up(self, index):
        if index > 0:
            item = self.ladder.pop(index)
            self.ladder.insert(index - 1, item)
            self.populate_table()
            self.table.selectRow(index - 1)

    def move_down(self, index):
        if index < len(self.ladder) - 1:
            item = self.ladder.pop(index)
            self.ladder.insert(index + 1, item)
            self.populate_table()
            self.table.selectRow(index + 1)
            
    def get_ladder(self):
        return self.ladder

# --- Main Window ---
class TaskFamiliesOverlay(QDialog):
    def __init__(self, parent=None, data_path=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Families & Groups")
        if parent:
            self.resize(int(parent.width() * 0.9), int(parent.height() * 0.9))
        else:
            self.resize(1000, 700)
            
        self.data_path = Path(data_path) if data_path else (BASE_DIR / "data" / "task_families.json")
        self.families_data = [] 
        self.all_tasks = set()
        self.current_group_ref = None # Reference to the dict object being edited
        
        # Main Layout (Vertical)
        self.layout_root = QVBoxLayout(self)
        
        # --- Main Splitter (2 Panes: Work Area | Source Area) ---
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # === Left Pane (Work Area) ===
        # Vertical Layout:
        #   [ Hierarchy Tree ]
        #   [ Config | Assigned Tasks ]
        
        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # 1. Hierarchy Tree (Top)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Hierarchy")
        self.tree.setWordWrap(True)
        self.tree.setUniformRowHeights(False) 
        self.tree.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.itemSelectionChanged.connect(self.on_selection_changed)
        
        # Tree Toolbar (Vertical on the right of tree)
        tree_btn_box = QVBoxLayout()
        tree_btn_box.setContentsMargins(0, 0, 0, 0) # Minimize margins
        tree_btn_box.addStretch() # Top align? Or center? User said "align right edges".
        # If we want alignment, typically center is safer or top.
        # Let's match the Transfer buttons which have stretch on top and bottom (Centered).
        
        self.btn_add_grp = QPushButton("+")
        self.btn_add_grp.setToolTip("Add Family or Group")
        self.btn_add_grp.clicked.connect(self.show_add_menu)
        self.btn_add_grp.setFixedWidth(40)
        self.btn_add_grp.setStyleSheet("padding: 0px; font-size: 18px; font-weight: bold;")
        
        self.btn_del_grp = QPushButton("-")
        self.btn_del_grp.setToolTip("Delete Item")
        self.btn_del_grp.clicked.connect(self.delete_item)
        self.btn_del_grp.setFixedWidth(40)
        self.btn_del_grp.setStyleSheet("padding: 0px; font-size: 18px; font-weight: bold;")
        
        tree_btn_box.addWidget(self.btn_add_grp)
        tree_btn_box.addWidget(self.btn_del_grp)
        tree_btn_box.addStretch()
        
        # Combine Tree + Toolbar (Horizontal)
        tree_container = QWidget()
        tree_layout = QHBoxLayout(tree_container)
        tree_layout.setContentsMargins(0, 0, 0, 0)
        tree_layout.addWidget(self.tree)
        tree_layout.addLayout(tree_btn_box)
        
        # 2. Bottom Row (Config | Assigned)
        bottom_row = QWidget()
        bottom_layout = QHBoxLayout(bottom_row)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        
        # A. Config (Properties)
        self.props_widget = QScrollArea()
        self.props_widget.setWidgetResizable(True)
        props_inner = QWidget()
        self.props_layout = QVBoxLayout(props_inner)
        
        # Name
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Group Name:"))
        self.edit_name = QLineEdit()
        self.edit_name.editingFinished.connect(self.save_name)
        name_row.addWidget(self.edit_name)
        self.props_layout.addLayout(name_row)
        
        # Counts
        cnt_box = QGroupBox("Role Counts")
        cnt_row = QHBoxLayout(cnt_box)
        cnt_row.addWidget(QLabel("Leader:"))
        self.spin_leader = QSpinBox()
        self.spin_leader.setRange(0, 10)
        self.spin_leader.valueChanged.connect(self.save_props)
        cnt_row.addWidget(self.spin_leader)
        
        cnt_row.addWidget(QLabel("Follower:"))
        self.spin_follower = QSpinBox()
        self.spin_follower.setRange(0, 10)
        self.spin_follower.valueChanged.connect(self.save_props)
        cnt_row.addWidget(self.spin_follower)
        
        cnt_row.addWidget(QLabel("Any:"))
        self.spin_any = QSpinBox()
        self.spin_any.setRange(0, 10)
        self.spin_any.valueChanged.connect(self.save_props)
        cnt_row.addWidget(self.spin_any)
        self.props_layout.addWidget(cnt_box)
        
        # Priority
        self.props_layout.addWidget(QLabel("Priority Assignees:"))
        self.edit_priority = QTextEdit()
        self.edit_priority.setMaximumHeight(60)
        self.edit_priority.textChanged.connect(self.save_priority)
        self.props_layout.addWidget(self.edit_priority)
        
        # Exclusive
        self.props_layout.addWidget(QLabel("Mutually Exclusive:"))
        self.list_exclusive = QListWidget()
        self.list_exclusive.setWordWrap(True)
        self.list_exclusive.setMinimumHeight(200) # Expanded ~4x
        self.list_exclusive.itemChanged.connect(self.save_exclusive)
        self.props_layout.addWidget(self.list_exclusive)
        
        self.props_widget.setWidget(props_inner)
        bottom_layout.addWidget(self.props_widget, stretch=1)
        
        # B. Assigned Tasks
        assigned_box = QGroupBox("Group Tasks") # Renamed from "Group Tasks (Chosen)"
        assigned_layout = QVBoxLayout(assigned_box)
        self.list_assigned = QListWidget()
        self.list_assigned.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_assigned.setWordWrap(True)
        self.list_assigned.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        assigned_layout.addWidget(self.list_assigned)
        bottom_layout.addWidget(assigned_box, stretch=1)
        
        # C. Transfer Buttons (Moved here, right of Assigned)
        btn_widget = QWidget()
        btn_layout = QVBoxLayout(btn_widget)
        btn_layout.setContentsMargins(0, 0, 0, 0) # Zero margins to remove padding
        btn_layout.addStretch()
        self.btn_add_task = QPushButton("←") # To Assigned (Left)
        self.btn_add_task.setToolTip("Add to Group")
        self.btn_add_task.clicked.connect(self.add_tasks_to_group)
        self.btn_add_task.setFixedWidth(40)
        self.btn_add_task.setStyleSheet("padding: 0px; font-size: 16px; font-weight: bold;")
        
        self.btn_remove_task = QPushButton("→") # To Available (Right)
        self.btn_remove_task.setToolTip("Remove from Group")
        self.btn_remove_task.clicked.connect(self.remove_tasks_from_group)
        self.btn_remove_task.setFixedWidth(40)
        self.btn_remove_task.setStyleSheet("padding: 0px; font-size: 16px; font-weight: bold;")
        
        btn_layout.addWidget(self.btn_add_task)
        btn_layout.addWidget(self.btn_remove_task)
        btn_layout.addStretch()
        bottom_layout.addWidget(btn_widget)
        
        # Assemble Left Pane
        left_layout.addWidget(tree_container, stretch=1)
        left_layout.addWidget(bottom_row, stretch=1)
        
        self.splitter.addWidget(left_pane)
        
        # === Right Pane (Source Area) ===
        # [ Available Tasks ]
        
        right_pane = QWidget()
        right_layout = QHBoxLayout(right_pane)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Available List
        avail_box = QGroupBox("Available Tasks (All known)")
        avail_layout = QVBoxLayout(avail_box)
        self.list_avail = QListWidget()
        self.list_avail.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_avail.setWordWrap(True)
        self.list_avail.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        avail_layout.addWidget(self.list_avail)
        right_layout.addWidget(avail_box)
        
        self.splitter.addWidget(right_pane)
        
        # Set Ratios (Left Pane vs Right Pane)
        # Left Pane is wider (contains Tree and Config/Assigned)
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 1)
        
        self.layout_root.addWidget(self.splitter)
        
        # Bottom Buttons
        btn_box = QHBoxLayout()
        
        restore_btn = QPushButton("Restore Defaults")
        restore_btn.clicked.connect(self.restore_defaults)
        
        btn_box.addWidget(restore_btn)
        btn_box.addStretch()
        
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_box.addWidget(cancel_btn)
        btn_box.addWidget(save_btn)
        self.layout_root.addLayout(btn_box)
        
        self.load_data()
        
    def load_data(self):
        if self.data_path.exists():
            with open(self.data_path, 'r', encoding='utf-8') as f:
                self.families_data = json.load(f)
        
        # Harvest tasks
        self.all_tasks = set()
        for fam in self.families_data:
            for grp in fam.get("groups", []):
                for t in grp.get("tasks", []):
                    self.all_tasks.add(t)
        
        self.populate_tree()
        self.enable_editor(False)

    def populate_tree(self):
        self.tree.clear()
        for fam in self.families_data:
            fam_item = QTreeWidgetItem(self.tree)
            fam_item.setText(0, fam.get("name", "Unnamed Family"))
            fam_item.setData(0, Qt.ItemDataRole.UserRole, ("FAMILY", fam))
            
            for grp in fam.get("groups", []):
                grp_item = QTreeWidgetItem(fam_item)
                grp_item.setText(0, grp.get("name", "Unnamed Group"))
                grp_item.setData(0, Qt.ItemDataRole.UserRole, ("GROUP", grp))
                
        self.tree.expandAll()

    def on_selection_changed(self):
        items = self.tree.selectedItems()
        if not items:
            self.enable_editor(False)
            return
            
        role, data = items[0].data(0, Qt.ItemDataRole.UserRole)
        if role == "GROUP":
            self.current_group_ref = data
            self.load_group_to_ui(data)
            self.enable_editor(True)
        else:
            self.enable_editor(False)

    def enable_editor(self, enabled):
        # Always keep available list enabled so user can browse
        self.list_avail.setEnabled(True)
        
        # Disable assignment actions and properties if no group selected
        self.list_assigned.setEnabled(enabled)
        self.btn_add_task.setEnabled(enabled)
        self.btn_remove_task.setEnabled(enabled)
        # props_widget is now in middle layout, not right_splitter
        self.props_widget.setEnabled(enabled)
        
        if not enabled:
            self.list_assigned.clear()
            self.edit_name.clear()
            # Reset avail to all tasks when nothing selected
            self.list_avail.clear()
            self.list_avail.addItems(sorted(list(self.all_tasks)))

    def load_group_to_ui(self, group_data):
        self.block_signals(True)
        
        # 1. Tasks
        self.list_avail.clear()
        self.list_assigned.clear()
        
        g_tasks = set(group_data.get("tasks", []))
        
        # Assigned
        for t in group_data.get("tasks", []):
            self.list_assigned.addItem(t)
            
        # Available (All - Assigned)
        sorted_avail = sorted(list(self.all_tasks - g_tasks))
        self.list_avail.addItems(sorted_avail)
        
        # 2. Props
        self.edit_name.setText(group_data.get("name", ""))
        self.spin_leader.setValue(group_data.get("leader-group-count", 0))
        self.spin_follower.setValue(group_data.get("follower-group-count", 0))
        self.spin_any.setValue(group_data.get("any-group-count", 0))
        
        assignees = group_data.get("PriorityAssignees", [])
        self.edit_priority.setPlainText("\n".join(assignees))
        
        # 3. Exclusive Groups
        # Populate list of ALL groups except self
        self.list_exclusive.clear()
        current_excl = set(group_data.get("exclusive", []))
        
        for fam in self.families_data:
            for grp in fam.get("groups", []):
                g_name = grp.get("name")
                if g_name == group_data.get("name"):
                    continue
                    
                item = QListWidgetItem(g_name)
                item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                if g_name in current_excl:
                    item.setCheckState(Qt.CheckState.Checked)
                else:
                    item.setCheckState(Qt.CheckState.Unchecked)
                self.list_exclusive.addItem(item)
                
        self.block_signals(False)

    def block_signals(self, block):
        self.edit_name.blockSignals(block)
        self.spin_leader.blockSignals(block)
        self.spin_follower.blockSignals(block)
        self.spin_any.blockSignals(block)
        self.edit_priority.blockSignals(block)
        self.list_exclusive.blockSignals(block)

    def add_tasks_to_group(self):
        if not self.current_group_ref: return
        items = self.list_avail.selectedItems()
        if not items: return
        
        current_tasks = self.current_group_ref.setdefault("tasks", [])
        for item in items:
            t_name = item.text()
            current_tasks.append(t_name)
            
        self.load_group_to_ui(self.current_group_ref) # Refresh

    def remove_tasks_from_group(self):
        if not self.current_group_ref: return
        items = self.list_assigned.selectedItems()
        if not items: return
        
        current_tasks = self.current_group_ref.get("tasks", [])
        for item in items:
            t_name = item.text()
            if t_name in current_tasks:
                current_tasks.remove(t_name)
                
        self.load_group_to_ui(self.current_group_ref)

    def save_name(self):
        if self.current_group_ref:
            self.current_group_ref["name"] = self.edit_name.text()
            # Need to refresh tree node text?
            self.populate_tree() 
            # Re-select?
            # Complexity: Tree rebuild loses selection. Ideally find item and rename.
            # Simplified: Just keep data ref.

    def save_props(self):
        if not self.current_group_ref: return
        self.current_group_ref["leader-group-count"] = self.spin_leader.value()
        self.current_group_ref["follower-group-count"] = self.spin_follower.value()
        self.current_group_ref["any-group-count"] = self.spin_any.value()

    def save_priority(self):
        if not self.current_group_ref: return
        text = self.edit_priority.toPlainText()
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        self.current_group_ref["PriorityAssignees"] = lines

    def save_exclusive(self, item):
        if not self.current_group_ref: return
        name = item.text()
        checked = (item.checkState() == Qt.CheckState.Checked)
        
        excl = set(self.current_group_ref.get("exclusive", []))
        if checked:
            excl.add(name)
        else:
            if name in excl:
                excl.remove(name)
        self.current_group_ref["exclusive"] = list(excl)

    def show_add_menu(self):
        menu = QMenu(self)
        
        # Determine context
        items = self.tree.selectedItems()
        target_fam = None
        if items:
            role, data = items[0].data(0, Qt.ItemDataRole.UserRole)
            if role == "FAMILY":
                target_fam = data
            elif role == "GROUP":
                 for fam in self.families_data:
                    if data in fam.get("groups", []):
                        target_fam = fam
                        break
        
        # Actions
        action_fam = QAction("Add New Family", self)
        action_fam.triggered.connect(self.add_family)
        menu.addAction(action_fam)
        
        if target_fam:
            fam_name = target_fam.get('name', 'Family')
            action_grp = QAction(f"Add Group to '{fam_name}'", self)
            action_grp.triggered.connect(lambda: self.add_group_to_family(target_fam))
            menu.addAction(action_grp)
            
        menu.exec(self.btn_add_grp.mapToGlobal(self.btn_add_grp.rect().bottomLeft()))

    def add_family(self):
        new_fam = {
            "name": "New Family",
            "groups": []
        }
        self.families_data.append(new_fam)
        self.populate_tree()

    def add_group_to_family(self, target_fam):
        new_grp = {
            "name": "New Group",
            "tasks": [],
            "exclusive": [],
            "PriorityAssignees": [],
            "leader-group-count": 0,
            "follower-group-count": 0,
            "any-group-count": 0
        }
        target_fam.setdefault("groups", []).append(new_grp)
        self.populate_tree()

    def delete_item(self):
        items = self.tree.selectedItems()
        if not items: return
        
        role, data = items[0].data(0, Qt.ItemDataRole.UserRole)
        
        if role == "FAMILY":
            if data in self.families_data:
                self.families_data.remove(data)
        elif role == "GROUP":
            # Remove from parent
            for fam in self.families_data:
                if data in fam.get("groups", []):
                    fam["groups"].remove(data)
                    break
        
        self.populate_tree()
        self.enable_editor(False)

    def restore_defaults(self):
        import copy
        self.families_data = copy.deepcopy(DEFAULT_FAMILIES)
        self.populate_tree()
        self.enable_editor(False)

    def get_data(self):
        return self.families_data

    def accept(self):
        # Save to disk
        try:
            with open(self.data_path, 'w', encoding='utf-8') as f:
                json.dump(self.families_data, f, indent=4)
        except Exception as e:
            print(f"Error saving task families: {e}")
            
        super().accept()
        
class TeamMemberOverlay(QDialog):
    def __init__(self, parent=None, data_path=None):
        super().__init__(parent)
        self.setWindowTitle("Team Config")
        self.resize(800, 600)
        self.data_path = Path(data_path)
        self.team_data = []
        self.current_member = None
        
        self.setup_ui()
        self.load_data()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Splitter: List | Form
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left: List (No buttons)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0,0,0,0)
        
        self.list_members = QListWidget()
        self.list_members.itemSelectionChanged.connect(self.on_selection_changed)
        left_layout.addWidget(self.list_members)
        
        splitter.addWidget(left_widget)
        
        # Right: Form
        self.right_widget = QWidget()
        right_layout = QVBoxLayout(self.right_widget)
        right_layout.setContentsMargins(10, 0, 0, 0)
        
        # Name
        form_layout = QVBoxLayout()
        form_layout.addWidget(QLabel("Name:"))
        self.edit_name = QLineEdit()
        self.edit_name.setReadOnly(True) # Name is immutable
        # self.edit_name.editingFinished.connect(self.save_current) # No editing
        form_layout.addWidget(self.edit_name)
        
        # Role
        group_role = QGroupBox("Primary Role")
        vbox_role = QVBoxLayout(group_role)
        self.rb_leader = QRadioButton("Leader")
        self.rb_follower = QRadioButton("Follower")
        self.rb_group = QButtonGroup(self)
        self.rb_group.addButton(self.rb_leader)
        self.rb_group.addButton(self.rb_follower)
        
        # Connect toggled to save
        self.rb_leader.toggled.connect(self.save_current)
        self.rb_follower.toggled.connect(self.save_current) # Redundant if exclusive, but safe
        
        vbox_role.addWidget(self.rb_leader)
        vbox_role.addWidget(self.rb_follower)
        form_layout.addWidget(group_role)
        
        # Flags
        # Flags
        self.cb_both = QCheckBox("Can do Both")
        self.cb_both.toggled.connect(self.save_current)
        form_layout.addWidget(self.cb_both)
        
        form_layout.addStretch()
        right_layout.addLayout(form_layout)
        
        # Initially disabled
        self.right_widget.setEnabled(False)
        
        splitter.addWidget(self.right_widget)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        
        layout.addWidget(splitter)
        
        # Bottom Buttons
        bottom_box = QHBoxLayout()
        self.btn_restore = QPushButton("Restore Defaults")
        self.btn_restore.clicked.connect(self.restore_defaults)
        bottom_box.addWidget(self.btn_restore)
        bottom_box.addStretch()
        
        btn_save = QPushButton("Save")
        btn_save.clicked.connect(self.accept)
        bottom_box.addWidget(btn_save)
        
        layout.addLayout(bottom_box)
        
    def load_data(self):
        # 1. Load Available Names from processed/tasks.json (Source of Truth)
        # We need to access PROCESSED_DIR. Since this class is in gui.py, we might have access to globals?
        # Yes, BASE_DIR and DATA_DIR are global.
        processed_tasks_path = DATA_DIR / "processed" / "tasks.json"
        
        self.available_names = set()
        
        if processed_tasks_path.exists():
            try:
                with open(processed_tasks_path, 'r', encoding='utf-8') as f:
                    tasks_data = json.load(f)
                    # Extract all candidates
                    for t in tasks_data:
                         if "candidates" in t:
                             self.available_names.update(t["candidates"])
            except Exception as e:
                print(f"Error loading tasks.json: {e}")
        else:
             print("processed/tasks.json not found. Run download/convert step first.")
             # Fallback? Maybe empty list.
        
        # 2. Load Config from team_members.json
        self.team_config = {} # Map name -> {role, both}
        if self.data_path.exists():
            try:
                with open(self.data_path, 'r', encoding='utf-8') as f:
                    raw_list = json.load(f)
                    for item in raw_list:
                        name = item.get("name")
                        if name:
                            self.team_config[name] = item
            except Exception as e:
                print(f"Error loading team: {e}")
        else:
            self.restore_defaults() # This populates self.team_data, we need to convert to config
            # But restore_defaults logic is different now.
            # Let's just init empty if not found.
            pass

        self.populate_list()
        
    def populate_list(self):
        self.list_members.clear()
        
        # Sort names
        sorted_names = sorted(list(self.available_names))
        
        for name in sorted_names:
            # Get config or default
            config = self.team_config.get(name, {"name": name, "role": "follower", "both": False})
            
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, config)
            self.list_members.addItem(item)
            
    def on_selection_changed(self):
        items = self.list_members.selectedItems()
        if not items:
            self.right_widget.setEnabled(False)
            self.current_member = None
            return
            
        self.right_widget.setEnabled(True)
        member = items[0].data(Qt.ItemDataRole.UserRole)
        self.current_member = member
        
        # Populate Form (block signals to prevent auto-save loop)
        self.block_signals(True)
        self.edit_name.setText(member.get("name", ""))
        
        # Role
        role = member.get("role", "follower").lower()
        if role == "leader":
            self.rb_leader.setChecked(True)
        else:
            self.rb_follower.setChecked(True)
            
        # Both
        self.cb_both.setChecked(member.get("both", False))
        self.block_signals(False)
        
    def block_signals(self, block):
        self.edit_name.blockSignals(block)
        self.rb_leader.blockSignals(block)
        self.rb_follower.blockSignals(block)
        self.cb_both.blockSignals(block)

    def save_current(self):
        if not self.current_member: return
        
        # Update Dictionary Object (which is shared/mutable)
        # Note: current_member is the dict stored in ItemData. 
        # We need to make sure we update self.team_config too if it wasn't there.
        name = self.current_member["name"]
        
        if self.rb_leader.isChecked():
            self.current_member["role"] = "leader"
        else:
            self.current_member["role"] = "follower"
            
        self.current_member["both"] = self.cb_both.isChecked()
        
        # Ensure it's in the master config
        self.team_config[name] = self.current_member
        
    # Remove add_member / remove_member methods as they are no longer used
    def add_member(self): pass
    def remove_member(self): pass

    def restore_defaults(self):
        # Restore logic: Reset config for EVERYONE in available_names to Default?
        # Or just reload the default file into team_config?
        # User said "The list itself... should be taken from...".
        # "Restore Defaults" usually matches the provided defaults.
        # But we must respect the available list.
        # So we load DEFAULT_TEAM and use it as the config source.
        import copy
        self.team_config = {}
        for item in DEFAULT_TEAM:
            name = item.get("name")
            if name:
                self.team_config[name] = copy.deepcopy(item)
        
        self.populate_list()
        
    def accept(self):
        # Save to disk
        # Convert self.team_config map back to list
        # We should save ALL config entries, even those not currently in availability list?
        # Or only those? User said "json adds extra info".
        # Safe to save all known configs so settings persist if someone comes back.
        
        export_list = list(self.team_config.values())
        
        try:
            with open(self.data_path, 'w', encoding='utf-8') as f:
                json.dump(export_list, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving team: {e}")
        super().accept()

class PartykaSolverApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Partyka Solver Pro")
        self.resize(1200, 500) # Minimized height
        self.setStyleSheet(LIGHT_THEME)
        
        self.config = self.load_config()
        self.data_dir = DATA_DIR # Set data directory for overlays
        self.worker = None
        self.solve_start_time = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_live_time)
        
        self.setup_ui()
        
    def load_config(self):
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"ladder": [], "time_limit_seconds": 120, "effort_threshold": 8.0}

    def save_config(self):
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=4)

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        # Root Layout: Horizontal (Sidebar | Right Column)
        root_layout = QHBoxLayout(main_widget)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(10)
        
        # --- LEFT SIDEBAR (Controls) ---
        sidebar_frame = QFrame()
        sidebar_frame.setFixedWidth(300)
        sidebar_layout = QVBoxLayout(sidebar_frame)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        
        # 1. Config Section
        config_group = QGroupBox("Configuration")
        config_layout = QVBoxLayout()
        
        # Month/Year
        date_layout = QHBoxLayout()
        self.month_combo = QComboBox()
        self.month_combo.addItems(["January", "February", "March", "April", "May", "June", 
                                   "July", "August", "September", "October", "November", "December"])
        self.year_combo = QComboBox()
        self.year_combo.addItems([str(y) for y in range(2025, 2030)])
        
        # Calculate next month defaults
        now = datetime.now()
        # If we are in Dec (12), next month is 1. Year + 1.
        # Otherwise Month + 1, Year same.
        # QComboBox index is 0-based.
        
        # Simple math: (current_month_index + 1) % 12
        # current_month_index is now.month - 1
        current_month_index = now.month - 1
        target_month_index = (current_month_index + 1) % 12
        
        self.month_combo.setCurrentIndex(target_month_index)
        
        target_year = now.year
        if now.month == 12:
            target_year += 1
            
        # Dynamic year range: Current Year - 1 to +5
        # Ensure target_year is covered
        start_year = now.year - 1
        end_year = max(target_year + 2, now.year + 5)
        
        self.year_combo.clear()
        self.year_combo.addItems([str(y) for y in range(start_year, end_year)])
        self.year_combo.setCurrentText(str(target_year))
        
        date_layout.addWidget(self.month_combo)
        date_layout.addWidget(self.year_combo)
        
        config_layout.addLayout(date_layout)
        
        # Time Limit
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("Time Limit (s):"))
        self.time_spin = QSpinBox()
        self.time_spin.setRange(0, 86400) # 0 to 24 hours
        self.time_spin.setSpecialValueText("Infinity") # Display "Infinity" for 0
        self.time_spin.setValue(int(self.config.get("time_limit_seconds", 120)))
        self.time_spin.valueChanged.connect(self.update_config_values)
        time_layout.addWidget(self.time_spin)
        config_layout.addLayout(time_layout)

        # Effort Threshold
        thresh_layout = QHBoxLayout()
        thresh_layout.addWidget(QLabel("Effort Threshold:"))
        self.thresh_spin = QDoubleSpinBox()
        self.thresh_spin.setRange(1.0, 100.0)
        self.thresh_spin.setSingleStep(0.5)
        self.thresh_spin.setValue(float(self.config.get("effort_threshold", 8.0)))
        self.thresh_spin.valueChanged.connect(self.update_config_values)
        thresh_layout.addWidget(self.thresh_spin)
        config_layout.addLayout(thresh_layout)
        
        config_group.setLayout(config_layout)
        sidebar_layout.addWidget(config_group)

        # Restore Defaults Button
        self.btn_defaults = QPushButton("Restore Defaults")
        self.btn_defaults.setStyleSheet(f"background-color: {COLORS['border']}; color: {COLORS['text_secondary']}; font-size: 12px; padding: 4px;")
        self.btn_defaults.clicked.connect(self.restore_defaults)
        
        config_layout.addWidget(self.btn_defaults)

        config_group.setLayout(config_layout)
        sidebar_layout.addWidget(config_group)

        # --- Advanced Setup (Ladder + Families) ---
        ladder_group = QGroupBox("Advanced Setup")
        ladder_layout = QVBoxLayout()
        
        btn_families = QPushButton("Configure Groups...")
        btn_families.clicked.connect(self.open_task_families_overlay)
        ladder_layout.addWidget(btn_families)

        btn_team = QPushButton("Configure Team...")
        btn_team.clicked.connect(self.open_team_overlay)
        ladder_layout.addWidget(btn_team)

        btn_ladder = QPushButton("Configure Priorities...")
        btn_ladder.clicked.connect(self.open_priority_overlay)
        ladder_layout.addWidget(btn_ladder)
        
        ladder_group.setLayout(ladder_layout)
        sidebar_layout.addWidget(ladder_group)

        # 3. Action Buttons
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout()
        
        self.btn_download = QPushButton("1. Download Data")
        self.btn_download.clicked.connect(self.run_download_flow)
        
        self.btn_aggregate = QPushButton("2. Aggregate Groups")
        self.btn_aggregate.clicked.connect(lambda: self.run_aggregate_flow())
        
        self.btn_solve = QPushButton("3. Start Search")
        # Use pseudo-states for proper disabled styling
        self.btn_solve.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['success']};
                color: white;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:disabled {{
                background-color: {COLORS['border']};
                color: {COLORS['text_secondary']};
            }}
        """)
        self.btn_solve.clicked.connect(self.start_solver)
        
        self.btn_export = QPushButton("4. Export CSV")
        self.btn_export.clicked.connect(self.run_export_flow)

        actions_layout.addWidget(self.btn_download)
        actions_layout.addWidget(self.btn_aggregate)
        actions_layout.addWidget(self.btn_solve)
        actions_layout.addWidget(self.btn_export)
        
        actions_group.setLayout(actions_layout)
        sidebar_layout.addWidget(actions_group)
        
        root_layout.addWidget(sidebar_frame) # Sidebar first

        # --- RIGHT SIDE (Tabs & Viz) ---
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)
        
        # Tabs for Results
        self.tabs = QTabWidget()
        
        # TAB 1: Live Graph
        self.tab_graph = QWidget()
        graph_layout = QVBoxLayout(self.tab_graph)
        
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(COLORS['chart_bg'])
        self.plot_widget.setTitle("Objective vs Penalties", color=COLORS['text_primary'], size="12pt")
        # Style Bottom Axis
        self.plot_widget.setLabel('bottom', "Time (s)", **{'color': COLORS['axis_text']})
        self.plot_widget.getAxis('bottom').setPen(COLORS['axis_line'])
        self.plot_widget.getAxis('bottom').setTextPen(COLORS['axis_text'])
        
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        # Create legend but anchor it to top-right
        self.legend = self.plot_widget.addLegend()
        self.legend.anchor((1,0), (1,0), offset=(-30, 30))
        
        self.plot_widget.setMouseEnabled(x=False, y=False) # Disable zoom/pan
        self.plot_widget.setMenuEnabled(False) # Disable right-click menu
        
        # Axis 1: Objective (Left, Log)
        p1 = self.plot_widget.getPlotItem()
        p1.setLogMode(x=False, y=True)
        # Style Left Axis (White)
        # Style Left Axis
        p1.setLabel('left', 'Objective (Log)', **{'color': COLORS['axis_text']})
        p1.getAxis('left').setPen(COLORS['axis_line'])
        p1.getAxis('left').setTextPen(COLORS['axis_text'])
        # Disable SI prefix
        p1.getAxis('left').enableAutoSIPrefix(False)
        
        # Restrict View: Time > 0, Objective > 1 (Log 0)
        p1.setLimits(xMin=0, yMin=0)
        
        self.curve_obj = p1.plot(name="Objective", pen=pg.mkPen(COLORS['graph_obj'], width=3))
        
        # Axis 2: Penalties (Right, Linear)
        self.vb2 = pg.ViewBox()
        p1.showAxis('right')
        p1.scene().addItem(self.vb2)
        p1.getAxis('right').linkToView(self.vb2)
        self.vb2.setXLink(p1)
        
        # Explicitly disable Log Mode for the Right Axis
        p1.getAxis('right').setLogMode(False)
        # Style Right Axis (Magenta)
        # Style Right Axis
        p1.getAxis('right').setLabel('Penalties (Linear)', color=COLORS['danger'])
        p1.getAxis('right').setPen(COLORS['danger'])
        p1.getAxis('right').setTextPen(COLORS['danger'])
        
        # Enable Auto-Range for the secondary ViewBox
        self.vb2.enableAutoRange(axis=pg.ViewBox.YAxis)
        # Restrict View: Time > 0, Penalties > 0
        self.vb2.setLimits(xMin=0, yMin=0)
        
        self.curve_pen = pg.PlotCurveItem(pen=pg.mkPen(COLORS['danger'], width=2, style=Qt.PenStyle.DashLine), name="Penalties")
        self.vb2.addItem(self.curve_pen)
        
        # Manually add to legend
        self.legend.addItem(self.curve_pen, "Penalties")

        def updateViews():
            # p1.getAxis('right').linkedViewChanged(p1.vb, self.vb2.XAxis) # INCORRECT: Caused TypeError
            self.vb2.setGeometry(p1.vb.sceneBoundingRect())
            self.vb2.linkedViewChanged(p1.vb, self.vb2.XAxis)

        updateViews()
        p1.vb.sigResized.connect(updateViews)
        
        graph_layout.addWidget(self.plot_widget)
        self.tabs.addTab(self.tab_graph, "Solver Progress")
        
        # TAB 2: Effort Chart (SVG)
        self.tab_effort = QWidget()
        self.effort_layout = QVBoxLayout(self.tab_effort)
        
        self.effort_svg_widget = SvgViewer()
        self.effort_layout.addWidget(self.effort_svg_widget)
        
        self.tabs.addTab(self.tab_effort, "Effort Chart")
        
        # TAB 3: Assignments
        self.tab_assign = QWidget()
        assign_layout = QVBoxLayout(self.tab_assign)
        self.tree_assign = QTreeWidget()
        self.tree_assign.setHeaderLabels(["Person / Task", "Detail"])
        self.tree_assign.setColumnWidth(0, 300)
        assign_layout.addWidget(self.tree_assign)
        self.tabs.addTab(self.tab_assign, "Assignments")
        
        # TAB 4: Penalties
        self.tab_penalties = QWidget()
        pen_layout = QVBoxLayout(self.tab_penalties)
        self.tree_pen = QTreeWidget()
        self.tree_pen.setHeaderLabels(["Rule", "Person", "Cost", "Details"])
        pen_layout.addWidget(self.tree_pen)
        self.tabs.addTab(self.tab_penalties, "Penalties")

        right_layout.addWidget(self.tabs)
        
        # --- Bottom Area: Collapsible Console ---
        self.console_container = QWidget()
        console_layout = QVBoxLayout(self.console_container)
        console_layout.setContentsMargins(0, 0, 0, 0)
        
        self.btn_toggle_console = QPushButton("Show Console ▲") # Points UP to indicate expansion
        self.btn_toggle_console.setCheckable(True)
        self.btn_toggle_console.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                padding: 5px;
                background-color: {COLORS['surface']};
                color: {COLORS['text_secondary']};
                border: 1px solid {COLORS['border']};
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
            }}
        """)
        self.btn_toggle_console.clicked.connect(self.toggle_console)
        console_layout.addWidget(self.btn_toggle_console)
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Courier New", 12))
        self.log_output.setVisible(False) # Hidden by default
        console_layout.addWidget(self.log_output)
        
        # Add Console to Right Column (below tabs)
        right_layout.addWidget(self.console_container)
        
        # Set stretch: Tabs get 1 (expand), Console gets 0 (fixed/content)
        right_layout.setStretchFactor(self.tabs, 1)
        right_layout.setStretchFactor(self.console_container, 0)
        
        # Add Right Column to Root
        root_layout.addWidget(right_container)
        
        # Connect Signals (Now that all widgets exist)
        self.month_combo.currentIndexChanged.connect(self.update_button_states)
        self.year_combo.currentIndexChanged.connect(self.update_button_states)
        
        # Initial State Check
        self.update_button_states()

    def restore_defaults(self):
        # 1. Reset Values
        
        self.time_spin.blockSignals(True)
        self.thresh_spin.blockSignals(True)
        
        self.time_spin.setValue(120)
        self.thresh_spin.setValue(8.0)
        
        self.time_spin.blockSignals(False)
        self.thresh_spin.blockSignals(False)
        
        # 2. Reset Ladder UI
        # self.ladder_list.clear() 
        # for rule in default_ladder:
        #     item = QListWidgetItem(rule)
        #     item.setCheckState(Qt.CheckState.Checked)
        #     self.ladder_list.addItem(item)
            
        # 3. Update Config & Save
        self.config["time_limit_seconds"] = 120
        self.config["effort_threshold"] = 8.0
        self.config["ladder"] = DEFAULT_LADDER
        self.save_config()
        self.log("Configuration restored to defaults.", "orange")

    def open_priority_overlay(self):
        current = self.config.get("ladder", [])
        dlg = PriorityOverlay(current, self)
        if dlg.exec():
            new_ladder = dlg.get_ladder()
            if new_ladder != current:
                self.config["ladder"] = new_ladder
                self.save_config()
                self.log("Priority ladder updated via overlay.", COLORS['text_secondary'])
            else:
                self.log("No changes to priority ladder.", COLORS['text_secondary'])

    def open_task_families_overlay(self):
        # Path to data
        data_path = self.data_dir / "task_families.json"
        
        dlg = TaskFamiliesOverlay(self, str(data_path))
        dlg.exec()

    def open_team_overlay(self):
        data_path = self.data_dir / "team_members.json"
        dlg = TeamMemberOverlay(self, str(data_path))
        dlg.exec()



    # --- Logic ---
    def log(self, text, color=None):
        if color is None:
            color = COLORS['text_primary']
        self.log_output.append(f'<span style="color:{color}">{text}</span>')
        # Auto-scroll
        cursor = self.log_output.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.log_output.setTextCursor(cursor)
        
    def toggle_console(self):
        visible = self.log_output.isVisible()
        if visible:
            self.log_output.setVisible(False)
            self.btn_toggle_console.setText("Show Console ▲")
        else:
            self.log_output.setVisible(True)
            self.btn_toggle_console.setText("Hide Console ▼")

    def update_ladder_config(self, *args):
        # Deprecated: Ladder is now managed via Overlay
        pass

    def update_config_values(self):
        self.config["time_limit_seconds"] = self.time_spin.value()
        self.config["effort_threshold"] = self.thresh_spin.value()
        self.save_config()

    def update_button_states(self):
        """Enable/Disable buttons based on file availability."""
        month = self.month_combo.currentText().lower()
        year = self.year_combo.currentText()
        
        
        # 1. Download: Always Enabled
        self.btn_download.setEnabled(True)
        
        # Note: Step 1 (Download) automatically chains Step 2 (Convert).
        # So we don't have a separate Convert button.
        # But we DO check Step 2 outputs to enable Step 3 (Aggregate).
        
        # 3. Aggregate: Requires Processed Tasks
        processed_tasks = PROCESSED_DIR / f"{month}_{year}_tasks.json"
        can_aggregate = processed_tasks.exists()
        self.btn_aggregate.setEnabled(can_aggregate)
        self.btn_aggregate.setToolTip("Requires processed tasks" if not can_aggregate else "")

        # 4. Solve: Requires Aggregated Groups
        groups_file = PROCESSED_DIR / f"{month}_{year}_groups.json"
        can_solve = groups_file.exists()
        self.btn_solve.setEnabled(can_solve)
        self.btn_solve.setToolTip("Requires aggregated groups" if not can_solve else "")

        # 5. Export: Requires Results
        assignments_file = RESULTS_DIR / f"{month}_{year}_assignments_by_person.json"
        # Or checking general results existence? "step_05" uses `assignments.json` usually?
        # step_05 reads: assignments_path = results_dir / f"{month}_{year}_assignments.json"
        # Let's check that one.
        assignments_file = RESULTS_DIR / f"{month}_{year}_assignments.json"
        can_export = assignments_file.exists()
        self.btn_export.setEnabled(can_export)
        self.btn_export.setToolTip("Requires solution results" if not can_export else "")

    def run_step(self, script_name, args=None):
        if self.worker and self.worker.isRunning():
            return
            
        self.btn_download.setEnabled(False)
        self.btn_aggregate.setEnabled(False)
        self.btn_solve.setEnabled(False)
        self.btn_export.setEnabled(False)
        
        self.log(f"--- Running {script_name} ---", COLORS['blue'])
        
        self.worker = ScriptWorker(script_name, args)
        self.worker.progress_signal.connect(self.log)
        # Use built-in 'finished' signal which is emitted AFTER run() returns
        self.worker.finished.connect(self.on_step_finished) 
        self.worker.start()

    def run_download_flow(self):
        # Pass "January 2026"
        arg = f"{self.month_combo.currentText()} {self.year_combo.currentText()}" 
        self.run_step("step_01_download_data.py", args=[arg])

    def run_aggregate_flow(self):
        # Pass "january_2026"
        month = self.month_combo.currentText().lower()
        year = self.year_combo.currentText()
        prefix = f"{month}_{year}"
        self.run_step("step_03_aggregate_groups.py", args=[prefix]) 

    def run_export_flow(self):
        # Pass "january_2026"
        month = self.month_combo.currentText().lower()
        year = self.year_combo.currentText()
        prefix = f"{month}_{year}"
        self.run_step("step_05_export_csv.py", args=[prefix])

    def start_solver(self):
        if self.worker and self.worker.isRunning():
            self.log("Stopping solver...")
            self.worker.stop()
            return

        # Explicitly save any pending config changes from spinboxes
        self.update_config_values()
        
        # Clear Graph
        self.times = []
        self.objs = []
        self.pens = []
        self.curve_obj.setData([], [])
        self.curve_pen.setData([], [])
        self.log_output.clear()
        
        self.solve_start_time = None
        # Timer will be started in update_graph upon first data
        # self.timer.start(50) 
        
        # Switch to Progress Tab
        self.tabs.setCurrentIndex(0)
        
        self.btn_solve.setText("Stop Search")
        # Preserve styling (padding, bold, rounded) but change color to Red
        self.btn_solve.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['danger']};
                color: white;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }}
        """)
        self.btn_download.setEnabled(False)
        self.btn_aggregate.setEnabled(False)
        self.btn_export.setEnabled(False)
        
        # Pass "january_2026"
        month = self.month_combo.currentText().lower()
        year = self.year_combo.currentText()
        prefix = f"{month}_{year}"
        script_args = [prefix] 
        
        self.log("--- Starting Solver ---", COLORS['success'])
        self.worker = ScriptWorker("step_04_run_solver.py", script_args, parse_output=True)
        self.worker.progress_signal.connect(self.log)
        self.worker.data_signal.connect(self.update_graph)
        self.worker.finished.connect(self.on_solver_finished)
        self.worker.start()

    def update_graph(self, data):
        # Initialize timer on first data point
        if self.solve_start_time is None:
            # Sync local time to the solver's reported time
            # So if solver says "Time = 3.0s", we set start_time to 3.0s ago.
            self.solve_start_time = time.time() - data['time']
            self.timer.start(50)

        self.times.append(data['time'])
        self.objs.append(data['objective'])
        self.pens.append(data['penalties'])
        self.curve_obj.setData(self.times, self.objs)
        self.curve_pen.setData(self.times, self.pens)

    def update_live_time(self):
        if not self.solve_start_time:
            return
            
        elapsed = time.time() - self.solve_start_time
        
        # Extend the X-axis view to accommodate current time
        p1 = self.plot_widget.getPlotItem()
        
        # If we have data, we want to see it, but also seeing the empty space where search is happening
        current_max = max(elapsed, 1.0)
        min_x = 0
        if self.times:
            current_max = max(current_max, max(self.times))
            # Start the graph at the first solution time to avoid "mid-air" gap
            min_x = self.times[0]
            
        p1.setXRange(min_x, current_max, padding=0)

    def on_step_finished(self):
        script_name = self.worker.script_name if self.worker else None
        
        self.log("Finished.", COLORS['success'])
        self.worker = None
        self.timer.stop()
        self.update_button_states()
        
        # Check if we just finished Export
        if script_name == "step_05_export_csv.py":
            month = self.month_combo.currentText().lower()
            year = self.year_combo.currentText()
            prefix = f"{month}_{year}"
            
            # Construct path (RESULTS_DIR is defined globally in this file)
            # Standard output is {prefix}_filled.csv
            csv_path = RESULTS_DIR / f"{prefix}_filled.csv"
            
            if csv_path.exists():
                self.log(f"Opening {csv_path.name}...", COLORS['accent_primary'])
                try:
                    if platform.system() == "Windows":
                        os.startfile(str(csv_path))
                    elif platform.system() == "Darwin":
                        subprocess.call(["open", str(csv_path)])
                    else:
                        subprocess.call(["xdg-open", str(csv_path)])
                except Exception as e:
                    self.log(f"Failed to open file: {e}", "red")

        self.log("--- Finished ---", COLORS['blue'])

    def on_solver_finished(self):
        self.btn_solve.setText("3. Start Search")
        self.btn_solve.setStyleSheet(f"background-color: {COLORS['success']}; color: white;")
        self.on_step_finished()
        
        # Load Result Files
        self.load_results()

    def load_results(self):
        # 1. Load Effort Chart (SVG)
        prefix = f"{self.month_combo.currentText().lower()}_{self.year_combo.currentText()}" 
        
        # Look for SVG
        chart_path = RESULTS_DIR / f"{prefix}_effort_chart.svg"
        if not chart_path.exists():
             chart_path = RESULTS_DIR / "january_2026_effort_chart.svg" # Fallback
             prefix = "january_2026"
        
        if chart_path.exists():
            self.effort_svg_widget.load(str(chart_path))
            self.effort_svg_widget.show()
        else:
            # Fallback text since QSvgWidget doesn't setText
            self.log("Chart not found.", "orange")

        # 2. Load Assignments (by Person)
        assign_path = RESULTS_DIR / f"{prefix}_assignments_by_person.json"
        
        self.tree_assign.clear()
        self.tree_assign.clear()
        if assign_path.exists():
            with open(assign_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            for person, info in data.items():
                p_item = QTreeWidgetItem(self.tree_assign)
                p_item.setText(0, person)
                # Calculate total tasks helper
                tasks = info.get("assignments", [])
                p_item.setText(1, f"{len(tasks)} Tasks")
                
                for task in tasks:
                    t_item = QTreeWidgetItem(p_item)
                    txt = f"[{task.get('role', '?')}] {task.get('group_name','')}"
                    detail = f"W{task.get('week')} {task.get('day')}"
                    t_item.setText(0, txt)
                    t_item.setText(1, detail)
            
            self.tree_assign.expandAll()
        
        # 3. Load Penalties
        pen_path = RESULTS_DIR / f"{prefix}_penalties.json"
        self.tree_pen.clear()
        self.tree_pen.clear()
        if pen_path.exists():
            with open(pen_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for p in data:
                item = QTreeWidgetItem(self.tree_pen)
                item.setText(0, p.get('rule', ''))
                item.setText(1, p.get('person_name') or 'Group')
                item.setText(2, str(p.get('cost', 0)))
                item.setText(3, str(p.get('details', '')))
                
                # Color code high penalties?
                if p.get('cost', 0) > 1000:
                    item.setForeground(2, QColor(COLORS['danger']))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PartykaSolverApp()
    window.show()
    sys.exit(app.exec())
