import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QDockWidget, QLabel, QSplitter, 
                             QMenu, QPushButton, QHBoxLayout, QVBoxLayout, QWidget, QFileDialog)
from PyQt6.QtGui import QAction, QKeySequence, QShortcut
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QByteArray
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

class DataLoader(QThread):
    finished = pyqtSignal(object)
    def __init__(self, path): super().__init__(); self.path = path
    def run(self):
        df = engine.find_and_process_stats(self.path)
        if df is not None and not df.empty: df = engine.enrich_history_with_stats(df)
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

        self.setDockOptions(QMainWindow.DockOption.AllowNestedDocks | 
                            QMainWindow.DockOption.AnimatedDocks | 
                            QMainWindow.DockOption.AllowTabbedDocks)

        self.setup_layout() # Builds the whole UI structure
        self.setup_menu()   # Adds the top 'View' menu
        self.load_app_state() 
        
        self.shortcut_refresh = QShortcut(QKeySequence("F5"), self)
        self.shortcut_refresh.activated.connect(self.refresh_stats)
        
        self.auto_load()

    def setup_layout(self):
        # --- CENTRAL WIDGET CONTAINER ---
        # We create a container to hold the Custom Toolbar + The Splitter
        self.central_container = QWidget()
        self.central_layout = QVBoxLayout(self.central_container)
        self.central_layout.setContentsMargins(0, 0, 0, 0)
        self.central_layout.setSpacing(0)
        self.setCentralWidget(self.central_container)

        # 1. CUSTOM HEADER (The Toolbar)
        self.header_widget = QWidget()
        self.header_widget.setFixedHeight(50)
        self.header_widget.setStyleSheet("background-color: #131722; border-bottom: 1px solid #363a45;")
        header_layout = QHBoxLayout(self.header_widget)
        header_layout.setContentsMargins(20, 0, 20, 0)
        
        # Logo / Dynamic Title
        self.header_label = QLabel("ANALYTICS")
        self.header_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #d1d4dc; margin-right: 20px;")
        header_layout.addWidget(self.header_label)
        
        # Connect signal to label
        self.state_manager.chart_title_changed.connect(self.header_label.setText)
        # --- MODIFIED SECTION END ---
        
        header_layout.addStretch()
        
        # Load Button
        btn_load = QPushButton("Load Folder")
        btn_load.clicked.connect(self.select_folder)
        btn_load.setStyleSheet("""
            QPushButton { background-color: #2a2e39; border: 1px solid #363a45; color: #d1d4dc; padding: 6px 12px; }
            QPushButton:hover { background-color: #363a45; }
        """)
        header_layout.addWidget(btn_load)
        
        # Refresh Button
        self.btn_refresh = QPushButton("Refresh (F5)")
        self.btn_refresh.clicked.connect(self.refresh_stats)
        self.btn_refresh.setStyleSheet("""
            QPushButton { background-color: #2962FF; border: none; color: white; padding: 6px 12px; font-weight: bold;}
            QPushButton:hover { background-color: #1e53e5; }
            QPushButton:disabled { background-color: #363a45; color: #787b86; }
        """)
        header_layout.addWidget(self.btn_refresh)
        
        # Add Header to Central Layout
        self.central_layout.addWidget(self.header_widget)

        # 2. SPLITTER (Chart + Grid)
        self.center_splitter = QSplitter(Qt.Orientation.Vertical)
        self.center_splitter.setObjectName("CenterSplitter")
        
        self.chart_widget = ChartWidget(self.state_manager)
        self.chart_widget.setMinimumHeight(200)
        
        self.grid_container = GridContainer(self.state_manager, self.config_manager)
        self.grid_container.setMinimumHeight(200)
        
        self.center_splitter.addWidget(self.chart_widget)
        self.center_splitter.addWidget(self.grid_container)
        
        # Add Splitter to Central Layout (Below Header)
        self.central_layout.addWidget(self.center_splitter)

        # 3. DOCKS (Sidebars)
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
        self.dock_analyst.setWidget(AnalystTabs(self.state_manager))
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_analyst)

    def setup_menu(self):
        # Standard Menu Bar
        menu_bar = self.menuBar()
        view_menu = menu_bar.addMenu("View")
        
        def add_dock_toggle(dock):
            action = dock.toggleViewAction()
            view_menu.addAction(action)
        
        add_dock_toggle(self.dock_nav)
        add_dock_toggle(self.dock_analyst)

    # --- LOGIC ---

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
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText("Loading...")
        
        self.worker = DataLoader(path)
        self.worker.finished.connect(self.on_data_loaded)
        self.worker.start()

    def on_data_loaded(self, df):
        self.btn_refresh.setEnabled(True)
        self.btn_refresh.setText("Refresh (F5)")
        self.state_manager.data_updated.emit(df)
        self.grid_container.restore_state()

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