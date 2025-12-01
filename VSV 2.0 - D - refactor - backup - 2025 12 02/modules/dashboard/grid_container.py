from PyQt6.QtWidgets import (QTabWidget, QTabBar, QMenu, QWidget, QVBoxLayout, 
                             QPushButton, QToolButton)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QAction, QCursor
from modules.dashboard.grid_widget import GridWidget

class GridContainer(QTabWidget):
    def __init__(self, state_manager, config_manager):
        super().__init__()
        self.state_manager = state_manager
        self.config_manager = config_manager
        self.all_runs_df = None 

        self.setTabsClosable(True)
        self.setMovable(True)
        self.setDocumentMode(True)
        
        # Events
        self.tabCloseRequested.connect(self.close_tab_request)
        
        # Context Menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
        # CORNER WIDGET
        self.btn_clear = QToolButton()
        self.btn_clear.setText("Clear Unpinned")
        self.btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear.clicked.connect(self.close_all_unpinned)
        self.btn_clear.setStyleSheet("border: none; color: #787b86; font-weight: bold; padding: 2px 8px;")
        self.setCornerWidget(self.btn_clear, Qt.Corner.TopRightCorner)

        # Connect
        self.state_manager.data_updated.connect(self.on_data_updated)
        self.state_manager.scenario_selected.connect(self.open_scenario_tab)

        # Style
        self.setStyleSheet("""
            QTabBar::tab {
                background: #1e222d;
                color: #787b86;
                padding: 8px 15px;
                border-right: 1px solid #363a45;
                border-top: 2px solid transparent;
                min-width: 120px;
            }
            QTabBar::tab:selected {
                background: #131722;
                color: #d1d4dc;
                border-top: 2px solid #2962FF;
            }
            QTabBar::tab:hover {
                background: #2a2e39;
            }
            QTabWidget::pane { 
                border: none; 
                background: #131722;
            }
        """)

    def on_data_updated(self, df):
        self.all_runs_df = df
        for i in range(self.count()):
            widget = self.widget(i)
            if isinstance(widget, GridWidget): widget.on_data_updated(df)

    def open_scenario_tab(self, scenario_name):
        # Check existing
        for i in range(self.count()):
            clean_name = self.tabText(i).replace("★ ", "")
            if clean_name == scenario_name:
                self.setCurrentIndex(i)
                return

        new_grid = GridWidget(self.state_manager, self.config_manager)
        if self.all_runs_df is not None:
            new_grid.on_data_updated(self.all_runs_df)
        
        # Initialize
        new_grid.on_scenario_selected(scenario_name)
        
        index = self.addTab(new_grid, scenario_name)
        self.setCurrentIndex(index)
        self.tabBar().setTabData(index, False) # Not pinned

    # --- CLOSING LOGIC ---

    def close_tab_request(self, index):
        if self.is_pinned(index): return 
        widget = self.widget(index)
        self.removeTab(index)
        widget.deleteLater()

    def close_all_unpinned(self):
        for i in range(self.count() - 1, -1, -1):
            if not self.is_pinned(i):
                self.close_tab_request(i)

    # --- PINNING LOGIC ---

    def is_pinned(self, index):
        data = self.tabBar().tabData(index)
        return data is True

    def toggle_pin(self, index):
        current_state = self.is_pinned(index)
        new_state = not current_state
        self.tabBar().setTabData(index, new_state)
        
        text = self.tabText(index)
        if new_state:
            self.setTabText(index, "★ " + text)
            self.tabBar().setTabButton(index, QTabBar.ButtonPosition.RightSide, None)
        else:
            self.setTabText(index, text.replace("★ ", ""))

    # --- CONTEXT MENU ---

    def show_context_menu(self, pos):
        tab_bar = self.tabBar()
        if not tab_bar.geometry().contains(pos): return
        
        local_pos = tab_bar.mapFrom(self, pos)
        index = tab_bar.tabAt(local_pos)
        if index == -1: return

        menu = QMenu(self)
        
        pinned = self.is_pinned(index)
        action_pin = menu.addAction("Unpin Tab" if pinned else "Pin Tab")
        action_pin.triggered.connect(lambda: self.toggle_pin(index))
        
        menu.addSeparator()
        
        action_close = menu.addAction("Close")
        action_close.setEnabled(not pinned)
        action_close.triggered.connect(lambda: self.close_tab_request(index))
        
        action_other = menu.addAction("Close Other Tabs")
        action_other.triggered.connect(lambda: self.close_others(index))
        
        action_all = menu.addAction("Close All Unpinned")
        action_all.triggered.connect(self.close_all_unpinned)

        menu.exec(QCursor.pos())

    def close_others(self, keep_index):
        target_widget = self.widget(keep_index)
        for i in range(self.count() - 1, -1, -1):
            w = self.widget(i)
            if w != target_widget and not self.is_pinned(i):
                self.removeTab(i)
                w.deleteLater()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            tab_bar = self.tabBar()
            local_pos = tab_bar.mapFrom(self, event.pos())
            index = tab_bar.tabAt(local_pos)
            if index != -1:
                self.close_tab_request(index)
                return
        super().mousePressEvent(event)

    # --- PERSISTENCE ---

    def save_state(self):
        tabs = []
        for i in range(self.count()):
            raw_name = self.tabText(i)
            is_pinned = self.is_pinned(i)
            clean_name = raw_name.replace("★ ", "")
            
            tabs.append({
                "name": clean_name,
                "pinned": is_pinned,
                "active": (i == self.currentIndex())
            })
        
        self.config_manager.set_global("open_tabs", tabs)

    def restore_state(self):
        tabs = self.config_manager.get("open_tabs", default=[])
        if not tabs: return
        
        for t in tabs:
            new_grid = GridWidget(self.state_manager, self.config_manager)
            
            # Inject Data
            if self.all_runs_df is not None:
                new_grid.on_data_updated(self.all_runs_df)
                
            # Trigger Logic (Safe way)
            new_grid.on_scenario_selected(t['name'])
            
            index = self.addTab(new_grid, t['name'])
            if t['pinned']: self.toggle_pin(index)
            if t['active']: self.setCurrentIndex(index)