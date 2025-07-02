# finance_tools/finance_tool.py

from langchain_core.tools import tool
from typing import Optional, List, Dict, Any
from pathlib import Path
import logging

# Import generic tools
from shared_tools.query_uploaded_docs_tool import QueryUploadedDocs
from shared_tools.scraper_tool import scrape_web
from shared_tools.doc_summarizer import summarize_document
from shared_tools.import_utils import process_upload, clear_indexed_data # Used by Streamlit apps, not directly as agent tools
from shared_tools.export_utils import export_response, export_vector_results # To be used internally by other tools, or for direct exports
from shared_tools.vector_utils import build_vectorstore, load_docs_from_json_file, BASE_VECTOR_DIR # For testing and potential future direct use

# Import Python REPL for data analysis capabilities
from langchain_community.tools.python.tool import PythonREPLTool

# Constants for the finance section
FINANCE_SECTION = "finance"
DEFAULT_USER_TOKEN = "default" # Or use a proper user management if available

logger = logging.getLogger(__name__)

@tool
def finance_search_web(query: str, user_token: str = DEFAULT_USER_TOKEN, max_chars: int = 2000) -> str:
    """
    Searches the web for finance-related information using a smart search fallback mechanism.
    This tool wraps the generic `scrape_web` tool, providing a finance-specific interface.
    
    Args:
        query (str): The finance-related search query (e.g., "latest stock market news", "explain quantitative easing").
        user_token (str): The unique identifier for the user. Defaults to "default".
        max_chars (int): Maximum characters for the returned snippet. Defaults to 2000.
    
    Returns:
        str: A string containing relevant information from the web.
    """
    logger.info(f"Tool: finance_search_web called with query: '{query}' for user: '{user_token}'")
    return scrape_web(query=query, user_token=user_token, max_chars=max_chars)

@tool
def finance_query_uploaded_docs(query: str, user_token: str = DEFAULT_USER_TOKEN, export: Optional[bool] = False, k: int = 5) -> str:
    """
    Queries previously uploaded and indexed finance documents for a user using vector similarity search.
    This tool wraps the generic `QueryUploadedDocs` tool, fixing the section to "finance".
    
    Args:
        query (str): The search query to find relevant finance documents (e.g., "what is in the Q3 earnings report", "summary of the company's annual filing").
        user_token (str): The unique identifier for the user. Defaults to "default".
        export (bool): If True, the results will be saved to a file in markdown format. Defaults to False.
        k (int): The number of top relevant documents to retrieve. Defaults to 5.
    
    Returns:
        str: A string containing the combined content of the relevant document chunks,
             or a message indicating no data/results found, or the export path if exported.
    """
    logger.info(f"Tool: finance_query_uploaded_docs called with query: '{query}' for user: '{user_token}'")
    return QueryUploadedDocs(query=query, user_token=user_token, section=FINANCE_SECTION, export=export, k=k)

@tool
def finance_summarize_document_by_path(file_path_str: str) -> str:
    """
    Summarizes a document related to finance located at the given file path.
    The file path should be accessible by the system (e.g., in the 'uploads' directory).
    This tool wraps the generic `summarize_document` tool.
    
    Args:
        file_path_str (str): The full path to the document file to be summarized.
                              Example: "uploads/default/finance/earnings_report.pdf"
    
    Returns:
        str: A concise summary of the document content.
    """
    logger.info(f"Tool: finance_summarize_document_by_path called for file: '{file_path_str}'")
    file_path = Path(file_path_str)
    if not file_path.exists():
        logger.error(f"Document not found at '{file_path_str}' for summarization.")
        return f"Error: Document not found at '{file_path_str}'."
    
    try:
        summary = summarize_document(file_path)
        return f"Summary of '{file_path.name}':\n{summary}"
    except ValueError as e:
        logger.error(f"Error summarizing document '{file_path_str}': {e}")
        return f"Error summarizing document: {e}"
    except Exception as e:
        logger.critical(f"An unexpected error occurred during summarization of '{file_path_str}': {e}", exc_info=True)
        return f"An unexpected error occurred during summarization: {e}"

# === Advanced Finance Tools ===

# Initialize the Python REPL tool.
# This allows the agent to execute arbitrary Python code, which is powerful for data analysis.
# Be cautious with security in production environments.
python_repl = PythonREPLTool()
python_repl.name = "python_interpreter"
python_repl.description = """
Executes Python code. Use this for complex calculations, data analysis, time-series analysis,
or any task that requires programmatic logic.
Input should be a valid Python code string.
The output will be the result of the code execution (stdout/stderr).
You have access to common libraries like pandas, numpy, matplotlib, datetime, etc.
Example:
Action: python_interpreter
Action Input:
import pandas as pd
df = pd.DataFrame({'col1': [1, 2], 'col2': [3, 4]})
print(df.mean())
"""

