from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QLabel, QFrame, 
                             QRadioButton, QButtonGroup, QAbstractItemView, 
                             QCheckBox, QComboBox, QSpinBox, QDoubleSpinBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
import pandas as pd
import numpy as np
from modules.charts.chart_widget import ChartWidget, COLORS_CYCLE_10

class OngoingToolbar(QFrame):
    def __init__(self, parent_widget):
        super().__init__()
        self.parent_widget = parent_widget
        self.setStyleSheet("background: #1e222d; border-bottom: 1px solid #363a45;")
        self.setFixedHeight(50)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5,5,5,5)
        
        # 1. Baseline
        layout.addWidget(QLabel("Base:"))
        self.rb_avg = QRadioButton("Avg"); self.rb_avg.setChecked(True)
        self.rb_75 = QRadioButton("75th")
        self.bg = QButtonGroup(); self.bg.addButton(self.rb_avg); self.bg.addButton(self.rb_75)
        self.bg.buttonClicked.connect(parent_widget.refresh_view)
        layout.addWidget(self.rb_avg); layout.addWidget(self.rb_75)
        
        layout.addSpacing(10)
        
        # 2. Visual Style
        self.cb_vis = QComboBox()
        self.cb_vis.addItems(["Line Plot", "Dot Only", "Filled Area"])
        self.cb_vis.currentIndexChanged.connect(parent_widget.refresh_view)
        layout.addWidget(self.cb_vis)
        
        # 3. Color
        self.chk_color = QCheckBox("Color by Scenario")
        self.chk_color.setChecked(True)
        self.chk_color.stateChanged.connect(parent_widget.refresh_view)
        layout.addWidget(self.chk_color)
        
        # 4. Hide
        layout.addWidget(QLabel("Hide <"))
        self.sb_hide = QDoubleSpinBox()
        self.sb_hide.setRange(0, 999999); self.sb_hide.setValue(0)
        self.sb_hide.setFixedWidth(50)
        self.sb_hide.valueChanged.connect(parent_widget.refresh_view)
        layout.addWidget(self.sb_hide)
        
        # 5. Indicators
        self.chk_trend = QCheckBox("Trend"); self.chk_trend.setChecked(True)
        self.chk_trend.stateChanged.connect(parent_widget.refresh_view)
        layout.addWidget(self.chk_trend)
        
        self.chk_flow = QCheckBox("Flow"); self.chk_flow.setChecked(True)
        self.chk_flow.stateChanged.connect(parent_widget.refresh_view)
        layout.addWidget(self.chk_flow)
        
        self.chk_sma = QCheckBox("SMA")
        self.chk_sma.stateChanged.connect(parent_widget.refresh_view)
        layout.addWidget(self.chk_sma)
        
        self.sb_sma = QSpinBox(); self.sb_sma.setRange(2, 50); self.sb_sma.setValue(5)
        self.sb_sma.valueChanged.connect(parent_widget.refresh_view)
        layout.addWidget(self.sb_sma)
        
        layout.addStretch()

