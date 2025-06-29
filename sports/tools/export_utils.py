# sports/tools/export_utils.py

import os
import json
from datetime import datetime

# === Supported export formats ===
EXPORT_FORMATS = ["txt", "json", "md"]
BASE_EXPORT_DIR = "sports/exports"

# === Ensure base directory exists ===
os.makedirs(BASE_EXPORT_DIR, exist_ok=True)


def export_response(text: str, section: str = "sports", user_id: str = "default", format: str = "txt") -> str:
    """
    Saves the assistant response in the desired format for the user and section.
    Returns the full file path of the export.
    """
    if format not in EXPORT_FORMATS:
        raise ValueError(f"Unsupported export format: {format}")

    export_dir = os.path.join(BASE_EXPORT_DIR, user_id, section)
    os.makedirs(export_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"response_{timestamp}.{format}"
    filepath = os.path.join(export_dir, filename)

    # Save content based on format
    if format == "txt" or format == "md":
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(text)

    elif format == "json":
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({"response": text}, f, indent=2)

    return filepath


# === Optional CLI test ===
if __name__ == "__main__":
    dummy = "Lionel Messi has scored over 800 career goals."
    print(export_response(dummy, section="sports", user_id="admin", format="txt"))
