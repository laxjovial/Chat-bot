# finance_tools/finance_tool.py

import requests
import json
from typing import Optional, List, Dict, Any
from pathlib import Path
import logging
import yaml # Added for loading finance_apis.yaml

# Import generic tools
from langchain_core.tools import tool
from shared_tools.query_uploaded_docs_tool import QueryUploadedDocs
from shared_tools.scraper_tool import scrape_web
from shared_tools.doc_summarizer import summarize_document
from shared_tools.import_utils import process_upload, clear_indexed_data # Used by Streamlit apps, not directly as agent tools
from shared_tools.export_utils import export_response, export_vector_results # To be used internally by other tools, or for direct exports
from shared_tools.vector_utils import build_vectorstore, load_docs_from_json_file, BASE_VECTOR_DIR # For testing and potential future direct use

# Import Python REPL for data analysis capabilities
from langchain_community.tools.python.tool import PythonREPLTool

# Import config_manager to access API configurations
from config.config_manager import config_manager

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
python_repl = PythonREPLTool()
python_repl.name = "python_interpreter"
python_repl.description = """
Executes Python code. Use this for complex calculations, data analysis, time-series analysis,
or any task that requires programmatic logic.
Input should be a valid Python code string.
The output will be the result of the code execution (stdout/stderr).
You have access to common libraries like pandas, numpy, matplotlib, datetime, json, etc.
Example for parsing and analyzing fetched data:
Action: python_interpreter
Action Input:
import pandas as pd
import json
data_str = '''[{"date": "2023-01-01", "close": 125.0}, {"date": "2023-01-02", "close": 126.5}]''' # Assume this came from finance_data_fetcher
df = pd.DataFrame(json.loads(data_str))
df['date'] = pd.to_datetime(df['date'])
df.set_index('date', inplace=True)
print(df['close'].mean())
"""

# Helper to load API configs
def _load_finance_apis() -> Dict[str, Any]:
    """Loads finance API configurations from data/finance_apis.yaml."""
    finance_apis_path = Path("data/finance_apis.yaml")
    if not finance_apis_path.exists():
        logger.warning(f"data/finance_apis.yaml not found at {finance_apis_path}")
        return {}
    try:
        with open(finance_apis_path, "r") as f:
            full_config = yaml.safe_load(f) or {}
            return {api['name']: api for api in full_config.get('apis', [])}
    except Exception as e:
        logger.error(f"Error loading finance_apis.yaml: {e}")
        return {}

FINANCE_APIS_CONFIG = _load_finance_apis()

