from PyQt6.QtWidgets import QTabWidget, QWidget, QVBoxLayout, QLabel
from modules.navigation.sidebar import NavigationWidget

class BrowserTabs(QTabWidget):
    def __init__(self, state_manager, config_manager):
        super().__init__()
        self.state_manager = state_manager
        
        # 1. Scenarios
        # Pass config_manager directly
        self.scenarios_tab = NavigationWidget(state_manager, config_manager)
        self.addTab(self.scenarios_tab, "Scenarios")
        
        # 2. Playlists
        self.playlists_tab = QWidget()
        pl_layout = QVBoxLayout(self.playlists_tab)
        pl_layout.addWidget(QLabel("Playlists (Coming Soon)"))
        self.addTab(self.playlists_tab, "Playlists")
        
        # 3. Benchmarks
        self.benchmarks_tab = QWidget()
        bm_layout = QVBoxLayout(self.benchmarks_tab)
        bm_layout.addWidget(QLabel("Benchmarks (Coming Soon)"))
        self.addTab(self.benchmarks_tab, "Benchmarks")
        
        self.setStyleSheet("""
            QTabBar::tab {
                background: #1e222d;
                color: #787b86;
                padding: 8px 12px;
                border-bottom: 1px solid #363a45;
            }
            QTabBar::tab:selected {
                background: #131722;
                color: #d1d4dc;
                border-bottom: 2px solid #2962FF;
            }
            QTabWidget::pane { border: none; background: #131722; }
        """)