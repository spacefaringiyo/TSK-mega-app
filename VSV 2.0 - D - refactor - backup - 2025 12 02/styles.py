# styles.py

BG_DARK = "#131722"
BG_PANEL = "#1e222d"
BG_HOVER = "#2a2e39"
ACCENT = "#2962FF"
TEXT_MAIN = "#d1d4dc"
TEXT_DIM = "#787b86"
BORDER = "#363a45"

QSS = f"""
QMainWindow {{
    background-color: {BG_DARK};
}}
/* --- DOCK WIDGETS --- */
QDockWidget {{
    titlebar-close-icon: url(close.png);
    titlebar-normal-icon: url(float.png);
    color: {TEXT_MAIN};
    font-weight: bold;
}}
QDockWidget::title {{
    background: {BG_PANEL};
    padding-left: 10px;
    padding-top: 4px;
    padding-bottom: 4px;
    border-bottom: 1px solid {BORDER};
}}
QDockWidget::close-button, QDockWidget::float-button {{
    background: transparent;
    border: none;
}}
QDockWidget::close-button:hover, QDockWidget::float-button:hover {{
    background: {BG_HOVER};
}}

/* --- COMMON --- */
QWidget {{
    color: {TEXT_MAIN};
}}
QFrame#Panel {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 4px;
}}
QLineEdit {{
    background-color: {BG_DARK};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 6px;
    color: {TEXT_MAIN};
}}
QPushButton {{
    background-color: {BG_HOVER};
    border: 1px solid {BORDER};
    color: {TEXT_MAIN};
    padding: 6px 12px;
    border-radius: 4px;
}}
QPushButton:hover {{
    background-color: {ACCENT};
    border: 1px solid {ACCENT};
    color: white;
}}
QTableWidget {{
    background-color: {BG_DARK};
    gridline-color: {BORDER};
    border: none;
}}
QHeaderView::section {{
    background-color: {BG_PANEL};
    color: {TEXT_DIM};
    border: none;
    border-bottom: 1px solid {BORDER};
    border-right: 1px solid {BORDER};
    padding: 4px;
}}
"""