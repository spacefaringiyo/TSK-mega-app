from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QLabel, QFrame, QHBoxLayout, 
                             QAbstractItemView, QComboBox, QRadioButton, 
                             QCheckBox, QButtonGroup, QMenu, QDialog, QListWidget, QPushButton)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor, QCursor
import pandas as pd
import numpy as np
import re
from core.analytics import parsers, stats
from modules.dashboard import strategies
from modules.dashboard.tooltip import CustomTooltip

class ManageHiddenDialog(QDialog):
    def __init__(self, hidden_scens, hidden_cms, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Hidden Items")
        self.resize(400, 300)
        self.hidden_scens = hidden_scens
        self.hidden_cms = hidden_cms
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Hidden Scenarios:"))
        self.list_scens = QListWidget()
        self.list_scens.addItems(self.hidden_scens)
        layout.addWidget(self.list_scens)
        btn_unhide_scen = QPushButton("Unhide Selected Scenario")
        btn_unhide_scen.clicked.connect(self.unhide_scen)
        layout.addWidget(btn_unhide_scen)

        layout.addWidget(QLabel("Hidden CMs (Global/Current):"))
        self.list_cms = QListWidget()
        self.list_cms.addItems(self.hidden_cms)
        layout.addWidget(self.list_cms)
        btn_unhide_cm = QPushButton("Unhide Selected CM")
        btn_unhide_cm.clicked.connect(self.unhide_cm)
        layout.addWidget(btn_unhide_cm)

    def unhide_scen(self):
        for item in self.list_scens.selectedItems():
            self.hidden_scens.remove(item.text())
            self.list_scens.takeItem(self.list_scens.row(item))

    def unhide_cm(self):
        for item in self.list_cms.selectedItems():
            self.hidden_cms.remove(item.text())
            self.list_cms.takeItem(self.list_cms.row(item))

class GridWidget(QWidget):
    def __init__(self, state_manager, config_manager):
        super().__init__()
        self.state_manager = state_manager
        self.config_manager = config_manager
        
        # Data State
        self.all_runs_df = None
        self.current_family_df = None
        self.base_scenario_name = ""
        self.is_loading_state = False
        self.recent_data_map = {}
        
        self.agg_strategies = {cls.name: cls() for cls in strategies.AGGREGATION_MODES}
        self.hl_strategies = {cls.name: cls() for cls in strategies.HIGHLIGHT_MODES}
        self.active_agg = self.agg_strategies["Personal Best"]
        self.active_hl = self.hl_strategies["Row Heatmap"]

        self.hidden_scenarios = set()
        self.hidden_cms = set()

        self.agg_setting_widget = None
        self.hl_setting_widget = None
        self.format_checkboxes = {} 
        self.current_axis = "Sens"
        self.axis_filter_cache = {} 
        
        self.tooltip = CustomTooltip(self)
        self.tooltip.hide()

        self.setup_ui()
        
        self.state_manager.data_updated.connect(self.on_data_updated)
        self.state_manager.scenario_selected.connect(self.on_scenario_selected)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
        
        # ROW 1
        self.row1 = self.create_toolbar_row("Compare by:")
        self.axis_container = QHBoxLayout()
        self.row1.layout().addLayout(self.axis_container)
        self.row1.layout().addStretch()
        self.axis_group = QButtonGroup(self)
        self.axis_group.buttonClicked.connect(self.on_axis_changed)
        layout.addWidget(self.row1)

        # ROW 2
        self.row2 = self.create_toolbar_row("Filter Format:")
        self.format_container = QHBoxLayout()
        self.row2.layout().addLayout(self.format_container)
        self.row2.layout().addStretch()
        layout.addWidget(self.row2)
        self.row2.setVisible(False)

        # ROW 3
        self.row3 = self.create_toolbar_row("Sens Step:")
        self.sens_combo = QComboBox()
        self.sens_combo.addItems(["All", "2cm", "3cm", "5cm", "10cm"])
        self.sens_combo.currentIndexChanged.connect(self.on_control_changed)
        self.row3.layout().addWidget(self.sens_combo)
        
        self.row3.layout().addSpacing(20)
        self.row3.layout().addWidget(QLabel("Mode:"))
        
        self.mode_group = QButtonGroup(self)
        self.mode_group.buttonClicked.connect(self.on_mode_changed)
        for mode_cls in strategies.AGGREGATION_MODES:
            btn = QRadioButton(mode_cls.name)
            self.row3.layout().addWidget(btn)
            self.mode_group.addButton(btn)
            if mode_cls.name == "Personal Best": btn.setChecked(True)
            
        self.agg_setting_container = QHBoxLayout()
        self.row3.layout().addLayout(self.agg_setting_container)
        self.row3.layout().addStretch()
        layout.addWidget(self.row3)

        # ROW 4
        self.row4 = self.create_toolbar_row("Highlight:")
        self.hl_group = QButtonGroup(self)
        self.hl_group.buttonClicked.connect(self.on_highlight_changed)
        for hl_cls in strategies.HIGHLIGHT_MODES:
            btn = QRadioButton(hl_cls.name)
            self.row4.layout().addWidget(btn)
            self.hl_group.addButton(btn)
            if hl_cls.name == "Row Heatmap": btn.setChecked(True)

        self.hl_setting_container = QHBoxLayout()
        self.row4.layout().addLayout(self.hl_setting_container)
        self.row4.layout().addStretch()
        
        btn_manage = QPushButton("Manage Hidden")
        btn_manage.clicked.connect(self.open_manage_hidden)
        self.row4.layout().addWidget(btn_manage)

        layout.addWidget(self.row4)

        # ROW 5
        self.grid = QTableWidget()
        self.grid.verticalHeader().setVisible(False)
        self.grid.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.grid.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.grid.cellClicked.connect(self.on_cell_clicked)
        self.grid.setMouseTracking(True)
        self.grid.cellEntered.connect(self.on_cell_entered)
        
        self.grid.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.grid.customContextMenuRequested.connect(self.on_table_context_menu)
        self.grid.horizontalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.grid.horizontalHeader().customContextMenuRequested.connect(self.on_header_context_menu)

        layout.addWidget(self.grid)
        self.update_strategy_widgets()

    def create_toolbar_row(self, label_text):
        frame = QFrame()
        frame.setObjectName("Panel")
        frame.setStyleSheet("border-bottom: 1px solid #363a45;")
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(10, 5, 10, 5)
        lay.addWidget(QLabel(label_text))
        return frame

    def leaveEvent(self, event):
        self.tooltip.hide()
        super().leaveEvent(event)

    def focusOutEvent(self, event):
        self.tooltip.hide()
        super().focusOutEvent(event)

    def on_data_updated(self, df): self.all_runs_df = df

    def on_scenario_selected(self, scenario_name):
        if self.all_runs_df is None: return
        self.base_scenario_name = scenario_name
        self.is_loading_state = True
        
        # 1. Title
        # Fix: We removed self.title_lbl in the V2 layout (Toolbar rows replaced it)
        # If you want a title, we can add it to Row 1 or rely on Tab Name.
        # Current design relies on Tab Name.

        # 2. Get Family
        family_df = parsers.get_scenario_family_info(self.all_runs_df, scenario_name)
        if family_df is None or family_df.empty:
            family_df = self.all_runs_df[self.all_runs_df['Scenario'] == scenario_name].copy()
            family_df['Modifiers'] = [{}] * len(family_df)
        self.current_family_df = family_df

        # 3. Populate Axes
        axes = set()
        for mods in family_df['Modifiers']:
            if isinstance(mods, dict): axes.update(mods.keys())
        available_axes = sorted(list(axes))
        if not available_axes: available_axes = ["Default"]
        
        for btn in self.axis_group.buttons():
            self.axis_group.removeButton(btn)
            btn.deleteLater()
        
        for axis in available_axes:
            btn = QRadioButton(axis)
            self.axis_container.addWidget(btn)
            self.axis_group.addButton(btn)
        
        # Default Select
        if self.axis_group.buttons():
            self.axis_group.buttons()[0].setChecked(True)
            self.current_axis = self.axis_group.buttons()[0].text()
            self.rebuild_format_options()

        self.load_view_settings()
        self.is_loading_state = False
        self.refresh_grid_view()

    def on_axis_changed(self, btn):
        if not btn: return
        
        # 1. Save state of OLD axis to cache
        old_disabled = []
        for pat, chk in self.format_checkboxes.items():
            if not chk.isChecked(): old_disabled.append(pat)
        self.axis_filter_cache[self.current_axis] = old_disabled
        
        # 2. Switch
        self.current_axis = btn.text()
        self.rebuild_format_options()
        if not self.is_loading_state: self.save_view_settings()
        self.refresh_grid_view()

    def rebuild_format_options(self):
        patterns = set()
        if self.current_family_df is not None:
            for mods in self.current_family_df['Modifiers']:
                if isinstance(mods, dict) and self.current_axis in mods:
                    patterns.add(mods[self.current_axis][1])
        
        while self.format_container.count():
            item = self.format_container.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.format_checkboxes = {}
        
        if len(patterns) > 1:
            self.row2.setVisible(True)
            
            # --- UPDATE: Retrieve saved disabled list ---
            disabled_list = self.axis_filter_cache.get(self.current_axis, [])
            
            for pat in patterns:
                label = f"{self.current_axis} #" if pat == 'word_value' else (f"# {self.current_axis}" if pat == 'value_word' else "Standalone")
                chk = QCheckBox(label)
                
                # Check if in disabled list
                if pat in disabled_list: chk.setChecked(False)
                else: chk.setChecked(True)
                    
                chk.stateChanged.connect(self.on_control_changed)
                self.format_container.addWidget(chk)
                self.format_checkboxes[pat] = chk
        else:
            self.row2.setVisible(False)

    def on_mode_changed(self, btn):
        self.active_agg = self.agg_strategies[btn.text()]
        self.update_strategy_widgets()
        self.on_control_changed()

    def on_highlight_changed(self, btn):
        self.active_hl = self.hl_strategies[btn.text()]
        self.update_strategy_widgets()
        self.on_control_changed()

    def on_control_changed(self):
        if not self.is_loading_state: self.save_view_settings()
        self.refresh_grid_view()

    def update_strategy_widgets(self):
        for layout in [self.agg_setting_container, self.hl_setting_container]:
            while layout.count():
                item = layout.takeAt(0)
                if item.widget(): item.widget().deleteLater()
        
        self.agg_setting_widget = self.active_agg.get_setting_widget()
        if self.agg_setting_widget:
            if hasattr(self.agg_setting_widget, 'valueChanged'):
                self.agg_setting_widget.valueChanged.connect(self.on_control_changed)
            self.agg_setting_container.addWidget(self.agg_setting_widget)

        self.hl_setting_widget = self.active_hl.get_setting_widget()
        if self.hl_setting_widget:
            widget_to_bind = self.hl_setting_widget
            if hasattr(widget_to_bind, 'spin'): widget_to_bind = widget_to_bind.spin
            if hasattr(widget_to_bind, 'valueChanged'):
                widget_to_bind.valueChanged.connect(self.on_control_changed)
            self.hl_setting_container.addWidget(self.hl_setting_widget)

    # --- PERSISTENCE ---
    def load_view_settings(self):
        settings = self.config_manager.get("grid_view", scenario=self.base_scenario_name, default={})
        
        self.hidden_scenarios = set(settings.get("hidden_scenarios", []))
        self.hidden_cms = set(settings.get("hidden_cms", []))
        
        # --- UPDATE: Load the cache map ---
        # Format: {'Size': ['pattern1', 'pattern2'], 'Speed': []}
        self.axis_filter_cache = settings.get("axis_filters", {})
        # ----------------------------------

        if not settings: return

        if "axis" in settings:
            for btn in self.axis_group.buttons():
                if btn.text() == settings["axis"]: 
                    btn.setChecked(True)
                    self.current_axis = btn.text()
                    # Rebuild checks logic handles the restoration from cache
                    self.rebuild_format_options() 
                    break
        
        # 2. Restore Filter Format
        saved_patterns = settings.get("disabled_patterns", [])
        for pat, chk in self.format_checkboxes.items():
            if pat in saved_patterns: chk.setChecked(False)

        if "sens_step" in settings: self.sens_combo.setCurrentText(settings["sens_step"])

        if "mode" in settings:
            for btn in self.mode_group.buttons():
                if btn.text() == settings["mode"]: 
                    btn.setChecked(True); self.active_agg = self.agg_strategies[settings["mode"]]; break
        
        if "highlight" in settings:
            for btn in self.hl_group.buttons():
                if btn.text() == settings["highlight"]: 
                    btn.setChecked(True); self.active_hl = self.hl_strategies[settings["highlight"]]; break
        
        self.update_strategy_widgets()
        
        if "agg_val" in settings and self.agg_setting_widget:
            self.active_agg.set_setting_value(self.agg_setting_widget, settings["agg_val"])
        if "hl_val" in settings and self.hl_setting_widget:
            self.active_hl.set_setting_value(self.hl_setting_widget, settings["hl_val"])

    def save_view_settings(self):
        if not self.base_scenario_name: return
        
        # --- UPDATE: Capture current state to cache before saving ---
        current_disabled = []
        for pat, chk in self.format_checkboxes.items():
            if not chk.isChecked(): current_disabled.append(pat)
        self.axis_filter_cache[self.current_axis] = current_disabled
        # ------------------------------------------------------------

        settings = {
            "axis": self.current_axis,
            "mode": self.active_agg.name,
            "highlight": self.active_hl.name,
            "sens_step": self.sens_combo.currentText(),
            "hidden_scenarios": list(self.hidden_scenarios),
            "hidden_cms": list(self.hidden_cms),
            "axis_filters": self.axis_filter_cache # Save the whole map
        }
        if self.agg_setting_widget:
            settings["agg_val"] = self.active_agg.get_setting_value(self.agg_setting_widget)
        if self.hl_setting_widget:
            settings["hl_val"] = self.active_hl.get_setting_value(self.hl_setting_widget)
            
        self.config_manager.set_scenario(self.base_scenario_name, "grid_view", settings)

    # --- CORE CALCULATION ---

    def refresh_grid_view(self):
        if self.current_family_df is None: return
        df = self.current_family_df.copy()
        
        # Optimization: List of dicts
        records = df.to_dict('records')
        
        base_name = self.base_scenario_name
        curr_axis = self.current_axis
        
        active_formats = {pat: chk.isChecked() for pat, chk in self.format_checkboxes.items()}
        hidden_scens = self.hidden_scenarios

        filtered_rows = []
        for row in records:
            scen = row['Scenario']
            if scen in hidden_scens: continue

            if scen == base_name:
                filtered_rows.append(row)
                continue

            # Check Modifiers
            mods = row['Modifiers']
            if isinstance(mods, dict) and curr_axis in mods:
                # STRICT CHECK: Ensure no other modifiers exist
                mod_keys = list(mods.keys())
                remaining = [k for k in mod_keys if k != curr_axis]
                
                if len(remaining) == 0:
                    val, pat = mods[curr_axis]
                    # Check Format Checkbox
                    if pat in active_formats:
                        if active_formats[pat]: filtered_rows.append(row)
                    else:
                        filtered_rows.append(row)

        if not filtered_rows: self.grid.clear(); return
        filtered_df = pd.DataFrame(filtered_rows)
        
        # ... (Rest of function remains exactly the same from "Prepare ActiveAxis" onwards)
        # Prepare ActiveAxis for grouping (visual pivot only)
        if self.current_axis == "Sens": 
            filtered_df['ActiveAxis'] = filtered_df['Sens']
        else:
            filtered_df['ActiveAxis'] = filtered_df['Modifiers'].apply(
                lambda m: m[self.current_axis][0] if self.current_axis in m else np.nan)

        setting_val = None
        if self.agg_setting_widget:
            setting_val = self.active_agg.get_setting_value(self.agg_setting_widget)
        
        summary = self.active_agg.calculate(filtered_df, setting_val)
        pivot = summary.pivot_table(index='Scenario', columns='Sens', values='Score')

        sens_filter = self.sens_combo.currentText()
        step = 0
        if sens_filter != "All":
            try: step = float(sens_filter.replace("cm", ""))
            except: pass
            
        cols = []
        for c in pivot.columns:
            if str(c) in self.hidden_cms or f"{c}cm" in self.hidden_cms: continue
            if step > 0:
                if self._is_step_match(c, step): cols.append(c)
            else:
                cols.append(c)
                
        pivot = pivot[cols]
        pivot = self.sort_pivot_rows(pivot)

        self.recent_data_map = {}
        if self.active_hl.name == "Recent Success":
            days = 14
            if self.hl_setting_widget:
                days = self.active_hl.get_setting_value(self.hl_setting_widget)
            
            cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
            recent_df = self.current_family_df[self.current_family_df['Timestamp'] >= cutoff]
            if not recent_df.empty:
                self.recent_data_map = recent_df.groupby(['Scenario', 'Sens'])['Score'].max().to_dict()

        self.populate_table(pivot)


    def _is_step_match(self, col, step):
        try:
            val = float(col)
            return abs(val % step) < 0.05 or abs((val % step)-step) < 0.05
        except: return False

    def sort_pivot_rows(self, pivot_df):
        def key(name):
            if name == self.base_scenario_name: return 100.0
            mod = name.replace(self.base_scenario_name, "").strip()
            nums = re.findall(r"(\d+\.?\d*)", mod)
            return float(nums[-1]) if nums else 999.0
        rows = list(pivot_df.index)
        rows.sort(key=key)
        return pivot_df.reindex(rows)

    def populate_table(self, df):
        self.grid.clear()
        cols = sorted(df.columns, key=lambda x: float(x) if str(x).replace('.','').isdigit() else str(x))
        headers = ["Scenario"] + [f"{c}cm" for c in cols] + ["AVG", "Best", "%"]
        
        self.grid.setRowCount(len(df) + 1)
        self.grid.setColumnCount(len(headers))
        self.grid.setHorizontalHeaderLabels(headers)
        
        header = self.grid.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        if len(headers) > 1:
            for i in range(1, len(headers)):
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

        avg_vals = {c: df[c].mean() for c in cols}
        
        # ROW 0
        self.grid.setItem(0,0, QTableWidgetItem("-- Average --"))
        row_means_list = []
        for i, c in enumerate(cols):
            val = avg_vals.get(c, np.nan)
            if pd.notna(val):
                row_means_list.append(val)
                it = QTableWidgetItem(f"{val:.1f}")
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                it.setBackground(QColor(40,44,52))
                self.grid.setItem(0, i+1, it)
        
        if row_means_list:
            it_avg = QTableWidgetItem(f"{np.mean(row_means_list):.1f}")
            it_avg.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid.setItem(0, len(cols)+1, it_avg)
            
            it_max = QTableWidgetItem(f"{np.max(row_means_list):.1f}")
            it_max.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid.setItem(0, len(cols)+2, it_max)

        # Settings for Highlight
        hl_setting = None
        if self.hl_setting_widget:
            hl_setting = self.active_hl.get_setting_value(self.hl_setting_widget)

        # DATA
        row_idx = 1
        for sc, row in df.iterrows():
            self.grid.setItem(row_idx, 0, QTableWidgetItem(str(sc)))
            vals = row.dropna().values
            if len(vals) == 0:
                for i, c in enumerate(cols): self.grid.setItem(row_idx, i+1, QTableWidgetItem("-"))
                row_idx += 1
                continue

            # Context for Coloring
            # Ensure we handle empty dataframe gracefully for global stats
            g_vals = df.values.flatten()
            g_vals = g_vals[~np.isnan(g_vals)]
            
            ctx = {
                'r_min': vals.min(), 'r_max': vals.max(),
                'g_min': g_vals.min() if len(g_vals) > 0 else 0,
                'g_max': g_vals.max() if len(g_vals) > 0 else 1
            }

            for i, c in enumerate(cols):
                val = row.get(c, np.nan)
                if pd.notna(val):
                    it = QTableWidgetItem(f"{val:.0f}")
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    
                   # Logic for Performance Drop (prev_val)
                    # FIX: Only compare if NOT the first data row (row_idx 1 is first data row)
                    if row_idx > 1:
                        prev_item = self.grid.item(row_idx-1, i+1)
                        if prev_item and prev_item.text() != "-" and prev_item.text():
                            try: ctx['prev_val'] = float(prev_item.text())
                            except: ctx['prev_val'] = None
                        else: ctx['prev_val'] = None
                    else:
                        ctx['prev_val'] = None # No comparison for top row

                    # APPLY COLOR
                    col = self.active_hl.get_color(val, ctx, hl_setting)
                    if col: it.setBackground(col)
                    
                    self.grid.setItem(row_idx, i+1, it)
                else:
                    self.grid.setItem(row_idx, i+1, QTableWidgetItem("-"))
            
            it_mean = QTableWidgetItem(f"{vals.mean():.1f}")
            it_mean.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid.setItem(row_idx, len(cols)+1, it_mean)
            
            it_best = QTableWidgetItem(f"{vals.max():.0f}")
            it_best.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid.setItem(row_idx, len(cols)+2, it_best)
            
            base_pb = 1.0
            if self.base_scenario_name in df.index: base_pb = df.loc[self.base_scenario_name].max()
            pct = (vals.max()/base_pb*100) if base_pb>0 else 0
            
            it_pct = QTableWidgetItem(f"{pct:.0f}%")
            it_pct.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid.setItem(row_idx, len(cols)+3, it_pct)
            
            row_idx += 1

    # ... Context Menu handlers remain same ...
    def on_table_context_menu(self, pos):
        item = self.grid.itemAt(pos)
        if not item: return
        if item.column() != 0: return 
        menu = QMenu(self)
        hide_action = QAction(f"Hide Scenario: {item.text()}", self)
        hide_action.triggered.connect(lambda: self.hide_scenario(item.text()))
        menu.addAction(hide_action)
        menu.exec(self.grid.viewport().mapToGlobal(pos))

    def on_header_context_menu(self, pos):
        idx = self.grid.horizontalHeader().logicalIndexAt(pos)
        if idx <= 0: return 
        header_text = self.grid.horizontalHeaderItem(idx).text()
        if header_text in ["AVG", "Best", "%", "cm"]: return
        menu = QMenu(self)
        hide_action = QAction(f"Hide {header_text}", self)
        hide_action.triggered.connect(lambda: self.hide_cm(header_text))
        menu.addAction(hide_action)
        menu.exec(self.grid.horizontalHeader().mapToGlobal(pos))

    def hide_scenario(self, name):
        self.hidden_scenarios.add(name)
        self.save_view_settings()
        self.refresh_grid_view()

    def hide_cm(self, cm_text):
        self.hidden_cms.add(cm_text)
        self.save_view_settings()
        self.refresh_grid_view()

    def open_manage_hidden(self):
        dlg = ManageHiddenDialog(list(self.hidden_scenarios), list(self.hidden_cms), self)
        dlg.exec()
        self.hidden_scenarios = set(dlg.hidden_scens)
        self.hidden_cms = set(dlg.hidden_cms)
        self.save_view_settings()
        self.refresh_grid_view()

    def on_cell_clicked(self, r, c):
        item_scen = self.grid.item(r, 0)
        if not item_scen or item_scen.text() == "-- Average --": return
        
        scenario_name = item_scen.text()
        sens_val = None
        
        # If clicked column > 0, try to find sensitivity
        if c > 0:
            header_text = self.grid.horizontalHeaderItem(c).text()
            # Ignore aggregate columns like AVG, Best, %
            if header_text not in ["AVG", "Best", "%"]:
                try:
                    sens_val = float(header_text)
                except:
                    sens_val = None # Fallback to All Sens
        
        # Emit the new dictionary payload
        self.state_manager.variant_selected.emit({
            'scenario': scenario_name,
            'sens': sens_val
        })

    def on_cell_entered(self, row, col):
        if row < 0 or col < 0: self.tooltip.hide(); return
        
        item_scen = self.grid.item(row, 0)
        if not item_scen: self.tooltip.hide(); return
        
        scenario_name = item_scen.text()
        if scenario_name == "-- Average --": self.tooltip.hide(); return
        
        # Get Sens
        sens_val = None
        sens_str = self.grid.horizontalHeaderItem(col).text().replace("cm", "")
        if col > 0:
            try: sens_val = float(sens_str)
            except: pass
            
        if self.current_family_df is None: return
        
        # Filter DF
        df = self.current_family_df[self.current_family_df['Scenario'] == scenario_name]
        if sens_val is not None:
            df = df[df['Sens'] == sens_val]
            sub_title = f"Sensitivity: {sens_val}cm"
        else:
            if col == 0: sub_title = "Sensitivity: All"
            else: self.tooltip.hide(); return # Empty cell area
            
        if df.empty: self.tooltip.hide(); return
        
        # Calc Stats
        # Import stats module if not available in scope
        from core.analytics import stats
        stats_data = stats.calculate_detailed_stats(df)
        scores = df.sort_values('Timestamp')['Score'].tolist()
        
        self.tooltip.update_data(scenario_name, sub_title, stats_data, scores)
        
        # Move
        cursor_pos = QCursor.pos()
        self.tooltip.move(cursor_pos.x() + 20, cursor_pos.y() + 20)
        self.tooltip.show()
        self.tooltip.raise_()
