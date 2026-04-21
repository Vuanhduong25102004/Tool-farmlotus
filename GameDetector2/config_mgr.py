import os
import json

CONFIG_FILE = "config.json"
DEFAULT_CONFIG = {
    "webhook": "", 
    "play_sound": True, 
    "sound_volume": 50
}

def load_config():
    """Hàm đọc cấu hình từ file json"""
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, "r") as f:
            c = json.load(f)
            # Tự động bù đắp nếu file json cũ bị thiếu key
            if "play_sound" not in c: c["play_sound"] = True
            if "sound_volume" not in c: c["sound_volume"] = 50
            if "webhook" not in c: c["webhook"] = ""
            return c
    except:
        return DEFAULT_CONFIG.copy()

def save_config(config_dict):
    """Hàm ghi cấu hình xuống file json"""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_dict, f, indent=4)