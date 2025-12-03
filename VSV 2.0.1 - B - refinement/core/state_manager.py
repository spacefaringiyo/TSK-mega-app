from PyQt6.QtCore import QObject, pyqtSignal

class StateManager(QObject):
    """
    Central Hub for application state.
    """
    data_updated = pyqtSignal(object) 
    scenario_selected = pyqtSignal(str) 
    variant_selected = pyqtSignal(dict) 
    settings_changed = pyqtSignal() 
    session_selected = pyqtSignal(int)
    
    # NEW: Updates the main window header
    chart_title_changed = pyqtSignal(str) 

    def __init__(self):
        super().__init__()