from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
                             QCheckBox, QScrollArea, QSizePolicy, QRadioButton, QButtonGroup)
from PyQt6.QtCore import Qt
import pandas as pd
from core.analytics import stats as engine
from modules.charts.chart_widget import ChartWidget
from modules.charts import indicators

class SessionReportWidget(QWidget):
    def __init__(self, state_manager):
        super().__init__()
        self.state_manager = state_manager
        self.full_df = None
        self.summary = None
        self.view_mode = 'grid' 

        self.setup_ui()
        
        self.state_manager.data_updated.connect(self.on_data_updated)
        if hasattr(self.state_manager, 'session_selected'):
            self.state_manager.session_selected.connect(self.on_session_selected)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0,0,0,0)
        
        # 1. HEADER
        self.header = QFrame()
        self.header.setStyleSheet("background: #1e222d; border-bottom: 1px solid #363a45;")
        self.header.setFixedHeight(80)
        self.header_layout = QHBoxLayout(self.header)
        main_layout.addWidget(self.header)
        
        # 2. CONTROLS
        controls = QFrame()
        c_layout = QHBoxLayout(controls)
        c_layout.setContentsMargins(10,5,10,5)
        
        self.chk_trend = QCheckBox("Trend"); self.chk_trend.setChecked(True)
        self.chk_flow = QCheckBox("Flow"); self.chk_flow.setChecked(True)
        self.chk_pulse = QCheckBox("Pulse")
        
        for chk in [self.chk_trend, self.chk_flow, self.chk_pulse]:
            chk.stateChanged.connect(self.refresh_view)
            c_layout.addWidget(chk)
            
        c_layout.addSpacing(30)
        
        c_layout.addWidget(QLabel("Summarize by:"))
        self.rb_grid = QRadioButton("Grid (Scenario + Sens)")
        self.rb_scen = QRadioButton("Scenario Only")
        self.rb_grid.setChecked(True)
        
        self.view_group = QButtonGroup()
        self.view_group.addButton(self.rb_grid)
        self.view_group.addButton(self.rb_scen)
        self.view_group.buttonClicked.connect(self.on_view_toggle)
        
        c_layout.addWidget(self.rb_grid)
        c_layout.addWidget(self.rb_scen)
        c_layout.addStretch()
        main_layout.addWidget(controls)

        # 3. CHART (ISOLATED)
        # Fix: Stop listening to global grid clicks!
        self.chart = ChartWidget(self.state_manager, listen_to_global_signals=False)
        self.chart.setMinimumHeight(300)
        main_layout.addWidget(self.chart, stretch=2)

        # 4. LISTS
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: #131722; border: none;")
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(10, 10, 10, 10)
        self.scroll_layout.setSpacing(10)
        self.scroll.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll, stretch=3)

    def on_data_updated(self, df): self.full_df = df

    def on_session_selected(self, session_id):
        if self.full_df is None: return
        session_df = self.full_df[self.full_df['SessionID'] == session_id].copy()
        
        self.summary = engine.analyze_session(session_df, self.full_df)
        if not self.summary: return
        
        self.refresh_view()

    def on_view_toggle(self, btn):
        self.view_mode = 'scenario' if self.rb_scen.isChecked() else 'grid'
        self.refresh_view()

    def refresh_view(self):
        if not self.summary: return
        data = self.summary[self.view_mode]
        meta = self.summary['meta']
        
        self.refresh_metrics(meta, data['pb_count'])
        self.plot_graph(data['graph_data'])
        self.render_lists(data['lists'])

    def refresh_metrics(self, meta, pb_count):
        while self.header_layout.count(): 
            child = self.header_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
            
        def add_metric(label, val):
            vbox = QVBoxLayout()
            l1 = QLabel(label); l1.setStyleSheet("color: #787b86; font-size: 10px;")
            l2 = QLabel(str(val)); l2.setStyleSheet("font-size: 16px; font-weight: bold;")
            vbox.addWidget(l1); vbox.addWidget(l2)
            self.header_layout.addLayout(vbox)
            self.header_layout.addSpacing(20)

        add_metric("Date", meta['date_str'])
        add_metric("Duration", meta['duration_str'])
        add_metric("Active", meta['active_str'])
        add_metric("Plays", meta['play_count'])
        add_metric("PBs", pb_count)

    def plot_graph(self, graph_data):
        payload = []
        
        # 1. GENERATE MARKERS (LABELS)
        # We scan the data. If the scenario/sens changes, we add a label.
        markers = []
        last_label = None
        
        for d in graph_data:
            # Determine label text based on view mode logic
            # Engine passes 'scenario' and 'sens' in data
            label_text = d['scenario']
            if d['sens']: label_text += f" ({d['sens']}cm)"
            
            if label_text != last_label:
                markers.append({
                    'time': d['time'],
                    'position': 'aboveBar',
                    'color': '#FF9800', # Orange text
                    'shape': 'arrowDown',
                    'text': label_text
                })
                last_label = label_text

        # 2. Main Score Line
        scores = [{'time': d['time'], 'value': d['pct']} for d in graph_data]
        payload.append({
            'id': 'score', 
            'color': '#4aa3df', 
            'width': 2, 
            'data': scores,
            'markers': markers # Pass markers here
        })
        
        # 3. Indicators
        if self.chk_trend.isChecked(): payload.append(self.get_ind(indicators.IndTrend, graph_data))
        if self.chk_flow.isChecked(): payload.append(self.get_ind(indicators.IndFlow, graph_data))
        if self.chk_pulse.isChecked(): payload.append(self.get_ind(indicators.IndPulse, graph_data))
        
        self.chart.plot_payload(payload)

    def get_ind(self, cls, data):
        inst = cls()
        return {'id': inst.name, 'color': inst.color, 'width': inst.width, 'data': inst.extract_data(data)}

    # ... (Render Lists logic remains the same as previous) ...
    def render_lists(self, lists):
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        if lists['pbs']:
            self.add_header(f"Personal Bests ({len(lists['pbs'])})", "#4CAF50")
            for item in lists['pbs']: self.add_pb_card(item)

        if lists['avgs']:
            self.add_header("Average Comparison", "#FF9800")
            for item in lists['avgs']: self.add_avg_card(item)

        self.add_header("Scenarios Played", "#2962FF")
        for item in lists['played']: self.add_played_card(item)
            
        self.scroll_layout.addStretch()

    def add_header(self, text, color):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 14px; margin-top: 10px; border-bottom: 1px solid #363a45; padding-bottom: 5px;")
        self.scroll_layout.addWidget(lbl)

    def add_pb_card(self, item):
        frame = QFrame()
        frame.setStyleSheet("background: #1e222d; border-radius: 4px; border-left: 3px solid #4CAF50;")
        layout = QHBoxLayout(frame)
        name = item['name']
        if item.get('sens'): name += f" ({item['sens']}cm)"
        layout.addWidget(QLabel(name))
        layout.addStretch()
        detail = f"New: {item['score']:.0f} (Prev: {item['prev']:.0f})"
        diff = f"+{item['imp']:.0f} (+{item['imp_pct']:.1f}%)"
        layout.addWidget(QLabel(detail))
        layout.addSpacing(15)
        lbl_diff = QLabel(diff); lbl_diff.setStyleSheet("color: #4CAF50; font-weight: bold;")
        layout.addWidget(lbl_diff)
        self.scroll_layout.addWidget(frame)

    def add_avg_card(self, item):
        frame = QFrame()
        frame.setStyleSheet("background: #1e222d; border-radius: 4px;")
        layout = QHBoxLayout(frame)
        name = item['name']
        if item.get('sens'): name += f" ({item['sens']}cm)"
        val_text = f"Sess: {item['sess_avg']:.1f} vs All: {item['all_avg']:.1f}"
        color = "#4CAF50" if item['diff_pct'] > 0 else "#EF5350"
        diff_text = f"{item['diff_pct']:+.1f}%"
        layout.addWidget(QLabel(name))
        layout.addStretch()
        lbl_val = QLabel(val_text); lbl_val.setStyleSheet("color: #787b86;")
        layout.addWidget(lbl_val)
        layout.addSpacing(15)
        lbl_diff = QLabel(diff_text); lbl_diff.setStyleSheet(f"color: {color}; font-weight: bold;")
        layout.addWidget(lbl_diff)
        self.scroll_layout.addWidget(frame)

    def add_played_card(self, item):
        border = "border-left: 3px solid gold;" if item['is_pb'] else ""
        frame = QFrame()
        frame.setStyleSheet(f"background: #1e222d; border-radius: 4px; {border}")
        layout = QHBoxLayout(frame)
        name = item['name']
        if item.get('sens'): name += f" ({item['sens']}cm)"
        if item['is_pb']: name = "🏆 " + name
        layout.addWidget(QLabel(name))
        layout.addStretch()
        layout.addWidget(QLabel(f"{item['count']} runs | Best: {item['best']:.0f} | Avg: {item['avg']:.1f}"))
        self.scroll_layout.addWidget(frame)