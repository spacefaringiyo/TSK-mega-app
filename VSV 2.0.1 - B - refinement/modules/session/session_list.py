from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QListWidget, QListWidgetItem, 
                             QLabel, QFrame)
from PyQt6.QtCore import Qt
import pandas as pd

class SessionListWidget(QWidget):
    def __init__(self, state_manager):
        super().__init__()
        self.state_manager = state_manager
        self.current_selected_id = None # Track selection to handle refreshes gracefully
        
        self.setup_ui()
        
        self.state_manager.data_updated.connect(self.on_data_updated)
        self.state_manager.session_selected.connect(self.on_external_selection)

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

    def on_external_selection(self, sess_id):
        """Sync selection if session is chosen from elsewhere (e.g. Calendar)"""
        self.current_selected_id = sess_id
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == sess_id:
                self.list_widget.setCurrentItem(item)
                return
        # If ID not found in list (e.g. filtered), clear selection
        self.list_widget.clearSelection()

    def on_data_updated(self, df):
        if df is None or 'SessionID' not in df.columns: return
        self.list_widget.clear()
        
        sessions = df.groupby('SessionID').agg(
            StartTime=('Timestamp', 'min'),
            Count=('Score', 'size'),
            Duration=('Duration', 'sum')
        ).sort_index(ascending=False)

        # Re-populate List
        item_to_select = None
        
        for sess_id, row in sessions.iterrows():
            date_str = row['StartTime'].strftime('%Y-%m-%d %H:%M')
            duration_min = int(row['Duration'] // 60)
            label = f"#{int(sess_id)} - {date_str}\n{row['Count']} Runs ({duration_min}m)"
            
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, int(sess_id))
            self.list_widget.addItem(item)
            
            # Check if this was the previously selected session
            if self.current_selected_id == int(sess_id):
                item_to_select = item

        # --- SELECTION LOGIC ---
        if item_to_select:
            # Case A: Restore previous selection (F5 Refresh)
            # We select it visually, but DO NOT emit the signal.
            # This prevents the main tab from forcibly jumping to "Session Report".
            # The SessionReportWidget listens to data_updated and will refresh itself.
            self.list_widget.setCurrentItem(item_to_select)
            
        elif self.list_widget.count() > 0:
            # Case B: First Load OR Selection Lost
            # Select the latest session (Top Item)
            first_item = self.list_widget.item(0)
            self.list_widget.setCurrentItem(first_item)
            
            new_id = first_item.data(Qt.ItemDataRole.UserRole)
            self.current_selected_id = new_id
            
            # Emit signal so views populate for the first time
            self.state_manager.session_selected.emit(new_id)

    def on_item_clicked(self, item):
        sess_id = item.data(Qt.ItemDataRole.UserRole)
        self.current_selected_id = sess_id
        self.state_manager.session_selected.emit(sess_id)