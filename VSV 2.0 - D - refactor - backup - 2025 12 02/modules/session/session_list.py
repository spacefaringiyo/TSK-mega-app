from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QListWidget, QListWidgetItem, 
                             QLabel, QFrame)
from PyQt6.QtCore import Qt
import pandas as pd

class SessionListWidget(QWidget):
    def __init__(self, state_manager):
        super().__init__()
        self.state_manager = state_manager
        self.setup_ui()
        self.state_manager.data_updated.connect(self.on_data_updated)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        
        lbl = QLabel("History")
        lbl.setStyleSheet("font-weight: bold; padding: 10px;")
        layout.addWidget(lbl)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("border: none;")
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        layout.addWidget(self.list_widget)

    def on_data_updated(self, df):
        if df is None or 'SessionID' not in df.columns: return
        self.list_widget.clear()
        
        sessions = df.groupby('SessionID').agg(
            StartTime=('Timestamp', 'min'),
            Count=('Score', 'size'),
            Duration=('Duration', 'sum')
        ).sort_index(ascending=False)

        for sess_id, row in sessions.iterrows():
            date_str = row['StartTime'].strftime('%Y-%m-%d %H:%M')
            duration_min = int(row['Duration'] // 60)
            label = f"#{int(sess_id)} - {date_str}\n{row['Count']} Runs ({duration_min}m)"
            
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, int(sess_id))
            self.list_widget.addItem(item)

    def on_item_clicked(self, item):
        sess_id = item.data(Qt.ItemDataRole.UserRole)
        # FIX: Send the signal now!
        self.state_manager.session_selected.emit(sess_id)