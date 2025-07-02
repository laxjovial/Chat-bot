# sports_query_app.py

import streamlit as st
import logging

# Assume config_manager and get_user_token exist
from config.config_manager import config_manager
from utils.user_manager import get_user_token

from sports_tools.sports_tool import sports_search_web

logging.basicConfig(level=logging.INFO)

# --- Configuration (Minimal setup, assumes config_manager is globally accessible) ---
def initialize_config():
    """Initializes the config_manager and st.secrets."""
    if not hasattr(st, 'secrets'):
        class MockSecrets:
            def __init__(self):
                self.serpapi = {"api_key": "YOUR_SERPAPI_KEY"} # Replace with your real SerpAPI key
                self.google = {"api_key": "YOUR_GOOGLE_API_KEY"}
                self.google_custom_search = {"api_key": "YOUR_GOOGLE_CUSTOM_SEARCH_API_KEY"}
        st.secrets = MockSecrets()
        logging.info("Mocked st.secrets for standalone testing.")
    
    if not hasattr(config_manager, '_instance') or config_manager._instance is None:
        try:
            # You might need to create a dummy config.yml in the 'data' directory for initialization
            logging.info("ConfigManager assumed to be initialized by importing. Ensure data/config.yml exists.")
        except Exception as e:
            st.error(f"Failed to initialize configuration: {e}. Please ensure data/config.yml and .streamlit/secrets.toml are set up correctly.")
            st.stop()

initialize_config()


# --- Streamlit UI ---
st.set_page_config(page_title="Sports Web Query", page_icon="🌐")
st.title("Sports Web Query 🌐")

st.write("Query the web for sports-related information.")

user_token = get_user_token() # Get user token for personalization

query = st.text_input("Enter your sports query:")
max_chars = st.slider("Maximum characters in result:", min_value=100, max_value=5000, value=1500, step=100)

if st.button("Search"):
    if query:
        with st.spinner("Searching the web..."):
            try:
                result = sports_search_web(query=query, user_token=user_token, max_chars=max_chars)
                st.subheader("Search Results:")
                st.markdown(result)
            except Exception as e:
                st.error(f"An error occurred during web search: {e}")
                logging.error(f"Web search failed: {e}", exc_info=True)
    else:
        st.warning("Please enter a query to search.")
