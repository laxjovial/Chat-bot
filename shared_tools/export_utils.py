# shared_tools/export_utils.py

import os
import json
from datetime import datetime
from typing import Optional, List
from pathlib import Path
from langchain_core.documents import Document

# Base export directory, now generic (not tied to 'sports')
BASE_EXPORT_DIR = Path("exports") 
EXPORT_FORMATS = ["txt", "json", "md"]

# Ensure base directory exists (this will create exports/ if it doesn't)
BASE_EXPORT_DIR.mkdir(parents=True, exist_ok=True)

def export_response(
    text: str,
    section: str, # 'section' is now a required parameter
    user_token: str = "default",
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
    export_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not filename:
        filename = f"response_{timestamp}.{format}"
    else:
        # Ensure filename has the correct extension, add if missing
        filename = f"{filename}.{format}" if not filename.endswith(f".{format}") else filename

    filepath = export_dir / filename

    # Save based on format
    if format in ["txt", "md"]:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(text)

    elif format == "json":
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({"response": text}, f, indent=2)

    return str(filepath) # Return as string for wider compatibility

def export_vector_results(
    results: List[Document], 
    query: str, 
    section: str, # 'section' is now a required parameter
    user_token: str = "default",
    format: str = "md", # Default to markdown for vector results
    filename: Optional[str] = None
) -> str:
    """
    Exports a list of Document results from vector query with source chunks.
    """
    if format not in EXPORT_FORMATS:
        raise ValueError(f"Unsupported export format: {format}")

    export_dir = BASE_EXPORT_DIR / user_token / section
    export_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not filename:
        filename = f"vector_query_{timestamp}.{format}"
    else:
        filename = f"{filename}.{format}" if not filename.endswith(f".{format}") else filename

    filepath = export_dir / filename

    content_to_write = ""
    if format == "md":
        content_to_write += f"## Query: {query}\n\n"
        for i, doc in enumerate(results):
            content_to_write += f"### Result {i+1}\n"
            content_to_write += f"**Source:** {doc.metadata.get('source', 'N/A')}\n" # Add source if available
            content_to_write += f"**Page/Chunk:** {doc.metadata.get('page', 'N/A')}\n" # Add page if available
            content_to_write += doc.page_content.strip() + "\n\n---\n\n"
    elif format == "txt":
        content_to_write += f"Query: {query}\n\n"
        for i, doc in enumerate(results):
            content_to_write += f"--- Result {i+1} ---\n"
            content_to_write += f"Source: {doc.metadata.get('source', 'N/A')}\n"
            content_to_write += f"Page/Chunk: {doc.metadata.get('page', 'N/A')}\n"
            content_to_write += doc.page_content.strip() + "\n\n"
    elif format == "json":
        json_data = {
            "query": query,
            "results": [
                {"page_content": doc.page_content, "metadata": doc.metadata}
                for doc in results
            ]
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2)
        return str(filepath) # JSON is handled differently

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content_to_write)

    return str(filepath)


# CLI Test (optional)
if __name__ == "__main__":
    print("Testing export_utils.py:")
    
    # Create dummy data for testing
    test_text = "This is a test response from the AI assistant."
    test_query = "What is the capital of France?"
    test_docs = [
        Document(page_content="Paris is the capital and most populous city of France.", metadata={"source": "Wikipedia", "page": 1}),
        Document(page_content="It is located on the River Seine.", metadata={"source": "Travel Guide", "page": 5})
    ]

    user = "test_user_export"
    section_name = "general"

    # Test export_response
    print("\nTesting export_response (TXT):")
    txt_path = export_response(test_text, section=section_name, user_token=user, format="txt", filename="test_response")
    print(f"Exported TXT to: {txt_path}")
    print(f"Content: {Path(txt_path).read_text()}")

    print("\nTesting export_response (JSON):")
    json_path = export_response(test_text, section=section_name, user_token=user, format="json")
    print(f"Exported JSON to: {json_path}")
    print(f"Content: {Path(json_path).read_text()}")

    # Test export_vector_results
    print("\nTesting export_vector_results (MD):")
    vector_md_path = export_vector_results(test_docs, test_query, section=section_name, user_token=user, format="md")
    print(f"Exported Vector MD to: {vector_md_path}")
    print(f"Content: {Path(vector_md_path).read_text()}")

    print("\nTesting export_vector_results (JSON):")
    vector_json_path = export_vector_results(test_docs, test_query, section=section_name, user_token=user, format="json")
    print(f"Exported Vector JSON to: {vector_json_path}")
    print(f"Content: {Path(vector_json_path).read_text()}")

    # Clean up test files and directories
    try:
        shutil.rmtree(BASE_EXPORT_DIR / user)
        print(f"\nCleaned up test directory: {BASE_EXPORT_DIR / user}")
    except OSError as e:
        print(f"Error during cleanup: {e}")
