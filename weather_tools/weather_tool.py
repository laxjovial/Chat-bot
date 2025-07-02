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

# Import Python REPL for data analysis capabilities
from langchain_community.tools.python.tool import PythonREPLTool

# Import config_manager to access API configurations
from config.config_manager import config_manager

# Constants for the weather section
WEATHER_SECTION = "weather"
DEFAULT_USER_TOKEN = "default" # Or use a proper user management if available

logger = logging.getLogger(__name__)

@tool
def weather_search_web(query: str, user_token: str = DEFAULT_USER_TOKEN, max_chars: int = 2000) -> str:
    """
    Searches the web for general weather or climate-related information using a smart search fallback mechanism.
    This tool wraps the generic `scrape_web` tool, providing a weather-specific interface.
    
    Args:
        query (str): The weather/climate-related search query (e.g., "impact of El Nino", "how do hurricanes form").
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
    Queries previously uploaded and indexed weather/climate documents for a user using vector similarity search.
    This tool wraps the generic `QueryUploadedDocs` tool, fixing the section to "weather".
    
    Args:
        query (str): The search query to find relevant weather/climate documents (e.g., "summary of the IPCC report I uploaded", "my local weather station data analysis").
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
    Summarizes a document related to weather or climate topics located at the given file path.
    The file path should be accessible by the system (e.g., in the 'uploads' directory).
    This tool wraps the generic `summarize_document` tool.
    
    Args:
        file_path_str (str): The full path to the document file to be summarized.
                              Example: "uploads/default/weather/climate_study.pdf"
    
    Returns:
        str: A concise summary of the document content.
    """
    logger.info(f"Tool: weather_summarize_document_by_path called for file: '{file_path_str}'")
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

# === Advanced Weather Tools ===

