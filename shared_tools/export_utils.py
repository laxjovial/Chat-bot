# shared_tools/export_utils.py

import os
import json
from datetime import datetime
from typing import Optional, List
from pathlib import Path
from langchain_core.documents import Document

# Base directory for all exports, now generic
BASE_EXPORT_DIR = Path("exports") # Changed from "sports/exports"

# Ensure base directory exists
os.makedirs(BASE_EXPORT_DIR, exist_ok=True)

EXPORT_FORMATS = ["txt", "json", "md"]

def export_response(
    text: str,
    user_token: str = "default",
    section: str = "general", # Generic section, e.g., "sports", "media"
    format: str = "txt",
    filename: Optional[str] = None
) -> str:
    """
    Saves assistant response for the user and section.
    Returns the full file path of the export.
    """
    if format not in EXPORT_FORMATS:
        raise ValueError(f"Unsupported export format: {format}")

    # Exports go into exports/{user_token}/{section}/
    export_dir = BASE_EXPORT_DIR / user_token / section
    os.makedirs(export_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not filename:
        filename = f"response_{timestamp}.{format}"
    else:
        # Ensure filename has the correct extension
        filename = f"{filename}.{format}" if not filename.endswith(f".{format}") else filename

    filepath = export_dir / filename

    # Save based on format
    if format in ["txt", "md"]:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(text)

    elif format == "json":
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({"response": text}, f, indent=2)

    return str(filepath)

def export_vector_results(
    results: List[Document],
    query: str,
    user_token: str = "default",
    section: str = "general" # Generic section
) -> str:
    """
    Exports a list of Document results from vector query with source chunks.
    """
    export_dir = BASE_EXPORT_DIR / user_token / section
    os.makedirs(export_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"vector_query_{timestamp}.md"
    filepath = export_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"## Vector Query Results: '{query}'\\n\\n")
        f.write(f"### Section: {section.capitalize()}\\n\\n")
        for i, doc in enumerate(results):
            f.write(f"--- Result {i+1} ---\\n")
            f.write(doc.page_content.strip())
            if doc.metadata:
                f.write("\\n**Metadata:** ")
                f.write(json.dumps(doc.metadata))
            f.write("\\n\\n")
    return str(filepath)

# CLI Test (optional, for direct testing outside Streamlit)
if __name__ == "__main__":
    test_user = "test_user_export"
    test_section = "test_section"
    
    print("Testing export_response:")
    export_path = export_response(
        text="This is a test response.",
        user_token=test_user,
        section=test_section,
        format="txt",
        filename="test_response"
    )
    print(f"Response exported to: {export_path}")

    print("\nTesting export_vector_results:")
    sample_docs = [
        Document(page_content="This is the first chunk of a document.", metadata={"source": "doc1.pdf"}),
        Document(page_content="This is the second chunk, containing more info.", metadata={"source": "doc2.txt", "page": 1})
    ]
    vector_export_path = export_vector_results(
        results=sample_docs,
        query="test query for vector data",
        user_token=test_user,
        section=test_section
    )
    print(f"Vector results exported to: {vector_export_path}")

    # Clean up test files (optional)
    # import shutil
    # shutil.rmtree(BASE_EXPORT_DIR / test_user)
