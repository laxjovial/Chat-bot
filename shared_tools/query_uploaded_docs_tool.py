# shared_tools/query_uploaded_docs_tool.py

from typing import Optional
from langchain_core.documents import Document
from langchain_core.tools import tool
from pathlib import Path

# Import from the new shared utilities
from shared_tools.vector_utils import query_vectorstore, BASE_VECTOR_DIR # Import BASE_VECTOR_DIR for path checking
from shared_tools.export_utils import export_vector_results # Use the shared export tool

@tool
def QueryUploadedDocs(
    query: str, 
    user_token: str = "default", 
    section: str = "general", # Make section generic
    export: Optional[bool] = False,
    k: int = 5 # Add k as a parameter for top_k_results
) -> str:
    """
    Queries uploaded and indexed documents for a user and specific section using vector similarity search.
    Returns text chunks from relevant documents or saves results if export is enabled.
    
    Args:
        query (str): The search query to find relevant documents.
        user_token (str): The unique identifier for the user. Defaults to "default".
        section (str): The specific section (e.g., "sports", "media", "finance", "general")
                       where the documents are indexed. Defaults to "general".
        export (bool): If True, the results will be saved to a file in markdown format.
                       Defaults to False.
        k (int): The number of top relevant documents to retrieve. Defaults to 5.
    
    Returns:
        str: A string containing the combined content of the relevant document chunks,
             or a message indicating no data/results found, or the export path.
    """
    vector_path = BASE_VECTOR_DIR / user_token / section
    if not vector_path.exists():
        return f"No indexed data found for section '{section}'. Please upload relevant documents first."

    # Use the generic query_vectorstore from shared_tools
    results: list[Document] = query_vectorstore(query, user_token, section, k=k)

    if not results:
        return f"No matching results found in uploaded content for section '{section}'."

    combined = "\n\n---\n\n".join([r.page_content.strip() for r in results])

    if export:
        # Use the generic export_vector_results from shared_tools
        export_path = export_vector_results(results, query, section, user_token)
        return f"Results exported to: {export_path}\n\n{combined[:500]}..." # Show a snippet even when exported
    
    # Otherwise, return the combined content
    return combined

# CLI Test (optional)
if __name__ == "__main__":
    import os
    import json
    import shutil
    import streamlit as st
    import logging
    from shared_tools.vector_utils import build_vectorstore, load_docs_from_json_file
    
    logging.basicConfig(level=logging.INFO)

    # Mock Streamlit secrets for local testing if needed
    class MockSecrets:
        def __init__(self):
            self.openai = {"api_key": "sk-mock-openai-key-12345"} # Use a real key for actual testing

    # Mock the global config_manager instance if it's not already initialized
    try:
        from config.config_manager import ConfigManager
        if not hasattr(ConfigManager, '_instance') or ConfigManager._instance is None:
            # Create a dummy config.yml for the ConfigManager to load
            dummy_data_dir = Path("data")
            dummy_data_dir.mkdir(exist_ok=True)
            with open(dummy_data_dir / "config.yml", "w") as f:
                f.write("rag:\n  embedding_mode: openai\n  embedding_model: text-embedding-ada-002\n")
            
            # Initialize config_manager with mocked secrets
            if not hasattr(st, 'secrets'):
                st.secrets = MockSecrets()
                print("Mocked st.secrets for standalone testing.")
            
            # Ensure config_manager is a fresh instance for this test run
            config_manager = ConfigManager()
            print("ConfigManager initialized for testing.")

    except Exception as e:
        print(f"Could not initialize ConfigManager for testing: {e}. Skipping LLM-dependent tests.")
        config_manager = None # Set to None to skip tests

    
    print("\nTesting QueryUploadedDocs tool:")
    test_user = "test_user_qdocs"
    test_section = "test_docs"
    test_vector_dir = BASE_VECTOR_DIR / test_user / test_section
    
    if config_manager:
        # 1. Prepare dummy data and build a vectorstore
        dummy_json_path = Path("temp_qdocs_data.json")
        dummy_data = [
            {"id": 1, "text": "The latest sports news features soccer, basketball, and tennis."},
            {"id": 2, "text": "Financial markets saw a dip in tech stocks today."},
            {"id": 3, "text": "Recent media releases include a new sci-fi movie and a popular TV series."},
            {"id": 4, "text": "The fastest land animal is the cheetah, capable of speeds up to 120 km/h."},
            {"id": 5, "text": "Paris is the capital of France and a major European city."}
        ]
        with open(dummy_json_path, "w", encoding="utf-8") as f:
            json.dump(dummy_data, f)
        
        loaded_docs = load_docs_from_json_file(dummy_json_path)
        # Manually set page_content from 'text' for these dummy docs for better search
        for doc, record in zip(loaded_docs, dummy_data):
            doc.page_content = record["text"]

        print(f"Building vectorstore for '{test_section}'...")
        build_vectorstore(test_user, test_section, loaded_docs, chunk_size=200, chunk_overlap=0)
        print("Vectorstore built.")

        # 2. Test queries
        print("\n--- Test 1: Simple query ---")
        query1 = "What is the capital of France?"
        result1 = QueryUploadedDocs(query1, user_token=test_user, section=test_section)
        print(f"Query: {query1}\nResult:\n{result1}")

        print("\n--- Test 2: Sports query ---")
        query2 = "Tell me about recent sports events."
        result2 = QueryUploadedDocs(query2, user_token=test_user, section=test_section)
        print(f"Query: {query2}\nResult:\n{result2}")
        
        print("\n--- Test 3: Query with export ---")
        query3 = "What happened in the financial markets?"
        result3 = QueryUploadedDocs(query3, user_token=test_user, section=test_section, export=True)
        print(f"Query: {query3}\nResult:\n{result3}")
        
        print("\n--- Test 4: Query for non-existent section ---")
        query4 = "some query"
        result4 = QueryUploadedDocs(query4, user_token=test_user, section="non_existent_section")
        print(f"Query: {query4}\nResult:\n{result4}")

    else:
        print("Skipping QueryUploadedDocs tests due to ConfigManager issues or missing API keys.")

    # Clean up dummy files and directories
    if dummy_json_path.exists():
        dummy_json_path.unlink()
    if test_vector_dir.exists():
        shutil.rmtree(test_vector_dir)
    if (Path("exports") / test_user).exists():
        shutil.rmtree(Path("exports") / test_user) # Clean up export folder
    
    dummy_data_dir = Path("data")
    if dummy_data_dir.exists():
        if (dummy_data_dir / "config.yml").exists():
            (dummy_data_dir / "config.yml").unlink()
        if not list(dummy_data_dir.iterdir()): # Check if directory is empty
            dummy_data_dir.rmdir()