# Initialize the Python REPL tool.
python_repl = PythonREPLTool()
python_repl.name = "python_interpreter"
python_repl.description = """
Executes Python code. Use this for complex data analysis, calculations, or any task that requires programmatic logic
on structured weather or climate data (e.g., analyzing temperature trends, precipitation patterns).
Input should be a valid Python code string.
The output will be the result of the code execution (stdout/stderr).
You have access to common libraries like pandas, numpy, matplotlib, datetime, json, etc.
Example:
Action: python_interpreter
Action Input:
import json
import pandas as pd
data = json.loads(tool_output) # Assuming tool_output from weather_data_fetcher
df = pd.DataFrame(data['daily'])
print(df[['date', 'temp_max', 'temp_min']].head())
"""

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
    data_type: str, # e.g., "current_weather", "forecast", "historical_weather", "alerts"
    location: Optional[str] = None, # City name, zip code, or lat/lon (e.g., "London", "90210", "34.05,-118.25")
    days: Optional[int] = None, # For forecast (e.g., 5-day forecast)
    start_date: Optional[str] = None, # YYYY-MM-DD for historical data
    end_date: Optional[str] = None, # YYYY-MM-DD for historical data
    units: Optional[str] = "metric" # "metric" or "imperial"
) -> str:
    """
    Fetches weather data (current, forecast, historical, alerts) from configured APIs.
    This is a placeholder and needs actual implementation to connect to real weather APIs
    like OpenWeatherMap, WeatherAPI.com, AccuWeather, etc.
    
    Args:
        api_name (str): The name of the API to use (e.g., "OpenWeatherMap", "WeatherAPI").
                        This must match a 'name' field in data/weather_apis.yaml.
        data_type (str): The type of weather data to fetch (e.g., "current_weather", "forecast", "historical_weather", "alerts").
        location (str, optional): The city name, zip code, or latitude/longitude for the weather query.
        days (int, optional): Number of days for the forecast (e.g., 1, 3, 5, 7).
        start_date (str, optional): Start date for historical weather data (YYYY-MM-DD).
        end_date (str, optional): End date for historical weather data (YYYY-MM-DD).
        units (str, optional): Units for temperature (e.g., "metric" for Celsius, "imperial" for Fahrenheit). Defaults to "metric".
        
    Returns:
        str: A JSON string of the fetched weather data or an error message.
             The agent can then use `python_interpreter` to parse and analyze this JSON.
    """
    logger.info(f"Tool: weather_data_fetcher called for API: {api_name}, data_type: {data_type}, location: '{location}'")

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
    
    if key_name and api_key:
        if key_name.lower() == "authorization": # Handle Bearer tokens
            headers["Authorization"] = f"Bearer {api_key}"
        else:
            default_params[key_name] = api_key
    elif key_name and not api_key:
        logger.warning(f"API key for '{api_name}' not found in secrets.toml. Proceeding without key if API allows.")

    params = {**default_params} # Start with default parameters
    url = endpoint

    try:
        # --- Placeholder/Mock Implementations ---
        if api_name == "OpenWeatherMap":
            if not location: return "Error: 'location' is required for OpenWeatherMap."
            if data_type == "current_weather":
                # Mock current weather data
                return json.dumps({
                    "location": location,
                    "temperature": "25°C" if units == "metric" else "77°F",
                    "conditions": "Partly Cloudy",
                    "humidity": "60%",
                    "wind_speed": "10 km/h" if units == "metric" else "6 mph",
                    "timestamp": "2024-07-02 10:00:00"
                })
            elif data_type == "forecast":
                if not days: return "Error: 'days' is required for OpenWeatherMap forecast."
                # Mock forecast data
                return json.dumps({
                    "location": location,
                    "forecast": [
                        {"date": "2024-07-02", "temp_max": "28°C", "temp_min": "18°C", "conditions": "Sunny"},
                        {"date": "2024-07-03", "temp_max": "26°C", "temp_min": "17°C", "conditions": "Cloudy with chance of rain"},
                        {"date": "2024-07-04", "temp_max": "29°C", "temp_min": "19°C", "conditions": "Clear"}
                    ][:days]
                })
            elif data_type == "alerts":
                # Mock weather alerts
                return json.dumps([
                    {"type": "Severe Thunderstorm Warning", "area": location, "expires": "2024-07-02 18:00:00", "description": "Strong winds and heavy rain expected."}
                ])
            else:
                return f"Error: Unsupported data_type '{data_type}' for OpenWeatherMap."
        
        elif api_name == "WeatherAPI":
            if not location: return "Error: 'location' is required for WeatherAPI."
            if data_type == "current_weather":
                # Mock current weather data
                return json.dumps({
                    "location": location,
                    "temp_c": 26.0, "temp_f": 78.8,
                    "condition": "Sunny",
                    "humidity": 55,
                    "wind_kph": 12.0, "wind_mph": 7.5,
                    "last_updated": "2024-07-02 10:05"
                })
            elif data_type == "historical_weather":
                if not start_date or not end_date: return "Error: 'start_date' and 'end_date' are required for historical weather."
                # Mock historical data
                return json.dumps({
                    "location": location,
                    "history": [
                        {"date": "2024-06-30", "avg_temp_c": 24.5, "avg_temp_f": 76.1, "condition": "Sunny"},
                        {"date": "2024-06-29", "avg_temp_c": 23.0, "avg_temp_f": 73.4, "condition": "Partly cloudy"}
                    ]
                })
            else:
                return f"Error: Unsupported data_type '{data_type}' for WeatherAPI."

        else:
            return f"Error: API '{api_name}' is not supported by weather_data_fetcher."

    except requests.exceptions.RequestException as req_e:
        logger.error(f"API request failed for {api_name} ({data_type}): {req_e}")
        if hasattr(req_e, 'response') and req_e.response is not None:
            logger.error(f"Response content: {req_e.response.text}")
            return f"API request failed for {api_name}: {req_e.response.text}"
        return f"API request failed for {api_name}: {req_e}"
    except Exception as e:
        logger.error(f"Error processing {api_name} response or request setup: {e}", exc_info=True)
        return f"An unexpected error occurred: {e}"

@tool
def climate_info_explainer(topic: str) -> str:
    """
    Explains complex climate phenomena, terms, or impacts in understandable language.
    
    Args:
        topic (str): The climate topic to explain (e.g., "El Nino", "Greenhouse Effect", "Carbon Sequestration", "Arctic Amplification").
        
    Returns:
        str: A simplified explanation of the climate topic.
    """
    logger.info(f"Tool: climate_info_explainer called for topic: '{topic}'")
    topic_lower = topic.lower()
    if "el nino" in topic_lower:
        return "**El Niño:** A climate pattern that describes the unusual warming of surface waters in the eastern tropical Pacific Ocean. El Niño is the 'warm phase' of a larger phenomenon called El Niño-Southern Oscillation (ENSO). It can lead to significant changes in global weather patterns, affecting rainfall, temperature, and storm activity worldwide."
    elif "greenhouse effect" in topic_lower:
        return "**Greenhouse Effect:** The process by which radiation from a planet's atmosphere warms the planet's surface to a temperature above what it would be without its atmosphere. Greenhouse gases (like carbon dioxide, methane, and water vapor) trap heat, preventing it from escaping into space and keeping the Earth warm enough to sustain life. Human activities have increased these gases, leading to enhanced warming."
    elif "carbon sequestration" in topic_lower:
        return "**Carbon Sequestration:** The process of capturing and storing atmospheric carbon dioxide. It is one method of reducing the amount of carbon dioxide in the atmosphere with the goal of reducing global climate change. This can occur naturally (e.g., forests absorbing CO2) or artificially (e.g., capturing emissions from power plants and injecting them underground)."
    elif "arctic amplification" in topic_lower:
        return "**Arctic Amplification:** The phenomenon where the Arctic region is warming at a rate significantly faster than the rest of the planet. This is largely due to positive feedback loops, such as the melting of ice and snow which reduces the Earth's albedo (reflectivity), causing more solar radiation to be absorbed and further warming the region."
    else:
        return f"I can explain various climate topics. Please provide a specific climate phenomenon or term for explanation."


