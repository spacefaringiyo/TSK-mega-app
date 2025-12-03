import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QDockWidget, QLabel, QSplitter, 
                             QMenu, QPushButton, QHBoxLayout, QVBoxLayout, QWidget, 
                             QFileDialog, QDialog, QFormLayout, QSpinBox, QMessageBox,
                             QComboBox, QCheckBox)
from PyQt6.QtGui import QAction, QKeySequence, QShortcut
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QByteArray, QFileSystemWatcher, QTimer
from pathlib import Path

import styles
from core.state_manager import StateManager
from core.config_manager import ConfigManager
from core.analytics import processors as engine 

# Modules
from modules.navigation.browser_tabs import BrowserTabs
from modules.dashboard.grid_container import GridContainer
from modules.charts.chart_widget import ChartWidget
from modules.right_panel.analyst_tabs import AnalystTabs

# --- SETTINGS DIALOG ---
class SettingsDialog(QDialog):
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.setWindowTitle("Preferences")
        self.resize(300, 200)
        self.setStyleSheet(styles.QSS)
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        # Session Gap
        self.sb_gap = QSpinBox()
        self.sb_gap.setRange(1, 1440)
        self.sb_gap.setValue(self.config_manager.get("session_gap", default=30))
        self.sb_gap.setSuffix(" min")
        form.addRow("Session Gap:", self.sb_gap)
        
        # Startup Tab
        self.cb_startup = QComboBox()
        self.cb_startup.addItems(["Last", "Calendar", "Ongoing", "Session Report", "Career Profile"])
        current = self.config_manager.get("startup_tab_mode", default="Last")
        self.cb_startup.setCurrentText(current)
        form.addRow("Startup Tab:", self.cb_startup)
        
        layout.addLayout(form)
        
        lbl_info = QLabel("Note: Changing Session Gap will reload all stats.")
        lbl_info.setStyleSheet("color: #787b86; font-size: 11px; font-style: italic;")
        lbl_info.setWordWrap(True)
        layout.addWidget(lbl_info)
        layout.addStretch()
        
        btn_box = QHBoxLayout()
        btn_save = QPushButton("Save & Reload"); btn_save.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancel"); btn_cancel.clicked.connect(self.reject)
        btn_box.addStretch(); btn_box.addWidget(btn_cancel); btn_box.addWidget(btn_save)
        layout.addLayout(btn_box)

    def get_values(self):
        return {
            "session_gap": self.sb_gap.value(),
            "startup_tab_mode": self.cb_startup.currentText()
        }

# --- DATA LOADER THREAD ---
class DataLoader(QThread):
    finished = pyqtSignal(object)
    
    def __init__(self, path, session_gap): 
        super().__init__()
        self.path = path
        self.session_gap = session_gap

    def run(self):
        # Pass the gap to the processor
        df = engine.find_and_process_stats(self.path, session_gap_minutes=self.session_gap)
        if df is not None and not df.empty: 
            df = engine.enrich_history_with_stats(df)
        self.finished.emit(df)