@tool
def finance_data_fetcher(
    api_name: str, 
    data_type: str, 
    symbol: Optional[str] = None, 
    base_currency: Optional[str] = None, # For currency exchange
    target_currency: Optional[str] = None, # For currency exchange
    amount: Optional[float] = None, # For currency conversion
    ids: Optional[str] = None, # For crypto (comma-separated coin IDs)
    vs_currencies: Optional[str] = None, # For crypto (comma-separated currency symbols)
    days: Optional[int] = None, # For crypto market chart
    start_date: Optional[str] = None, # YYYY-MM-DD
    end_date: Optional[str] = None, # YYYY-MM-DD
    limit: Optional[int] = None # For number of records
) -> str:
    """
    Fetches financial data from configured APIs (AlphaVantage, CoinGecko, ExchangeRate-API).
    
    Args:
        api_name (str): The name of the API to use (e.g., "AlphaVantage", "CoinGecko", "ExchangeRate-API").
                        This must match a 'name' field in data/finance_apis.yaml.
        data_type (str): The type of data to fetch.
                         - For AlphaVantage: "stock_prices", "company_overview", "global_quote".
                         - For CoinGecko: "crypto_price", "crypto_list", "crypto_market_chart".
                         - For ExchangeRate-API: "exchange_rate_latest", "exchange_rate_convert".
        symbol (str, optional): Stock symbol (e.g., "AAPL", "MSFT") for AlphaVantage.
        base_currency (str, optional): Base currency for exchange rates (e.g., "USD", "EUR").
        target_currency (str, optional): Target currency for exchange rates (e.g., "GBP", "JPY").
        amount (float, optional): Amount to convert for exchange rates.
        ids (str, optional): Comma-separated crypto coin IDs (e.g., "bitcoin,ethereum") for CoinGecko.
        vs_currencies (str, optional): Comma-separated currency symbols (e.g., "usd,eur") for CoinGecko.
        days (int, optional): Number of days for crypto market chart (e.g., 1, 7, 30).
        start_date (str, optional): Start date for time-series data (YYYY-MM-DD). Not fully implemented for all APIs.
        end_date (str, optional): End date for time-series data (YYYY-MM-DD). Not fully implemented for all APIs.
        limit (int, optional): Maximum number of records to return.
        
    Returns:
        str: A JSON string of the fetched data or an error message.
             The agent can then use `python_interpreter` to parse and analyze this JSON.
    """
    logger.info(f"Tool: finance_data_fetcher called for API: {api_name}, data_type: {data_type}, symbol: {symbol}, ids: {ids}, base_currency: {base_currency}")

    api_info = FINANCE_APIS_CONFIG.get(api_name)
    if not api_info:
        return f"Error: API '{api_name}' not found in data/finance_apis.yaml configuration."

    endpoint = api_info.get("endpoint")
    key_name = api_info.get("key_name")
    api_key_value_ref = api_info.get("key_value")
    default_params = api_info.get("default_params", {})
    headers = api_info.get("headers", {})
    request_timeout = config_manager.get('web_scraping.timeout_seconds', 10)

    api_key = None
    if api_key_value_ref and api_key_value_ref.startswith("load_from_secrets."):
        secret_key_path = api_key_value_ref.split("load_from_secrets.")[1]
        api_key = config_manager.get_secret(secret_key_path)
    
    # For APIs where key is part of URL path (like ExchangeRate-API)
    if api_name == "ExchangeRate-API" and not api_key:
        return f"Error: API key for '{api_name}' not found in secrets.toml. It's required for this API."
    elif key_name and not api_key: # For APIs where key is a param/header
        logger.warning(f"API key for '{api_name}' not found in secrets.toml. Proceeding without key if API allows.")


    params = {**default_params} # Start with default parameters

    try:
        # --- AlphaVantage ---
        if api_name == "AlphaVantage":
            if data_type == "stock_prices":
                if not symbol: return "Error: 'symbol' is required for AlphaVantage stock_prices."
                params.update(api_info['functions']['TIME_SERIES_DAILY']['params'])
                params['symbol'] = symbol
            elif data_type == "company_overview":
                if not symbol: return "Error: 'symbol' is required for AlphaVantage company_overview."
                params.update(api_info['functions']['COMPANY_OVERVIEW']['params'])
                params['symbol'] = symbol
            elif data_type == "global_quote":
                if not symbol: return "Error: 'symbol' is required for AlphaVantage global_quote."
                params.update(api_info['functions']['GLOBAL_QUOTE']['params'])
                params['symbol'] = symbol
            else:
                return f"Error: Unsupported data_type '{data_type}' for AlphaVantage."
            
            if api_key: params[key_name] = api_key # Add API key to params if available
            response = requests.get(endpoint, headers=headers, params=params, timeout=request_timeout)

        # --- CoinGecko ---
        elif api_name == "CoinGecko":
            if data_type == "crypto_price":
                if not ids or not vs_currencies: return "Error: 'ids' (e.g., 'bitcoin') and 'vs_currencies' (e.g., 'usd') are required for CoinGecko crypto_price."
                url = f"{endpoint}{api_info['functions']['SIMPLE_PRICE']['path']}"
                params['ids'] = ids
                params['vs_currencies'] = vs_currencies
            elif data_type == "crypto_list":
                url = f"{endpoint}{api_info['functions']['COINS_LIST']['path']}"
            elif data_type == "crypto_market_chart":
                if not ids or not vs_currencies or not days: return "Error: 'ids', 'vs_currencies', and 'days' are required for CoinGecko crypto_market_chart."
                url = f"{endpoint}coins/{ids.split(',')[0].strip()}/market_chart" # Use first ID for path
                params['vs_currency'] = vs_currencies.split(',')[0].strip() # Use first vs_currency
                params['days'] = str(days)
            else:
                return f"Error: Unsupported data_type '{data_type}' for CoinGecko."
            
            response = requests.get(url, headers=headers, params=params, timeout=request_timeout)

        # --- ExchangeRate-API ---
        elif api_name == "ExchangeRate-API":
            if not api_key: return "Error: API key is required for ExchangeRate-API."
            if data_type == "exchange_rate_latest":
                if not base_currency: return "Error: 'base_currency' is required for ExchangeRate-API latest rates."
                url = f"{endpoint}{api_key}/latest/{base_currency.upper()}"
            elif data_type == "exchange_rate_convert":
                if not base_currency or not target_currency or amount is None: return "Error: 'base_currency', 'target_currency', and 'amount' are required for conversion."
                url = f"{endpoint}{api_key}/pair/{base_currency.upper()}/{target_currency.upper()}/{amount}"
            else:
                return f"Error: Unsupported data_type '{data_type}' for ExchangeRate-API."
            
            response = requests.get(url, headers=headers, timeout=request_timeout) # Params might not be needed if all in URL

        else:
            return f"Error: API '{api_name}' is not supported by finance_data_fetcher."

        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
        data = response.json()
        return json.dumps(data, ensure_ascii=False, indent=2)

    except requests.exceptions.RequestException as req_e:
        logger.error(f"API request failed for {api_name} ({data_type}): {req_e}")
        if hasattr(req_e, 'response') and req_e.response is not None:
            logger.error(f"Response content: {req_e.response.text}")
            return f"API request failed for {api_name}: {req_e.response.text}"
        return f"API request failed for {api_name}: {req_e}"
    except Exception as e:
        logger.error(f"Error processing {api_name} response or request setup: {e}", exc_info=True)
        return f"An unexpected error occurred: {e}"