# Placeholder for a dedicated financial data fetching tool.
# This tool would interact with APIs configured in data/finance_apis.yaml
# and return data in a structured format (e.g., JSON, or even a string that can be parsed by PythonREPLTool).
@tool
def finance_data_fetcher(
    data_type: str, 
    symbol: Optional[str] = None, 
    start_date: Optional[str] = None, 
    end_date: Optional[str] = None, 
    limit: Optional[int] = None
) -> str:
    """
    Fetches financial data from configured APIs.
    This is a placeholder and needs actual implementation to connect to APIs
    like Alpha Vantage, Finnhub, etc., as defined in `data/finance_apis.yaml`.
    
    Args:
        data_type (str): The type of data to fetch (e.g., "stock_prices", "company_overview", "earnings_report", "economic_indicator").
        symbol (str, optional): The stock symbol (e.g., "AAPL", "MSFT") if fetching stock-related data.
        start_date (str, optional): Start date for time-series data (YYYY-MM-DD).
        end_date (str, optional): End date for time-series data (YYYY-MM-DD).
        limit (int, optional): Maximum number of records to return.
        
    Returns:
        str: A JSON string of the fetched data or an error message.
             The agent can then use `python_interpreter` to parse and analyze this JSON.
    """
    logger.info(f"Tool: finance_data_fetcher called for data_type: {data_type}, symbol: {symbol}, dates: {start_date}-{end_date}")
    # This function needs actual implementation to call external APIs.
    # For now, it returns a mock response.
    if data_type == "stock_prices" and symbol == "AAPL":
        return """
        [
            {"date": "2023-01-01", "close": 125.0, "volume": 100000},
            {"date": "2023-01-02", "close": 126.5, "volume": 120000},
            {"date": "2023-01-03", "close": 124.0, "volume": 90000},
            {"date": "2023-01-04", "close": 127.2, "volume": 150000}
        ]
        """
    elif data_type == "company_overview" and symbol == "GOOG":
        return """
        {"symbol": "GOOG", "companyName": "Alphabet Inc.", "sector": "Technology", "industry": "Internet Content & Information", "description": "Alphabet Inc. is an American multinational technology conglomerate..."}
        """
    else:
        return f"Error: finance_data_fetcher not implemented for data_type: {data_type} or symbol: {symbol}. This is a placeholder tool."


