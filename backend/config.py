import json
import os
from typing import Dict, Any

CONFIG_FILE = 'config.json'

DEFAULT_CONFIG: Dict[str, Any] = {
    "webcam": {
        "url": "http://192.168.50.3/capture?size=VGA&flash=1",
        "enabled": True,
        "title": "📹 Cabana 1 Electricity Meter"
    },
    "usb": {
        "port": None,
        "baudrate": 115200
    }
}

def load_config() -> Dict[str, Any]:
    """Loads the application configuration from a JSON file.

    If the configuration file does not exist, it creates one with default values.
    If the file is corrupted, it prints a warning and returns the default
    configuration. It also merges the loaded configuration with the defaults
    to ensure all necessary keys are present.

    Returns:
        A dictionary containing the application configuration.
    """
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                # Merge with defaults for any missing keys
                for key in DEFAULT_CONFIG:
                    if key not in config:
                        config[key] = DEFAULT_CONFIG[key]
                    elif isinstance(DEFAULT_CONFIG[key], dict):
                        for sub_key in DEFAULT_CONFIG[key]:
                            if sub_key not in config[key]:
                                config[key][sub_key] = DEFAULT_CONFIG[key][sub_key]
                return config
        except (json.JSONDecodeError, IOError):
            print("Warning: Could not load config file, using defaults")
    
    # Create default config file
    save_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG.copy()

def save_config(config: Dict[str, Any]) -> bool:
    """Saves the given configuration dictionary to a JSON file.

    Args:
        config: The configuration dictionary to save.

    Returns:
        True if the configuration was saved successfully, False otherwise.
    """
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except IOError:
        print("Error: Could not save config file")
        return False

def get_config() -> Dict[str, Any]:
    """Gets the current application configuration.

    This is a convenience function that simply calls `load_config`.

    Returns:
        A dictionary containing the application configuration.
    """
    return load_config()

def update_config(updates: Dict[str, Any]) -> bool:
    """Updates the configuration file with new values.

    It loads the current configuration, applies the updates, and saves the
    modified configuration back to the file.

    Args:
        updates: A dictionary containing the configuration keys and values to
            update.

    Returns:
        True if the configuration was updated and saved successfully, False
        otherwise.
    """
    config = load_config()
    for key, value in updates.items():
        if key in config and isinstance(config[key], dict) and isinstance(value, dict):
            config[key].update(value)
        else:
            config[key] = value
    return save_config(config)

# Usage Examples:
# 
# To change webcam URL:
# curl -X POST -H "Content-Type: application/json" \
#   -d '{"webcam":{"url":"http://your-camera-ip/capture","enabled":true,"title":"📹 Your Camera"}}' \
#   http://localhost:5000/api/config
#
# To disable webcam:
# curl -X POST -H "Content-Type: application/json" \
#   -d '{"webcam":{"enabled":false}}' \
#   http://localhost:5000/api/config
