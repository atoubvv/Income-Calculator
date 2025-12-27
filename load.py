import json
import os

def lastSave():
    if not os.path.exists('save.json'):
        return {
            "Balance": "0",
            "Expenses": [],
            "lastPayCheck": "0",
            "Debts": [],
            "Settings": {
                "appearance_mode": "Dark",
                "color_theme": "blue"
            }
        }
    with open('save.json', 'r') as f:
        data = json.load(f)
    # Add Settings if it doesn't exist (for backwards compatibility)
    if "Settings" not in data:
        data["Settings"] = {
            "appearance_mode": "Dark",
            "color_theme": "blue"
        }
    return data