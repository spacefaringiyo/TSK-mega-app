from PyQt6.QtWidgets import QTabWidget, QWidget, QVBoxLayout, QLabel
from modules.right_panel.ongoing import OngoingWidget
from modules.session.session_manager import SessionManager
from modules.career.career_widget import CareerWidget

class AnalystTabs(QTabWidget):
    def __init__(self, state_manager):
        super().__init__()
        self.state_manager = state_manager
        
        # 1. Ongoing (Placeholder for next step)
        # 1. Ongoing
        self.ongoing_tab = OngoingWidget(state_manager)
        self.addTab(self.ongoing_tab, "Ongoing")
        
        # 2. Session (Drill Down Manager)
        self.session_tab = SessionManager(state_manager)
        self.addTab(self.session_tab, "Session Report")
        
        # 3. Career
        self.career_tab = CareerWidget(state_manager)
        self.addTab(self.career_tab, "Career Profile")
        
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