# CLI Test (optional)
if __name__ == "__main__":
    import streamlit as st
    import shutil
    import json
    import os
    from config.config_manager import ConfigManager # Import ConfigManager for testing setup
    from shared_tools.llm_embedding_utils import get_llm # For testing summarization with a real LLM

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
        # Create dummy config.yml
        dummy_data_dir = Path("data")
        dummy_data_dir.mkdir(exist_ok=True)
        dummy_config_path = dummy_data_dir / "config.yml"
        with open(dummy_config_path, "w") as f:
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
        dummy_sports_apis_path = dummy_data_dir / "sports_apis.yaml"
        with open(dummy_sports_apis_path, "w") as f:
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
        dummy_media_apis_path = dummy_data_dir / "media_apis.yaml"
        with open(dummy_media_apis_path, "w") as f:
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
        # Create dummy finance_apis.yaml (for finance_data_fetcher test)
        dummy_finance_apis_path = dummy_data_dir / "finance_apis.yaml"
        with open(dummy_finance_apis_path, "w") as f:
            f.write("""
apis:
  - name: "AlphaVantage"
    type: "finance"
    endpoint: "https://www.alphavantage.co/query"
    key_name: "apikey"
    key_value: "load_from_secrets.alphavantage_api_key"
    default_params:
      outputsize: "compact"
""")

        if not hasattr(st, 'secrets'):
            st.secrets = MockSecrets()
            print("Mocked st.secrets for standalone testing.")
        
        # Ensure config_manager is a fresh instance for this test run
        ConfigManager._instance = None # Reset the singleton
        ConfigManager._is_loaded = False
        config_manager = ConfigManager()
        print("ConfigManager initialized for testing.")

    except Exception as e:
        print(f"Could not initialize ConfigManager for testing: {e}. Skipping API/LLM-dependent tests.")
        config_manager = None

    print("\n--- Testing finance_tool functions ---")
    test_user = "test_user_finance"
    
    if config_manager:
        # Test finance_search_web
        print("\n--- Testing finance_search_web ---")
        search_query = "latest inflation rate in US"
        search_result = finance_search_web(search_query, user_token=test_user)
        print(f"Search Result for '{search_query}':\n{search_result[:500]}...")

        # Prepare dummy data for finance_query_uploaded_docs
        print("\n--- Preparing dummy data for finance_query_uploaded_docs ---")
        dummy_json_path = Path("temp_finance_docs.json")
        dummy_data = [
            {"id": 1, "text": "Company X reported Q3 2023 earnings of $1.50 per share, beating estimates.", "category": "earnings"},
            {"id": 2, "text": "The Federal Reserve indicated a hawkish stance on interest rates in its latest meeting minutes.", "category": "monetary policy"},
            {"id": 3, "text": "An analysis of the bond market suggests increasing volatility for the next quarter.", "category": "market analysis"}
        ]
        with open(dummy_json_path, "w", encoding="utf-8") as f:
            json.dump(dummy_data, f)
        
        # Load documents from the dummy JSON for build_vectorstore
        loaded_docs_for_vector = load_docs_from_json_file(dummy_json_path)
        for i, doc in enumerate(loaded_docs_for_vector):
            doc.page_content = dummy_data[i]["text"]

        build_vectorstore(test_user, FINANCE_SECTION, loaded_docs_for_vector, chunk_size=200, chunk_overlap=0)
        print(f"Vectorstore built for {FINANCE_SECTION}.")

        # Test finance_query_uploaded_docs
        print("\n--- Testing finance_query_uploaded_docs ---")
        doc_query = "What were Company X's Q3 earnings?"
        doc_results = finance_query_uploaded_docs(doc_query, user_token=test_user)
        print(f"Query uploaded docs for '{doc_query}':\n{doc_results}")

        doc_query_export = "Summarize the Fed's latest stance."
        doc_results_export = finance_query_uploaded_docs(doc_query_export, user_token=test_user, export=True)
        print(f"Query uploaded docs with export for '{doc_query_export}':\n{doc_results_export}")
        
        # Test finance_summarize_document_by_path
        print("\n--- Testing finance_summarize_document_by_path ---")
        # Create a dummy upload directory and file
        test_upload_dir = Path("uploads") / test_user / FINANCE_SECTION
        test_upload_dir.mkdir(parents=True, exist_ok=True)
        summarize_file_path = test_upload_dir / "finance_article.txt"
        with open(summarize_file_path, "w") as f:
            f.write("This financial report details the company's performance over the last fiscal year. " * 30 + 
                    "Revenue increased by 15% due to strong sales in the tech sector, while operating expenses were well-managed. " * 20 +
                    "The outlook for the next quarter remains positive, with projected growth of 5-7%. " * 25)
        print(f"Created dummy file for summarization: {summarize_file_path}")

        summary_result = finance_summarize_document_by_path(str(summarize_file_path))
        print(summary_result)

        # Test finance_data_fetcher (mocked)
        print("\n--- Testing finance_data_fetcher (mocked) ---")
        aapl_prices = finance_data_fetcher(data_type="stock_prices", symbol="AAPL")
        print(f"AAPL Prices (mocked): {aapl_prices}")
        goog_overview = finance_data_fetcher(data_type="company_overview", symbol="GOOG")
        print(f"GOOG Overview (mocked): {goog_overview}")

        # Test python_interpreter (requires pandas and other libs to be installed)
        print("\n--- Testing python_interpreter ---")
        python_code = """
import pandas as pd
data = [
    {"date": "2023-01-01", "value": 100},
    {"date": "2023-01-02", "value": 105},
    {"date": "2023-01-03", "value": 102}
]
df = pd.DataFrame(data)
df['date'] = pd.to_datetime(df['date'])
df['daily_change'] = df['value'].diff()
print(df)
print(f"Average value: {df['value'].mean()}")
"""
        print(f"Executing Python code:\n{python_code}")
        try:
            repl_output = python_repl.run(python_code)
            print(f"Python REPL Output:\n{repl_output}")
        except Exception as e:
            print(f"Error executing Python REPL: {e}. Make sure pandas and other libraries are installed.")


    else:
        print("Skipping finance_tool tests due to ConfigManager issues or missing API keys.")

    # Clean up dummy files and directories
    if Path("exports").exists() and (Path("exports") / test_user).exists():
        shutil.rmtree(Path("exports") / test_user, ignore_errors=True)
    if Path("uploads").exists() and (Path("uploads") / test_user).exists():
        shutil.rmtree(Path("uploads") / test_user, ignore_errors=True)
    if BASE_VECTOR_DIR.exists() and (BASE_VECTOR_DIR / test_user).exists():
        shutil.rmtree(BASE_VECTOR_DIR / test_user, ignore_errors=True)
    if dummy_json_path.exists():
        dummy_json_path.unlink()
    
    dummy_data_dir = Path("data")
    if dummy_data_dir.exists():
        # Remove only if contents are dummy files created by this script
        if dummy_config_path.exists():
            os.remove(dummy_config_path)
        if dummy_sports_apis_path.exists():
            os.remove(dummy_sports_apis_path)
        if dummy_media_apis_path.exists():
            os.remove(dummy_media_apis_path)
        if dummy_finance_apis_path.exists():
            os.remove(dummy_finance_apis_path)
        if not os.listdir(dummy_data_dir):
            os.rmdir(dummy_data_dir)