@tool
def weather_alert_checker(location: str) -> str:
    """
    Checks for any active severe weather alerts for a specified location.
    
    Args:
        location (str): The location to check for alerts (e.g., "New York City", "London").
        
    Returns:
        str: A summary of active alerts or a message indicating no alerts.
    """
    logger.info(f"Tool: weather_alert_checker called for location: '{location}'")
    # This calls the weather_data_fetcher with a specific data_type for alerts
    return weather_data_fetcher(api_name="OpenWeatherMap", data_type="alerts", location=location)


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
            self.openweathermap_api_key = "YOUR_OPENWEATHERMAP_API_KEY" # For OpenWeatherMap
            self.weatherapi_api_key = "YOUR_WEATHERAPI_API_KEY" # For WeatherAPI.com

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
        # Create dummy API YAMLs for scraper_tool and weather_data_fetcher
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
apis: []
search_apis: []
""")
        dummy_medical_apis_path = dummy_data_dir / "medical_apis.yaml"
        with open(dummy_medical_apis_path, "w") as f:
            f.write("""
apis: []
search_apis: []
""")
        dummy_legal_apis_path = dummy_data_dir / "legal_apis.yaml"
        with open(dummy_legal_apis_path, "w") as f:
            f.write("""
apis: []
search_apis: []
""")
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
      current_weather: {path: "weather"}
      forecast: {path: "forecast"}
      alerts: {path: "onecall"} # OneCall API for alerts, requires lat/lon
    query_param: "q" # For city name

  - name: "WeatherAPI"
    type: "weather"
    endpoint: "http://api.weatherapi.com/v1/"
    key_name: "key"
    key_value: "load_from_secrets.weatherapi_api_key"
    headers: {}
    default_params: {}
    functions:
      current_weather: {path: "current.json"}
      forecast: {path: "forecast.json"}
      historical_weather: {path: "history.json"}
    query_param: "q" # For city name
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

    print("\n--- Testing weather_tool functions ---")
    test_user = "test_user_weather"
    
    if config_manager:
        # Test weather_search_web
        print("\n--- Testing weather_search_web ---")
        search_query = "effects of climate change on sea levels"
        search_result = weather_search_web(search_query, user_token=test_user)
        print(f"Search Result for '{search_query}':\n{search_result[:500]}...")

        # Prepare dummy data for weather_query_uploaded_docs
        print("\n--- Preparing dummy data for weather_query_uploaded_docs ---")
        dummy_json_path = Path("temp_weather_docs.json")
        dummy_data = [
            {"id": 1, "text": "Summary of the latest climate model predictions for global temperature rise.", "category": "climate_models"},
            {"id": 2, "text": "Notes on local weather patterns in my region over the past decade.", "category": "local_weather"},
            {"id": 3, "text": "Research paper on the frequency of extreme weather events.", "category": "extreme_weather"}
        ]
        with open(dummy_json_path, "w", encoding="utf-8") as f:
            json.dump(dummy_data, f)
        
        # Load documents from the dummy JSON for build_vectorstore
        loaded_docs_for_vector = load_docs_from_json_file(dummy_json_path)
        for i, doc in enumerate(loaded_docs_for_vector):
            doc.page_content = dummy_data[i]["text"]

        build_vectorstore(test_user, WEATHER_SECTION, loaded_docs_for_vector, chunk_size=200, chunk_overlap=0)
        print(f"Vectorstore built for {WEATHER_SECTION}.")

        # Test weather_query_uploaded_docs
        print("\n--- Testing weather_query_uploaded_docs ---")
        doc_query = "What did I upload about extreme weather?"
        doc_results = weather_query_uploaded_docs(doc_query, user_token=test_user)
        print(f"Query uploaded docs for '{doc_query}':\n{doc_results}")

        # Test weather_summarize_document_by_path
        print("\n--- Testing weather_summarize_document_by_path ---")
        # Create a dummy upload directory and file
        test_upload_dir = Path("uploads") / test_user / WEATHER_SECTION
        test_upload_dir.mkdir(parents=True, exist_ok=True)
        summarize_file_path = test_upload_dir / "weather_report.txt"
        with open(summarize_file_path, "w") as f:
            f.write("This report analyzes the unusually high temperatures recorded last summer. " * 30 + 
                    "It discusses potential causes, including a persistent high-pressure system and climate change factors. " * 20 +
                    "The impact on local agriculture and water resources is also examined." * 25)
        print(f"Created dummy file for summarization: {summarize_file_path}")

        summary_result = weather_summarize_document_by_path(str(summarize_file_path))
        print(summary_result)

        # Test weather_data_fetcher (mocked)
        print("\n--- Testing weather_data_fetcher (mocked) ---")
        current_weather = weather_data_fetcher(api_name="OpenWeatherMap", data_type="current_weather", location="London")
        print(f"Current Weather (London, OpenWeatherMap): {current_weather}")
        forecast_5_days = weather_data_fetcher(api_name="OpenWeatherMap", data_type="forecast", location="Paris", days=5)
        print(f"5-day Forecast (Paris, OpenWeatherMap): {forecast_5_days[:200]}...")
        historical_weather = weather_data_fetcher(api_name="WeatherAPI", data_type="historical_weather", location="Berlin", start_date="2024-06-01", end_date="2024-06-02")
        print(f"Historical Weather (Berlin, WeatherAPI): {historical_weather[:200]}...")

        # Test climate_info_explainer
        print("\n--- Testing climate_info_explainer ---")
        climate_explanation = climate_info_explainer("greenhouse effect")
        print(f"Explanation of 'Greenhouse Effect':\n{climate_explanation}")

        # Test weather_alert_checker
        print("\n--- Testing weather_alert_checker ---")
        alerts_check = weather_alert_checker("New York City")
        print(f"Weather Alerts (New York City): {alerts_check}")

        # Test python_interpreter (example with mock data)
        print("\n--- Testing python_interpreter with mock data ---")
        python_code_weather_data = """
