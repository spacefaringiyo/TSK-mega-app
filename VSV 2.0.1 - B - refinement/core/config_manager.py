import json
from pathlib import Path

# --- THE TRUTH SOURCE ---
# Update this dictionary when you add new features.
# The app will automatically merge these defaults into user configs.
DEFAULT_SETTINGS = {
    "config_version": 2,
    "global": {
        "stats_path": "",
        "session_gap": 30,
        "theme": "dark",
        "app_layout": {},
        "open_tabs": []
    },
    "scenarios": {},  # Will hold per-scenario view settings
    "favorites": []
}

class ConfigManager:
    def __init__(self):
        self.config_path = Path.home() / '.kovaaks_stats_viewer' / "v2_config.json"
        self.settings = self._load_settings()

    def _load_settings(self):
        """Loads settings and performs a deep merge with defaults."""
        user_data = {}
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    user_data = json.load(f)
            except:
                print("Config file corrupted, starting fresh.")
        
        # Merge User Data INTO Defaults
        # This ensures new keys in DEFAULT_SETTINGS always exist
        merged = self._deep_merge(DEFAULT_SETTINGS.copy(), user_data)
        
        # (Optional) Basic Migration Logic could go here if structures change drastically
        # e.g. if merged['config_version'] < 2: self._migrate_v1_to_v2(merged)

        return merged

    def _deep_merge(self, default, user):
        """
        Recursively merges user settings into default settings.
        1. If key exists in both and is dict, recurse.
        2. If key exists in user, use user value.
        3. If key missing in user, keep default.
        """
        for key, value in user.items():
            if key in default and isinstance(default[key], dict) and isinstance(value, dict):
                self._deep_merge(default[key], value)
            else:
                default[key] = value
        return default

    def save_settings(self):
        with open(self.config_path, 'w') as f:
            json.dump(self.settings, f, indent=2)

    def get(self, key, scenario=None, default=None):
        if scenario and scenario in self.settings["scenarios"]:
            if key in self.settings["scenarios"][scenario]:
                return self.settings["scenarios"][scenario][key]
        if key in self.settings["global"]:
            return self.settings["global"][key]
        return default

    def set_global(self, key, value):
        self.settings["global"][key] = value
        self.save_settings()

    def set_scenario(self, scenario, key, value):
        if scenario not in self.settings["scenarios"]:
            self.settings["scenarios"][scenario] = {}
        self.settings["scenarios"][scenario][key] = value
        self.save_settings()

    # --- FAVORITES ---
    def get_favorites(self):
        return self.settings.get("favorites", [])

    def add_favorite(self, scenario_name):
        favs = self.get_favorites()
        if scenario_name not in favs:
            favs.append(scenario_name)
            self.settings["favorites"] = favs
            self.save_settings()

    def remove_favorite(self, scenario_name):
        favs = self.get_favorites()
        if scenario_name in favs:
            favs.remove(scenario_name)
            self.settings["favorites"] = favs
            self.save_settings()
            
    def is_favorite(self, scenario_name):
        return scenario_name in self.get_favorites()