import datetime
import calendar
import pandas as pd
import numpy as np
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QPushButton, QLabel, QFrame, QScrollArea, 
                             QTableWidget, QTableWidgetItem, QHeaderView, 
                             QAbstractItemView, QComboBox, QCheckBox)
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QColor
from modules.calendar.day_cell import DayCell
from modules.calendar.daily_activity import DailyActivityWidget

class DayDetailWidget(QWidget):
    def __init__(self, state_manager, config_manager):
        super().__init__()
        self.state_manager = state_manager
        self.config = config_manager
        self.day_df = None; self.full_df = None
        self.current_date_str = None
        
        layout = QVBoxLayout(self); layout.setContentsMargins(0,0,0,0)
        h_layout = QHBoxLayout()
        self.lbl_title = QLabel("Select a day")
        self.lbl_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #d1d4dc;")
        
        self.chk_group = QCheckBox("Group by Scenario")
        self.chk_group.stateChanged.connect(self.save_state)
        self.chk_group.stateChanged.connect(self.refresh_table)
        self.chk_group.setVisible(False)
        
        self.cb_sort = QComboBox()
        self.cb_sort.addItems(["Most Played", "Performance", "Time", "A-Z"])
        self.cb_sort.currentIndexChanged.connect(self.save_state)
        self.cb_sort.currentIndexChanged.connect(self.refresh_table)
        self.cb_sort.setVisible(False)
        
        h_layout.addWidget(self.lbl_title); h_layout.addStretch()
        h_layout.addWidget(self.chk_group); h_layout.addSpacing(10)
        h_layout.addWidget(QLabel("Sort:")); h_layout.addWidget(self.cb_sort)
        layout.addLayout(h_layout)
        
        self.sess_container = QFrame()
        self.sess_layout = QHBoxLayout(self.sess_container)
        self.sess_layout.setContentsMargins(0,5,0,5); self.sess_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.sess_container)
        
        self.table = QTableWidget()
        cols = ["Scenario", "Runs", "Best", "vs Avg", "vs 75th", "vs PB", "Gain"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        h = self.table.horizontalHeader(); h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, len(cols)): h.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)
        
        self.load_state()

    def save_state(self):
        state = {"group_by": self.chk_group.isChecked(), "sort_mode": self.cb_sort.currentText()}
        self.config.set_global("calendar_detail", state)

    def load_state(self):
        state = self.config.get("calendar_detail", default={})
        if "group_by" in state: self.chk_group.setChecked(state["group_by"])
        if "sort_mode" in state: self.cb_sort.setCurrentText(state["sort_mode"])

    def load_day(self, date_str, daily_df, full_df):
        self.day_df = daily_df; self.full_df = full_df; self.current_date_str = date_str
        self.lbl_title.setText(f"Activity for {date_str}")
        self.cb_sort.setVisible(True); self.chk_group.setVisible(True)
        while self.sess_layout.count(): child = self.sess_layout.takeAt(0); child.widget().deleteLater() if child.widget() else None
        sessions = sorted(daily_df['SessionID'].unique())
        self.sess_layout.addWidget(QLabel("Sessions:"))
        for sid in sessions:
            btn = QPushButton(f"#{int(sid)}")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("QPushButton { background: #2a2e39; border: 1px solid #363a45; padding: 2px 8px; color: #4aa3df; font-weight: bold; } QPushButton:hover { background: #363a45; border: 1px solid #4aa3df; }")
            btn.clicked.connect(lambda ch, s=sid: self.state_manager.session_selected.emit(s))
            self.sess_layout.addWidget(btn)
        self.refresh_table()

    def refresh_table(self):
        if self.day_df is None or self.day_df.empty: return
        group_by_scen = self.chk_group.isChecked()
        if group_by_scen: grouped = self.day_df.groupby('Scenario')
        else: grouped = self.day_df.groupby(['Scenario', 'Sens'])
        
        day_start_ts = pd.Timestamp(self.current_date_str)
        
        rows = []
        for key, group in grouped:
            scen = key if group_by_scen else key[0]
            sens = None if group_by_scen else key[1]
            best_score = group['Score'].max(); run_count = len(group)
            
            if group_by_scen: hist = self.full_df[self.full_df['Scenario'] == scen]
            else: hist = self.full_df[(self.full_df['Scenario'] == scen) & (self.full_df['Sens'] == sens)]
            
            prev_runs = hist[hist['Timestamp'] < day_start_ts]
            
            prev_pb = 0; avg = 0; p75 = 0
            if not prev_runs.empty:
                prev_pb = prev_runs['Score'].max()
                avg = prev_runs['Score'].mean()
                p75 = prev_runs['Score'].quantile(0.75)
            
            gain_val = 0; gain_pct = 0; pb_status = "NONE"; vs_pb_pct = 0
            
            if prev_runs.empty: pb_status = "NEW"
            elif best_score > prev_pb:
                pb_status = "PB"
                gain_val = best_score - prev_pb
                if prev_pb > 0: gain_pct = (gain_val / prev_pb) * 100
            else:
                if prev_pb > 0: vs_pb_pct = ((best_score - prev_pb) / prev_pb) * 100

            # Calculate vs_avg for sorting
            vs_avg_pct = -999.0
            if avg > 0: vs_avg_pct = ((best_score - avg) / avg) * 100

            rows.append({
                'name': scen, 'sens': sens, 'count': run_count, 'best': best_score,
                'avg': avg, 'p75': p75, 'prev_pb': prev_pb,
                'pb_status': pb_status, 'gain_val': gain_val, 'gain_pct': gain_pct, 'vs_pb_pct': vs_pb_pct,
                'vs_avg_pct': vs_avg_pct,
                'time': group['Timestamp'].min()
            })
            
        mode = self.cb_sort.currentText()
        
        if mode == "Most Played": 
            rows.sort(key=lambda x: x['count'], reverse=True)
            
        elif mode == "Performance": 
            # Custom Logic: PB (Gain) -> Normal (vs Avg) -> NEW (A-Z)
            pbs = [r for r in rows if r['pb_status'] == 'PB']
            news = [r for r in rows if r['pb_status'] == 'NEW']
            others = [r for r in rows if r['pb_status'] not in ('PB', 'NEW')]
            
            pbs.sort(key=lambda x: x['gain_pct'], reverse=True)
            others.sort(key=lambda x: x['vs_avg_pct'], reverse=True)
            news.sort(key=lambda x: x['name'].lower()) # A-Z
            
            rows = pbs + others + news
            
        elif mode == "Time": 
            rows.sort(key=lambda x: x['time']) 
            
        elif mode == "A-Z": 
            rows.sort(key=lambda x: x['name'].lower())
        
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            name_txt = r['name']; 
            if r['sens']: name_txt += f" ({r['sens']}cm)"
            self.table.setItem(i, 0, QTableWidgetItem(name_txt))
            item_runs = QTableWidgetItem(str(r['count']))
            item_runs.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 1, item_runs)
            item_best = QTableWidgetItem(f"{r['best']:.0f}")
            item_best.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 2, item_best)
            
            def set_cell(col, val, color=None):
                it = QTableWidgetItem(val); it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if color: it.setForeground(QColor(color))
                self.table.setItem(i, col, it)

            if r['pb_status'] == "NEW":
                set_cell(3, "NEW!", "#4aa3df"); set_cell(4, "NEW!", "#4aa3df"); set_cell(5, "NEW!", "#4aa3df"); set_cell(6, "NEW!", "#4aa3df")
            else:
                avg_diff = ((r['best'] - r['avg'])/r['avg'])*100 if r['avg']>0 else 0
                set_cell(3, f"{avg_diff:+.1f}%", "#4CAF50" if avg_diff>0 else "#EF5350")
                
                p75_diff = ((r['best'] - r['p75'])/r['p75'])*100 if r['p75']>0 else 0
                set_cell(4, f"{p75_diff:+.1f}%", "#4CAF50" if p75_diff>0 else "#EF5350")
                
                if r['pb_status'] == "PB":
                    set_cell(5, "PB 🏆", "#FFD700")
                    set_cell(6, f"+{r['gain_val']:.0f} (+{r['gain_pct']:.1f}%)", "#FFD700")
                else:
                    set_cell(5, f"{r['vs_pb_pct']:.1f}%", "#EF5350")
                    set_cell(6, "-")