class KovaaksV2App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VSV 2.0")
        self.resize(1800, 1000)
        self.setStyleSheet(styles.QSS)
        
        self.state_manager = StateManager()
        self.config_manager = ConfigManager()
        self.current_stats_path = None
        self.is_initial_load = True
        
        # Auto-Refresh Logic
        self.file_watcher = QFileSystemWatcher(self)
        self.file_watcher.directoryChanged.connect(self.on_dir_changed)
        self.debounce_timer = QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.setInterval(2000) # Wait 2 seconds after file write
        self.debounce_timer.timeout.connect(self.refresh_stats)
        
        # Listen for chart titles to update header
        self.state_manager.chart_title_changed.connect(self.update_header_title)

        self.setDockOptions(QMainWindow.DockOption.AllowNestedDocks | 
                            QMainWindow.DockOption.AnimatedDocks | 
                            QMainWindow.DockOption.AllowTabbedDocks)

        self.setup_layout() 
        self.setup_menu()   
        self.load_app_state() 
        
        self.shortcut_refresh = QShortcut(QKeySequence("F5"), self)
        self.shortcut_refresh.activated.connect(self.refresh_stats)
        
        self.auto_load()

    def setup_layout(self):
        self.central_container = QWidget()
        self.central_layout = QVBoxLayout(self.central_container)
        self.central_layout.setContentsMargins(0, 0, 0, 0)
        self.central_layout.setSpacing(0)
        self.setCentralWidget(self.central_container)

        # 1. HEADER
        self.header_widget = QWidget()
        self.header_widget.setFixedHeight(50)
        self.header_widget.setStyleSheet("background-color: #131722; border-bottom: 1px solid #363a45;")
        header_layout = QHBoxLayout(self.header_widget)
        header_layout.setContentsMargins(20, 0, 20, 0)
        
        # Dynamic Title Label
        self.header_label = QLabel("ANALYTICS")
        self.header_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #d1d4dc; margin-right: 20px;")
        header_layout.addWidget(self.header_label)
        
        header_layout.addStretch()
        
        # Auto-Refresh Checkbox
        self.chk_auto = QCheckBox("Auto-Refresh")
        self.chk_auto.setStyleSheet("color: #d1d4dc; font-weight: bold; margin-right: 15px;")
        # Load state
        auto_state = self.config_manager.get("auto_refresh", default=True)
        self.chk_auto.setChecked(auto_state)
        self.chk_auto.stateChanged.connect(self.on_auto_toggled)
        header_layout.addWidget(self.chk_auto)
        
        btn_load = QPushButton("Load Folder")
        btn_load.clicked.connect(self.select_folder)
        btn_load.setStyleSheet("""
            QPushButton { background-color: #2a2e39; border: 1px solid #363a45; color: #d1d4dc; padding: 6px 12px; }
            QPushButton:hover { background-color: #363a45; }
        """)
        header_layout.addWidget(btn_load)
        
        self.btn_refresh = QPushButton("Refresh (F5)")
        self.btn_refresh.clicked.connect(self.refresh_stats)
        self.btn_refresh.setStyleSheet("""
            QPushButton { background-color: #2962FF; border: none; color: white; padding: 6px 12px; font-weight: bold;}
            QPushButton:hover { background-color: #1e53e5; }
            QPushButton:disabled { background-color: #363a45; color: #787b86; }
        """)
        header_layout.addWidget(self.btn_refresh)
        
        self.central_layout.addWidget(self.header_widget)

        # 2. SPLITTER
        self.center_splitter = QSplitter(Qt.Orientation.Vertical)
        self.center_splitter.setObjectName("CenterSplitter")
        
        self.chart_widget = ChartWidget(self.state_manager)
        self.chart_widget.setMinimumHeight(200)
        
        self.grid_container = GridContainer(self.state_manager, self.config_manager)
        self.grid_container.setMinimumHeight(200)
        
        self.center_splitter.addWidget(self.chart_widget)
        self.center_splitter.addWidget(self.grid_container)
        
        self.central_layout.addWidget(self.center_splitter)

        # 3. DOCKS
        self.dock_nav = QDockWidget("Browser", self)
        self.dock_nav.setObjectName("DockNav")
        self.dock_nav.setMinimumWidth(50) 
        self.dock_nav.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea)
        self.dock_nav.setWidget(BrowserTabs(self.state_manager, self.config_manager))
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock_nav)

        self.dock_analyst = QDockWidget("Analyst", self)
        self.dock_analyst.setObjectName("DockAnalyst")
        self.dock_analyst.setMinimumWidth(50)
        self.dock_analyst.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)

        self.dock_analyst.setWidget(AnalystTabs(self.state_manager, self.config_manager))
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_analyst)

    def setup_menu(self):
        menu_bar = self.menuBar()
        
        # Settings Menu
        settings_menu = menu_bar.addMenu("Settings")
        act_pref = QAction("Preferences...", self)
        act_pref.triggered.connect(self.open_preferences)
        settings_menu.addAction(act_pref)

        # View Menu
        view_menu = menu_bar.addMenu("View")
        def add_dock_toggle(dock):
            action = dock.toggleViewAction()
            view_menu.addAction(action)
        add_dock_toggle(self.dock_nav)
        add_dock_toggle(self.dock_analyst)

    def update_header_title(self, text):
        self.header_label.setText(text)

    def open_preferences(self):
        dlg = SettingsDialog(self.config_manager, self)
        if dlg.exec():
            vals = dlg.get_values()
            
            old_gap = self.config_manager.get("session_gap", default=30)
            new_gap = vals["session_gap"]
            
            self.config_manager.set_global("session_gap", new_gap)
            self.config_manager.set_global("startup_tab_mode", vals["startup_tab_mode"])
            
            if old_gap != new_gap:
                self.refresh_stats()

    # --- WATCHER LOGIC ---
    def update_watcher(self, path):
        # Clear old paths
        if self.file_watcher.directories():
            self.file_watcher.removePaths(self.file_watcher.directories())
        
        if path and self.chk_auto.isChecked():
            self.file_watcher.addPath(path)

    def on_auto_toggled(self, state):
        self.config_manager.set_global("auto_refresh", self.chk_auto.isChecked())
        if self.chk_auto.isChecked():
            self.update_watcher(self.current_stats_path)
        else:
            if self.file_watcher.directories():
                self.file_watcher.removePaths(self.file_watcher.directories())

    def on_dir_changed(self, path):
        # File added or deleted. Start/Restart debounce timer.
        self.debounce_timer.start()

    # --- LOADING LOGIC ---

    def auto_load(self):
        saved_path = self.config_manager.get("stats_path")
        if saved_path and Path(saved_path).exists():
            self.start_loading(saved_path)
            return

        paths = [
            Path("C:/Program Files (x86)/Steam/steamapps/common/FPSAimTrainer/FPSAimTrainer/stats"),
            Path("D:/SteamLibrary/steamapps/common/FPSAimTrainer/FPSAimTrainer/stats")
        ]
        for p in paths:
            if p.exists():
                self.start_loading(str(p))
                break

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Stats Folder")
        if folder:
            self.config_manager.set_global("stats_path", folder)
            self.start_loading(folder)

    def refresh_stats(self):
        if self.current_stats_path:
            self.start_loading(self.current_stats_path)

    def start_loading(self, path):
        self.current_stats_path = path
        self.update_watcher(path) # Ensure watcher is active if checked
        
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText("Loading...")
        
        gap = self.config_manager.get("session_gap", default=30)
        
        self.worker = DataLoader(path, gap) 
        self.worker.finished.connect(self.on_data_loaded)
        self.worker.start()

    def on_data_loaded(self, df):
        self.btn_refresh.setEnabled(True)
        self.btn_refresh.setText("Refresh (F5)")
        self.state_manager.data_updated.emit(df)
        
        if self.is_initial_load:
            self.grid_container.restore_state()
            self.is_initial_load = False 

    # --- PERSISTENCE ---
    def closeEvent(self, event):
        settings = {
            "geometry": self.saveGeometry().toHex().data().decode(),
            "windowState": self.saveState().toHex().data().decode(),
            "splitterState": self.center_splitter.saveState().toHex().data().decode()
        }
        self.config_manager.set_global("app_layout", settings)
        self.grid_container.save_state()
        super().closeEvent(event)

    def load_app_state(self):
        settings = self.config_manager.get("app_layout", default={})
        if "geometry" in settings:
            self.restoreGeometry(QByteArray.fromHex(settings["geometry"].encode()))
        if "windowState" in settings:
            self.restoreState(QByteArray.fromHex(settings["windowState"].encode()))
        if "splitterState" in settings:
            self.center_splitter.restoreState(QByteArray.fromHex(settings["splitterState"].encode()))
        else:
            self.resizeDocks([self.dock_nav], [250], Qt.Orientation.Horizontal)
            self.resizeDocks([self.dock_analyst], [400], Qt.Orientation.Horizontal)
            self.center_splitter.setStretchFactor(0, 4)
            self.center_splitter.setStretchFactor(1, 6)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = KovaaksV2App()
    window.show()
    sys.exit(app.exec())