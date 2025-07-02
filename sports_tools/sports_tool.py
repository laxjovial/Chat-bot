# sports_tools/sports_tool.py

from langchain_core.tools import tool
from typing import Optional, List, Dict, Any
from pathlib import Path

# Import generic tools
from shared_tools.query_uploaded_docs_tool import QueryUploadedDocs
from shared_tools.scraper_tool import scrape_web
from shared_tools.doc_summarizer import summarize_document
from shared_tools.import_utils import process_upload, clear_indexed_data
from shared_tools.export_utils import export_response, export_vector_results # To be used internally by other tools, or for direct exports

# Constants for the sports section
SPORTS_SECTION = "sports"
DEFAULT_USER_TOKEN = "default" # Or use a proper user management if available

@tool
def sports_search_web(query: str, user_token: str = DEFAULT_USER_TOKEN, max_chars: int = 1500) -> str:
    """
    Searches the web for sports-related information using a smart search fallback mechanism.
    
    Args:
        query (str): The sports-related search query.
        user_token (str): The unique identifier for the user. Defaults to "default".
        max_chars (int): Maximum characters for the returned snippet. Defaults to 1500.
    
    Returns:
        str: A string containing relevant information from the web.
    """
    # This tool directly wraps the generic scrape_web tool
    return scrape_web(query=query, user_token=user_token, max_chars=max_chars)

@tool
def sports_query_uploaded_docs(query: str, user_token: str = DEFAULT_USER_TOKEN, export: Optional[bool] = False, k: int = 5) -> str:
    """
    Queries previously uploaded and indexed sports documents for a user using vector similarity search.
    
    Args:
        query (str): The search query to find relevant sports documents.
        user_token (str): The unique identifier for the user. Defaults to "default".
        export (bool): If True, the results will be saved to a file in markdown format. Defaults to False.
        k (int): The number of top relevant documents to retrieve. Defaults to 5.
    
    Returns:
        str: A string containing the combined content of the relevant document chunks,
             or a message indicating no data/results found, or the export path.
    """
    # This tool directly wraps the generic QueryUploadedDocs tool, fixing the section to "sports"
    return QueryUploadedDocs(query=query, user_token=user_token, section=SPORTS_SECTION, export=export, k=k)

@tool
def sports_summarize_document_by_path(file_path_str: str) -> str:
    """
    Summarizes a document related to sports located at the given file path.
    The file path should be accessible by the system (e.g., in the 'uploads' directory).
    
    Args:
        file_path_str (str): The full path to the document file to be summarized.
    
    Returns:
        str: A concise summary of the document content.
    """
    file_path = Path(file_path_str)
    if not file_path.exists():
        return f"Error: Document not found at '{file_path_str}'."
    
    # This tool directly wraps the generic summarize_document tool
    try:
        summary = summarize_document(file_path)
        return f"Summary of '{file_path.name}':\n{summary}"
    except ValueError as e:
        return f"Error summarizing document: {e}"
    except Exception as e:
        return f"An unexpected error occurred during summarization: {e}"

# Note: process_upload and clear_indexed_data are not exposed as direct tools
# in a conversational agent, but rather used by backend Streamlit apps.
# If an agent *needed* to directly trigger uploads/clears, they could be wrapped too.

