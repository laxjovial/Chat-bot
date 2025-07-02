# ui/entertainment_query_app.py

import streamlit as st
import logging
import json
import pandas as pd # Potentially useful for displaying structured data

# Assume config_manager and get_user_token exist
from config.config_manager import config_manager
from utils.user_manager import get_current_user, get_user_tier_capability # Import for RBAC

from entertainment_tools.entertainment_tool import (
    entertainment_search_web, 
    entertainment_data_fetcher
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
                self.themoviedb_api_key = "YOUR_THEMOVIEDB_API_KEY_HERE"
                self.omdbapi_api_key = "YOUR_OMDBAPI_API_KEY_HERE"
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

# Define the required tier for this specific page (Entertainment Query Tools)
# This should match the 'tier_access' defined in main_app.py for this page.
REQUIRED_TIER_FOR_THIS_PAGE = "basic" 

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
        st.error(f"🚫 Access Denied: Your current tier ({user_tier.capitalize()}) does not have access to the Entertainment Query Tools. Please upgrade your plan to {REQUIRED_TIER_FOR_THIS_PAGE.capitalize()} or higher.")
        st.stop() # Halts execution
# --- End RBAC Access Check ---


# --- Streamlit UI ---
st.set_page_config(page_title="Entertainment Query Tools", page_icon="🎬", layout="centered")
st.title("Entertainment Query Tools 🎬")

st.markdown("Access various entertainment-related tools directly.")

user_token = current_user.get('user_id', 'default') # Get user token for personalization

tool_selection = st.selectbox(
    "Select an Entertainment Tool:",
    (
        "Web Search (General Entertainment Info)",
        "Movie Search",
        "TV Series Search",
        "Music Search",
        "Anime Search",
        "Entertainment Data Fetcher (Advanced)"
    )
)

# --- Web Search ---
if tool_selection == "Web Search (General Entertainment Info)":
    st.subheader("General Entertainment Web Search")
    query = st.text_input("Enter your entertainment web query:", placeholder="e.g., 'latest movie trailers', 'music festival announcements'")
    
    # RBAC for max_chars in web search
    allowed_max_chars = get_user_tier_capability(user_token, 'web_search_limit_chars', 2000)
    max_chars = st.slider(f"Maximum characters in result snippet (Max for your tier: {allowed_max_chars}):", min_value=100, max_value=allowed_max_chars, value=min(1500, allowed_max_chars), step=100)

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

# --- Movie Search ---
elif tool_selection == "Movie Search":
    st.subheader("Movie Search")
    movie_query = st.text_input("Enter movie title:", placeholder="Inception")
    movie_year = st.text_input("Year (optional):", placeholder="2010")
    
    if st.button("Search Movie"):
        if movie_query:
            with st.spinner(f"Searching for movie '{movie_query}'..."):
                try:
                    result = entertainment_data_fetcher(
                        api_name="TheMovieDB", # Using TheMovieDB as primary
                        data_type="movie",
                        query=movie_query,
                        year=movie_year if movie_year else None
                    )
                    st.subheader(f"Movie Search Results for '{movie_query}':")
                    try:
                        parsed_data = json.loads(result)
                        if parsed_data.get('results'):
                            df = pd.DataFrame(parsed_data['results'])
                            # Display relevant columns for movies
                            st.dataframe(df[['title', 'release_date', 'vote_average', 'overview']].head())
                        else:
                            st.info("No movie found with that title.")
                            st.json(parsed_data) # Show raw if no results
                    except json.JSONDecodeError:
                        st.write(result)
                except Exception as e:
                    st.error(f"An error occurred during movie search: {e}")
                    logger.error(f"Movie search failed: {e}", exc_info=True)
        else:
            st.warning("Please enter a movie title.")

# --- TV Series Search ---
elif tool_selection == "TV Series Search":
    st.subheader("TV Series Search")
    series_query = st.text_input("Enter TV series title:", placeholder="Breaking Bad")
    series_year = st.text_input("Year (optional):", placeholder="2008")
    
    if st.button("Search TV Series"):
        if series_query:
            with st.spinner(f"Searching for TV series '{series_query}'..."):
                try:
                    result = entertainment_data_fetcher(
                        api_name="TheMovieDB", # Using TheMovieDB as primary
                        data_type="tv_series",
                        query=series_query,
                        year=series_year if series_year else None
                    )
                    st.subheader(f"TV Series Search Results for '{series_query}':")
                    try:
                        parsed_data = json.loads(result)
                        if parsed_data.get('results'):
                            df = pd.DataFrame(parsed_data['results'])
                            # Display relevant columns for TV series
                            st.dataframe(df[['name', 'first_air_date', 'vote_average', 'overview']].head())
                        else:
                            st.info("No TV series found with that title.")
                            st.json(parsed_data)
                    except json.JSONDecodeError:
                        st.write(result)
                except Exception as e:
                    st.error(f"An error occurred during TV series search: {e}")
                    logger.error(f"TV series search failed: {e}", exc_info=True)
        else:
            st.warning("Please enter a TV series title.")

# --- Music Search ---
elif tool_selection == "Music Search":
    st.subheader("Music Search (Placeholder)")
    st.info("Music search functionality will be implemented here, potentially integrating with APIs like Spotify or Last.fm.")
    st.text_input("Enter artist or song title:", placeholder="Artist or Song")
    st.button("Search Music (Coming Soon)")

# --- Anime Search ---
elif tool_selection == "Anime Search":
    st.subheader("Anime Search (Placeholder)")
    st.info("Anime search functionality will be implemented here, potentially integrating with APIs like AniList or MyAnimeList.")
    st.text_input("Enter anime title:", placeholder="Attack on Titan")
    st.button("Search Anime (Coming Soon)")

# --- Entertainment Data Fetcher (Advanced) ---
elif tool_selection == "Entertainment Data Fetcher (Advanced)":
    st.subheader("Advanced Entertainment Data Fetcher")
    st.info("This tool directly interacts with configured entertainment APIs. Note that many real APIs require specific access and may have usage limits.")

    api_name = st.selectbox(
        "Select API to use:",
        ("TheMovieDB", "OMDbAPI"), # Add more APIs as configured in entertainment_apis.yaml
        key="advanced_api_select"
    )

    data_type_options = []
    if api_name == "TheMovieDB":
        data_type_options = ["movie", "tv_series", "person"]
    elif api_name == "OMDbAPI":
        data_type_options = ["movie", "series", "episode"]
    # Add logic for other APIs if they have different data types

    data_type = st.selectbox(
        "Select Data Type:",
        data_type_options,
        key="advanced_data_type_select"
    )

    query_input = st.text_input("Query (title/name):", key="query_input_adv")
    id_input = st.text_input("ID (optional, for specific item lookup):", key="id_input_adv")
    year_input = st.text_input("Year (optional):", key="year_input_adv")
    limit_input = st.number_input("Limit results (optional):", min_value=1, value=5, step=1, key="limit_input_fetcher")

    if st.button("Fetch Advanced Entertainment Data"):
        if not query_input and not id_input:
            st.warning("Please enter a query (title/name) or an ID.")
        else:
            with st.spinner(f"Fetching {data_type} data from {api_name}..."):
                try:
                    result_json_str = entertainment_data_fetcher(
                        api_name=api_name,
                        data_type=data_type,
                        query=query_input if query_input else None,
                        id=id_input if id_input else None,
                        year=year_input if year_input else None,
                        limit=limit_input if limit_input > 0 else None
                    )
                    
                    st.subheader("Fetched Data:")
                    try:
                        parsed_data = json.loads(result_json_str)
                        st.json(parsed_data)
                        
                        # Attempt to display as DataFrame if suitable
                        if isinstance(parsed_data, dict) and parsed_data.get('results'):
                            df = pd.DataFrame(parsed_data['results'])
                            st.subheader("Results as DataFrame:")
                            st.dataframe(df)
                        elif isinstance(parsed_data, list) and parsed_data:
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
                    logger.error(f"Entertainment data fetcher failed: {e}", exc_info=True)


st.markdown("---")
st.caption(f"Current User Token: `{current_user.get('user_id', 'N/A')}` (for demo purposes)")
st.caption("This app provides direct access to various entertainment tools.")
