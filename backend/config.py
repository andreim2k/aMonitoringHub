import json
import os

CONFIG_FILE = 'config.json'

DEFAULT_CONFIG = {
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

def load_config():
    """Load configuration from file or create default"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                # Merge with defaults for any missing keys
                for key in DEFAULT_CONFIG:
                    if key not in config:
                        config[key] = DEFAULT_CONFIG[key]
                return config
        except (json.JSONDecodeError, IOError):
            print("Warning: Could not load config file, using defaults")
    
    # Create default config file
    save_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG.copy()

def save_config(config):
    """Save configuration to file"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except IOError:
        print("Error: Could not save config file")
        return False

def get_config():
    """Get current configuration"""
    return load_config()

def update_config(updates):
    """Update configuration with new values"""
    config = load_config()
    config.update(updates)
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