import json
import pandas as pd
mock_forecast_data = '''{
    "location": "Test City",
    "forecast": [
        {"date": "2024-07-01", "temp_max": "28°C", "temp_min": "18°C", "conditions": "Sunny"},
        {"date": "2024-07-02", "temp_max": "26°C", "temp_min": "17°C", "conditions": "Cloudy"},
        {"date": "2024-07-03", "temp_max": "29°C", "temp_min": "19°C", "conditions": "Clear"}
    ]
}'''
data = json.loads(mock_forecast_data)
df = pd.DataFrame(data['forecast'])
df['temp_max_c'] = df['temp_max'].str.extract('(\d+)').astype(float)
print(f"Average max temperature: {df['temp_max_c'].mean()}°C")
"""
        print(f"Executing Python code:\n{python_code_weather_data}")
        try:
            repl_output = python_repl.run(python_code_weather_data)
            print(f"Python REPL Output:\n{repl_output}")
        except Exception as e:
            print(f"Error executing Python REPL: {e}. Make sure pandas, numpy, json are installed.")


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
        dummy_medical_apis_path = dummy_data_dir / "medical_apis.yaml"
        dummy_legal_apis_path = dummy_data_dir / "legal_apis.yaml"
        dummy_weather_apis_path = dummy_data_dir / "weather_apis.yaml"

        if dummy_config_path.exists(): os.remove(dummy_config_path)
        if dummy_sports_apis_path.exists(): os.remove(dummy_sports_apis_path)
        if dummy_media_apis_path.exists(): os.remove(dummy_media_apis_path)
        if dummy_finance_apis_path.exists(): os.remove(dummy_finance_apis_path)
        if dummy_medical_apis_path.exists(): os.remove(dummy_medical_apis_path)
        if dummy_legal_apis_path.exists(): os.remove(dummy_legal_apis_path)
        if dummy_weather_apis_path.exists(): os.remove(dummy_weather_apis_path)
        if not os.listdir(dummy_data_dir):
            os.rmdir(dummy_data_dir)
