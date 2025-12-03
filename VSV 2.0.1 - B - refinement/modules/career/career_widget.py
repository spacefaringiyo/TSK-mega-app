from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
                             QScrollArea, QGridLayout, QToolButton)
from PyQt6.QtCore import Qt
import pandas as pd
from core.analytics import stats as engine
from core import locales

class CareerWidget(QWidget):
    def __init__(self, state_manager):
        super().__init__()
        self.state_manager = state_manager
        self.full_df = None
        self.setup_ui()
        self.state_manager.data_updated.connect(self.on_data_updated)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: #131722; border: none;")
        layout.addWidget(self.scroll)
        
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(20, 20, 20, 20)
        self.content_layout.setSpacing(20)
        self.scroll.setWidget(self.content)

    def on_data_updated(self, df):
        if df is None: return
        self.full_df = df
        
        # Calculate Stats
        stats = engine.calculate_profile_stats(df)
        self.render_view(stats)

    def render_view(self, stats):
        # Clear
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        # 1. TOP STATS GRID
        grid_frame = QFrame()
        grid = QGridLayout(grid_frame)
        grid.setSpacing(15)
        
        # Using keys for future localization
        self.add_stat_card(grid, 0, 0, locales.get_text("cp_total_runs", "Total Runs"), f"{stats['total_runs']:,}")
        self.add_stat_card(grid, 0, 1, locales.get_text("cp_active_time", "Active Playtime"), engine.format_timedelta_hours(stats['active_time']))
        self.add_stat_card(grid, 0, 2, locales.get_text("cp_total_pbs", "Total PBs"), f"{stats['total_pbs']:,}")
        self.add_stat_card(grid, 1, 0, locales.get_text("cp_scenarios", "Unique Scenarios"), f"{stats['unique_scens']:,}")
        self.add_stat_card(grid, 1, 1, locales.get_text("cp_combos", "Unique Combos"), f"{stats['unique_combos']:,}")
        
        self.content_layout.addWidget(grid_frame)

        # 2. RANKS
        lbl_rank = QLabel(locales.get_text("cp_ranks", "Rank Distribution"))
        lbl_rank.setStyleSheet("font-weight: bold; font-size: 16px; margin-top: 10px;")
        self.content_layout.addWidget(lbl_rank)
        
        rank_frame = QFrame()
        r_layout = QHBoxLayout(rank_frame)
        r_layout.setSpacing(10)
        
        # Order: Transmute -> Singularity
        rank_order = ["TRANSMUTE", "BLESSED", "EXALTED", "UBER", "ARCADIA", "SINGULARITY"]
        colors = ["#448AFF", "#FF5252", "#FDD835", "#673AB7", "#2E7D32", "#000000"]
        
        for i, name in enumerate(rank_order):
            count = stats['ranks'].get(name, 0)
            self.add_rank_card(r_layout, name, count, colors[i])
            
        self.content_layout.addWidget(rank_frame)

        # 3. MONTHLY ARCHIVES
        lbl_hist = QLabel(locales.get_text("cp_history", "Monthly History"))
        lbl_hist.setStyleSheet("font-weight: bold; font-size: 16px; margin-top: 10px;")
        self.content_layout.addWidget(lbl_hist)
        
        # Group by Month
        df = self.full_df.copy()
        df['Month'] = df['Timestamp'].dt.to_period('M')
        
        for period in sorted(df['Month'].unique(), reverse=True):
            m_df = df[df['Month'] == period]
            self.add_month_row(period.strftime("%B %Y"), len(m_df), m_df['Duration'].sum())

        self.content_layout.addStretch()

    def add_stat_card(self, grid, r, c, label, value):
        frame = QFrame()
        frame.setStyleSheet("background: #1e222d; border-radius: 6px; border: 1px solid #363a45;")
        lay = QVBoxLayout(frame)
        
        l1 = QLabel(label.upper())
        l1.setStyleSheet("color: #787b86; font-size: 10px; font-weight: bold;")
        l2 = QLabel(str(value))
        l2.setStyleSheet("color: #d1d4dc; font-size: 20px; font-weight: bold;")
        
        lay.addWidget(l1)
        lay.addWidget(l2)
        grid.addWidget(frame, r, c)

    def add_rank_card(self, layout, name, count, color):
        frame = QFrame()
        frame.setStyleSheet(f"background: {color}; border-radius: 4px;")
        frame.setMinimumWidth(80)
        lay = QVBoxLayout(frame)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        txt_col = "white" if name in ["SINGULARITY", "UBER", "ARCADIA"] else "black"
        
        l1 = QLabel(name[:3]) # Short name
        l1.setStyleSheet(f"color: {txt_col}; font-size: 10px; font-weight: bold;")
        l2 = QLabel(str(count))
        l2.setStyleSheet(f"color: {txt_col}; font-size: 16px; font-weight: bold;")
        
        lay.addWidget(l1)
        lay.addWidget(l2)
        layout.addWidget(frame)

    def add_month_row(self, title, runs, duration):
        frame = QFrame()
        frame.setStyleSheet("background: #1e222d; border-radius: 4px; border-left: 3px solid #2962FF;")
        lay = QHBoxLayout(frame)
        
        lay.addWidget(QLabel(title))
        lay.addStretch()
        
        dur_str = engine.format_timedelta_hours(duration)
        info = f"{runs} Runs | {dur_str}"
        lay.addWidget(QLabel(info))
        
        self.content_layout.addWidget(frame)