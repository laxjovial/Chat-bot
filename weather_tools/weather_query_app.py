# weather_query_app.py

import streamlit as st
import logging
import json
import pandas as pd # Potentially useful for displaying structured data

# Assume config_manager and get_user_token exist
from config.config_manager import config_manager
from utils.user_manager import get_user_token

from weather_tools.weather_tool import (
    weather_search_web, 
    weather_data_fetcher,
    climate_info_explainer,
    weather_alert_checker
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
                self.openweathermap_api_key = "YOUR_OPENWEATHERMAP_API_KEY_HERE"
                self.weatherapi_api_key = "YOUR_WEATHERAPI_API_KEY_HERE"
        st.secrets = MockSecrets()
        logger.info("Mocked st.secrets for standalone testing.")
    
    if not config_manager._is_loaded:
        try:
            logger.info("ConfigManager assumed to be initialized by importing. Ensure data/config.yml and other config files exist.")
        except Exception as e:
            st.error(f"Failed to initialize configuration: {e}. Please ensure data/config.yml and .streamlit/secrets.toml are set up correctly.")
            st.stop()

initialize_app_config()


# --- Streamlit UI ---
st.set_page_config(page_title="Weather Query Tools", page_icon="🌤️", layout="centered")
st.title("Weather Query Tools 🌤️")

st.markdown("Access various weather and climate-related tools directly.")

user_token = get_user_token() # Get user token for personalization

tool_selection = st.selectbox(
    "Select a Weather Tool:",
    (
        "Web Search (General Weather/Climate Info)",
        "Current Weather",
        "Weather Forecast",
        "Historical Weather (requires WeatherAPI.com)",
        "Weather Alerts",
        "Climate Info Explainer",
        "Weather Data Fetcher (Advanced)"
    )
)

# --- Web Search ---
if tool_selection == "Web Search (General Weather/Climate Info)":
    st.subheader("General Weather/Climate Web Search")
    query = st.text_input("Enter your weather/climate web query:", placeholder="e.g., 'impact of El Nino on rainfall', 'how do tornadoes form'")
    max_chars = st.slider("Maximum characters in result snippet:", min_value=100, max_value=5000, value=1500, step=100)

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

# --- Current Weather ---
elif tool_selection == "Current Weather":
    st.subheader("Current Weather")
    location_input = st.text_input("Enter location (city, zip code, or lat/lon):", placeholder="London")
    units_input = st.radio("Units:", ("metric (Celsius)", "imperial (Fahrenheit)"), key="current_weather_units")
    
    if st.button("Get Current Weather"):
        if location_input:
            with st.spinner("Fetching current weather..."):
                try:
                    result = weather_data_fetcher(
                        api_name="OpenWeatherMap", # Can choose either, OpenWeatherMap is common
                        data_type="current_weather",
                        location=location_input,
                        units="metric" if units_input == "metric (Celsius)" else "imperial"
                    )
                    st.subheader(f"Current Weather for '{location_input}':")
                    try:
                        parsed_data = json.loads(result)
                        st.json(parsed_data)
                        # Display a more user-friendly summary
                        if parsed_data.get('location'):
                            temp_unit = "°C" if units_input == "metric (Celsius)" else "°F"
                            temp = parsed_data.get('temperature') or parsed_data.get('temp_c') or parsed_data.get('temp_f')
                            if isinstance(temp, (int, float)):
                                if units_input == "metric (Celsius)":
                                    temp = f"{temp}°C"
                                else:
                                    temp = f"{temp}°F"
                            
                            st.write(f"**Location:** {parsed_data.get('location')}")
                            st.write(f"**Temperature:** {temp}")
                            st.write(f"**Conditions:** {parsed_data.get('conditions') or parsed_data.get('condition')}")
                            st.write(f"**Humidity:** {parsed_data.get('humidity')}%")
                            st.write(f"**Wind Speed:** {parsed_data.get('wind_speed') or parsed_data.get('wind_kph') or parsed_data.get('wind_mph')}")
                        else:
                            st.write("Could not parse detailed weather info.")
                    except json.JSONDecodeError:
                        st.write(result)
                except Exception as e:
                    st.error(f"An error occurred while fetching current weather: {e}")
                    logger.error(f"Current weather fetch failed: {e}", exc_info=True)
        else:
            st.warning("Please enter a location.")

# --- Weather Forecast ---
elif tool_selection == "Weather Forecast":
    st.subheader("Weather Forecast")
    location_input = st.text_input("Enter location (city, zip code, or lat/lon):", key="forecast_location_input", placeholder="Paris")
    days_input = st.slider("Number of days for forecast:", min_value=1, max_value=14, value=3, step=1)
    units_input = st.radio("Units:", ("metric (Celsius)", "imperial (Fahrenheit)"), key="forecast_weather_units")

    if st.button("Get Forecast"):
        if location_input:
            with st.spinner("Fetching weather forecast..."):
                try:
                    result = weather_data_fetcher(
                        api_name="OpenWeatherMap", # Can choose either, OpenWeatherMap is common
                        data_type="forecast",
                        location=location_input,
                        days=days_input,
                        units="metric" if units_input == "metric (Celsius)" else "imperial"
                    )
                    st.subheader(f"{days_input}-Day Forecast for '{location_input}':")
                    try:
                        parsed_data = json.loads(result)
                        if parsed_data.get('forecast'):
                            df = pd.DataFrame(parsed_data['forecast'])
                            # Adjust column names based on OpenWeatherMap or WeatherAPI structure
                            if 'temp_max' in df.columns and 'temp_min' in df.columns:
                                df_display = df[['date', 'temp_max', 'temp_min', 'conditions']]
                            elif 'day' in df.columns and 'maxtemp_c' in df['day'].iloc[0]: # For WeatherAPI.com
                                df_data = []
                                for _, row in df.iterrows():
                                    day_data = row['day']
                                    df_data.append({
                                        'date': row['date'],
                                        'temp_max': f"{day_data['maxtemp_c']}°C" if units_input == "metric (Celsius)" else f"{day_data['maxtemp_f']}°F",
                                        'temp_min': f"{day_data['mintemp_c']}°C" if units_input == "metric (Celsius)" else f"{day_data['mintemp_f']}°F",
                                        'conditions': day_data['condition']['text']
                                    })
                                df_display = pd.DataFrame(df_data)
                            else:
                                df_display = df # Fallback to raw DataFrame
                            
                            st.dataframe(df_display)
                        else:
                            st.json(parsed_data) # Show raw JSON if forecast structure not found
                    except json.JSONDecodeError:
                        st.write(result)
                except Exception as e:
                    st.error(f"An error occurred while fetching forecast: {e}")
                    logger.error(f"Forecast fetch failed: {e}", exc_info=True)
        else:
            st.warning("Please enter a location.")

# --- Historical Weather ---
elif tool_selection == "Historical Weather (requires WeatherAPI.com)":
    st.subheader("Historical Weather Data")
    st.info("This feature requires the 'WeatherAPI' integration. Ensure you have a valid API key for WeatherAPI.com in your `secrets.toml`.")
    location_input = st.text_input("Enter location:", key="historical_location_input", placeholder="Berlin")
    start_date_input = st.date_input("Start Date:", key="historical_start_date")
    end_date_input = st.date_input("End Date:", key="historical_end_date")
    units_input = st.radio("Units:", ("metric (Celsius)", "imperial (Fahrenheit)"), key="historical_weather_units")

    if st.button("Get Historical Weather"):
        if location_input and start_date_input and end_date_input:
            if start_date_input > end_date_input:
                st.error("Start date cannot be after end date.")
            else:
                with st.spinner("Fetching historical weather..."):
                    try:
                        result = weather_data_fetcher(
                            api_name="WeatherAPI", # Explicitly use WeatherAPI for historical
                            data_type="historical_weather",
                            location=location_input,
                            start_date=str(start_date_input),
                            end_date=str(end_date_input),
                            units="metric" if units_input == "metric (Celsius)" else "imperial"
                        )
                        st.subheader(f"Historical Weather for '{location_input}' ({start_date_input} to {end_date_input}):")
                        try:
                            parsed_data = json.loads(result)
                            if parsed_data.get('history') and parsed_data['history'].get('forecastday'):
                                df_data = []
                                for day_entry in parsed_data['history']['forecastday']:
                                    date = day_entry['date']
                                    avg_temp_c = day_entry['day']['avgtemp_c']
                                    avg_temp_f = day_entry['day']['avgtemp_f']
                                    condition = day_entry['day']['condition']['text']
                                    df_data.append({
                                        'date': date,
                                        'avg_temp_c': avg_temp_c,
                                        'avg_temp_f': avg_temp_f,
                                        'condition': condition
                                    })
                                df = pd.DataFrame(df_data)
                                st.dataframe(df)
                            else:
                                st.json(parsed_data)
                        except json.JSONDecodeError:
                            st.write(result)
                    except Exception as e:
                        st.error(f"An error occurred while fetching historical weather: {e}")
                        logger.error(f"Historical weather fetch failed: {e}", exc_info=True)
        else:
            st.warning("Please enter location, start date, and end date.")

# --- Weather Alerts ---
elif tool_selection == "Weather Alerts":
    st.subheader("Severe Weather Alerts")
    location_input = st.text_input("Enter location to check for alerts:", key="alerts_location_input", placeholder="New York City")
    
    if st.button("Check for Alerts"):
        if location_input:
            with st.spinner("Checking for alerts..."):
                try:
                    result = weather_alert_checker(location=location_input)
                    st.subheader(f"Active Weather Alerts for '{location_input}':")
                    try:
                        parsed_data = json.loads(result)
                        if isinstance(parsed_data, list) and parsed_data:
                            for alert in parsed_data:
                                st.write(f"**Type:** {alert.get('type')}")
                                st.write(f"**Area:** {alert.get('area')}")
                                st.write(f"**Expires:** {alert.get('expires')}")
                                st.write(f"**Description:** {alert.get('description')}")
                                st.markdown("---")
                        elif parsed_data.get('alerts'): # For OpenWeatherMap OneCall structure
                            alerts_list = parsed_data['alerts']
                            if alerts_list:
                                for alert in alerts_list:
                                    st.write(f"**Event:** {alert.get('event')}")
                                    st.write(f"**Start:** {pd.to_datetime(alert.get('start'), unit='s')}")
                                    st.write(f"**End:** {pd.to_datetime(alert.get('end'), unit='s')}")
                                    st.write(f"**Description:** {alert.get('description')}")
                                    st.markdown("---")
                            else:
                                st.info("No active severe weather alerts for this location.")
                        else:
                            st.info("No active severe weather alerts for this location.")
                    except json.JSONDecodeError:
                        st.write(result)
                except Exception as e:
                    st.error(f"An error occurred while checking for alerts: {e}")
                    logger.error(f"Weather alert checker failed: {e}", exc_info=True)
        else:
            st.warning("Please enter a location.")

# --- Climate Info Explainer ---
elif tool_selection == "Climate Info Explainer":
    st.subheader("Climate Information Explainer")
    topic_input = st.text_input("Enter a climate topic to explain (e.g., El Nino, Greenhouse Effect, Carbon Sequestration):", placeholder="El Nino")
    
    if st.button("Explain Climate Topic"):
        if topic_input:
            with st.spinner("Explaining climate topic..."):
                try:
                    result = climate_info_explainer(topic=topic_input)
                    st.subheader(f"Explanation of '{topic_input}':")
                    st.markdown(result)
                except Exception as e:
                    st.error(f"An error occurred while explaining the climate topic: {e}")
                    logger.error(f"Climate info explainer failed: {e}", exc_info=True)
        else:
            st.warning("Please enter a climate topic.")

# --- Weather Data Fetcher (Advanced) ---
elif tool_selection == "Weather Data Fetcher (Advanced)":
    st.subheader("Advanced Weather Data Fetcher")
    st.info("This tool directly interacts with configured weather APIs. Note that real weather APIs may require specific access and have usage limits.")

    api_name = st.selectbox(
        "Select API to use:",
        ("OpenWeatherMap", "WeatherAPI"),
        key="advanced_weather_api_select"
    )

    data_type_options = []
    if api_name == "OpenWeatherMap":
        data_type_options = ["current_weather", "forecast", "alerts"]
    elif api_name == "WeatherAPI":
        data_type_options = ["current_weather", "forecast", "historical_weather"]

    data_type = st.selectbox(
        "Select Data Type:",
        data_type_options,
        key="advanced_weather_data_type_select"
    )

    location_input_adv = st.text_input("Location:", key="location_input_adv")
    days_input_adv = st.number_input("Days (for forecast, optional):", min_value=1, max_value=14, value=1, step=1, key="days_input_adv")
    start_date_input_adv = st.date_input("Start Date (for historical, optional):", key="start_date_input_adv")
    end_date_input_adv = st.date_input("End Date (for historical, optional):", key="end_date_input_adv")
    units_input_adv = st.radio("Units:", ("metric", "imperial"), key="units_input_adv")

    if st.button("Fetch Advanced Weather Data"):
        if not location_input_adv:
            st.warning("Location is required for this tool.")
        else:
            with st.spinner(f"Fetching {data_type} data from {api_name}..."):
                try:
                    result_json_str = weather_data_fetcher(
                        api_name=api_name,
                        data_type=data_type,
                        location=location_input_adv,
                        days=days_input_adv if data_type == "forecast" else None,
                        start_date=str(start_date_input_adv) if data_type == "historical_weather" else None,
                        end_date=str(end_date_input_adv) if data_type == "historical_weather" else None,
                        units=units_input_adv
                    )
                    
                    st.subheader("Fetched Data:")
                    try:
                        parsed_data = json.loads(result_json_str)
                        st.json(parsed_data)
                        
                        # Attempt to display as DataFrame if suitable
                        if isinstance(parsed_data, list) and parsed_data:
                            try:
                                df = pd.DataFrame(parsed_data)
                                st.subheader("Data as DataFrame:")
                                st.dataframe(df)
                            except Exception as df_e:
                                logger.warning(f"Could not convert fetched list data to DataFrame: {df_e}")
                                st.write("Could not display as DataFrame.")
                        elif isinstance(parsed_data, dict):
                            st.write("Data is a dictionary.")

                    except json.JSONDecodeError:
                        st.write(result_json_str) # If not JSON, display as plain text
                    
                except Exception as e:
                    st.error(f"An error occurred during data fetching: {e}")
                    logger.error(f"Weather data fetcher failed: {e}", exc_info=True)


st.markdown("---")
st.caption(f"Current User Token: `{get_user_token()}` (for demo purposes)")
st.caption("This app provides direct access to various weather tools.")
