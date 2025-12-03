from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QStackedWidget, QPushButton, 
                             QHBoxLayout, QLabel, QFrame, QCheckBox)
from PyQt6.QtCore import Qt
from core.config_manager import ConfigManager
from modules.session.session_list import SessionListWidget
from modules.session.session_report import SessionReportWidget

class SessionManager(QWidget):
    def __init__(self, state_manager):
        super().__init__()
        self.state_manager = state_manager
        self.config_manager = ConfigManager() # For persistence
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        
        # HEADER (Back Button + Title + Stack PBs)
        self.header = QFrame()
        self.header.setStyleSheet("background: #1e222d; border-bottom: 1px solid #363a45;")
        self.header.setFixedHeight(40)
        h_layout = QHBoxLayout(self.header)
        h_layout.setContentsMargins(5,0,5,0)
        
        # LEFT: Back Button
        self.btn_back = QPushButton("← History")
        self.btn_back.setStyleSheet("border: none; font-weight: bold; color: #2962FF;")
        self.btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_back.clicked.connect(self.go_to_list)
        self.btn_back.setVisible(False) 
        self.btn_back.setFixedWidth(80) # Fixed width for balancing
        
        # CENTER: Title
        self.lbl_title = QLabel("Session History")
        self.lbl_title.setStyleSheet("font-weight: bold; color: #d1d4dc; font-size: 14px;")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # RIGHT: Toggle
        self.chk_stack = QCheckBox("Stack PBs")
        is_stacked = self.config_manager.get("session_stack_pbs", default=False)
        self.chk_stack.setChecked(is_stacked)
        self.chk_stack.stateChanged.connect(self.on_stack_toggled)
        self.chk_stack.setVisible(False) # Hidden on list view
        
        # Layout Assembly for Centering
        # Trick: Left Widget, Stretch, Center Widget, Stretch, Right Widget
        h_layout.addWidget(self.btn_back)
        h_layout.addStretch()
        h_layout.addWidget(self.lbl_title)
        h_layout.addStretch()
        h_layout.addWidget(self.chk_stack)
        
        layout.addWidget(self.header)

        # STACK (Pages)
        self.stack = QStackedWidget()
        
        self.page_list = SessionListWidget(state_manager)
        self.state_manager.session_selected.connect(self.go_to_report)
        
        self.page_report = SessionReportWidget(state_manager)
        
        self.stack.addWidget(self.page_list)
        self.stack.addWidget(self.page_report)
        
        layout.addWidget(self.stack)

        # Connect Checkbox to Report Refresh
        self.chk_stack.stateChanged.connect(self.page_report.refresh_view)

    def on_stack_toggled(self):
        val = self.chk_stack.isChecked()
        self.config_manager.set_global("session_stack_pbs", val)
        # We also need to update the report's internal state logic
        self.page_report.set_stack_mode(val)

    def go_to_report(self, session_id):
        self.stack.setCurrentWidget(self.page_report)
        self.btn_back.setVisible(True)
        self.chk_stack.setVisible(True)
        self.lbl_title.setText(f"Session #{int(session_id)}")
        
        # Ensure report has correct stack mode
        self.page_report.set_stack_mode(self.chk_stack.isChecked())

    def go_to_list(self):
        self.stack.setCurrentWidget(self.page_list)
        self.btn_back.setVisible(False)
        self.chk_stack.setVisible(False)
        self.lbl_title.setText("Session History")