# shared_tools/import_utils.py

import os
import shutil
import uuid
from typing import List
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma

# Import from the new shared utility file
from shared_tools.llm_embedding_utils import get_embedder, load_document_file, SUPPORTED_DOC_EXTS

from config.config_manager import config_manager # Use the new ConfigManager instance
from utils.user_manager import get_user_token # Assuming this is in your utils folder

# === Base Upload & Chroma Paths ===
# These paths are now generic and will use the section name
BASE_UPLOAD_DIR = Path("uploads") # Changed from "sports/uploads"
BASE_VECTOR_DIR = Path("chroma") # Changed from "sports/chroma"


# === Upload and Vectorize ===
def process_upload(file, user_token: str, section: str) -> str:
    """
    Saves and vectorizes uploaded file for user/section.
    `section` parameter makes it generic (e.g., "sports", "media", "finance").
    """
    # 1. Save file
    # Files go into uploads/{user_token}/{section}/
    upload_dir = BASE_UPLOAD_DIR / user_token / section
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_ext = Path(file.name).suffix
    if file_ext.lower() not in SUPPORTED_DOC_EXTS:
        raise ValueError(f"Unsupported file type: {file_ext}. Supported types are: {', '.join(SUPPORTED_DOC_EXTS)}")

    file_id = str(uuid.uuid4())
    saved_path = upload_dir / f"{file_id}{file_ext}"
    with open(saved_path, "wb") as f:
        f.write(file.read())

    # 2. Load + chunk
    docs = load_document_file(saved_path)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config_manager.get('rag.chunk_size', 1000), 
        chunk_overlap=config_manager.get('rag.chunk_overlap', 150)
    )
    chunks = splitter.split_documents(docs)

    # 3. Vectorize
    # Vectors go into chroma/{user_token}/{section}/
    vector_dir = BASE_VECTOR_DIR / user_token / section
    embedder = get_embedder() # Embedder is now generic, no user_token needed here
    
    # Initialize Chroma DB
    # If the directory exists, it will load the existing collection.
    # Otherwise, it will create a new one.
    vectordb = Chroma.from_documents(
        chunks, 
        embedder, 
        persist_directory=str(vector_dir)
    )
    vectordb.persist() # Ensure changes are saved to disk

    return f"Successfully processed '{file.name}' for {section} and added to memory."

def clear_indexed_data(user_token: str, section: str) -> str:
    """
    Clears all uploaded files and indexed vector data for a given user and section.
    """
    upload_path = BASE_UPLOAD_DIR / user_token / section
    vector_path = BASE_VECTOR_DIR / user_token / section

    messages = []
    if upload_path.exists() and upload_path.is_dir():
        shutil.rmtree(upload_path)
        messages.append(f"Cleared uploaded files for {section}.")
    else:
        messages.append(f"No uploaded files found for {section}.")

    if vector_path.exists() and vector_path.is_dir():
        # Chroma needs to be explicitly deleted, or its internal files removed
        # Simplest way is to remove the directory as we persist on creation
        shutil.rmtree(vector_path)
        messages.append(f"Cleared indexed data for {section}.")
    else:
        messages.append(f"No indexed data found for {section}.")
    
    if not messages:
        return "No data to clear for this user and section."

    return " ".join(messages)

# CLI Test (optional, for direct testing outside Streamlit)
if __name__ == "__main__":
    import streamlit as st
    import logging
    import os
    
    logging.basicConfig(level=logging.INFO)

    # Mock Streamlit secrets for local testing if needed
    class MockSecrets:
        def __init__(self):
            self.openai = {"api_key": "sk-mock-openai-key-12345"} # Replace with a real key for live testing
            self.rag = {"embedding_mode": "openai", "embedding_model": "text-embedding-ada-002"}

    if not hasattr(st, 'secrets'):
        st.secrets = MockSecrets()
        print("Mocked st.secrets for standalone testing.")
    
    # Create dummy config.yml for testing embedder
    dummy_config_dir = Path("data")
    dummy_config_dir.mkdir(exist_ok=True)
    dummy_config_path = dummy_config_dir / "config.yml"
    with open(dummy_config_path, "w") as f:
        f.write("rag:\n  embedding_mode: openai\n  embedding_model: text-embedding-ada-002\n  chunk_size: 500\n  chunk_overlap: 50\n")
    
    # Create dummy text file for upload
    dummy_upload_dir = Path("temp_test_data/uploads/test_user/test_section")
    dummy_upload_dir.mkdir(parents=True, exist_ok=True)
    dummy_file_path = dummy_upload_dir / "test_document.txt"
    with open(dummy_file_path, "w") as f:
        f.write("This is a test document for the import utility. It has some sample text to be processed and vectorized.")
    
    # Simulate an uploaded file object
    class MockUploadedFile:
        def __init__(self, path: Path):
            self.name = path.name
            self._path = path
        def read(self):
            with open(self._path, "rb") as f:
                return f.read()

    print("\nTesting process_upload:")
    try:
        # We need to explicitly create the ConfigManager instance if running standalone
        from config.config_manager import ConfigManager
        # Reset the singleton instance to ensure it reloads with mock data
        ConfigManager._instance = None
        ConfigManager._is_loaded = False
        config_manager = ConfigManager()
        print("ConfigManager initialized for testing.")

        mock_file = MockUploadedFile(dummy_file_path)
        result_msg = process_upload(mock_file, user_token="test_user", section="test_section")
        print(result_msg)

        # Verify if Chroma DB was created
        vector_check_path = BASE_VECTOR_DIR / "test_user" / "test_section"
        print(f"Chroma DB directory exists: {vector_check_path.exists()}")
        
        print("\nTesting clear_indexed_data:")
        clear_msg = clear_indexed_data(user_token="test_user", section="test_section")
        print(clear_msg)
        print(f"Chroma DB directory exists after clear: {vector_check_path.exists()}")

    except Exception as e:
        print(f"Test failed: {e}")
    finally:
        # Clean up dummy files and directories
        if Path("temp_test_data").exists():
            shutil.rmtree("temp_test_data")
        if dummy_config_dir.exists():
            if dummy_config_path.exists():
                dummy_config_path.unlink()
            if not list(dummy_config_dir.iterdir()):
                dummy_config_dir.rmdir()
        if BASE_UPLOAD_DIR.exists() and (BASE_UPLOAD_DIR / "test_user").exists():
            shutil.rmtree(BASE_UPLOAD_DIR / "test_user")
        if BASE_VECTOR_DIR.exists() and (BASE_VECTOR_DIR / "test_user").exists():
            shutil.rmtree(BASE_VECTOR_DIR / "test_user")