class OngoingWidget(QWidget):
    def __init__(self, state_manager):
        super().__init__()
        self.state_manager = state_manager
        self.full_df = None
        self.recent_runs = []
        
        self.stats_cache_avg = {}
        self.stats_cache_75 = {}
        self.stats_cache_pb = {} 

        self.setup_ui()
        self.state_manager.data_updated.connect(self.on_data_updated)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        
        # Toolbar
        self.toolbar = OngoingToolbar(self)
        layout.addWidget(self.toolbar)

        # Graph
        self.chart = ChartWidget(self.state_manager, listen_to_global_signals=False)
        self.chart.setMinimumHeight(250)
        layout.addWidget(self.chart, stretch=2)

        # Table
        self.table = QTableWidget()
        columns = ["Scenario", "Sens", "Score", "vs Avg", "vs 75th", "vs PB"]
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, len(columns)): header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        
        layout.addWidget(self.table, stretch=3)

    def on_data_updated(self, df):
        if df is None: return
        self.full_df = df
        
        grouped = df.groupby(['Scenario', 'Sens'])['Score']
        self.stats_cache_avg = grouped.mean().to_dict()
        self.stats_cache_75 = grouped.quantile(0.75).to_dict()
        self.stats_cache_pb = grouped.max().to_dict()
        
        # Get Last 50 Runs
        self.recent_runs = df.sort_values('Timestamp', ascending=False).head(50)
        # Reverse to chronological for graphing
        self.recent_runs = self.recent_runs.iloc[::-1] 
        
        self.refresh_view()

    def refresh_view(self):
        if self.full_df is None or self.recent_runs.empty: return
        
        # 1. Gather Settings
        is_avg_mode = self.toolbar.rb_avg.isChecked()
        vis_style = self.toolbar.cb_vis.currentText()
        use_color = self.toolbar.chk_color.isChecked()
        cutoff = self.toolbar.sb_hide.value()
        
        graph_points = []
        filtered_runs = []
        
        # Map Scenarios to Colors
        unique_scens = sorted(self.recent_runs['Scenario'].unique())
        color_map = {scen: COLORS_CYCLE_10[i % len(COLORS_CYCLE_10)] for i, scen in enumerate(unique_scens)}

        # 2. Process Data
        for idx, row in self.recent_runs.iterrows():
            score = row['Score']
            if cutoff > 0 and score < cutoff: continue
            
            filtered_runs.append(row)
            
            key = (row['Scenario'], row['Sens'])
            baseline = self.stats_cache_avg.get(key, 0) if is_avg_mode else self.stats_cache_75.get(key, 0)
            
            pct = 0.0
            if baseline > 0: pct = ((score - baseline) / baseline) * 100
            
            # --- META ---
            vs_str = f"{pct:+.1f}% vs {'Avg' if is_avg_mode else '75th'}"
            meta = {
                'scenario': row['Scenario'],
                'sens': row['Sens'],
                'score': score,
                'subtext': vs_str
            }
            
            # Determine Color
            # If Color Mode ON: Use map.
            # If Color Mode OFF: Use Blue.
            pt_color = color_map[row['Scenario']] if use_color else '#2962FF'
            
            graph_points.append({
                'time': int(row['Timestamp'].timestamp()),
                'value': pct,
                'label': row['Scenario'],
                'color': pt_color, # Store for segmenting
                'meta': meta
            })

        # 3. Build Segments
        # CRITICAL CHANGE: We segment whenever the Scenario changes, 
        # NOT just when color changes. This ensures markers/bridges work even in mono-color mode.
        segments = []
        if graph_points:
            current_scen = graph_points[0]['label']
            current_segment = {'data': [], 'color': graph_points[0]['color']}
            
            for p in graph_points:
                scen = p['label']
                
                # If Scenario changed (OR color changed, though color follows scenario)
                if scen != current_scen:
                    segments.append(current_segment)
                    current_segment = {'data': [], 'color': p['color']}
                    current_scen = scen
                
                current_segment['data'].append(p)
            segments.append(current_segment)

        # 4. Build Payload
        payload = []
        
        for i, seg in enumerate(segments):
            item = {
                'data': seg['data'],
                'color': seg['color'],
                'width': 2,
                'filled': (vis_style == "Filled Area"),
                'fill_negative': True,
                'markers': []
            }
            if vis_style == "Dot Only": item['width'] = 0
            
            # Markers
            if seg['data']:
                first = seg['data'][0]
                # Only add label if Color Mode is OFF (per user request)
                # "remove scenario name label in color by scenario mode"
                if not use_color:
                    item['markers'].append({
                        'time': first['time'],
                        'text': first['label'],
                        'color': '#FF9800'
                    })
            payload.append(item)
            
            # Bridges
            if i < len(segments) - 1:
                next_seg = segments[i+1]
                last_pt = seg['data'][-1]
                first_pt = next_seg['data'][0]
                
                bridge_data = [last_pt, first_pt]
                
                bridge_item = {
                    'data': bridge_data,
                    'color': next_seg['color'], # Color of next segment
                    'width': 2,
                    'filled': (vis_style == "Filled Area"),
                    'fill_negative': True
                }
                if vis_style == "Dot Only": bridge_item['width'] = 0
                payload.append(bridge_item)

        # 5. Indicators
        all_y = [p['value'] for p in graph_points]
        all_t = [p['time'] for p in graph_points]
        
        if len(all_y) > 1:
            series = pd.Series(all_y)
            
            if self.toolbar.chk_trend.isChecked():
                trend = series.expanding().mean().values
                # Explicitly create new dicts for indicators to avoid ref issues
                trend_data = [{'time': t, 'value': v} for t, v in zip(all_t, trend)]
                payload.append({'data': trend_data, 'color': '#FF9800', 'width': 3})
            
            if self.toolbar.chk_flow.isChecked():
                flow = series.rolling(5).mean().values
                flow_data = [{'time': t, 'value': v} for t, v in zip(all_t, flow) if not np.isnan(v)]
                payload.append({'data': flow_data, 'color': '#E040FB', 'width': 3})
                
            if self.toolbar.chk_sma.isChecked():
                n = self.toolbar.sb_sma.value()
                sma = series.rolling(n).mean().values
                sma_data = [{'time': t, 'value': v} for t, v in zip(all_t, sma) if not np.isnan(v)]
                payload.append({'data': sma_data, 'color': '#00E5FF', 'width': 3})

        self.chart.plot_payload(payload)

        # 6. Populate Table
        table_runs = filtered_runs[::-1]
        self.table.setRowCount(len(table_runs))
        
        for row_idx, row in enumerate(table_runs):
            key = (row['Scenario'], row['Sens'])
            score = row['Score']
            
            self.table.setItem(row_idx, 0, QTableWidgetItem(row['Scenario']))
            self.table.setItem(row_idx, 1, QTableWidgetItem(f"{row['Sens']}cm"))
            self.table.setItem(row_idx, 2, QTableWidgetItem(f"{score:.0f}"))
            
            def set_vs(col, base, name):
                if name == "PB" and score >= base:
                    it = QTableWidgetItem("🏆 PB")
                    it.setForeground(QColor("#FFD700"))
                    it.setToolTip(f"Previous PB: {base:.0f}")
                    self.table.setItem(row_idx, col, it)
                    return

                if base > 0:
                    pct = ((score - base)/base)*100
                    it = QTableWidgetItem(f"{pct:+.1f}%")
                    if pct > 0: it.setForeground(QColor("#4CAF50"))
                    elif pct < 0: it.setForeground(QColor("#EF5350"))
                    else: it.setForeground(QColor("#787b86"))
                    it.setToolTip(f"{name}: {base:.1f}")
                    self.table.setItem(row_idx, col, it)
                else: self.table.setItem(row_idx, col, QTableWidgetItem("-"))

            set_vs(3, self.stats_cache_avg.get(key,0), "Avg")
            set_vs(4, self.stats_cache_75.get(key,0), "75th")
            set_vs(5, self.stats_cache_pb.get(key,0), "PB")