# CLI Test (optional)
if __name__ == "__main__":
    import streamlit as st
    import shutil
    import os
    from config.config_manager import ConfigManager # Import ConfigManager for testing setup
    from shared_tools.llm_embedding_utils import get_llm # For testing summarization with a real LLM

    logging.basicConfig(level=logging.INFO)

    # Mock Streamlit secrets for local testing if needed
    class MockSecrets:
        def __init__(self):
            self.openai = {"api_key": "sk-mock-openai-key-12345"} # Replace with a real key
            self.google = {"api_key": "AIzaSy-mock-google-key"} # Replace with a real key
            self.ollama = {"api_url": "http://localhost:11434", "model": "llama3"}
            self.serpapi = {"api_key": "YOUR_SERPAPI_KEY"} # For scrape_web testing
            self.google_custom_search = {"api_key": "YOUR_GOOGLE_CUSTOM_SEARCH_API_KEY"} # For scrape_web testing
            self.alphavantage_api_key = "YOUR_ALPHAVANTAGE_API_KEY" # For AlphaVantage
            self.coingecko_api_key = "YOUR_COINGECKO_API_KEY" # For CoinGecko (if paid tier)
            self.exchangerate_api_key = "YOUR_EXCHANGERATE_API_KEY" # For ExchangeRate-API
            self.financial_news_api_key = "YOUR_FINANCIAL_NEWS_API_KEY" # For FinancialNewsSearch

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
        # Create dummy API YAMLs for scraper_tool and finance_data_fetcher
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
apis: []
search_apis: []
""")
        dummy_finance_apis_path = dummy_data_dir / "finance_apis.yaml"
        with open(dummy_finance_apis_path, "w") as f:
            f.write("""
apis:
  - name: "AlphaVantage"
    type: "finance"
    endpoint: "https://www.alphavantage.co/query"
    key_name: "apikey"
    key_value: "load_from_secrets.alphavantage_api_key"
    headers: {}
    default_params: {}
    functions:
      TIME_SERIES_DAILY:
        params: {function: "TIME_SERIES_DAILY", symbol: "", outputsize: "compact", datatype: "json"}
      GLOBAL_QUOTE:
        params: {function: "GLOBAL_QUOTE", symbol: "", datatype: "json"}
      COMPANY_OVERVIEW:
        params: {function: "OVERVIEW", symbol: "", datatype: "json"}
    query_param: "symbol"

  - name: "CoinGecko"
    type: "crypto"
    endpoint: "https://api.coingecko.com/api/v3/"
    key_name: ""
    key_value: "" # Or "load_from_secrets.coingecko_api_key"
    headers: {}
    default_params: {}
    functions:
      SIMPLE_PRICE:
        path: "simple/price"
        params: {ids: "", vs_currencies: ""}
      COINS_LIST:
        path: "coins/list"
      COINS_MARKET_CHART:
        path: "coins/{id}/market_chart"
        params: {vs_currency: "usd", days: "7"}
    query_param: "ids"

  - name: "ExchangeRate-API"
    type: "currency_exchange"
    endpoint: "https://v6.exchangerate-api.com/v6/"
    key_name: ""
    key_value: "load_from_secrets.exchangerate_api_key"
    headers: {}
    default_params: {}
    functions:
      LATEST:
        path: "{api_key}/latest/{base_currency}"
      PAIR_CONVERSION:
        path: "{api_key}/pair/{base_currency}/{target_currency}/{amount}"
    query_param: "base_currency"

