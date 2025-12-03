import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

class DailyActivityWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.setFixedHeight(100) # Compact height
        
        # Plot Setup
        pg.setConfigOption('background', '#131722')
        pg.setConfigOption('foreground', '#d1d4dc')
        pg.setConfigOptions(antialias=True)
        
        self.plot = pg.PlotWidget()
        self.plot.showGrid(x=False, y=False)
        self.plot.setMouseEnabled(x=False, y=False)
        self.plot.hideButtons()
        
        # Axis Style
        ax_b = self.plot.getAxis('bottom')
        ax_b.setTicks([
            [(0, '00:00'), (6, '06:00'), (12, '12:00'), (18, '18:00'), (24, '24:00')],
            []
        ])
        ax_b.setPen(color='#363a45')
        ax_b.setTextPen(color='#787b86')
        
        self.plot.getAxis('left').hide()
        self.plot.setYRange(0, 0.60) # Fixed range 0% to 60%
        self.plot.setXRange(0, 24)
        
        layout.addWidget(self.plot)

    def load_data(self, day_df, stack_pbs=True):
        self.plot.clear()
        if day_df is None or day_df.empty: return
        
        # 1. Activity Curve (30m) - Unaffected by Toggle
        bins = np.zeros(48)
        day_start = day_df['Timestamp'].min().floor('D')
        start_ts = day_start.timestamp()
        
        for _, row in day_df.iterrows():
            rel_sec = row['Timestamp'].timestamp() - start_ts
            rel_hour = rel_sec / 3600.0
            bin_idx = int(rel_hour * 2) 
            if 0 <= bin_idx < 48: bins[bin_idx] += row['Duration'] / 1800.0

        data = pd.Series(bins)
        smoothed = data.rolling(window=3, center=True, min_periods=1).mean().values
        x_axis = np.linspace(0, 24, 48)
        c = QColor("#4CAF50"); c.setAlpha(50)
        brush = pg.mkBrush(c); pen = pg.mkPen("#4CAF50", width=2)
        self.plot.plot(x_axis, smoothed, pen=pen, brush=brush, fillLevel=0)
        
        # 2. PB Markers (10m)
        pb_bins = {}
        
        # Filter Logic based on Toggle
        pbs = day_df[(day_df['Is_PB'] == 1) | (day_df.get('Is_Scen_PB', 0) == 1)].copy()
        
        if not stack_pbs and not pbs.empty:
            # UNIQUE MODE: Keep only the row with the Max Score for each Scenario/Sens combo
            # If multiple runs match max score, keep the first one
            # Note: We group by Sens for 'Is_PB' and Scenario for 'Is_Scen_PB'
            
            # Since a run can be BOTH Scen PB and Sens PB, strict separation is tricky.
            # Simplified approach: Group by [Scenario, Sens], pick Max Score.
            idx_to_keep = pbs.groupby(['Scenario', 'Sens'])['Score'].idxmax()
            pbs = pbs.loc[idx_to_keep]

        for _, row in pbs.iterrows():
            if row.get('Is_First', False): continue
            
            rel_sec = row['Timestamp'].timestamp() - start_ts
            bin_idx = int((rel_sec / 3600.0) * 6)
            
            if bin_idx not in pb_bins: pb_bins[bin_idx] = {'scen': 0, 'sens': 0}
            
            if row.get('Is_Scen_PB', 0) == 1: pb_bins[bin_idx]['scen'] += 1
            elif row.get('Is_PB', 0) == 1: pb_bins[bin_idx]['sens'] += 1
                
        # Draw Icons
        for b_idx, counts in pb_bins.items():
            x_pos = (b_idx / 6.0) + (1/12.0)
            
            # Helper to get size
            def get_font(cnt):
                f = QFont()
                if cnt >= 3: f.setPointSize(18)   # Large
                elif cnt == 2: f.setPointSize(14) # Medium
                else: f.setPointSize(10)          # Small
                return f

            # Scen (Top)
            if counts['scen'] > 0:
                item = pg.TextItem("🏆", color="#FFD700", anchor=(0.5, 0.5))
                item.setFont(get_font(counts['scen']))
                item.setPos(x_pos, 0.55)
                self.plot.addItem(item)
                
            # Sens (Bottom)
            if counts['sens'] > 0:
                item = pg.TextItem("🎯", color="#00E5FF", anchor=(0.5, 0.5))
                item.setFont(get_font(counts['sens']))
                item.setPos(x_pos, 0.45)
                self.plot.addItem(item)