# CLI Test (optional)
if __name__ == "__main__":
    import streamlit as st
    import logging
    import shutil
    import json
    from shared_tools.vector_utils import build_vectorstore, load_docs_from_json_file, BASE_VECTOR_DIR
    from shared_tools.llm_embedding_utils import SUPPORTED_DOC_EXTS

    logging.basicConfig(level=logging.INFO)

    # Mock Streamlit secrets and config for local testing if needed
    class MockSecrets:
        def __init__(self):
            self.openai = {"api_key": "sk-mock-openai-key-12345"} # Replace with a real key
            self.google = {"api_key": "AIzaSy-mock-google-key"} # Replace with a real key
            self.ollama = {"api_url": "http://localhost:11434", "model": "llama3"}
            self.serpapi = {"api_key": "YOUR_SERPAPI_KEY"} # For scrape_web testing
            self.google_custom_search = {"api_key": "YOUR_GOOGLE_CUSTOM_SEARCH_API_KEY"} # For scrape_web testing

    try:
        from config.config_manager import ConfigManager
        # Create dummy config.yml
        dummy_data_dir = Path("data")
        dummy_data_dir.mkdir(exist_ok=True)
        with open(dummy_data_dir / "config.yml", "w") as f:
            f.write("""
llm:
  provider: openai
  model: gpt-3.5-turbo
  temperature: 0.5
rag:
  chunk_size: 500
  chunk_overlap: 50
web_scraping:
  user_agent: Mozilla/5.0 (Test; Python)
  timeout_seconds: 5
""")
        # Create dummy API YAMLs for scraper_tool
        with open(dummy_data_dir / "sports_apis.yaml", "w") as f:
            f.write("""
search_apis:
  - name: "SerpAPI"
    type: "search"
    endpoint: "https://serpapi.com/search"
    key_name: "api_key"
    key_value: "load_from_secrets.serpapi_api_key"
    query_param: "q"
    default_params:
      engine: "google"
      num: 3
            """)
        with open(dummy_data_dir / "media_apis.yaml", "w") as f:
            f.write("""
search_apis:
  - name: "GoogleCustomSearch"
    type: "search"
    endpoint: "https://www.googleapis.com/customsearch/v1"
    key_name: "key"
    key_value: "load_from_secrets.google_custom_search_api_key"
    query_param: "q"
    default_params:
      cx: "YOUR_CUSTOM_SEARCH_ENGINE_ID"
      num: 3
            """)

        if not hasattr(st, 'secrets'):
            st.secrets = MockSecrets()
            print("Mocked st.secrets for standalone testing.")
        
        global config_manager
        config_manager = ConfigManager()
        print("ConfigManager initialized for testing.")

    except Exception as e:
        print(f"Could not initialize ConfigManager for testing: {e}. Skipping API/LLM-dependent tests.")
        config_manager = None

    print("\nTesting sports_tool functions:")
    test_user = "test_user_sports"
    
    if config_manager:
        # Test sports_search_web
        print("\n--- Testing sports_search_web ---")
        search_query = "latest football transfer news"
        search_result = sports_search_web(search_query, user_token=test_user)
        print(f"Search Result for '{search_query}':\n{search_result[:500]}...")

        # Prepare dummy data for sports_query_uploaded_docs
        print("\n--- Preparing dummy data for sports_query_uploaded_docs ---")
        dummy_json_path = Path("temp_sports_docs.json")
        dummy_data = [
            {"id": 1, "text": "Lionel Messi won the Ballon d'Or for a record eighth time in 2023.", "sport": "soccer"},
            {"id": 2, "text": "The Los Angeles Lakers are a professional basketball team based in Los Angeles.", "sport": "basketball"},
            {"id": 3, "text": "Novak Djokovic holds the record for most Grand Slam men's singles titles.", "sport": "tennis"}
        ]
        with open(dummy_json_path, "w", encoding="utf-8") as f:
            json.dump(dummy_data, f)
        
        loaded_docs = load_docs_from_json_file(dummy_json_path)
        for doc, record in zip(loaded_docs, dummy_data):
            doc.page_content = record["text"]

        build_vectorstore(test_user, SPORTS_SECTION, loaded_docs, chunk_size=200, chunk_overlap=0)
        print(f"Vectorstore built for {SPORTS_SECTION}.")

        # Test sports_query_uploaded_docs
        print("\n--- Testing sports_query_uploaded_docs ---")
        doc_query = "Who won the Ballon d'Or recently?"
        doc_results = sports_query_uploaded_docs(doc_query, user_token=test_user)
        print(f"Query uploaded docs for '{doc_query}':\n{doc_results}")

        doc_query_export = "Tell me about famous tennis players."
        doc_results_export = sports_query_uploaded_docs(doc_query_export, user_token=test_user, export=True)
        print(f"Query uploaded docs with export for '{doc_query_export}':\n{doc_results_export}")
        
        # Test sports_summarize_document_by_path
        print("\n--- Testing sports_summarize_document_by_path ---")
        # Create a dummy upload directory and file
        test_upload_dir = Path("uploads") / test_user / SPORTS_SECTION
        test_upload_dir.mkdir(parents=True, exist_ok=True)
        summarize_file_path = test_upload_dir / "sports_article.txt"
        with open(summarize_file_path, "w") as f:
            f.write("This article discusses the rise of sports analytics in modern professional teams. " * 30 + 
                    "Data science is being used to optimize player performance, strategize game plans, and even predict injuries. " * 20 +
                    "Many teams are investing heavily in technologies that track player movements and physiological data. " * 25)
        print(f"Created dummy file for summarization: {summarize_file_path}")

        summary_result = sports_summarize_document_by_path(str(summarize_file_path))
        print(summary_result)

    else:
        print("Skipping sports_tool tests due to ConfigManager issues or missing API keys.")

    # Clean up dummy files and directories
    if Path("exports") / test_user:
        shutil.rmtree(Path("exports") / test_user, ignore_errors=True)
    if Path("uploads") / test_user:
        shutil.rmtree(Path("uploads") / test_user, ignore_errors=True)
    if BASE_VECTOR_DIR / test_user:
        shutil.rmtree(BASE_VECTOR_DIR / test_user, ignore_errors=True)
    if dummy_json_path.exists():
        dummy_json_path.unlink()
    
    dummy_data_dir = Path("data")
    if dummy_data_dir.exists():
        # Remove only if contents are dummy files created by this script
        if (dummy_data_dir / "config.yml").exists():
            os.remove(dummy_data_dir / "config.yml")
        if (dummy_data_dir / "sports_apis.yaml").exists():
            os.remove(dummy_data_dir / "sports_apis.yaml")
        if (dummy_data_dir / "media_apis.yaml").exists():
            os.remove(dummy_data_dir / "media_apis.yaml")
        if not os.listdir(dummy_data_dir):
            os.rmdir(dummy_data_dir)
