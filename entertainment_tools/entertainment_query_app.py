# entertainment_query_app.py

import streamlit as st
import logging
import json
import pandas as pd # Potentially useful for displaying structured data

# Assume config_manager and get_user_token exist
from config.config_manager import config_manager
from utils.user_manager import get_user_token

from entertainment_tools.entertainment_tool import entertainment_search_web, entertainment_data_fetcher

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
                self.themoviedb_api_key = "YOUR_THEMOVIEDB_API_KEY_HERE"
                self.omdbapi_api_key = "YOUR_OMDBAPI_API_KEY_HERE"
                # self.anilist_api_key = "YOUR_ANILIST_API_KEY_HERE" # If AniList needs a key
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
st.set_page_config(page_title="Entertainment Web & Data Query", page_icon="🎬", layout="centered")
st.title("Entertainment Web & Data Query 🎬")

st.markdown("Query the web for general entertainment news or fetch specific data about movies, music, series, or anime.")

user_token = get_user_token() # Get user token for personalization

query_type = st.radio("Select Query Type:", ("Web Search", "Entertainment Data Fetcher"))

if query_type == "Web Search":
    st.subheader("Web Search for Entertainment News/Information")
    query = st.text_input("Enter your entertainment web query:", placeholder="e.g., 'new movie releases 2024', 'music concert dates', 'anime streaming platforms'")
    max_chars = st.slider("Maximum characters in result snippet:", min_value=100, max_value=5000, value=1500, step=100)

    if st.button("Search Web"):
        if query:
            with st.spinner("Searching the web..."):
                try:
                    result = entertainment_search_web(query=query, user_token=user_token, max_chars=max_chars)
                    st.subheader("Search Results:")
                    st.markdown(result)
                except Exception as e:
                    st.error(f"An error occurred during web search: {e}")
                    logger.error(f"Web search failed: {e}", exc_info=True)
        else:
            st.warning("Please enter a query to search.")

elif query_type == "Entertainment Data Fetcher":
    st.subheader("Fetch Specific Entertainment Data")
    
    api_name = st.selectbox(
        "Select API to use:",
        ("TheMovieDB", "OMDbAPI", "AniList"),
        help="Choose the API best suited for your data type. TheMovieDB for movies/TV, OMDbAPI for movies/series by title/ID, AniList for anime."
    )

    media_type_options = {
        "TheMovieDB": ["movie", "tv", "person"],
        "OMDbAPI": ["movie", "series", "episode"],
        "AniList": ["anime"]
    }
    
    media_type = st.selectbox(
        "Select Media Type:",
        media_type_options.get(api_name, []),
        help="The type of entertainment content you are looking for."
    )

    query_input = st.text_input("Enter Search Query (e.g., 'Inception', 'Attack on Titan'):", key="query_input")
    id_input = st.text_input("Or Enter Specific ID (e.g., TMDB ID, IMDb ID, AniList ID):", key="id_input")
    year_input = st.number_input("Release Year (optional):", min_value=1900, max_value=2100, value=0, step=1, key="year_input")
    limit_input = st.number_input("Limit results (for searches, optional):", min_value=1, value=5, step=1, key="limit_input")

    if st.button("Fetch Data"):
        if not query_input and not id_input:
            st.warning("Please enter either a search query or a specific ID.")
        else:
            with st.spinner(f"Fetching data from {api_name}..."):
                try:
                    result_json_str = entertainment_data_fetcher(
                        api_name=api_name,
                        query=query_input if query_input else None,
                        media_type=media_type if media_type else None,
                        id=id_input if id_input else None,
                        year=year_input if year_input > 0 else None,
                        limit=limit_input if limit_input > 0 else None
                    )
                    
                    st.subheader("Fetched Data:")
                    try:
                        parsed_data = json.loads(result_json_str)
                        st.json(parsed_data)
                        
                        # Optionally display as DataFrame if suitable (e.g., list of results)
                        if isinstance(parsed_data, list) and parsed_data:
                            try:
                                df = pd.DataFrame(parsed_data)
                                st.subheader("Data as DataFrame:")
                                st.dataframe(df)
                            except Exception as df_e:
                                logger.warning(f"Could not convert fetched data to DataFrame: {df_e}")
                                st.write("Could not display as DataFrame.")
                        elif isinstance(parsed_data, dict):
                            st.write("Data is a dictionary (single item or overview).")

                    except json.JSONDecodeError:
                        st.write(result_json_str) # If not JSON, display as plain text
                    
                except Exception as e:
                    st.error(f"An error occurred during data fetching: {e}")
                    logger.error(f"Entertainment data fetcher failed: {e}", exc_info=True)

st.markdown("---")
st.caption(f"Current User Token: `{get_user_token()}` (for demo purposes)")
st.caption("This app uses web scraping and dedicated entertainment API tools.")
