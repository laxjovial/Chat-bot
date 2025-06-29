# media/tools/export_utils.py

import os
import json
from datetime import datetime
from typing import Optional

EXPORT_FORMATS = ["txt", "json", "md"]
BASE_EXPORT_DIR = "media/exports"

# Ensure base directory exists
os.makedirs(BASE_EXPORT_DIR, exist_ok=True)


def export_response(
    text: str,
    section: str = "media",
    user_token: str = "default",
    format: str = "txt",
    filename: Optional[str] = None
) -> str:
    """
    Saves assistant response or vector result for the user and section.
    Returns the full file path of the export.
    """
    if format not in EXPORT_FORMATS:
        raise ValueError(f"Unsupported export format: {format}")

    export_dir = os.path.join(BASE_EXPORT_DIR, user_token, section)
    os.makedirs(export_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not filename:
        filename = f"response_{timestamp}.{format}"
    else:
        filename = f"{filename}.{format}" if not filename.endswith(f".{format}") else filename

    filepath = os.path.join(export_dir, filename)

    # Save based on format
    if format in ["txt", "md"]:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(text)

    elif format == "json":
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({"response": text}, f, indent=2)

    return filepath


def export_vector_results(results: list, query: str, section: str = "media", user_token: str = "default") -> str:
    """
    Exports a list of Document results from vector query with source chunks.
    """
    export_dir = os.path.join(BASE_EXPORT_DIR, user_token, section)
    os.makedirs(export_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"vector_query_{timestamp}.md"
    filepath = os.path.join(export_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"## Query: {query}\n\n")
        for i, doc in enumerate(results):
            f.write(f"### Result {i+1}\n")
            f.write(doc.page_content.strip())
            f.write("\n\n")

    return filepath


# Optional test
if __name__ == "__main__":
    dummy = "Christopher Nolan directed Oppenheimer."
    print(export_response(dummy, section="media", user_token="usr_xyz", format="txt"))
