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
    QTreeWidget, QTreeWidgetItem, QDoubleSpinBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QRectF
from PyQt6.QtGui import QIcon, QFont, QColor, QPixmap, QPainter
from PyQt6.QtSvg import QSvgRenderer  # For sharp vector rendering

import pyqtgraph as pg

# --- Constants & Paths ---
# --- Constants & Paths ---
# --- Path Setup & Writability Check ---
import shutil
import os

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
DARK_THEME = """
QMainWindow {
    background-color: #1e1e1e;
    color: #ffffff;
}
QWidget {
    background-color: #1e1e1e;
    color: #e0e0e0;
    font-family: '.AppleSystemUIFont', 'Helvetica Neue', 'Arial', sans-serif;
    font-size: 14px;
}
QGroupBox {
    border: 1px solid #3e3e3e;
    border-radius: 6px;
    margin-top: 10px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}
QPushButton {
    background-color: #0d6efd;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #0b5ed7;
}
QPushButton:pressed {
    background-color: #0a58ca;
}
QPushButton:disabled {
    background-color: #444;
    color: #888;
}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QListWidget, QTextEdit, QTreeWidget {
    background-color: #2d2d2d;
    border: 1px solid #3e3e3e;
    border-radius: 4px;
    padding: 4px;
    color: #ffffff;
}
QListWidget::item {
    padding: 2px;
    border-bottom: 1px solid #3e3e3e;
}
QListWidget::item:selected {
    background-color: #0d6efd;
}
QScrollBar:vertical {
    background-color: #2d2d2d;
    width: 12px;
}
QScrollBar::handle:vertical {
    background-color: #555;
    border-radius: 6px;
}
QTabWidget::pane { 
    border: 1px solid #3e3e3e; 
}
QTabBar::tab {
    background: #2d2d2d;
    border: 1px solid #3e3e3e;
    padding: 8px 12px;
    color: #aaa;
}
QTabBar::tab:selected {
    background: #3e3e3e;
    color: white;
    font-weight: bold;
}
QHeaderView::section {
    background-color: #333;
    padding: 4px;
    border: 1px solid #3e3e3e;
}
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

class SvgViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.renderer = QSvgRenderer()

    def load(self, filename):
        self.renderer.load(filename)
        self.update()

    def paintEvent(self, event):
        if not self.renderer.isValid():
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Calculate aspect-ratio preserved rect
        s_size = self.renderer.defaultSize()
        w_ratio = self.width() / s_size.width()
        h_ratio = self.height() / s_size.height()
        scale = min(w_ratio, h_ratio)
        
        target_w = int(s_size.width() * scale)
        target_h = int(s_size.height() * scale)
        
        # Center the rect
        x = (self.width() - target_w) // 2
        y = (self.height() - target_h) // 2
        
        target_rect = QRectF(float(x), float(y), float(target_w), float(target_h))
        self.renderer.render(painter, target_rect)
        painter.end()

# --- Main Window ---
class PartykaSolverApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Partyka Solver Pro")
        self.resize(1200, 800)
        self.setStyleSheet(DARK_THEME)
        
        self.config = self.load_config()
        self.worker = None
        
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
        layout = QHBoxLayout(main_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

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
        self.year_combo.setCurrentText("2026") # Default
        
        date_layout.addWidget(self.month_combo)
        date_layout.addWidget(self.year_combo)
        
        # Signal connection moved to end of setup_ui to avoid AttributeErrors
        
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
        self.btn_defaults.setStyleSheet("background-color: #6c757d; font-size: 12px; padding: 4px;")
        self.btn_defaults.clicked.connect(self.restore_defaults)
        
        config_layout.addWidget(self.btn_defaults)

        # 2. Penalty Ladder (Draggable)
        ladder_group = QGroupBox("Penalty Ladder (Priority)")
        ladder_layout = QVBoxLayout()
        self.ladder_list = QListWidget()
        self.ladder_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        # Force vertical fit: Wrap text to next line, disable horizontal scroll
        self.ladder_list.setWordWrap(True)
        self.ladder_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.ladder_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        
        current_ladder = self.config.get("ladder", [])
        for rule in current_ladder:
            item = QListWidgetItem(rule)
            item.setCheckState(Qt.CheckState.Checked) # Assume all enabled for now
            self.ladder_list.addItem(item)
            
        # Hook up reorder/change events to auto-save config
        # Connect both rowsMoved (specific) and layoutChanged (general)
        self.ladder_list.model().rowsMoved.connect(self.update_ladder_config)
        self.ladder_list.model().layoutChanged.connect(self.update_ladder_config)
        
        ladder_layout.addWidget(self.ladder_list)
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
        self.btn_solve.setStyleSheet("background-color: #198754;") # Green
        self.btn_solve.clicked.connect(self.start_solver)
        
        self.btn_export = QPushButton("4. Export CSV")
        self.btn_export.clicked.connect(self.run_export_flow)

        actions_layout.addWidget(self.btn_download)
        actions_layout.addWidget(self.btn_aggregate)
        actions_layout.addWidget(self.btn_solve)
        actions_layout.addWidget(self.btn_export)
        
        actions_group.setLayout(actions_layout)
        sidebar_layout.addWidget(actions_group)
        
        layout.addWidget(sidebar_frame)

        # --- RIGHT SIDE (Tabs & Viz) ---
        viz_splitter = QSplitter(Qt.Orientation.Vertical)

        # Tabs for Results
        self.tabs = QTabWidget()
        
        # TAB 1: Live Graph
        self.tab_graph = QWidget()
        graph_layout = QVBoxLayout(self.tab_graph)
        
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('#1e1e1e')
        self.plot_widget.setTitle("Objective vs Penalties", color="w", size="12pt")
        # Style Bottom Axis (White)
        self.plot_widget.setLabel('bottom', "Time (s)", **{'color': '#ffffff'})
        self.plot_widget.getAxis('bottom').setPen('#ffffff')
        self.plot_widget.getAxis('bottom').setTextPen('#ffffff')
        
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.addLegend()
        
        # Axis 1: Objective (Left, Log)
        p1 = self.plot_widget.getPlotItem()
        p1.setLogMode(x=False, y=True)
        # Style Left Axis (White)
        p1.setLabel('left', 'Objective (Log)', **{'color': '#ffffff'})
        p1.getAxis('left').setPen('#ffffff')
        p1.getAxis('left').setTextPen('#ffffff')
        # Disable SI prefix
        p1.getAxis('left').enableAutoSIPrefix(False)
        
        # Restrict View: Time > 0, Objective > 1 (Log 0)
        p1.setLimits(xMin=0, yMin=0)
        
        self.curve_obj = p1.plot(name="Objective", pen=pg.mkPen('c', width=2))
        
        # Axis 2: Penalties (Right, Linear)
        self.vb2 = pg.ViewBox()
        p1.showAxis('right')
        p1.scene().addItem(self.vb2)
        p1.getAxis('right').linkToView(self.vb2)
        self.vb2.setXLink(p1)
        
        # Explicitly disable Log Mode for the Right Axis
        p1.getAxis('right').setLogMode(False)
        # Style Right Axis (Magenta)
        p1.getAxis('right').setLabel('Penalties (Linear)', color='#ff00ff')
        p1.getAxis('right').setPen('#ff00ff')
        p1.getAxis('right').setTextPen('#ff00ff')
        
        # Enable Auto-Range for the secondary ViewBox
        self.vb2.enableAutoRange(axis=pg.ViewBox.YAxis)
        # Restrict View: Time > 0, Penalties > 0
        self.vb2.setLimits(xMin=0, yMin=0)
        
        self.curve_pen = pg.PlotCurveItem(pen=pg.mkPen('m', width=2), name="Penalties")
        self.vb2.addItem(self.curve_pen)
        
        def updateViews():
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

        viz_splitter.addWidget(self.tabs)
        
        # 2. Log Output
        log_group = QGroupBox("Console Output")
        log_layout = QVBoxLayout()
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Courier New", 12))
        log_layout.addWidget(self.log_output)
        log_group.setLayout(log_layout)
        viz_splitter.addWidget(log_group)

        layout.addWidget(viz_splitter)
        
        # Initial sizing of splitter
        viz_splitter.setSizes([500, 300])
        
        # Initial sizing of splitter
        viz_splitter.setSizes([500, 300])
        
        # Connect Signals (Now that all widgets exist)
        self.month_combo.currentIndexChanged.connect(self.update_button_states)
        self.year_combo.currentIndexChanged.connect(self.update_button_states)
        
        # Initial State Check
        self.update_button_states()

    def restore_defaults(self):
        # 1. Reset Values
        default_ladder = [
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
            "Effort Equalization (Squared Deviation)"
        ]
        
        self.time_spin.blockSignals(True)
        self.thresh_spin.blockSignals(True)
        
        self.time_spin.setValue(120)
        self.thresh_spin.setValue(8.0)
        
        self.time_spin.blockSignals(False)
        self.thresh_spin.blockSignals(False)
        
        # 2. Reset Ladder UI
        self.ladder_list.clear() 
        for rule in default_ladder:
            item = QListWidgetItem(rule)
            item.setCheckState(Qt.CheckState.Checked)
            self.ladder_list.addItem(item)
            
        # 3. Update Config & Save
        self.config["time_limit_seconds"] = 120
        self.config["effort_threshold"] = 8.0
        self.config["ladder"] = default_ladder
        self.save_config()
        self.log("Configuration restored to defaults.", "orange")

    # --- Logic ---
    def log(self, text, color="#ffffff"):
        self.log_output.append(f'<span style="color:{color}">{text}</span>')
        # Auto-scroll
        cursor = self.log_output.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.log_output.setTextCursor(cursor)

    def update_ladder_config(self, *args):
        new_ladder = []
        for i in range(self.ladder_list.count()):
            item = self.ladder_list.item(i)
            new_ladder.append(item.text())
        
        # Only save if changed (layoutChanged fires often)
        if self.config["ladder"] != new_ladder:
            self.config["ladder"] = new_ladder
            self.save_config()
            self.log("Penalty ladder updated.", "#aaa")

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
        
        self.log(f"--- Running {script_name} ---", "#0d6efd")
        
        self.worker = ScriptWorker(script_name, args)
        self.worker.progress_signal.connect(self.log)
        self.worker.finished_signal.connect(self.on_step_finished)
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
        
        # Switch to Progress Tab
        self.tabs.setCurrentIndex(0)
        
        self.btn_solve.setText("Stop Search")
        self.btn_solve.setStyleSheet("background-color: #dc3545;") # Red
        self.btn_download.setEnabled(False)
        self.btn_aggregate.setEnabled(False)
        self.btn_export.setEnabled(False)
        
        # Pass "january_2026"
        month = self.month_combo.currentText().lower()
        year = self.year_combo.currentText()
        prefix = f"{month}_{year}"
        script_args = [prefix] 
        
        self.log("--- Starting Solver ---", "#198754")
        self.worker = ScriptWorker("step_04_run_solver.py", script_args, parse_output=True)
        self.worker.progress_signal.connect(self.log)
        self.worker.data_signal.connect(self.update_graph)
        self.worker.finished_signal.connect(self.on_solver_finished)
        self.worker.start()

    def update_graph(self, data):
        self.times.append(data['time'])
        self.objs.append(data['objective'])
        self.pens.append(data['penalties'])
        self.curve_obj.setData(self.times, self.objs)
        self.curve_pen.setData(self.times, self.pens)

    def on_step_finished(self):
        self.log("Finished.", "#28a745")
        self.worker = None
        self.update_button_states()
        
        # Re-enable all if they were disabled purely for "running" state
        # But update_button_states will handle the "file missing" logic.
        # We also need to re-enable them if they were disabled by run_step
        # Actually run_step disabled them. update_button_states will re-enable them IF satisfied.
        pass
        self.log("--- Finished ---", "#0d6efd")

    def on_solver_finished(self):
        self.btn_solve.setText("3. Start Search")
        self.btn_solve.setStyleSheet("background-color: #198754;")
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
                    item.setForeground(2, QColor('#ff4444'))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PartykaSolverApp()
    window.show()
    sys.exit(app.exec())
