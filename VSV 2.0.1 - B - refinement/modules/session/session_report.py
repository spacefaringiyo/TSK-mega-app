from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
                             QCheckBox, QScrollArea, QComboBox, QSizePolicy, QGridLayout)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
import pandas as pd
import numpy as np
from collections import defaultdict
from core.analytics import stats as engine
from modules.charts.chart_widget import ChartWidget, COLORS_CYCLE_10

class SessionToolbar(QFrame):
    def __init__(self, parent_widget):
        super().__init__()
        self.setStyleSheet("background: #1e222d; border-bottom: 1px solid #363a45;")
        self.setFixedHeight(50)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5,5,5,5)
        
        self.chk_group_scen = QCheckBox("Group by Scenario")
        self.chk_group_scen.stateChanged.connect(parent_widget.refresh_view)
        layout.addWidget(self.chk_group_scen)
        
        layout.addSpacing(10)
        
        # --- NEW: SORT COMBO ---
        layout.addWidget(QLabel("Sort:"))
        self.cb_sort = QComboBox()
        self.cb_vis_items = ["Performance", "Most Played", "Time", "A-Z"]
        self.cb_sort.addItems(self.cb_vis_items)
        self.cb_sort.currentIndexChanged.connect(parent_widget.refresh_view)
        layout.addWidget(self.cb_sort)
        
        layout.addSpacing(10)
        
        self.cb_vis = QComboBox()
        self.cb_vis.addItems(["Line Plot", "Dot Only", "Filled Area"])
        self.cb_vis.currentIndexChanged.connect(parent_widget.refresh_view)
        layout.addWidget(self.cb_vis)
        
        self.chk_color = QCheckBox("Color by Scenario")
        self.chk_color.setChecked(True)
        self.chk_color.stateChanged.connect(parent_widget.refresh_view)
        layout.addWidget(self.chk_color)
        
        self.chk_trend = QCheckBox("Trend"); self.chk_trend.setChecked(True)
        self.chk_trend.stateChanged.connect(parent_widget.refresh_view)
        layout.addWidget(self.chk_trend)
        
        self.chk_flow = QCheckBox("Flow"); self.chk_flow.setChecked(True)
        self.chk_flow.stateChanged.connect(parent_widget.refresh_view)
        layout.addWidget(self.chk_flow)
        
        layout.addStretch()

