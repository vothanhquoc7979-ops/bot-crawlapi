import json
import os

CONFIG_FILE = "config.json"

def get_config():
    # Mặc định lấy từ môi trường
    config = {
        "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN", ""),
        "GITHUB_REPO": os.getenv("GITHUB_REPO", ""),
        "TELEGRAM_TOKEN": os.getenv("TELEGRAM_TOKEN", "")
    }
    # Ghi đè bằng file nếu có
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                for k, v in saved.items():
                    if v: config[k] = v
        except Exception:
            pass
    return config

def save_config(new_config_data):
    current = get_config()
    for k, v in new_config_data.items():
        if v is not None:
             current[k] = v
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=4)
