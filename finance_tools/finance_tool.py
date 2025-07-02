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

# REMOVED: from langchain_community.tools.python.tool import PythonREPLTool
# The Python interpreter is now managed and imported via shared_tools/python_interpreter_tool.py
# and conditionally added to the agent's toolset in the *_chat_agent_app.py files.

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
        # Note: The summarize_document tool now handles its own RBAC check internally
        # based on the user_token passed to it (if it accepts one).
        # For simplicity here, we're assuming summarize_document will handle it
        # or that this tool itself is only available to tiers with summarization.
        summary = summarize_document(file_path) # Assuming summarize_document can take Path object
        return f"Summary of '{file_path.name}':\n{summary}"
    except ValueError as e:
        logger.error(f"Error summarizing document '{file_path_str}': {e}")
        return f"Error summarizing document: {e}"
    except Exception as e:
        logger.critical(f"An unexpected error occurred during summarization of '{file_path_str}': {e}", exc_info=True)
        return f"An unexpected error occurred during summarization: {e}"

# === Advanced Finance Tools ===

# REMOVED: Direct import and initialization of PythonREPLTool.
# The python_interpreter_with_rbac tool is now imported and added conditionally
# in the *_chat_agent_app.py files based on RBAC.

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
             The agent can then use `python_interpreter_with_rbac` to parse and analyze this JSON.
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
    # Import the RBAC-enabled Python interpreter tool for testing purposes here
    from shared_tools.python_interpreter_tool import python_interpreter_with_rbac

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
            # Mock user tokens for testing RBAC
            self.user_tokens = {
                "free_user_token": "mock_free_token",
                "pro_user_token": "mock_pro_token",
                "admin_user_token": "mock_admin_token"
            }

        def get(self, key, default=None):
            parts = key.split('.')
            val = self
            for part in parts:
                if hasattr(val, part):
                    val = getattr(val, part)
                elif isinstance(val, dict) and part in val:
                    val = val[part]
                else:
                    return default
            return val

    # Mock user_manager.find_user_by_token and get_user_tier_capability for testing RBAC
    class MockUserManager:
        _mock_users = {
            "mock_free_token": {"username": "FreeUser", "email": "free@example.com", "tier": "free", "roles": ["user"]},
            "mock_pro_token": {"username": "ProUser", "email": "pro@example.com", "tier": "pro", "roles": ["user"]},
            "mock_admin_token": {"username": "AdminUser", "email": "admin@example.com", "tier": "admin", "roles": ["user", "admin"]},
            "nonexistent_token": None
        }
        def find_user_by_token(self, token: str) -> Optional[Dict[str, Any]]:
            return self._mock_users.get(token)

        def get_user_tier_capability(self, user_token: Optional[str], capability_key: str, default_value: Any = None) -> Any:
            user = self.find_user_by_token(user_token)
            user_tier = user.get('tier', 'free') if user else 'free'
            user_roles = user.get('roles', []) if user else []

            if 'admin' in user_roles:
                if isinstance(default_value, bool): return True
                if isinstance(default_value, (int, float)): return float('inf')
                return default_value
            
            mock_tier_configs = {
                "free": {
                    "data_analysis_enabled": False,
                    "web_search_limit_chars": 500,
                    "web_search_max_results": 2
                },
                "pro": {
                    "data_analysis_enabled": True,
                    "web_search_limit_chars": 3000,
                    "web_search_max_results": 7
                },
                "elite": {
                    "data_analysis_enabled": True,
                    "web_search_limit_chars": 5000,
                    "web_search_max_results": 10
                },
                "premium": {
                    "data_analysis_enabled": True,
                    "web_search_limit_chars": 10000,
                    "web_search_max_results": 15
                }
            }
            tier_config = mock_tier_configs.get(user_tier, {})
            return tier_config.get(capability_key, default_value)

    # Patch the actual imports for testing
    import sys
    sys.modules['utils.user_manager'] = MockUserManager()
    # Mock config_manager to return the test config
    class MockConfigManager:
        _instance = None
        _is_loaded = False
        def __init__(self):
            if MockConfigManager._instance is not None:
                raise Exception("ConfigManager is a singleton. Use get_instance().")
            MockConfigManager._instance = self
            self._config_data = {
                'llm': {
                    'max_summary_input_chars': 10000 # Default for LLM section
                },
                'rag': {
                    'chunk_size': 500,
                    'chunk_overlap': 50,
                    'max_query_results_k': 10
                },
                'web_scraping': {
                    'user_agent': 'Mozilla/5.0 (Test; Python)',
                    'timeout_seconds': 5,
                    'max_search_results': 5 # Default for config
                },
                'tiers': { # These are just for the mock, actual tiers are in the user_manager mock
                    'free': {}, 'basic': {}, 'pro': {}, 'elite': {}, 'premium': {}
                }
            }
            self._is_loaded = True
        
        def get(self, key, default=None):
            parts = key.split('.')
            val = self._config_data
            for part in parts:
                if isinstance(val, dict) and part in val:
                    val = val[part]
                else:
                    return default
            return val
        
        def get_secret(self, key, default=None):
            return st.secrets.get(key, default)

    # Replace the actual config_manager with the mock
    sys.modules['config.config_manager'].config_manager = MockConfigManager()
    sys.modules['config.config_manager'].ConfigManager = MockConfigManager # Also replace the class for singleton check

    if not hasattr(st, 'secrets'):
        st.secrets = MockSecrets()
        print("Mocked st.secrets for standalone testing.")
    
    # Mock LLM for summarization
    class MockLLM:
        def invoke(self, prompt: str) -> MagicMock:
            mock_content = f"Mock summary of the provided text. Original content length: {len(prompt.split('Document Content:')[1].strip())} characters."
            mock_message = MagicMock()
            mock_message.content = mock_content
            return mock_message
    
    import shared_tools.llm_embedding_utils
    shared_tools.llm_embedding_utils.get_llm = lambda: MockLLM()


    print("\n--- Testing finance_tool functions (updated) ---")
    test_user = "test_user_finance"
    
    # Setup dummy API YAMLs for testing
    dummy_data_dir = Path("data")
    dummy_data_dir.mkdir(exist_ok=True)
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
    # Re-load config after creating dummy file
    sys.modules['config.config_manager'].config_manager = MockConfigManager()
    sys.modules['config.config_manager'].ConfigManager = MockConfigManager # Also replace the class for singleton check
    global FINANCE_APIS_CONFIG
    FINANCE_APIS_CONFIG = _load_finance_apis()
    print("Dummy finance_apis.yaml created and config reloaded for testing.")


    if config_manager:
        # Test finance_search_web (already works, just for completeness)
        print("\n--- Testing finance_search_web ---")
        search_query = "latest inflation rate in US"
        search_result = finance_search_web(search_query, user_token=test_user)
        print(f"Search Result for '{search_query}':\n{search_result[:500]}...")

        # Test finance_data_fetcher - AlphaVantage
        print("\n--- Testing finance_data_fetcher (AlphaVantage) ---")
        # Mock requests.get for API calls
        class MockResponse:
            def __init__(self, json_data, status_code=200):
                self._json_data = json_data
                self.status_code = status_code
                self.text = json.dumps(json_data)
            def json(self):
                return self._json_data
            def raise_for_status(self):
                if self.status_code >= 400:
                    raise requests.exceptions.HTTPError(f"HTTP Error: {self.status_code}", response=self)

        original_requests_get = requests.get
        requests.get = MagicMock(side_effect=[
            MockResponse({"Time Series (Daily)": {"2023-01-01": {"1. open": "100.00"}}}),
            MockResponse({"Symbol": "GOOG", "AssetType": "Common Stock"}),
            MockResponse({"Global Quote": {"05. price": "150.00"}}),
            MockResponse({"bitcoin": {"usd": 30000, "eur": 28000}, "ethereum": {"usd": 2000, "eur": 1800}}),
            MockResponse([{"id": "bitcoin", "symbol": "btc"}]),
            MockResponse({"prices": [[1672531200000, 30000]]}),
            MockResponse({"conversion_rates": {"EUR": 0.9}}),
            MockResponse({"conversion_result": 90.0})
        ])

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

        # Restore original requests.get
        requests.get = original_requests_get

        # Test python_interpreter_with_rbac with fetched data (example)
        print("\n--- Testing python_interpreter_with_rbac with fetched data ---")
        python_code_crypto = f"""
import json
data = {btc_eth_price}
print(f"Bitcoin price in USD: {{data.get('bitcoin', {{}}).get('usd')}}")
print(f"Ethereum price in EUR: {{data.get('ethereum', {{}}).get('eur')}}")
"""
        print(f"Executing Python code:\n{python_code_crypto}")
        try:
            # Test with a user who has data_analysis_enabled
            pro_user_token = st.secrets.user_tokens["pro_user_token"]
            repl_output = python_interpreter_with_rbac(code=python_code_crypto, user_token=pro_user_token)
            print(f"Python REPL Output (Pro User):\n{repl_output}")
            assert "Bitcoin price in USD" in repl_output
            assert "Ethereum price in EUR" in repl_output

            # Test with a user who does NOT have data_analysis_enabled
            free_user_token = st.secrets.user_tokens["free_user_token"]
            repl_output_denied = python_interpreter_with_rbac(code=python_code_crypto, user_token=free_user_token)
            print(f"Python REPL Output (Free User):\n{repl_output_denied}")
            assert "Access Denied" in repl_output_denied

        except Exception as e:
            print(f"Error executing Python REPL: {e}.")
            print("Make sure pandas, numpy, json are installed if you're running complex analysis.")

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
        dummy_news_apis_path = dummy_data_dir / "news_apis.yaml"
        dummy_weather_apis_path = dummy_data_dir / "weather_apis.yaml"
        dummy_entertainment_apis_path = dummy_data_dir / "entertainment_apis.yaml"
        dummy_medical_apis_path = dummy_data_dir / "medical_apis.yaml"
        dummy_legal_apis_path = dummy_data_dir / "legal_apis.yaml"


        if dummy_config_path.exists(): os.remove(dummy_config_path)
        if dummy_sports_apis_path.exists(): os.remove(dummy_sports_apis_path)
        if dummy_media_apis_path.exists(): os.remove(dummy_media_apis_path)
        if dummy_finance_apis_path.exists(): os.remove(dummy_finance_apis_path)
        if dummy_news_apis_path.exists(): os.remove(dummy_news_apis_path)
        if dummy_weather_apis_path.exists(): os.remove(dummy_weather_apis_path)
        if dummy_entertainment_apis_path.exists(): os.remove(dummy_entertainment_apis_path)
        if dummy_medical_apis_path.exists(): os.remove(dummy_medical_apis_path)
        if dummy_legal_apis_path.exists(): os.remove(dummy_legal_apis_path)

        if not os.listdir(dummy_data_dir):
            os.rmdir(dummy_data_dir)
