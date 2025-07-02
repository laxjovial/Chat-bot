# shared_tools/vector_utils.py

import json
from typing import List, Optional
from pathlib import Path

from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

# Import from the new shared utility file
from shared_tools.llm_embedding_utils import get_embedder

from config.config_manager import config_manager # Use the new ConfigManager instance

# === Base Paths (will be specified per section when used) ===
# Example: BASE_VECTOR_DIR / user_token / section_name
BASE_VECTOR_DIR = Path("chroma")

# === Load & Embed Data from JSON file ===
def load_docs_from_json_file(json_file_path: Path) -> List[Document]:
    """
    Loads data from a JSON file into LangChain Documents.
    Each item in the JSON array should ideally be a dictionary.
    """
    if not json_file_path.exists():
        return []
    
    with open(json_file_path, "r", encoding="utf-8") as f:
        records = json.load(f)
    
    # Convert each record into a Document.
    # The entire JSON object for each record is stringified into page_content.
    # Metadata can be extracted if the structure is known.
    documents = []
    for record in records:
        # Assuming record is a dict, we can put relevant fields into metadata
        # and the main content into page_content. Adjust this logic
        # based on the actual structure of your JSON data (e.g., offline_sports.json)
        
        # Simple approach: put the whole record as string into page_content
        # You might want to pick specific fields for page_content for better RAG.
        page_content = json.dumps(record, ensure_ascii=False)
        metadata = {"source_file": str(json_file_path)} # Add source file to metadata

        # If records have a 'title' or 'name' field, you could add it to metadata
        if isinstance(record, dict):
            if 'title' in record:
                metadata['title'] = record['title']
            if 'name' in record:
                metadata['name'] = record['name']
            # If you know the main text field, use that as page_content
            # E.g., if your JSON has {"article_text": "...", "date": "..."}
            # then page_content = record.get("article_text", page_content)
        
        documents.append(Document(page_content=page_content, metadata=metadata))
        
    return documents


def build_vectorstore(
    user_token: str, 
    section: str, 
    documents: List[Document], 
    chunk_size: int = 1000, 
    chunk_overlap: int = 150
) -> str:
    """
    Builds and saves the Chroma vector DB for a specific user and section.
    Takes a list of pre-loaded documents.
    """
    if not documents:
        return f"No documents provided to build vectorstore for {section}."

    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = splitter.split_documents(documents)

    vector_dir = BASE_VECTOR_DIR / user_token / section
    vector_dir.mkdir(parents=True, exist_ok=True) # Ensure directory exists

    embedder = get_embedder()
    
    # Initialize Chroma DB. If directory exists, it loads; otherwise, it creates.
    vectordb = Chroma.from_documents(
        chunks, 
        embedder, 
        persist_directory=str(vector_dir)
    )
    vectordb.persist() # Ensure changes are saved to disk
    
    return f"Vectorstore built/updated at: {vector_dir}"

def query_vectorstore(query: str, user_token: str, section: str, k: int = 5) -> List[Document]:
    """
    Search the vector DB for semantic matches for a given user and section.
    Returns a list of LangChain Document objects.
    """
    vector_dir = BASE_VECTOR_DIR / user_token / section
    if not vector_dir.exists():
        # print(f"Vector directory not found: {vector_dir}") # For debugging
        return []

    embedder = get_embedder()
    
    # Load the existing Chroma DB
    vectordb = Chroma(persist_directory=str(vector_dir), embedding_function=embedder)
    
    results = vectordb.similarity_search(query, k=k)
    return results


# CLI Test (optional, for direct testing outside Streamlit)
if __name__ == "__main__":
    import streamlit as st
    import shutil
    import logging
    
    logging.basicConfig(level=logging.INFO)

    # Mock Streamlit secrets for local testing if needed
    class MockSecrets:
        def __init__(self):
            self.openai = {"api_key": "sk-mock-openai-key-12345"} # Use a real key for actual testing

    # Mock the global config_manager instance if it's not already initialized
    try:
        from config.config_manager import ConfigManager
        # Also need a dummy config.yml for embedding mode/model
        dummy_data_dir = Path("data")
        dummy_data_dir.mkdir(exist_ok=True)
        with open(dummy_data_dir / "config.yml", "w") as f:
            f.write("rag:\n  embedding_mode: openai\n  embedding_model: text-embedding-ada-002\n")

        # Mock st.secrets if not already set
        if not hasattr(st, 'secrets'):
            st.secrets = MockSecrets()
            print("Mocked st.secrets for standalone testing.")
        
        # Ensure config_manager is a fresh instance for this test run
        global config_manager # Declare global to assign
        config_manager = ConfigManager()
        print("ConfigManager initialized for testing.")

    except Exception as e:
        print(f"Could not initialize ConfigManager for testing: {e}. Skipping LLM-dependent tests.")
        config_manager = None # Set to None to skip tests


    print("\nTesting vector_utils.py:")
    test_user = "test_user_vec"
    test_section = "test_section_vec"
    test_vector_dir = BASE_VECTOR_DIR / test_user / test_section

    if config_manager:
        # 1. Create a dummy JSON file
        dummy_json_path = Path("temp_dummy_data.json")
        dummy_data = [
            {"id": 1, "content": "The quick brown fox jumps over the lazy dog.", "category": "animals"},
            {"id": 2, "content": "Artificial intelligence is rapidly advancing.", "category": "technology"},
            {"id": 3, "content": "The capital of France is Paris.", "category": "geography"}
        ]
        with open(dummy_json_path, "w", encoding="utf-8") as f:
            json.dump(dummy_data)
        print(f"Created dummy JSON file: {dummy_json_path}")

        # 2. Load documents from the dummy JSON
        loaded_docs = load_docs_from_json_file(dummy_json_path)
        print(f"Loaded {len(loaded_docs)} documents from JSON.")

        # 3. Build vectorstore
        print(f"Building vectorstore at: {test_vector_dir}")
        build_msg = build_vectorstore(test_user, test_section, loaded_docs)
        print(build_msg)
        print(f"Vectorstore directory exists: {test_vector_dir.exists()}")

        # 4. Query vectorstore
        query = "What is the fastest animal?"
        print(f"\nQuerying vectorstore for: '{query}'")
        results = query_vectorstore(query, test_user, test_section, k=2)

        if results:
            print(f"Found {len(results)} results:")
            for i, doc in enumerate(results):
                print(f"--- Result {i+1} ---")
                print(f"Content: {doc.page_content[:100]}...")
                print(f"Metadata: {doc.metadata}")
        else:
            print("No results found.")

        # 5. Test clearing (from import_utils or a separate clear_vectorstore function)
        # For this test, we'll manually remove the directory
        if test_vector_dir.exists():
            shutil.rmtree(test_vector_dir)
            print(f"\nCleaned up test vector directory: {test_vector_dir}")

    else:
        print("Skipping vector_utils tests due to ConfigManager issues or missing API keys.")

    # Clean up dummy files
    if dummy_json_path.exists():
        dummy_json_path.unlink()
    
    dummy_data_dir = Path("data")
    if dummy_data_dir.exists():
        if (dummy_data_dir / "config.yml").exists():
            (dummy_data_dir / "config.yml").unlink()
        if not list(dummy_data_dir.iterdir()): # Check if directory is empty
            dummy_data_dir.rmdir()