class CalendarWidget(QWidget):
    def __init__(self, state_manager):
        super().__init__()
        self.state_manager = state_manager
        from core.config_manager import ConfigManager
        self.config_manager = ConfigManager()
        
        self.full_df = None
        self.current_date = QDate.currentDate(); self.selected_date = None; self.daily_stats = {} 
        self.setup_ui(); self.state_manager.data_updated.connect(self.on_data_updated)

    def setup_ui(self):
        layout = QVBoxLayout(self); layout.setContentsMargins(10,10,10,10)
        
        # --- FIXED NAV LAYOUT ---
        top_bar = QHBoxLayout()
        btn_prev = QPushButton("◀"); btn_prev.setFixedWidth(30); btn_prev.clicked.connect(self.prev_month)
        
        self.lbl_month = QLabel(); self.lbl_month.setFixedWidth(160) 
        self.lbl_month.setStyleSheet("font-weight: bold; font-size: 16px; color: #d1d4dc;")
        self.lbl_month.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        btn_next = QPushButton("▶"); btn_next.setFixedWidth(30); btn_next.clicked.connect(self.next_month)
        btn_today = QPushButton("Today"); btn_today.clicked.connect(self.go_today)
        
        top_bar.addWidget(btn_prev); top_bar.addWidget(self.lbl_month); top_bar.addWidget(btn_next); top_bar.addWidget(btn_today)
        
        top_bar.addStretch()
        
        # --- NEW TOGGLE (Persisted) ---
        self.chk_stack = QCheckBox("Stack PBs")
        
        # Load State
        is_stacked = self.config_manager.get("calendar_stack_pbs", default=False)
        self.chk_stack.setChecked(is_stacked)
        
        self.chk_stack.stateChanged.connect(self.on_stack_toggled) # Save on change
        self.chk_stack.stateChanged.connect(self.update_calendar)
        self.chk_stack.stateChanged.connect(self.refresh_graph_only) 
        top_bar.addWidget(self.chk_stack)
        
        top_bar.addSpacing(10)
        
        # --- LEGEND ---
        lbl_legend = QLabel("🏆 Scen PB   🎯 Sens PB")
        lbl_legend.setStyleSheet("color: #787b86; font-size: 11px; margin-right: 5px;")
        top_bar.addWidget(lbl_legend)
        
        layout.addLayout(top_bar)
        
        self.grid_layout = QGridLayout(); self.grid_layout.setSpacing(5)
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for i, d in enumerate(days):
            lbl = QLabel(d); lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); lbl.setStyleSheet("color: #787b86; font-weight: bold;")
            self.grid_layout.addWidget(lbl, 0, i)
        self.cells = []
        for row in range(1, 7):
            for col in range(7):
                cell = DayCell(); cell.clicked.connect(self.on_day_clicked)
                self.grid_layout.addWidget(cell, row, col); self.cells.append(cell)
        layout.addLayout(self.grid_layout)

        # DAILY ACTIVITY GRAPH 
        layout.addSpacing(10)
        self.activity_graph = DailyActivityWidget()
        layout.addWidget(self.activity_graph)
        
        # DETAIL PANEL
        layout.addSpacing(10)
        self.detail_panel = DayDetailWidget(self.state_manager, self.config_manager)
        layout.addWidget(self.detail_panel, stretch=1)
        self.update_calendar()

    def on_stack_toggled(self):
        # Save to config
        self.config_manager.set_global("calendar_stack_pbs", self.chk_stack.isChecked())

    def on_data_updated(self, df):
        if df is None: return
        self.full_df = df
        
        if 'DateStr' not in df.columns:
            df['DateStr'] = df['Timestamp'].dt.strftime('%Y-%m-%d')
            
        grouped = df.groupby('DateStr')
        self.daily_stats = {}
        
        for date_str, group in grouped:
            valid_sens_pbs = group[(group['Is_PB'] == 1) & (group.get('Is_First', False) == 0)]
            valid_scen_pbs = group[(group['Is_Scen_PB'] == 1) & (group.get('Is_First', False) == 0)]
            
            unique_scen_cnt = valid_scen_pbs['Scenario'].nunique()
            unique_sens_cnt = valid_sens_pbs.groupby(['Scenario', 'Sens']).ngroups
            
            stats = {
                'runs': len(group),
                'duration': group['Duration'].sum(),
                'pbs_scen_stacked': len(valid_scen_pbs),
                'pbs_scen_unique': unique_scen_cnt,
                'pbs_sens_stacked': len(valid_sens_pbs),
                'pbs_sens_unique': unique_sens_cnt,
                'sessions': group['SessionID'].unique().tolist()
            }
            self.daily_stats[date_str] = stats
            
        if self.daily_stats:
            latest_str = max(self.daily_stats.keys())
            latest_py_date = datetime.datetime.strptime(latest_str, '%Y-%m-%d').date()
            
            self.current_date = QDate(latest_py_date.year, latest_py_date.month, 1)
            self.selected_date = latest_py_date
            
            self.update_calendar()
            
            day_df = df[df['DateStr'] == latest_str].copy()
            self.detail_panel.load_day(latest_str, day_df, df)
            self.activity_graph.load_data(day_df, self.chk_stack.isChecked())
        else:
            self.update_calendar()

    def update_calendar(self):
        year, month = self.current_date.year(), self.current_date.month()
        self.lbl_month.setText(f"{calendar.month_name[month]} {year}")
        month_prefix = f"{year}-{month:02d}"
        month_durations = [v['duration'] for k,v in self.daily_stats.items() if k.startswith(month_prefix)]
        max_act = max(month_durations) if month_durations else 3600
        
        first_day = QDate(year, month, 1)
        start_day_of_week = first_day.dayOfWeek() - 1
        current_grid_date = first_day.addDays(-start_day_of_week)
        
        is_stacked = self.chk_stack.isChecked()
        
        for cell in self.cells:
            py_date = datetime.date(current_grid_date.year(), current_grid_date.month(), current_grid_date.day())
            date_str = py_date.strftime('%Y-%m-%d')
            stats = self.daily_stats.get(date_str, None)
            
            display_stats = None
            if stats:
                display_stats = stats.copy()
                if is_stacked:
                    display_stats['pbs_scen'] = stats['pbs_scen_stacked']
                    display_stats['pbs_sens'] = stats['pbs_sens_stacked']
                else:
                    display_stats['pbs_scen'] = stats['pbs_scen_unique']
                    display_stats['pbs_sens'] = stats['pbs_sens_unique']
            
            is_current = (current_grid_date.month() == month)
            is_sel = (self.selected_date == py_date)
            cell.set_data(py_date, display_stats, is_current, max_act, is_sel)
            current_grid_date = current_grid_date.addDays(1)

    def refresh_graph_only(self):
        if self.selected_date and self.full_df is not None:
            date_str = self.selected_date.strftime('%Y-%m-%d')
            day_df = self.full_df[self.full_df['DateStr'] == date_str].copy()
            self.activity_graph.load_data(day_df, self.chk_stack.isChecked())

    def prev_month(self): self.current_date = self.current_date.addMonths(-1); self.update_calendar()
    def next_month(self): self.current_date = self.current_date.addMonths(1); self.update_calendar()
    def go_today(self): self.current_date = QDate.currentDate(); self.update_calendar()
    def on_day_clicked(self, py_date):
        self.selected_date = py_date
        self.update_calendar()
        
        if self.full_df is not None:
            date_str = py_date.strftime('%Y-%m-%d')
            day_df = self.full_df[self.full_df['DateStr'] == date_str].copy()
            
            self.detail_panel.load_day(date_str, day_df, self.full_df)
            self.activity_graph.load_data(day_df, self.chk_stack.isChecked())