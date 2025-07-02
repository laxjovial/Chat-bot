# weather_tools/weather_tool.py

import requests
import json
from typing import Optional, List, Dict, Any
from pathlib import Path
import logging
import yaml # Added for loading weather_apis.yaml

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

# Constants for the weather section
WEATHER_SECTION = "weather"
DEFAULT_USER_TOKEN = "default" # Or use a proper user management if available

logger = logging.getLogger(__name__)

@tool
def weather_search_web(query: str, user_token: str = DEFAULT_USER_TOKEN, max_chars: int = 2000) -> str:
    """
    Searches the web for weather-related information (forecasts, current conditions, climate data) using a smart search fallback mechanism.
    This tool wraps the generic `scrape_web` tool, providing a weather-specific interface.
    
    Args:
        query (str): The weather-related search query (e.g., "weather in London tomorrow", "hurricane season outlook").
        user_token (str): The unique identifier for the user. Defaults to "default".
        max_chars (int): Maximum characters for the returned snippet. Defaults to 2000.
    
    Returns:
        str: A string containing relevant information from the web.
    """
    logger.info(f"Tool: weather_search_web called with query: '{query}' for user: '{user_token}'")
    return scrape_web(query=query, user_token=user_token, max_chars=max_chars)

@tool
def weather_query_uploaded_docs(query: str, user_token: str = DEFAULT_USER_TOKEN, export: Optional[bool] = False, k: int = 5) -> str:
    """
    Queries previously uploaded and indexed weather documents for a user using vector similarity search.
    This tool wraps the generic `QueryUploadedDocs` tool, fixing the section to "weather".
    
    Args:
        query (str): The search query to find relevant weather documents (e.g., "historical rainfall data for California", "climate change reports").
        user_token (str): The unique identifier for the user. Defaults to "default".
        export (bool): If True, the results will be saved to a file in markdown format. Defaults to False.
        k (int): The number of top relevant documents to retrieve. Defaults to 5.
    
    Returns:
        str: A string containing the combined content of the relevant document chunks,
             or a message indicating no data/results found, or the export path if exported.
    """
    logger.info(f"Tool: weather_query_uploaded_docs called with query: '{query}' for user: '{user_token}'")
    return QueryUploadedDocs(query=query, user_token=user_token, section=WEATHER_SECTION, export=export, k=k)

@tool
def weather_summarize_document_by_path(file_path_str: str) -> str:
    """
    Summarizes a document related to weather located at the given file path.
    The file path should be accessible by the system (e.g., in the 'uploads' directory).
    This tool wraps the generic `summarize_document` tool.
    
    Args:
        file_path_str (str): The full path to the document file to be summarized.
                              Example: "uploads/default/weather/annual_climate_report.pdf"
    
    Returns:
        str: A concise summary of the document content.
    """
    logger.info(f"Tool: weather_summarize_document_by_path called for file: '{file_path_str}'")
    file_path = Path(file_path_str)
    if not file_path.exists():
        logger.error(f"Document not found at '{file_path_str}' for summarization.")
        return f"Error: Document not found at '{file_path_str}'."
    
    try:
        summary = summarize_document(file_path) # Assuming summarize_document can take Path object
        return f"Summary of '{file_path.name}':\n{summary}"
    except ValueError as e:
        logger.error(f"Error summarizing document '{file_path_str}': {e}")
        return f"Error summarizing document: {e}"
    except Exception as e:
        logger.critical(f"An unexpected error occurred during summarization of '{file_path_str}': {e}", exc_info=True)
        return f"An unexpected error occurred during summarization: {e}"

# === Advanced Weather Tools ===

# REMOVED: Direct import and initialization of PythonREPLTool.
# The python_interpreter_with_rbac tool is now imported and added conditionally
# in the *_chat_agent_app.py files based on RBAC.

# Helper to load API configs
def _load_weather_apis() -> Dict[str, Any]:
    """Loads weather API configurations from data/weather_apis.yaml."""
    weather_apis_path = Path("data/weather_apis.yaml")
    if not weather_apis_path.exists():
        logger.warning(f"data/weather_apis.yaml not found at {weather_apis_path}")
        return {}
    try:
        with open(weather_apis_path, "r") as f:
            full_config = yaml.safe_load(f) or {}
            return {api['name']: api for api in full_config.get('apis', [])}
    except Exception as e:
        logger.error(f"Error loading weather_apis.yaml: {e}")
        return {}

