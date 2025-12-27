import json
import os


def save_data(gehalt, LastEGA, ausgaben, Schulden):
    # Load existing data to preserve Settings
    existing_data = {}
    if os.path.exists('save.json'):
        with open('save.json', 'r') as f:
            existing_data = json.load(f)

    my_data = {
        "Balance": gehalt,
        "Expenses": ausgaben,
        "lastPayCheck": LastEGA,
        "Debts": Schulden,
        "Settings": existing_data.get("Settings", {
            "appearance_mode": "Dark",
            "color_theme": "blue"
        })
    }

    # Preserve path if it exists
    if "path" in existing_data:
        my_data["path"] = existing_data["path"]

    # open json file
    with open('save.json', 'w') as f:
        # write into the file
        json.dump(my_data, f, indent=4)

