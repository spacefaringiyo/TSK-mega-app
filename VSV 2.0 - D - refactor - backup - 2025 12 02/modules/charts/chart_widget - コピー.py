import datetime
import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPen, QColor

class ChartWidget(QWidget):
    def __init__(self, state_manager, listen_to_global_signals=True):
        super().__init__()
        self.state_manager = state_manager
        self.listen_to_global = listen_to_global_signals
        self.all_runs_df = None
        
        # Internal state for tooltip lookup
        # Maps Index (int) -> Timestamp (float)
        self.index_to_time_map = {} 
        
        # 1. Setup Layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # 2. Configure PyQtGraph Global Look
        pg.setConfigOption('background', '#131722')
        pg.setConfigOption('foreground', '#d1d4dc')
        pg.setConfigOptions(antialias=True)

        # 3. Create Plot Widget
        self.plot_widget = pg.PlotWidget()
        
        # Style the Grid (Issue #4)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.25) # Slightly more visible
        
        # Style Axes
        for axis in ['bottom', 'left']:
            ax = self.plot_widget.getAxis(axis)
            ax.setPen(color='#363a45')
            ax.setTextPen(color='#787b86')
            ax.setStyle(tickTextOffset=8)

        self.layout.addWidget(self.plot_widget)

        # 4. Scenario Title Overlay (Issue #2)
        self.title_label = QLabel(self.plot_widget)
        self.title_label.setStyleSheet("color: #d1d4dc; font-size: 14px; font-weight: bold; background: transparent;")
        self.title_label.move(15, 10) # Top Left padding
        self.title_label.hide()

        # 5. Crosshair Setup
        self.v_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('#787b86', style=Qt.PenStyle.DashLine))
        self.h_line = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('#787b86', style=Qt.PenStyle.DashLine))
        self.plot_widget.addItem(self.v_line, ignoreBounds=True)
        self.plot_widget.addItem(self.h_line, ignoreBounds=True)
        
        # Crosshair Label
        self.label = pg.TextItem(text="", color="#d1d4dc", anchor=(0, 1))
        self.plot_widget.addItem(self.label, ignoreBounds=True)
        
        # Mouse Move Proxy
        self.proxy = pg.SignalProxy(self.plot_widget.scene().sigMouseMoved, rateLimit=60, slot=self.mouse_moved)

        # 6. Connect Signals
        self.state_manager.data_updated.connect(self.on_data_updated)
        if self.listen_to_global:
            self.state_manager.scenario_selected.connect(self.on_scenario_selected)
            self.state_manager.variant_selected.connect(self.on_scenario_selected)

    def mouse_moved(self, evt):
        pos = evt[0]
        if self.plot_widget.sceneBoundingRect().contains(pos):
            mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)
            
            # Snap to nearest integer index (Issue: Snapping)
            index = int(round(mouse_point.x()))
            
            self.v_line.setPos(index)
            self.h_line.setPos(mouse_point.y())
            
            # Lookup Date
            date_str = ""
            if index in self.index_to_time_map:
                ts = self.index_to_time_map[index]
                dt = datetime.datetime.fromtimestamp(ts)
                date_str = dt.strftime('%Y-%m-%d %H:%M')

            self.label.setText(f"{date_str}\n{mouse_point.y():.1f}")
            self.label.setPos(index, mouse_point.y())

    def on_data_updated(self, df): 
        self.all_runs_df = df

    # --- PLOT LOGIC ---
    def plot_payload(self, payload_list, title=None):
        self.plot_widget.clear()
        self.index_to_time_map = {}
        
        # Re-add persistent items
        self.plot_widget.addItem(self.v_line, ignoreBounds=True)
        self.plot_widget.addItem(self.h_line, ignoreBounds=True)
        self.plot_widget.addItem(self.label, ignoreBounds=True)
        
        # Set Title
        if title:
            self.title_label.setText(title)
            self.title_label.adjustSize()
            self.title_label.show()
        else:
            self.title_label.hide()

        for item in payload_list:
            if not item.get('data'): continue
            
            # --- ISSUE #1: COUNT ORIENTED ---
            # We ignore the 'time' for X pos, use Index (0, 1, 2...)
            # We assume data is sorted chronologically
            
            # Extract Y values
            y = [p['value'] for p in item['data']]
            x = list(range(len(y)))
            
            # Map Index -> Time (for tooltip)
            for i, p in enumerate(item['data']):
                self.index_to_time_map[i] = p['time']

            # Plot Line
            color_hex = item.get('color', '#FFFFFF')
            width = item.get('width', 2)
            pen = pg.mkPen(color=color_hex, width=width)
            
            # Scatter Points (Symbol)
            self.plot_widget.plot(x, y, pen=pen, symbol='o', symbolSize=5, symbolBrush=color_hex)
            
            # --- ISSUE #3: LABELS & SEPARATORS ---
            if item.get('markers'):
                for m in item['markers']:
                    m_time = m['time']
                    
                    # Find which Index this timestamp corresponds to
                    # (Find exact match)
                    idx_match = next((i for i, p in enumerate(item['data']) if p['time'] == m_time), None)
                    
                    if idx_match is not None:
                        m_val = y[idx_match]
                        
                        # Vertical Separator Line
                        sep_line = pg.InfiniteLine(pos=idx_match, angle=90, pen=pg.mkPen('#363a45', width=1))
                        self.plot_widget.addItem(sep_line)
                        
                        # Text Label (Vertical, Tilted)
                        text = pg.TextItem(
                            text=m.get('text', ''), 
                            color=m.get('color', '#FF9800'), 
                            anchor=(0, 0.5), # Anchor left-middle
                            angle=-90        # Vertical text
                        )
                        # Position slightly above the point
                        text.setPos(idx_match, m_val + (max(y)*0.05)) 
                        self.plot_widget.addItem(text)

            # --- ISSUE #5: REF LINES (Avg/75th) ---
            if item.get('ref_lines'):
                for ref in item['ref_lines']:
                    line = pg.InfiniteLine(
                        pos=ref['value'], 
                        angle=0, 
                        pen=pg.mkPen(ref['color'], style=Qt.PenStyle.DashLine, width=1)
                    )
                    self.plot_widget.addItem(line)
                    
                    # Label for the line (e.g. "Avg: 1200")
                    ref_lbl = pg.TextItem(text=ref['label'], color=ref['color'], anchor=(0, 1), angle=0)
                    ref_lbl.setPos(0, ref['value']) # At start of graph
                    self.plot_widget.addItem(ref_lbl)

    # --- MAIN TAB LOGIC ---
    def on_scenario_selected(self, scenario_name):
        if not self.listen_to_global: return
        if self.all_runs_df is None: return
        
        # 1. Filter Data
        mask = self.all_runs_df['Scenario'].str.startswith(scenario_name)
        df = self.all_runs_df[mask].copy()
        if df.empty: return

        # 2. Sort
        df['Timestamp'] = df['Timestamp'].dt.to_pydatetime()
        df.sort_values('Timestamp', inplace=True)
        
        # 3. Create Payload
        data_points = []
        for _, row in df.iterrows():
            data_points.append({
                'time': row['Timestamp'].timestamp(),
                'value': float(row['Score'])
            })

        # --- ISSUE #5: Calculate Stats for Lines ---
        scores = df['Score']
        avg_val = scores.mean()
        p75_val = scores.quantile(0.75)

        payload = [{
            'id': 'main_score',
            'color': '#2962FF',
            'width': 2,
            'data': data_points,
            'ref_lines': [
                {'value': avg_val, 'label': f'Avg: {avg_val:.1f}', 'color': '#787b86'},
                {'value': p75_val, 'label': f'75th: {p75_val:.1f}', 'color': '#4CAF50'}
            ]
        }]
        
        # Pass the scenario name for the Title Overlay
        self.plot_payload(payload, title=scenario_name)