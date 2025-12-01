from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QLabel, QFrame, 
                             QRadioButton, QButtonGroup, QAbstractItemView)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
import pandas as pd
from modules.charts.chart_widget import ChartWidget
from core import engine

class OngoingWidget(QWidget):
    def __init__(self, state_manager):
        super().__init__()
        self.state_manager = state_manager
        self.full_df = None
        self.recent_runs = []
        
        # Caches
        self.stats_cache_avg = {}
        self.stats_cache_75 = {}
        self.stats_cache_pb = {} # New: PB Cache

        # Graph State
        self.graph_baseline = "Avg" 

        self.setup_ui()
        self.state_manager.data_updated.connect(self.on_data_updated)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        
        # 1. GRAPH
        self.chart = ChartWidget(self.state_manager, listen_to_global_signals=False)
        self.chart.setMinimumHeight(250)
        layout.addWidget(self.chart, stretch=2)

        # 2. CONTROLS (Graph Only)
        controls = QFrame()
        controls.setStyleSheet("background: #1e222d; border-top: 1px solid #363a45; border-bottom: 1px solid #363a45;")
        c_layout = QHBoxLayout(controls)
        c_layout.setContentsMargins(10, 5, 10, 5)
        
        c_layout.addWidget(QLabel("Graph Baseline:"))
        self.rb_avg = QRadioButton("Average")
        self.rb_75 = QRadioButton("75th %")
        self.rb_avg.setChecked(True)
        
        self.bg_group = QButtonGroup()
        self.bg_group.addButton(self.rb_avg)
        self.bg_group.addButton(self.rb_75)
        self.bg_group.buttonClicked.connect(self.on_graph_baseline_changed)
        
        c_layout.addWidget(self.rb_avg)
        c_layout.addWidget(self.rb_75)
        c_layout.addStretch()
        layout.addWidget(controls)

        # 3. TABLE (Expanded)
        self.table = QTableWidget()
        columns = ["Scenario", "Sens", "Score", "vs Avg", "vs 75th", "vs PB"]
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        
        # Sizing
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch) # Name gets space
        for i in range(1, len(columns)):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents) # Others compact
        
        layout.addWidget(self.table, stretch=3)

    def on_data_updated(self, df):
        if df is None: return
        self.full_df = df
        
        # 1. Pre-calculate Stats
        grouped = df.groupby(['Scenario', 'Sens'])['Score']
        self.stats_cache_avg = grouped.mean().to_dict()
        self.stats_cache_75 = grouped.quantile(0.75).to_dict()
        self.stats_cache_pb = grouped.max().to_dict()
        
        # 2. Get Last 50 Runs
        self.recent_runs = df.sort_values('Timestamp', ascending=False).head(50)
        self.refresh_view()

    def on_graph_baseline_changed(self, btn):
        self.graph_baseline = "Avg" if self.rb_avg.isChecked() else "75th"
        self.refresh_view()

    def refresh_view(self):
        if self.full_df is None: return
        
        graph_points = []
        
        self.table.setRowCount(len(self.recent_runs))
        
        # Iterate (Newest is index 0 in recent_runs)
        for row_idx, (idx, row) in enumerate(self.recent_runs.iterrows()):
            key = (row['Scenario'], row['Sens'])
            score = row['Score']
            
            # Lookup Stats
            val_avg = self.stats_cache_avg.get(key, 0)
            val_75 = self.stats_cache_75.get(key, 0)
            val_pb = self.stats_cache_pb.get(key, 0)
            
            # --- POPULATE TABLE ---
            # 0: Name
            self.table.setItem(row_idx, 0, QTableWidgetItem(row['Scenario']))
            # 1: Sens
            self.table.setItem(row_idx, 1, QTableWidgetItem(f"{row['Sens']}cm"))
            # 2: Score
            self.table.setItem(row_idx, 2, QTableWidgetItem(f"{score:.0f}"))
            
            # Helpers for vs Columns
            def set_vs_cell(col_idx, baseline, baseline_label):
                if baseline > 0:
                    pct = ((score - baseline) / baseline) * 100
                    item = QTableWidgetItem(f"{pct:+.1f}%")
                    
                    # Color
                    if pct > 0: item.setForeground(QColor("#4CAF50"))
                    elif pct < 0: item.setForeground(QColor("#EF5350"))
                    else: item.setForeground(QColor("#787b86")) # Grey for 0
                    
                    # Tooltip
                    item.setToolTip(f"Score: {score:.0f}\n{baseline_label}: {baseline:.1f}\nDiff: {pct:+.1f}%")
                    self.table.setItem(row_idx, col_idx, item)
                else:
                    self.table.setItem(row_idx, col_idx, QTableWidgetItem("-"))

            set_vs_cell(3, val_avg, "Average")
            set_vs_cell(4, val_75, "75th Percentile")
            set_vs_cell(5, val_pb, "Personal Best")

            # --- PREPARE GRAPH DATA ---
            # Graph uses the selected baseline (Radio Button)
            base_for_graph = val_avg if self.graph_baseline == "Avg" else val_75
            graph_pct = 0.0
            if base_for_graph > 0:
                graph_pct = ((score - base_for_graph) / base_for_graph) * 100
            
            graph_points.append({
                'time': int(row['Timestamp'].timestamp()),
                'value': graph_pct,
                'label': row['Scenario']
            })

        # --- PLOT GRAPH ---
        # Sort chronologically (Oldest -> Newest)
        graph_points.sort(key=lambda x: x['time'])
        
        # Markers
        markers = []
        last_scen = None
        for p in graph_points:
            if p['label'] != last_scen:
                markers.append({
                    'time': p['time'],
                    'position': 'aboveBar',
                    'color': '#FF9800',
                    'shape': 'arrowDown',
                    'text': p['label']
                })
                last_scen = p['label']

        payload = [{
            'id': 'ongoing_perf',
            'color': '#4aa3df',
            'width': 2,
            'data': graph_points,
            'markers': markers
        }]
        self.chart.plot_payload(payload)