WEATHER_APIS_CONFIG = _load_weather_apis()

@tool
def weather_data_fetcher(
    api_name: str, 
    data_type: str, 
    location: Optional[str] = None, # City name, zip code, or lat/lon
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    date: Optional[str] = None, # YYYY-MM-DD for historical or specific day forecast
    days: Optional[int] = None, # Number of days for forecast
    unit: Optional[str] = "metric", # "metric" or "imperial"
    limit: Optional[int] = None # For lists of data, e.g., hourly forecasts
) -> str:
    """
    Fetches weather data from configured APIs (e.g., OpenWeatherMap, WeatherAPI).
    
    Args:
        api_name (str): The name of the API to use (e.g., "OpenWeatherMap", "WeatherAPI").
                        This must match a 'name' field in data/weather_apis.yaml.
        data_type (str): The type of data to fetch.
                          - For OpenWeatherMap: "current_weather", "forecast_daily", "forecast_hourly".
                          - For WeatherAPI: "current_weather", "forecast", "history".
        location (str, optional): City name, zip code, or IP address.
        latitude (float, optional): Latitude for coordinates-based queries.
        longitude (float, optional): Longitude for coordinates-based queries.
        date (str, optional): Date for historical or specific day forecast (YYYY-MM-DD).
        days (int, optional): Number of days for forecast (e.g., 3, 7, 10).
        unit (str, optional): Units for temperature ("metric" for Celsius, "imperial" for Fahrenheit). Defaults to "metric".
        limit (int, optional): Maximum number of records to return (e.g., for hourly forecasts).
        
    Returns:
        str: A JSON string of the fetched data or an error message.
             The agent can then use `python_interpreter_with_rbac` to parse and analyze this JSON.
    """
    logger.info(f"Tool: weather_data_fetcher called for API: {api_name}, data_type: {data_type}, location: {location}, lat: {latitude}, lon: {longitude}")

    api_info = WEATHER_APIS_CONFIG.get(api_name)
    if not api_info:
        return f"Error: API '{api_name}' not found in data/weather_apis.yaml configuration."

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
    
    if key_name and not api_key:
        logger.warning(f"API key for '{api_name}' not found in secrets.toml. Proceeding without key if API allows.")

    params = {**default_params} # Start with default parameters
    if api_key and key_name:
        params[key_name] = api_key
    
    url = endpoint # Base URL, might be modified

    try:
        # Determine location parameter based on availability
        if location:
            params['q'] = location # Common for many weather APIs
        elif latitude is not None and longitude is not None:
            params['lat'] = latitude
            params['lon'] = longitude
            params['q'] = f"{latitude},{longitude}" # Some APIs prefer combined q for lat/lon

        # Add units
        if api_name == "OpenWeatherMap":
            params['units'] = unit # OpenWeatherMap uses 'units'
        elif api_name == "WeatherAPI":
            if unit == "metric":
                params['aqi'] = "no" # WeatherAPI doesn't have a direct 'unit' param for all, uses 'aqi' for example
            elif unit == "imperial":
                params['aqi'] = "no" # Example, might need more specific handling

        # --- OpenWeatherMap ---
        if api_name == "OpenWeatherMap":
            if not api_key: return "Error: API key is required for OpenWeatherMap."
            if not (location or (latitude is not None and longitude is not None)):
                return "Error: 'location' or 'latitude' and 'longitude' are required for OpenWeatherMap."

            if data_type == "current_weather":
                url = f"{endpoint}{api_info['functions']['CURRENT_WEATHER']['path']}"
            elif data_type == "forecast_daily":
                url = f"{endpoint}{api_info['functions']['FORECAST_DAILY']['path']}"
                if days: params['cnt'] = days # Number of days for daily forecast
            elif data_type == "forecast_hourly":
                url = f"{endpoint}{api_info['functions']['FORECAST_HOURLY']['path']}"
                if days: params['cnt'] = days * 24 # For hourly, count is hours, so days * 24
            else:
                return f"Error: Unsupported data_type '{data_type}' for OpenWeatherMap."
            
            response = requests.get(url, headers=headers, params=params, timeout=request_timeout)

        # --- WeatherAPI.com ---
        elif api_name == "WeatherAPI":
            if not api_key: return "Error: API key is required for WeatherAPI.com."
            if not (location or (latitude is not None and longitude is not None)):
                return "Error: 'location' or 'latitude' and 'longitude' are required for WeatherAPI.com."

            if data_type == "current_weather":
                url = f"{endpoint}{api_info['functions']['CURRENT_WEATHER']['path']}"
            elif data_type == "forecast":
                url = f"{endpoint}{api_info['functions']['FORECAST']['path']}"
                if days: params['days'] = days
            elif data_type == "history":
                url = f"{endpoint}{api_info['functions']['HISTORY']['path']}"
                if not date: return "Error: 'date' is required for WeatherAPI.com 'history' data_type."
                params['dt'] = date # WeatherAPI uses 'dt' for date
            else:
                return f"Error: Unsupported data_type '{data_type}' for WeatherAPI.com."
            
            response = requests.get(url, headers=headers, params=params, timeout=request_timeout)

        else:
            return f"Error: API '{api_name}' is not supported by weather_data_fetcher."

        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
        data = response.json()
        
        # Apply limit if specified and data is a list (or has a list-like key)
        if limit and isinstance(data, dict):
            # Common keys for lists in weather APIs (e.g., hourly forecast)
            for key in ['hourly', 'daily', 'list', 'forecastday']:
                if key in data and isinstance(data[key], list):
                    data[key] = data[key][:limit]
                    break
            if 'forecast' in data and 'forecastday' in data['forecast'] and isinstance(data['forecast']['forecastday'], list):
                data['forecast']['forecastday'] = data['forecast']['forecastday'][:limit]
        elif limit and isinstance(data, list):
            data = data[:limit]

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
    from unittest.mock import MagicMock

    logging.basicConfig(level=logging.INFO)

    # Mock Streamlit secrets for local testing if needed
    class MockSecrets:
        def __init__(self):
            self.openai = {"api_key": "sk-mock-openai-key-12345"} # Replace with a real key
            self.google = {"api_key": "AIzaSy-mock-google-key"} # Replace with a real key
            self.ollama = {"api_url": "http://localhost:11434", "model": "llama3"}
            self.serpapi = {"api_key": "YOUR_SERPAPI_KEY"} # For scrape_web testing
            self.google_custom_search = {"api_key": "YOUR_GOOGLE_CUSTOM_SEARCH_API_KEY"} # For scrape_web testing
            self.openweathermap_api_key = "YOUR_OPENWEATHERMAP_API_KEY" # For OpenWeatherMap
            self.weatherapi_api_key = "YOUR_WEATHERAPI_API_KEY" # For WeatherAPI
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


    print("\n--- Testing weather_tool functions (updated) ---")
    test_user = "test_user_weather"
    
    # Setup dummy API YAMLs for testing
    dummy_data_dir = Path("data")
    dummy_data_dir.mkdir(exist_ok=True)
    dummy_weather_apis_path = dummy_data_dir / "weather_apis.yaml"
    with open(dummy_weather_apis_path, "w") as f:
        f.write("""
apis:
  - name: "OpenWeatherMap"
    type: "weather"
    endpoint: "https://api.openweathermap.org/data/2.5/"
    key_name: "appid"
    key_value: "load_from_secrets.openweathermap_api_key"
    headers: {}
    default_params: {}
    functions:
      CURRENT_WEATHER:
        path: "weather"
        params: {q: "", lat: "", lon: "", units: "metric"}
      FORECAST_DAILY:
        path: "forecast/daily" # Not directly supported by OpenWeatherMap free tier, but common concept
        params: {q: "", lat: "", lon: "", cnt: "7", units: "metric"}
      FORECAST_HOURLY:
        path: "forecast" # 5 day / 3 hour forecast
        params: {q: "", lat: "", lon: "", cnt: "40", units: "metric"}
    query_param: "q"

  - name: "WeatherAPI"
    type: "weather"
    endpoint: "http://api.weatherapi.com/v1/"
    key_name: "key"
    key_value: "load_from_secrets.weatherapi_api_key"
    headers: {}
    default_params: {}
    functions:
      CURRENT_WEATHER:
        path: "current.json"
        params: {q: "", aqi: "no"}
      FORECAST:
        path: "forecast.json"
        params: {q: "", days: "7", aqi: "no", alerts: "no"}
      HISTORY:
        path: "history.json"
        params: {q: "", dt: ""}
    query_param: "q"
""")
    # Re-load config after creating dummy file
    sys.modules['config.config_manager'].config_manager = MockConfigManager()
    sys.modules['config.config_manager'].ConfigManager = MockConfigManager # Also replace the class for singleton check
    global WEATHER_APIS_CONFIG
    WEATHER_APIS_CONFIG = _load_weather_apis()
    print("Dummy weather_apis.yaml created and config reloaded for testing.")


    if config_manager:
        # Test weather_search_web (already works, just for completeness)
        print("\n--- Testing weather_search_web ---")
        search_query = "weather in New York"
        search_result = weather_search_web(search_query, user_token=test_user)
        print(f"Search Result for '{search_query}':\n{search_result[:500]}...")

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
            MockResponse({"coord": {"lon": -0.13, "lat": 51.51}, "weather": [{"main": "Clouds"}], "main": {"temp": 20.0}}),
            MockResponse({"location": {"name": "London"}, "current": {"temp_c": 21.5, "condition": {"text": "Partly cloudy"}}}),
            MockResponse({"forecast": {"forecastday": [{"date": "2024-07-03", "day": {"avgtemp_c": 22.0}}]}}),
        ])

        # Test weather_data_fetcher - OpenWeatherMap
        print("\n--- Testing weather_data_fetcher (OpenWeatherMap) ---")
        owm_current = weather_data_fetcher(api_name="OpenWeatherMap", data_type="current_weather", location="London")
        print(f"OpenWeatherMap Current Weather (London): {owm_current}")

        # Test weather_data_fetcher - WeatherAPI.com Current
        print("\n--- Testing weather_data_fetcher (WeatherAPI) ---")
        weatherapi_current = weather_data_fetcher(api_name="WeatherAPI", data_type="current_weather", location="London")
        print(f"WeatherAPI Current Weather (London): {weatherapi_current}")

        # Test weather_data_fetcher - WeatherAPI.com Forecast
        weatherapi_forecast = weather_data_fetcher(api_name="WeatherAPI", data_type="forecast", location="London", days=1)
        print(f"WeatherAPI Forecast (London, 1 day): {weatherapi_forecast}")
        
        # Restore original requests.get
        requests.get = original_requests_get

        # Test python_interpreter_with_rbac with mock data (example)
        print("\n--- Testing python_interpreter_with_rbac with mock data ---")
        python_code_weather = f"""
import json
data = {owm_current}
temp = data.get('main', {{}}).get('temp')
weather_desc = data.get('weather', [{{}}])[0].get('main')
print(f"Temperature: {{temp}} C")
print(f"Weather: {{weather_desc}}")
"""
        print(f"Executing Python code:\n{python_code_weather}")
        try:
            # Test with a user who has data_analysis_enabled
            pro_user_token = st.secrets.user_tokens["pro_user_token"]
            repl_output = python_interpreter_with_rbac(code=python_code_weather, user_token=pro_user_token)
            print(f"Python REPL Output (Pro User):\n{repl_output}")
            assert "Temperature: 20.0 C" in repl_output
            assert "Weather: Clouds" in repl_output

            # Test with a user who does NOT have data_analysis_enabled
            free_user_token = st.secrets.user_tokens["free_user_token"]
            repl_output_denied = python_interpreter_with_rbac(code=python_code_weather, user_token=free_user_token)
            print(f"Python REPL Output (Free User):\n{repl_output_denied}")
            assert "Access Denied" in repl_output_denied

        except Exception as e:
            print(f"Error executing Python REPL: {e}.")
            print("Make sure pandas, numpy, json are installed if you're running complex analysis.")

    else:
        print("Skipping weather_tool tests due to ConfigManager issues or missing API keys.")

    # Clean up dummy files and directories
    dummy_json_path = Path("temp_weather_docs.json")
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

