# medical_query_app.py

import streamlit as st
import logging
import json
import pandas as pd # Potentially useful for displaying structured data

# Assume config_manager and get_user_token exist
from config.config_manager import config_manager
from utils.user_manager import get_user_token

from medical_tools.medical_tool import (
    medical_search_web, 
    medical_data_fetcher,
    symptom_checker,
    first_aid_instructions,
    health_tip_generator,
    emergency_locator,
    world_health_updates
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
                self.health_api_key = "YOUR_HEALTH_API_KEY_HERE"
                self.who_api_key = "YOUR_WHO_API_KEY_HERE"
                self.google_maps_api_key = "YOUR_GOOGLE_MAPS_API_KEY_HERE"
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
st.set_page_config(page_title="Medical Query Tools", page_icon="💊", layout="centered")
st.title("Medical Query Tools 💊")

st.markdown("Access various medical and health-related tools directly.")

user_token = get_user_token() # Get user token for personalization

tool_selection = st.selectbox(
    "Select a Medical Tool:",
    (
        "Web Search (General Health Info)",
        "Symptom Checker",
        "First Aid Instructions",
        "Health Tip Generator",
        "Emergency Locator",
        "World Health Updates",
        "Medical Data Fetcher (Advanced)"
    )
)

# --- Web Search ---
if tool_selection == "Web Search (General Health Info)":
    st.subheader("General Health Web Search")
    query = st.text_input("Enter your health-related web query:", placeholder="e.g., 'latest research on diabetes', 'benefits of mindfulness'")
    max_chars = st.slider("Maximum characters in result snippet:", min_value=100, max_value=5000, value=1500, step=100)

    if st.button("Search Web"):
        if query:
            with st.spinner("Searching the web..."):
                try:
                    result = medical_search_web(query=query, user_token=user_token, max_chars=max_chars)
                    st.subheader("Search Results:")
                    st.markdown(result)
                except Exception as e:
                    st.error(f"An error occurred during web search: {e}")
                    logger.error(f"Web search failed: {e}", exc_info=True)
        else:
            st.warning("Please enter a query to search.")

# --- Symptom Checker ---
elif tool_selection == "Symptom Checker":
    st.subheader("Symptom Checker")
    st.warning("**Disclaimer:** This tool provides general information and is NOT a substitute for professional medical advice, diagnosis, or treatment. Always consult a qualified healthcare provider for any health concerns.")
    symptoms_input = st.text_input("Enter comma-separated symptoms (e.g., fever, cough, headache):", placeholder="fever, cough, sore throat")
    
    if st.button("Check Symptoms"):
        if symptoms_input:
            with st.spinner("Checking symptoms..."):
                try:
                    result = symptom_checker(symptoms=symptoms_input)
                    st.subheader("Possible Conditions:")
                    st.markdown(result)
                except Exception as e:
                    st.error(f"An error occurred during symptom check: {e}")
                    logger.error(f"Symptom checker failed: {e}", exc_info=True)
        else:
            st.warning("Please enter symptoms.")

# --- First Aid Instructions ---
elif tool_selection == "First Aid Instructions":
    st.subheader("First Aid Instructions")
    condition_input = st.text_input("Enter condition or injury for first aid (e.g., cuts, burns, choking, sprain):", placeholder="minor cut")
    
    if st.button("Get First Aid"):
        if condition_input:
            with st.spinner("Retrieving first aid steps..."):
                try:
                    result = first_aid_instructions(condition=condition_input)
                    st.subheader(f"First Aid for '{condition_input}':")
                    st.markdown(result)
                except Exception as e:
                    st.error(f"An error occurred while getting first aid instructions: {e}")
                    logger.error(f"First aid tool failed: {e}", exc_info=True)
        else:
            st.warning("Please enter a condition.")

# --- Health Tip Generator ---
elif tool_selection == "Health Tip Generator":
    st.subheader("Health Tip Generator")
    topic_input = st.text_input("Enter topic for health tip (optional, e.g., sleep, nutrition, exercise):", placeholder="general")
    
    if st.button("Get Health Tip"):
        with st.spinner("Generating health tip..."):
            try:
                result = health_tip_generator(topic=topic_input if topic_input else "general")
                st.subheader("Your Health Tip:")
                st.markdown(result)
            except Exception as e:
                st.error(f"An error occurred while generating health tip: {e}")
                logger.error(f"Health tip generator failed: {e}", exc_info=True)

# --- Emergency Locator ---
elif tool_selection == "Emergency Locator":
    st.subheader("Emergency Services Locator")
    location_input = st.text_input("Enter your location (e.g., London, New York City, or 'near me'):", placeholder="London")
    
    if st.button("Find Emergency Services"):
        if location_input:
            with st.spinner("Finding emergency services..."):
                try:
                    result = emergency_locator(location=location_input)
                    st.subheader(f"Emergency Services near '{location_input}':")
                    try:
                        parsed_data = json.loads(result)
                        if isinstance(parsed_data, list):
                            for service in parsed_data:
                                st.write(f"**{service.get('name')}** ({service.get('type')}): {service.get('address')} - {service.get('distance')}")
                        else:
                            st.json(parsed_data) # Fallback if structure is unexpected
                    except json.JSONDecodeError:
                        st.write(result) # Display raw if not JSON
                except Exception as e:
                    st.error(f"An error occurred while locating emergency services: {e}")
                    logger.error(f"Emergency locator failed: {e}", exc_info=True)
        else:
            st.warning("Please enter a location.")

# --- World Health Updates ---
elif tool_selection == "World Health Updates":
    st.subheader("World Health Updates")
    if st.button("Get World Health Updates"):
        with st.spinner("Fetching world health updates..."):
            try:
                result = world_health_updates()
                st.subheader("Recent Global Health News:")
                try:
                    parsed_data = json.loads(result)
                    if isinstance(parsed_data, list):
                        for update in parsed_data:
                            st.write(f"**{update.get('title')}** ({update.get('date')}) - *Source: {update.get('source')}*")
                    else:
                        st.json(parsed_data)
                except json.JSONDecodeError:
                    st.write(result)
            except Exception as e:
                st.error(f"An error occurred while fetching world health updates: {e}")
                logger.error(f"World health updates failed: {e}", exc_info=True)

# --- Medical Data Fetcher (Advanced) ---
elif tool_selection == "Medical Data Fetcher (Advanced)":
    st.subheader("Advanced Medical Data Fetcher")
    st.info("This tool directly interacts with configured medical APIs. Note that many real medical APIs require specific access and may have usage limits.")

    api_name = st.selectbox(
        "Select API to use:",
        ("HealthAPI", "WHO_API", "GoogleMapsAPI"),
        help="Choose the API best suited for your data type. (Note: These are placeholders in medical_tool.py)"
    )

    data_type_options = []
    if api_name == "HealthAPI":
        data_type_options = ["symptoms_list", "conditions_list", "symptom_checker"]
    elif api_name == "WHO_API":
        data_type_options = ["world_health_updates"]
    elif api_name == "GoogleMapsAPI":
        data_type_options = ["emergency_services"]

    data_type = st.selectbox(
        "Select Data Type:",
        data_type_options,
        key="medical_data_type_select"
    )

    query_input = None
    location_input = None
    symptoms_input_fetcher = None
    
    if data_type == "symptom_checker" and api_name == "HealthAPI":
        symptoms_input_fetcher = st.text_input("Enter comma-separated symptoms:", key="symptoms_input_fetcher")
    elif data_type == "emergency_services" and api_name == "GoogleMapsAPI":
        location_input = st.text_input("Enter location:", key="location_input_fetcher")
    elif data_type in ["symptoms_list", "conditions_list"] and api_name == "HealthAPI":
        query_input = st.text_input("Enter optional query (e.g., 'common', 'infectious'):", key="query_input_fetcher")

    limit_input = st.number_input("Limit results (optional):", min_value=1, value=10, step=1, key="limit_input_fetcher")

    if st.button("Fetch Medical Data"):
        with st.spinner(f"Fetching {data_type} data from {api_name}..."):
            try:
                result_json_str = medical_data_fetcher(
                    api_name=api_name,
                    data_type=data_type,
                    query=query_input,
                    location=location_input,
                    symptoms=symptoms_input_fetcher,
                    limit=limit_input
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
                logger.error(f"Medical data fetcher failed: {e}", exc_info=True)


st.markdown("---")
st.caption(f"Current User Token: `{get_user_token()}` (for demo purposes)")
st.caption("This app provides direct access to various medical tools. Remember to always consult a healthcare professional for medical advice.")
