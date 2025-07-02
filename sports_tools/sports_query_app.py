# ui/sports_query_app.py

import streamlit as st
import logging
import json
import pandas as pd # Potentially useful for displaying structured data

# Assume config_manager and get_user_token exist
from config.config_manager import config_manager
from utils.user_manager import get_current_user, get_user_tier_capability # Import for RBAC

from sports_tools.sports_tool import (
    sports_search_web, 
    sports_data_fetcher,
    player_stats_checker,
    team_info_checker,
    match_schedule_checker
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
                self.thesportsdb = {"api_key": "YOUR_THESPORTSDB_API_KEY_HERE"}
                self.sportradar = {"api_key": "YOUR_SPORTRADAR_API_KEY_HERE"}
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

# Define the required tier for this specific page (Sports Query Tools)
# This should match the 'tier_access' defined in main_app.py for this page.
REQUIRED_TIER_FOR_THIS_PAGE = "free" 

# Check if user is logged in and has the required tier or admin role
if not current_user:
    st.warning("⚠️ You must be logged in to access this page.")
    st.stop() # Halts execution
elif not (user_tier and user_roles and (user_tier == REQUIRED_TIER_FOR_THIS_PAGE or TIER_HIERARCHY.get(user_tier, -1) >= TIER_HIERARCHY.get(REQUIRED_TIER_FOR_THIS_PAGE, -1) or "admin" in user_roles)):
    # Import TIER_HIERARCHY from main_app for comparison if not already available
    try:
        from main_app import TIER_HIERARCHY
    except ImportError:
        st.error("Error: Could not load tier hierarchy for access control. Please ensure main_app.py is accessible.")
        st.stop()

    st.error(f"🚫 Access Denied: Your current tier ({user_tier.capitalize()}) does not have access to the Sports Query Tools. Please upgrade your plan to {REQUIRED_TIER_FOR_THIS_PAGE.capitalize()} or higher.")
    st.stop() # Halts execution
# --- End RBAC Access Check ---


# --- Streamlit UI ---
st.set_page_config(page_title="Sports Query Tools", page_icon="🏆", layout="centered")
st.title("Sports Query Tools 🏆")

st.markdown("Access various sports-related tools directly.")

user_token = current_user.get('user_id', 'default') # Get user token for personalization

tool_selection = st.selectbox(
    "Select a Sports Tool:",
    (
        "Web Search (General Sports Info)",
        "Player Stats Checker",
        "Team Info Checker",
        "Match Schedule Checker",
        "Sports Data Fetcher (Advanced)"
    )
)

# --- Web Search ---
if tool_selection == "Web Search (General Sports Info)":
    st.subheader("General Sports Web Search")
    query = st.text_input("Enter your sports web query:", placeholder="e.g., 'latest NBA scores', 'history of the Olympics'")
    
    # RBAC for max_chars in web search
    allowed_max_chars = get_user_tier_capability(user_token, 'web_search_limit_chars', 2000)
    max_chars = st.slider(f"Maximum characters in result snippet (Max for your tier: {allowed_max_chars}):", min_value=100, max_value=allowed_max_chars, value=min(1500, allowed_max_chars), step=100)

    if st.button("Search Web"):
        if query:
            with st.spinner("Searching the web..."):
                try:
                    result = sports_search_web(query=query, user_token=user_token, max_chars=max_chars)
                    st.subheader("Search Results:")
                    st.markdown(result)
                except Exception as e:
                    st.error(f"An error occurred during web search: {e}")
                    logger.error(f"Web search failed: {e}", exc_info=True)
        else:
            st.warning("Please enter a query to search.")

# --- Player Stats Checker ---
elif tool_selection == "Player Stats Checker":
    st.subheader("Player Statistics Checker")
    player_name = st.text_input("Enter player name (e.g., Lionel Messi):", placeholder="Lionel Messi")
    sport = st.text_input("Enter sport (e.g., Soccer, Basketball):", placeholder="Soccer")
    
    if st.button("Get Player Stats"):
        if player_name:
            with st.spinner(f"Fetching stats for {player_name}..."):
                try:
                    result = player_stats_checker(player_name=player_name, sport=sport if sport else None)
                    st.subheader(f"Statistics for {player_name.title()}:")
                    st.markdown(result)
                except Exception as e:
                    st.error(f"An error occurred: {e}")
                    logger.error(f"Player stats check failed: {e}", exc_info=True)
        else:
            st.warning("Please enter a player name.")

# --- Team Info Checker ---
elif tool_selection == "Team Info Checker":
    st.subheader("Team Information Checker")
    team_name = st.text_input("Enter team name (e.g., Los Angeles Lakers):", placeholder="Los Angeles Lakers")
    sport = st.text_input("Enter sport (e.g., Basketball, Football):", placeholder="Basketball")
    
    if st.button("Get Team Info"):
        if team_name:
            with st.spinner(f"Fetching info for {team_name}..."):
                try:
                    result = team_info_checker(team_name=team_name, sport=sport if sport else None)
                    st.subheader(f"Information for {team_name.title()}:")
                    st.markdown(result)
                except Exception as e:
                    st.error(f"An error occurred: {e}")
                    logger.error(f"Team info check failed: {e}", exc_info=True)
        else:
            st.warning("Please enter a team name.")

# --- Match Schedule Checker ---
elif tool_selection == "Match Schedule Checker":
    st.subheader("Match Schedule/Results Checker")
    team_name = st.text_input("Enter team name (optional, e.g., Manchester United):", placeholder="Manchester United")
    league = st.text_input("Enter league (optional, e.g., Premier League):", placeholder="Premier League")
    date = st.date_input("Select date (optional, for specific day's matches):", value=None)
    
    if st.button("Get Match Schedule/Results"):
        if team_name or league or date:
            with st.spinner("Fetching match schedule/results..."):
                try:
                    result = match_schedule_checker(
                        team_name=team_name if team_name else None,
                        league=league if league else None,
                        date=str(date) if date else None
                    )
                    st.subheader("Match Schedule/Results:")
                    st.markdown(result)
                except Exception as e:
                    st.error(f"An error occurred: {e}")
                    logger.error(f"Match schedule check failed: {e}", exc_info=True)
        else:
            st.warning("Please enter a team name, league, or select a date.")

# --- Sports Data Fetcher (Advanced) ---
elif tool_selection == "Sports Data Fetcher (Advanced)":
    st.subheader("Advanced Sports Data Fetcher")
    st.info("This tool directly interacts with configured sports APIs. Note that many real sports APIs require specific access and may have usage limits.")

    api_name = st.selectbox(
        "Select API to use:",
        ("TheSportsDB", "SportRadar"), # Add more APIs as configured in sports_apis.yaml
        key="advanced_api_select"
    )

    data_type_options = []
    if api_name == "TheSportsDB":
        data_type_options = ["player_stats", "team_info", "match_schedule", "league_info"]
    elif api_name == "SportRadar":
        data_type_options = ["player_stats", "team_info", "match_schedule", "league_info"]
    # Add logic for other APIs if they have different data types

    data_type = st.selectbox(
        "Select Data Type:",
        data_type_options,
        key="advanced_data_type_select"
    )

    # Dynamic inputs based on data_type
    query_params = {}
    if data_type in ["player_stats"]:
        query_params['player_name'] = st.text_input("Player Name:", key="player_name_adv")
        query_params['sport'] = st.text_input("Sport (optional):", key="sport_player_adv")
    elif data_type in ["team_info"]:
        query_params['team_name'] = st.text_input("Team Name:", key="team_name_adv")
        query_params['sport'] = st.text_input("Sport (optional):", key="sport_team_adv")
    elif data_type in ["match_schedule"]:
        query_params['team_name'] = st.text_input("Team Name (optional):", key="team_name_match_adv")
        query_params['league'] = st.text_input("League (optional):", key="league_match_adv")
        query_params['date'] = st.date_input("Date (optional):", value=None, key="date_match_adv")
    elif data_type in ["league_info"]:
        query_params['league_name'] = st.text_input("League Name:", key="league_name_adv")

    limit_input = st.number_input("Limit results (optional):", min_value=1, value=5, step=1, key="limit_input_fetcher")
    if limit_input > 0:
        query_params['limit'] = limit_input

    if st.button("Fetch Advanced Sports Data"):
        # Basic validation for required fields based on data_type
        is_valid_input = True
        if data_type == "player_stats" and not query_params.get('player_name'):
            st.warning("Player Name is required for player stats.")
            is_valid_input = False
        elif data_type == "team_info" and not query_params.get('team_name'):
            st.warning("Team Name is required for team info.")
            is_valid_input = False
        elif data_type == "match_schedule" and not (query_params.get('team_name') or query_params.get('league') or query_params.get('date')):
            st.warning("At least a Team Name, League, or Date is required for match schedule.")
            is_valid_input = False
        elif data_type == "league_info" and not query_params.get('league_name'):
            st.warning("League Name is required for league info.")
            is_valid_input = False
        
        if is_valid_input:
            with st.spinner(f"Fetching {data_type} data from {api_name}..."):
                try:
                    # Convert date object to string if present
                    if 'date' in query_params and query_params['date']:
                        query_params['date'] = str(query_params['date'])

                    result_json_str = sports_data_fetcher(
                        api_name=api_name,
                        data_type=data_type,
                        **{k: v for k, v in query_params.items() if v is not None and v != ''} # Pass only non-empty params
                    )
                    
                    st.subheader("Fetched Data:")
                    try:
                        parsed_data = json.loads(result_json_str)
                        st.json(parsed_data)
                        
                        # Attempt to display as DataFrame if suitable (example for common structures)
                        if isinstance(parsed_data, dict) and parsed_data.get('players'):
                            df = pd.DataFrame(parsed_data['players'])
                            st.subheader("Players as DataFrame:")
                            st.dataframe(df)
                        elif isinstance(parsed_data, dict) and parsed_data.get('teams'):
                            df = pd.DataFrame(parsed_data['teams'])
                            st.subheader("Teams as DataFrame:")
                            st.dataframe(df)
                        elif isinstance(parsed_data, dict) and parsed_data.get('events'):
                            df = pd.DataFrame(parsed_data['events'])
                            st.subheader("Events as DataFrame:")
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
                    logger.error(f"Sports data fetcher failed: {e}", exc_info=True)


st.markdown("---")
st.caption(f"Current User Token: `{current_user.get('user_id', 'N/A')}` (for demo purposes)")
st.caption("This app provides direct access to various sports tools.")