search_apis:
  - name: "FinancialNewsSearch"
    type: "search"
    endpoint: "https://api.example.com/financial_news/search"
    key_name: "api_key"
    key_value: "load_from_secrets.financial_news_api_key"
    headers: {}
    default_params:
      sort_by: "publishedAt"
    query_param: "q"
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

    print("\n--- Testing finance_tool functions (updated) ---")
    test_user = "test_user_finance"
    
    if config_manager:
        # Test finance_search_web (already works, just for completeness)
        print("\n--- Testing finance_search_web ---")
        search_query = "latest inflation rate in US"
        search_result = finance_search_web(search_query, user_token=test_user)
        print(f"Search Result for '{search_query}':\n{search_result[:500]}...")

        # Test finance_data_fetcher - AlphaVantage
        print("\n--- Testing finance_data_fetcher (AlphaVantage) ---")
        aapl_prices = finance_data_fetcher(api_name="AlphaVantage", data_type="stock_prices", symbol="IBM") # Using IBM for test
        print(f"IBM Prices (AlphaVantage): {aapl_prices[:200]}...")
        goog_overview = finance_data_fetcher(api_name="AlphaVantage", data_type="company_overview", symbol="GOOG")
        print(f"GOOG Overview (AlphaVantage): {goog_overview[:200]}...")

        # Test finance_data_fetcher - CoinGecko
        print("\n--- Testing finance_data_fetcher (CoinGecko) ---")
        btc_eth_price = finance_data_fetcher(api_name="CoinGecko", data_type="crypto_price", ids="bitcoin,ethereum", vs_currencies="usd,eur")
        print(f"BTC/ETH Price (CoinGecko): {btc_eth_price}")
        coin_list = finance_data_fetcher(api_name="CoinGecko", data_type="crypto_list")
        print(f"Coin List (CoinGecko): {coin_list[:200]}...")
        btc_market_chart = finance_data_fetcher(api_name="CoinGecko", data_type="crypto_market_chart", ids="bitcoin", vs_currencies="usd", days=7)
        print(f"Bitcoin Market Chart (CoinGecko, 7 days): {btc_market_chart[:200]}...")


        # Test finance_data_fetcher - ExchangeRate-API
        print("\n--- Testing finance_data_fetcher (ExchangeRate-API) ---")
        usd_latest = finance_data_fetcher(api_name="ExchangeRate-API", data_type="exchange_rate_latest", base_currency="USD")
        print(f"USD Latest Rates (ExchangeRate-API): {usd_latest[:200]}...")
        usd_eur_convert = finance_data_fetcher(api_name="ExchangeRate-API", data_type="exchange_rate_convert", base_currency="USD", target_currency="EUR", amount=100.0)
        print(f"100 USD to EUR (ExchangeRate-API): {usd_eur_convert}")

        # Test python_interpreter with fetched data (example)
        print("\n--- Testing python_interpreter with fetched data ---")
        python_code_crypto = f"""
import json
data = {btc_eth_price}
print(f"Bitcoin price in USD: {{data.get('bitcoin', {{}}).get('usd')}}")
print(f"Ethereum price in EUR: {{data.get('ethereum', {{}}).get('eur')}}")
"""
        print(f"Executing Python code:\n{python_code_crypto}")
        try:
            repl_output = python_repl.run(python_code_crypto)
            print(f"Python REPL Output:\n{repl_output}")
        except Exception as e:
            print(f"Error executing Python REPL: {e}. Make sure pandas, numpy, json are installed.")

    else:
        print("Skipping finance_tool tests due to ConfigManager issues or missing API keys.")

    # Clean up dummy files and directories
    dummy_json_path = Path("temp_finance_docs.json")
    if dummy_json_path.exists():
        dummy_json_path.unlink()
    if Path("exports").exists() and (Path("exports") / test_user).exists():
        shutil.rmtree(Path("exports") / test_user, ignore_errors=True)
    if Path("uploads").exists() and (Path("uploads") / test_user).exists():
        shutil.rmtree(Path("uploads") / test_user, ignore_errors=True)
    if BASE_VECTOR_DIR.exists() and (BASE_VECTOR_DIR / test_user).exists():
        shutil.rmtree(BASE_VECTOR_DIR / test_user, ignore_errors=True)
    
    dummy_data_dir = Path("data")
    if dummy_data_dir.exists():
        # Remove only if contents are dummy files created by this script
        dummy_config_path = dummy_data_dir / "config.yml"
        dummy_sports_apis_path = dummy_data_dir / "sports_apis.yaml"
        dummy_media_apis_path = dummy_data_dir / "media_apis.yaml"
        dummy_finance_apis_path = dummy_data_dir / "finance_apis.yaml"

        if dummy_config_path.exists(): os.remove(dummy_config_path)
        if dummy_sports_apis_path.exists(): os.remove(dummy_sports_apis_path)
        if dummy_media_apis_path.exists(): os.remove(dummy_media_apis_path)
        if dummy_finance_apis_path.exists(): os.remove(dummy_finance_apis_path)
        if not os.listdir(dummy_data_dir):
            os.rmdir(dummy_data_dir)

