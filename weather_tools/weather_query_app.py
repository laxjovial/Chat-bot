# ui/weather_query_app.py

import streamlit as st
import logging
import json
import pandas as pd # Potentially useful for displaying structured data
from datetime import datetime, timedelta # For date inputs

# Assume config_manager and get_user_token exist
from config.config_manager import config_manager
from utils.user_manager import get_current_user, get_user_tier_capability # Import for RBAC

from weather_tools.weather_tool import (
    weather_search_web, 
    weather_data_fetcher
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration Initialization ---
def initialize_app_config():
    """
    Initializes the config_manager and ensures Streamlit secrets are accessible.
    This function is called once at the start of the app.
    """
    if not hasattr(st, 'secrets'):
        class MockSecrets:
            def __init__(self):
                self.serpapi = {"api_key": "YOUR_SERPAPI_KEY_HERE"}
                self.google = {"api_key": "AIzaSy_YOUR_GOOGLE_API_KEY_HERE"}
                self.google_custom_search = {"api_key": "YOUR_GOOGLE_CUSTOM_SEARCH_API_KEY_HERE"}
                self.openweathermap_api_key = "YOUR_OPENWEATHERMAP_API_KEY_HERE" # For weather_data_fetcher
        st.secrets = MockSecrets()
        logger.info("Mocked st.secrets for standalone testing.")
    
    if not config_manager._is_loaded:
        try:
            logger.info("ConfigManager assumed to be initialized by importing. Ensure data/config.yml and other config files exist.")
        except Exception as e:
            st.error(f"Failed to initialize configuration: {e}. Please ensure data/config.yml and .streamlit/secrets.toml are set up correctly.")
            st.stop()

initialize_app_config()

# --- RBAC Access Check at the Top of the App ---
current_user = get_current_user()
user_tier = current_user.get('tier', 'free')
user_roles = current_user.get('roles', [])

# Define the required tier for this specific page (Weather Query Tools)
# This should match the 'tier_access' defined in main_app.py for this page.
REQUIRED_TIER_FOR_THIS_PAGE = "free" 

# Check if user is logged in and has the required tier or admin role
if not current_user:
    st.warning("⚠️ You must be logged in to access this page.")
    st.stop() # Halts execution
else:
    # Import TIER_HIERARCHY from main_app for comparison
    try:
        from main_app import TIER_HIERARCHY
    except ImportError:
        st.error("Error: Could not load tier hierarchy for access control. Please ensure main_app.py is accessible.")
        st.stop()

    if not (user_tier and user_roles and (TIER_HIERARCHY.get(user_tier, -1) >= TIER_HIERARCHY.get(REQUIRED_TIER_FOR_THIS_PAGE, -1) or "admin" in user_roles)):
        st.error(f"🚫 Access Denied: Your current tier ({user_tier.capitalize()}) does not have access to the Weather Query Tools. Please upgrade your plan to {REQUIRED_TIER_FOR_THIS_PAGE.capitalize()} or higher.")
        st.stop() # Halts execution
# --- End RBAC Access Check ---


# --- Streamlit UI ---
st.set_page_config(page_title="Weather Query Tools", page_icon="☁️", layout="centered")
st.title("Weather Query Tools ☁️")

st.markdown("Access various weather-related tools directly.")

user_token = current_user.get('user_id', 'default') # Get user token for personalization

tool_selection = st.selectbox(
    "Select a Weather Tool:",
    (
        "Web Search (General Weather Info)",
        "Weather Data Fetcher (Advanced)"
    )
)

# --- Web Search ---
if tool_selection == "Web Search (General Weather Info)":
    st.subheader("General Weather Web Search")
    query = st.text_input("Enter your weather web query:", placeholder="e.g., 'impact of climate change on agriculture', 'history of hurricanes'")
    
    # RBAC for max_chars in web search
    allowed_max_chars = get_user_tier_capability(user_token, 'web_search_limit_chars', 2000)
    max_chars = st.slider(f"Maximum characters in result snippet (Max for your tier: {allowed_max_chars}):", min_value=100, max_value=allowed_max_chars, value=min(1500, allowed_max_chars), step=100)

    if st.button("Search Web"):
        if query:
            with st.spinner("Searching the web..."):
                try:
                    result = weather_search_web(query=query, user_token=user_token, max_chars=max_chars)
                    st.subheader("Search Results:")
                    st.markdown(result)
                except Exception as e:
                    st.error(f"An error occurred during web search: {e}")
                    logger.error(f"Web search failed: {e}", exc_info=True)
        else:
            st.warning("Please enter a query to search.")

# --- Weather Data Fetcher (Advanced) ---
elif tool_selection == "Weather Data Fetcher (Advanced)":
    st.subheader("Advanced Weather Data Fetcher")
    st.info("This tool directly interacts with configured weather APIs. Note that many real APIs require specific access and may have usage limits.")

    api_name = st.selectbox(
        "Select API to use:",
        ("OpenWeatherMap",), # Add more APIs as configured in weather_apis.yaml
        key="advanced_api_select"
    )

    data_type_options = []
    if api_name == "OpenWeatherMap":
        data_type_options = ["current_weather", "forecast_weather", "historical_weather"]
    # Add logic for other APIs if they have different data types

    data_type = st.selectbox(
        "Select Data Type:",
        data_type_options,
        key="weather_data_type_select"
    )

    location_input = st.text_input("Location (city name, e.g., London, New York):", key="location_input_adv")
    days_input = None
    if data_type == "forecast_weather":
        days_input = st.number_input("Number of forecast days (max 5 for OpenWeatherMap free tier):", min_value=1, max_value=5, value=3, step=1, key="days_input_adv")
    elif data_type == "historical_weather":
        st.warning("Historical weather data for OpenWeatherMap usually requires a paid plan or specific endpoints. This is a placeholder.")
        start_date_input = st.date_input("Start Date (YYYY-MM-DD):", datetime.today() - timedelta(days=7), key="start_date_input_adv")
        end_date_input = st.date_input("End Date (YYYY-MM-DD):", datetime.today(), key="end_date_input_adv")
        # Convert to Unix timestamps if the API requires it
        start_timestamp = int(datetime.combine(start_date_input, datetime.min.time()).timestamp()) if start_date_input else None
        end_timestamp = int(datetime.combine(end_date_input, datetime.max.time()).timestamp()) if end_date_input else None
        st.info(f"Start Timestamp: {start_timestamp}, End Timestamp: {end_timestamp}")


    units_input = st.selectbox("Units:", ("metric", "imperial"), key="units_input_adv")
    limit_input = st.number_input("Limit results (optional):", min_value=1, value=1, step=1, key="limit_input_fetcher") # Limit for general results, not time series

    if st.button("Fetch Advanced Weather Data"):
        if not location_input:
            st.warning("Please enter a location.")
        else:
            with st.spinner(f"Fetching {data_type} data from {api_name}..."):
                try:
                    result_json_str = weather_data_fetcher(
                        api_name=api_name,
                        data_type=data_type,
                        location=location_input,
                        days=days_input,
                        units=units_input,
                        # For historical, pass timestamps if the tool expects them
                        start_date=str(start_date_input) if data_type == "historical_weather" else None,
                        end_date=str(end_date_input) if data_type == "historical_weather" else None,
                        limit=limit_input if limit_input > 0 else None
                    )
                    
                    st.subheader("Fetched Data:")
                    try:
                        parsed_data = json.loads(result_json_str)
                        st.json(parsed_data)
                        
                        # Attempt to display as DataFrame if suitable
                        if isinstance(parsed_data, dict) and 'list' in parsed_data: # For OpenWeatherMap forecast
                            df = pd.DataFrame(parsed_data['list'])
                            # Extract relevant columns and flatten if needed
                            if 'main' in df.columns and 'weather' in df.columns:
                                df['temp'] = df['main'].apply(lambda x: x.get('temp'))
                                df['feels_like'] = df['main'].apply(lambda x: x.get('feels_like'))
                                df['description'] = df['weather'].apply(lambda x: x[0].get('description') if x else None)
                                df['dt_txt'] = pd.to_datetime(df['dt_txt'])
                                st.subheader("Forecast Data as DataFrame:")
                                st.dataframe(df[['dt_txt', 'temp', 'feels_like', 'description', 'pop', 'wind']].head(limit_input))
                            else:
                                st.dataframe(df.head(limit_input))
                        elif isinstance(parsed_data, dict): # For current weather
                            st.write("Data is a dictionary (current weather or single item).")

                    except json.JSONDecodeError:
                        st.write(result_json_str) # If not JSON, display as plain text
                    
                except Exception as e:
                    st.error(f"An error occurred during data fetching: {e}")
                    logger.error(f"Weather data fetcher failed: {e}", exc_info=True)


st.markdown("---")
st.caption(f"Current User Token: `{current_user.get('user_id', 'N/A')}` (for demo purposes)")
st.caption("This app provides direct access to various weather tools.")
