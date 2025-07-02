# sports_query_app.py

import streamlit as st
import logging

# Assume config_manager and get_user_token exist
from config.config_manager import config_manager
from utils.user_manager import get_user_token

from sports_tools.sports_tool import sports_search_web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration Initialization ---
def initialize_app_config():
    """
    Initializes the config_manager and ensures Streamlit secrets are accessible.
    This function is called once at the start of the app.
    """
    if not hasattr(st, 'secrets'):
        # This block is mainly for local testing outside of Streamlit's native 'secrets.toml'
        class MockSecrets:
            def __init__(self):
                self.serpapi = {"api_key": "YOUR_SERPAPI_KEY_HERE"} # Replace with your real SerpAPI key
                self.google = {"api_key": "AIzaSy_YOUR_GOOGLE_API_KEY_HERE"} # Replace with your real Google API key
                self.google_custom_search = {"api_key": "YOUR_GOOGLE_CUSTOM_SEARCH_API_KEY_HERE"} # Replace with your real GCSE API key
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
st.set_page_config(page_title="Sports Web Query", page_icon="🌐", layout="centered")
st.title("Sports Web Query 🌐")

st.markdown("Search the web for sports-related information using the integrated search tools.")

user_token = get_user_token() # Get user token for personalization

query = st.text_input("Enter your sports query:", placeholder="e.g., 'latest Premier League results', 'who is the top scorer in La Liga?'")
max_chars = st.slider("Maximum characters in result snippet:", min_value=100, max_value=5000, value=1500, step=100)

if st.button("Search"):
    if query:
        with st.spinner("Searching the web..."):
            try:
                # Call the sports_search_web tool
                result = sports_search_web(query=query, user_token=user_token, max_chars=max_chars)
                st.subheader("Search Results:")
                st.markdown(result)
            except Exception as e:
                st.error(f"An error occurred during web search: {e}")
                logger.error(f"Web search failed: {e}", exc_info=True)
    else:
        st.warning("Please enter a query to search.")

st.markdown("---")
st.caption(f"Current User Token: `{get_user_token()}` (for demo purposes)")
st.caption("This app uses web scraping tools to fetch real-time sports data.")