class SessionReportWidget(QWidget):
    def __init__(self, state_manager):
        super().__init__()
        self.state_manager = state_manager
        self.full_df = None
        self.summary = None
        self.current_session_id = None
        self.stack_pbs = False 
        
        self.setup_ui()
        
        self.state_manager.data_updated.connect(self.on_data_updated)
        self.state_manager.session_selected.connect(self.on_session_selected)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0,0,0,0)
        
        # 1. Header (Metrics)
        self.header = QFrame()
        self.header.setStyleSheet("background: #1e222d; border-bottom: 1px solid #363a45;")
        self.header.setFixedHeight(80)
        self.header_layout = QHBoxLayout(self.header)
        main_layout.addWidget(self.header)
        
        # 2. Toolbar
        self.toolbar = SessionToolbar(self)
        main_layout.addWidget(self.toolbar)

        # 3. Chart
        self.chart = ChartWidget(self.state_manager, listen_to_global_signals=False)
        self.chart.setMinimumHeight(300)
        main_layout.addWidget(self.chart, stretch=2)

        # 4. Lists
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: #131722; border: none;")
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(10, 10, 10, 10)
        self.scroll_layout.setSpacing(10)
        self.scroll.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll, stretch=3)

    def set_stack_mode(self, enabled):
        """Called by parent Manager when toggle changes"""
        if self.stack_pbs != enabled:
            self.stack_pbs = enabled
            if self.current_session_id is not None:
                self.on_session_selected(self.current_session_id)

    def on_data_updated(self, df): 
        self.full_df = df
        if self.current_session_id is not None:
            self.on_session_selected(self.current_session_id)

    def on_session_selected(self, session_id):
        self.current_session_id = session_id 
        if self.full_df is None: return
        if session_id not in self.full_df['SessionID'].values: return

        session_df = self.full_df[self.full_df['SessionID'] == session_id].copy()
        session_df.sort_values('Timestamp', inplace=True)
        
        self.summary = engine.analyze_session(session_df, self.full_df, stack_pbs=self.stack_pbs)
        if not self.summary: return
        
        self.refresh_view()

    def refresh_view(self):
        if not self.summary: return
        
        view_mode = 'scenario' if self.toolbar.chk_group_scen.isChecked() else 'grid'
        data = self.summary[view_mode]
        meta = self.summary['meta']
        
        vis_style = self.toolbar.cb_vis.currentText()
        use_color = self.toolbar.chk_color.isChecked()
        
        # 1. Metrics
        self.refresh_metrics(meta, data['pb_count'])
        
        # 2. Plot
        raw_points = data['graph_data']
        unique_scens = sorted(list(set(p['scenario'] for p in raw_points)))
        color_map = {scen: COLORS_CYCLE_10[i % len(COLORS_CYCLE_10)] for i, scen in enumerate(unique_scens)}
        
        for p in raw_points:
            p['color_hex'] = color_map[p['scenario']] if use_color else '#2962FF'
            p['meta'] = {
                'scenario': p['scenario'],
                'sens': p['sens'],
                'subtext': f"{p['pct']:.1f}% vs Avg"
            }
        
        segments = []
        if raw_points:
            curr_scen_name = raw_points[0]['scenario']
            curr_seg = {'data': [], 'color': raw_points[0]['color_hex']}
            for p in raw_points:
                if p['scenario'] != curr_scen_name:
                    segments.append(curr_seg)
                    curr_seg = {'data': [], 'color': p['color_hex']}
                    curr_scen_name = p['scenario']
                curr_seg['data'].append(p)
            segments.append(curr_seg)

        payload = []
        for i, seg in enumerate(segments):
            chart_data = [{'time': p['time'], 'value': p['pct'], 'meta': p['meta']} for p in seg['data']]
            item = {
                'data': chart_data,
                'color': seg['color'],
                'width': 2,
                'filled': (vis_style == "Filled Area"),
                'fill_negative': True,
                'markers': []
            }
            if vis_style == "Dot Only": item['width'] = 0
            
            if seg['data'] and not use_color:
                first = seg['data'][0]
                label = first['scenario']
                if first.get('sens'): label += f" ({first['sens']}cm)"
                item['markers'].append({
                    'time': first['time'],
                    'text': label,
                    'color': '#FF9800'
                })
            payload.append(item)
            
            if i < len(segments) - 1:
                next_seg = segments[i+1]
                last_p = seg['data'][-1]
                first_p = next_seg['data'][0]
                bridge_data = [{'time': last_p['time'], 'value': last_p['pct']}, {'time': first_p['time'], 'value': first_p['pct']}]
                bridge = {'data': bridge_data, 'color': next_seg['color'], 'width': 2, 'filled': (vis_style == "Filled Area"), 'fill_negative': True}
                if vis_style == "Dot Only": bridge['width'] = 0
                payload.append(bridge)

        if self.toolbar.chk_trend.isChecked():
            trend_pts = [{'time': p['time'], 'value': p['trend_pct']} for p in raw_points]
            payload.append({'data': trend_pts, 'color': '#FF9800', 'width': 3})
            
        if self.toolbar.chk_flow.isChecked():
            flow_pts = [{'time': p['time'], 'value': p['flow_pct']} for p in raw_points]
            payload.append({'data': flow_pts, 'color': '#E040FB', 'width': 3})

        self.chart.plot_payload(payload)
        
        # 3. Lists
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

    def render_lists(self, lists):
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        sort_mode = self.toolbar.cb_sort.currentText()

        # --- PB FLOW LOGIC ---
        if lists['pbs']:
            self.add_header(f"Personal Bests ({len(lists['pbs'])})", "#4CAF50")
            
            grouped_pbs = defaultdict(list)
            for item in lists['pbs']:
                key = (item['name'], item.get('sens'))
                grouped_pbs[key].append(item)
                
            group_list = list(grouped_pbs.items())
            
            # SORT GROUPS
            if sort_mode == "Performance":
                group_list.sort(key=lambda x: max(i['imp_pct'] for i in x[1]), reverse=True)
            elif sort_mode == "Most Played":
                group_list.sort(key=lambda x: len(x[1]), reverse=True)
            elif sort_mode == "Time":
                # Sort by earliest timestamp in the group
                # Each group is (key, [items]). We take min time of items.
                group_list.sort(key=lambda x: min(i['time'] for i in x[1]))
            elif sort_mode == "A-Z":
                group_list.sort(key=lambda x: x[0][0].lower())
            
            for key, items in group_list:
                self.add_pb_flow_card(key[0], key[1], items)

        # --- AVG COMPARISON ---
        if lists['avgs']:
            self.add_header("Average Comparison", "#FF9800")
            
            if sort_mode == "Performance":
                lists['avgs'].sort(key=lambda x: x['diff_pct'], reverse=True)
            elif sort_mode == "Time":
                lists['avgs'].sort(key=lambda x: x['time'])
            elif sort_mode == "A-Z":
                lists['avgs'].sort(key=lambda x: x['name'].lower())
                
            for item in lists['avgs']: self.add_avg_card(item)

        # --- SCENARIOS PLAYED ---
        self.add_header("Scenarios Played", "#2962FF")
        
        if sort_mode == "Performance":
            lists['played'].sort(key=lambda x: ((x['best']-x['avg'])/x['avg'] if x['avg']>0 else -1), reverse=True)
        elif sort_mode == "Most Played":
            lists['played'].sort(key=lambda x: x['count'], reverse=True)
        elif sort_mode == "Time":
            lists['played'].sort(key=lambda x: x['time'])
        elif sort_mode == "A-Z":
            lists['played'].sort(key=lambda x: x['name'].lower())
            
        for item in lists['played']: self.add_played_card(item)
            
        self.scroll_layout.addStretch()

    def add_header(self, text, color):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 14px; margin-top: 10px; border-bottom: 1px solid #363a45; padding-bottom: 5px;")
        self.scroll_layout.addWidget(lbl)

    def add_pb_flow_card(self, name, sens, pb_items):
        pb_items.sort(key=lambda x: x['score'])
        
        start_pb = pb_items[0]['prev']
        end_pb = pb_items[-1]['score']
        total_gain = end_pb - start_pb
        total_gain_pct = (total_gain / start_pb * 100) if start_pb > 0 else 0
        
        frame = QFrame()
        # ID used to stop style bleed
        frame.setObjectName("pb_card")
        frame.setStyleSheet("""
            QFrame#pb_card {
                background: #1e222d; 
                border-radius: 4px; 
                border-left: 3px solid #4CAF50;
            }
        """)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)
        
        # ROW 1: Header
        r1 = QHBoxLayout()
        r1.setContentsMargins(0,0,0,0)
        
        name_txt = name
        if sens: name_txt += f" {sens}cm"
        
        lbl_name = QLabel(name_txt)
        lbl_name.setStyleSheet("font-weight: bold; font-size: 13px; color: #d1d4dc; border: none; background: transparent;")
        
        lbl_gain = QLabel(f"+{total_gain:.0f}  +{total_gain_pct:.1f}%")
        lbl_gain.setStyleSheet("font-weight: bold; color: #4CAF50; border: none; background: transparent;")
        
        r1.addWidget(lbl_name)
        r1.addStretch()
        r1.addWidget(lbl_gain)
        layout.addLayout(r1)
        
        # ROW 2: The Flow Sequence
        r2 = QHBoxLayout()
        r2.setContentsMargins(0,0,0,0)
        r2.setSpacing(5)
        
        def create_badge(score, gain_pct=None, is_trophy=False, is_ghost=False):
            badge = QFrame()
            
            # Constraint: Consistent size
            badge.setMinimumWidth(80)
            badge.setMaximumWidth(120)
            badge.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            
            if is_ghost:
                bg, border, text_col = "transparent", "1px dashed #555", "#787b86"
            elif is_trophy:
                bg, border, text_col = "#332a00", "1px solid #FFD700", "#FFD700"
            else:
                bg, border, text_col = "#0d260d", "1px solid #2E7D32", "#4CAF50"
            
            # Inline style for the badge frame only
            badge.setStyleSheet(f".QFrame {{ background: {bg}; border: {border}; border-radius: 4px; }}")
            
            # Use Grid to center Score exactly, while fitting Trophy
            g = QGridLayout(badge)
            g.setContentsMargins(4, 4, 4, 4)
            g.setSpacing(0)
            
            # 1. Score Row
            # Left Spacer (same width as Trophy to balance it)
            if is_trophy:
                lbl_spacer = QLabel()
                lbl_spacer.setFixedWidth(15) 
                # FIX: Explicit Transparency
                lbl_spacer.setStyleSheet("border: none; background: transparent;")
                g.addWidget(lbl_spacer, 0, 0)
                
            # Score (Center)
            s_lbl = QLabel(f"{score:.0f}")
            s_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            # FIX: Explicit Transparency
            s_lbl.setStyleSheet(f"color: {text_col}; font-weight: bold; font-size: 13px; border: none; background: transparent;")
            g.addWidget(s_lbl, 0, 1)
            
            # Trophy (Right)
            if is_trophy:
                t_lbl = QLabel("🏆")
                t_lbl.setFixedWidth(15)
                # FIX: Explicit Transparency
                t_lbl.setStyleSheet("font-size: 11px; border: none; background: transparent;")
                g.addWidget(t_lbl, 0, 2)
            
            # 2. Gain Row (Span all columns)
            if gain_pct is not None:
                g_lbl = QLabel(f"+{gain_pct:.1f}%")
                g_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                # FIX: Explicit Transparency
                g_lbl.setStyleSheet(f"color: {text_col}; font-size: 10px; margin-top: 1px; border: none; background: transparent;")
                g.addWidget(g_lbl, 1, 0, 1, 3) 
                
            return badge

        # 1. Start (Ghost)
        r2.addWidget(create_badge(start_pb, is_ghost=True))
        
        # 2. Intermediate & Final
        prev_step_score = start_pb
        
        for i, item in enumerate(pb_items):
            current_score = item['score']
            is_final = (i == len(pb_items) - 1)
            
            # Arrow
            arrow = QLabel("➜")
            # FIX: Explicit Transparency
            arrow.setStyleSheet("color: #787b86; font-size: 16px; font-weight: bold; border: none; background: transparent;")
            r2.addWidget(arrow)
            
            step_gain_pct = 0
            if prev_step_score > 0:
                step_gain_pct = ((current_score - prev_step_score) / prev_step_score) * 100
            
            r2.addWidget(create_badge(current_score, step_gain_pct, is_trophy=is_final))
            prev_step_score = current_score 
            
        r2.addStretch()
        layout.addLayout(r2)
        
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