from PyQt6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget, QPushButton, QHBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt
from modules.session.session_list import SessionListWidget
from modules.session.session_report import SessionReportWidget

class SessionManager(QWidget):
    def __init__(self, state_manager):
        super().__init__()
        self.state_manager = state_manager
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        
        # HEADER (Back Button + Title)
        self.header = QFrame()
        self.header.setStyleSheet("background: #1e222d; border-bottom: 1px solid #363a45;")
        self.header.setFixedHeight(40)
        h_layout = QHBoxLayout(self.header)
        h_layout.setContentsMargins(5,0,5,0)
        
        self.btn_back = QPushButton("← History")
        self.btn_back.setStyleSheet("border: none; font-weight: bold; color: #2962FF;")
        self.btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_back.clicked.connect(self.go_to_list)
        self.btn_back.setVisible(False) # Hidden initially
        
        self.lbl_title = QLabel("Session History")
        self.lbl_title.setStyleSheet("font-weight: bold; color: #d1d4dc;")
        
        h_layout.addWidget(self.btn_back)
        h_layout.addStretch()
        h_layout.addWidget(self.lbl_title)
        h_layout.addStretch()
        
        layout.addWidget(self.header)

        # STACK (Pages)
        self.stack = QStackedWidget()
        
        # Page 1: List
        self.page_list = SessionListWidget(state_manager)
        # We need to intercept the click signal!
        # The list emits a signal to StateManager. We can listen to that.
        self.state_manager.session_selected.connect(self.go_to_report)
        
        # Page 2: Report
        self.page_report = SessionReportWidget(state_manager)
        
        self.stack.addWidget(self.page_list)
        self.stack.addWidget(self.page_report)
        
        layout.addWidget(self.stack)

    def go_to_report(self, session_id):
        # User clicked a session -> Slide to Report
        self.stack.setCurrentWidget(self.page_report)
        self.btn_back.setVisible(True)
        self.lbl_title.setText(f"Session #{int(session_id)}")

    def go_to_list(self):
        # User clicked Back -> Slide to List
        self.stack.setCurrentWidget(self.page_list)
        self.btn_back.setVisible(False)
        self.lbl_title.setText("Session History")