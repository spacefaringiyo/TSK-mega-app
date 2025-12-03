from PyQt6.QtWidgets import (QTabWidget, QTabBar, QMenu, QWidget, QVBoxLayout, 
                             QPushButton, QToolButton)
from PyQt6.QtCore import Qt, QPoint, QTimer
from PyQt6.QtGui import QAction, QCursor
from modules.dashboard.grid_widget import GridWidget

class GridContainer(QTabWidget):
    def __init__(self, state_manager, config_manager):
        super().__init__()
        self.state_manager = state_manager
        self.config_manager = config_manager
        self.all_runs_df = None
        self.tabs_to_restore = [] # Queue for async restore

        self.setTabsClosable(True)
        self.setMovable(True)
        self.setDocumentMode(True)
        
        self.tabCloseRequested.connect(self.close_tab_request)
        self.currentChanged.connect(self.on_tab_changed, Qt.ConnectionType.QueuedConnection)
        
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
        self.btn_clear = QToolButton()
        self.btn_clear.setText("Clear Unpinned")
        self.btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear.clicked.connect(self.close_all_unpinned)
        self.btn_clear.setStyleSheet("border: none; color: #787b86; font-weight: bold; padding: 2px 8px;")
        self.setCornerWidget(self.btn_clear, Qt.Corner.TopRightCorner)

        self.state_manager.data_updated.connect(self.on_data_updated)
        self.state_manager.scenario_selected.connect(self.open_scenario_tab)

        self.setStyleSheet("""
            QTabBar::tab { background: #1e222d; color: #787b86; padding: 8px 15px; border-right: 1px solid #363a45; border-top: 2px solid transparent; min-width: 120px; }
            QTabBar::tab:selected { background: #131722; color: #d1d4dc; border-top: 2px solid #2962FF; }
            QTabBar::tab:hover { background: #2a2e39; }
            QTabWidget::pane { border: none; background: #131722; }
        """)

    def on_data_updated(self, df):
        self.all_runs_df = df
        for i in range(self.count()):
            widget = self.widget(i)
            if isinstance(widget, GridWidget): widget.on_data_updated(df)

    def on_tab_changed(self, index):
        if index == -1: return
        widget = self.widget(index)
        if isinstance(widget, GridWidget):
            tab_text = self.tabText(index).replace("★ ", "")
            self.state_manager.scenario_selected.emit(tab_text)

    def open_scenario_tab(self, scenario_name):
        for i in range(self.count()):
            clean_name = self.tabText(i).replace("★ ", "")
            if clean_name == scenario_name:
                if self.currentIndex() != i: self.setCurrentIndex(i)
                return
        
        # Don't create the tab directly. Create the widget, then add.
        self._create_and_add_tab({"name": scenario_name, "pinned": False, "active": True})

    def close_tab_request(self, index):
        if self.is_pinned(index): return 
        widget = self.widget(index); self.removeTab(index); widget.deleteLater()

    def close_all_unpinned(self):
        for i in range(self.count() - 1, -1, -1):
            if not self.is_pinned(i): self.close_tab_request(i)

    def is_pinned(self, index): return self.tabBar().tabData(index) is True

    def toggle_pin(self, index):
        new_state = not self.is_pinned(index)
        self.tabBar().setTabData(index, new_state)
        text = self.tabText(index)
        if new_state: self.setTabText(index, "★ " + text); self.tabBar().setTabButton(index, QTabBar.ButtonPosition.RightSide, None)
        else: self.setTabText(index, text.replace("★ ", ""))

    def show_context_menu(self, pos):
        tab_bar = self.tabBar();
        if not tab_bar.geometry().contains(pos): return
        local_pos = tab_bar.mapFrom(self, pos); index = tab_bar.tabAt(local_pos)
        if index == -1: return
        menu = QMenu(self)
        pinned = self.is_pinned(index)
        menu.addAction("Unpin Tab" if pinned else "Pin Tab").triggered.connect(lambda: self.toggle_pin(index))
        menu.addSeparator()
        action_close = menu.addAction("Close"); action_close.setEnabled(not pinned); action_close.triggered.connect(lambda: self.close_tab_request(index))
        menu.addAction("Close Other Tabs").triggered.connect(lambda: self.close_others(index))
        menu.addAction("Close All Unpinned").triggered.connect(self.close_all_unpinned)
        menu.exec(QCursor.pos())

    def close_others(self, keep_index):
        for i in range(self.count() - 1, -1, -1):
            if i != keep_index and not self.is_pinned(i): self.close_tab_request(i)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            tab_bar = self.tabBar(); local_pos = tab_bar.mapFrom(self, event.pos()); index = tab_bar.tabAt(local_pos)
            if index != -1: self.close_tab_request(index); return
        super().mousePressEvent(event)

    def save_state(self):
        tabs = []
        for i in range(self.count()):
            tabs.append({"name": self.tabText(i).replace("★ ", ""), "pinned": self.is_pinned(i), "active": (i == self.currentIndex())})
        self.config_manager.set_global("open_tabs", tabs)

    # --- ASYNC RESTORE LOGIC ---
    def restore_state(self):
        tabs = self.config_manager.get("open_tabs", default=[])
        if not tabs: return
        
        # Don't create tabs directly, queue them for async creation
        self.tabs_to_restore = tabs
        QTimer.singleShot(0, self._restore_next_tab)

    def _restore_next_tab(self):
        if not self.tabs_to_restore: return # All done
        
        tab_data = self.tabs_to_restore.pop(0) # Get next tab from queue
        
        # Duplicate check
        current_names = {self.tabText(i).replace("★ ", "") for i in range(self.count())}
        if tab_data['name'] in current_names:
            # Still schedule next one
            QTimer.singleShot(0, self._restore_next_tab)
            return

        self._create_and_add_tab(tab_data)
        
        # Schedule the next tab creation
        QTimer.singleShot(50, self._restore_next_tab) # 50ms delay to let UI breathe

    def _create_and_add_tab(self, tab_data):
        new_grid = GridWidget(self.state_manager, self.config_manager)
        if self.all_runs_df is not None:
            new_grid.on_data_updated(self.all_runs_df)
            
        new_grid.on_scenario_selected(tab_data['name'])
        
        self.blockSignals(True)
        index = self.addTab(new_grid, tab_data['name'])
        if tab_data.get('pinned', False): self.toggle_pin(index)
        if tab_data.get('active', False): self.setCurrentIndex(index)
        self.blockSignals(False)
        
        # If this was the active tab, we need to manually trigger the update
        if tab_data.get('active', False):
             self.on_tab_changed(index)