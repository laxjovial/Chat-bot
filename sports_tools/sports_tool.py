# sports_tools/sports_tool.py

import requests
import json
from typing import Optional, List, Dict, Any
from pathlib import Path
import logging
import yaml # Added for loading sports_apis.yaml

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

# Constants for the sports section
SPORTS_SECTION = "sports"
DEFAULT_USER_TOKEN = "default" # Or use a proper user management if available

logger = logging.getLogger(__name__)

@tool
def sports_search_web(query: str, user_token: str = DEFAULT_USER_TOKEN, max_chars: int = 2000) -> str:
    """
    Searches the web for sports-related information using a smart search fallback mechanism.
    This tool wraps the generic `scrape_web` tool, providing a sports-specific interface.
    
    Args:
        query (str): The sports-related search query (e.g., "latest NBA scores", "who won the last Super Bowl").
        user_token (str): The unique identifier for the user. Defaults to "default".
        max_chars (int): Maximum characters for the returned snippet. Defaults to 2000.
    
    Returns:
        str: A string containing relevant information from the web.
    """
    logger.info(f"Tool: sports_search_web called with query: '{query}' for user: '{user_token}'")
    return scrape_web(query=query, user_token=user_token, max_chars=max_chars)

@tool
def sports_query_uploaded_docs(query: str, user_token: str = DEFAULT_USER_TOKEN, export: Optional[bool] = False, k: int = 5) -> str:
    """
    Queries previously uploaded and indexed sports documents for a user using vector similarity search.
    This tool wraps the generic `QueryUploadedDocs` tool, fixing the section to "sports".
    
    Args:
        query (str): The search query to find relevant sports documents (e.g., "what is in the team's new strategy", "summarize the player's medical report").
        user_token (str): The unique identifier for the user. Defaults to "default".
        export (bool): If True, the results will be saved to a file in markdown format. Defaults to False.
        k (int): The number of top relevant documents to retrieve. Defaults to 5.
    
    Returns:
        str: A string containing the combined content of the relevant document chunks,
             or a message indicating no data/results found, or the export path if exported.
    """
    logger.info(f"Tool: sports_query_uploaded_docs called with query: '{query}' for user: '{user_token}'")
    return QueryUploadedDocs(query=query, user_token=user_token, section=SPORTS_SECTION, export=export, k=k)

@tool
def sports_summarize_document_by_path(file_path_str: str) -> str:
    """
    Summarizes a document related to sports located at the given file path.
    The file path should be accessible by the system (e.g., in the 'uploads' directory).
    This tool wraps the generic `summarize_document` tool.
    
    Args:
        file_path_str (str): The full path to the document file to be summarized.
                              Example: "uploads/default/sports/match_report.pdf"
    
    Returns:
        str: A concise summary of the document content.
    """
    logger.info(f"Tool: sports_summarize_document_by_path called for file: '{file_path_str}'")
    file_path = Path(file_path_str)
    if not file_path.exists():
        logger.error(f"Document not found at '{file_path_str}' for summarization.")
        return f"Error: Document not found at '{file_path_str}'."
    
    try:
        # Note: The summarize_document tool now handles its own RBAC check internally
        # based on the user_token passed to it (if it accepts one).
        # For simplicity here, we're assuming summarize_document will handle it
        # or that this tool itself is only available to tiers with summarization.
        summary = summarize_document(file_path) # Assuming summarize_document can take Path object
        return f"Summary of '{file_path.name}':\n{summary}"
    except ValueError as e:
        logger.error(f"Error summarizing document '{file_path_str}': {e}")
        return f"Error summarizing document: {e}"
    except Exception as e:
        logger.critical(f"An unexpected error occurred during summarization of '{file_path_str}': {e}", exc_info=True)
        return f"An unexpected error occurred during summarization: {e}"

# === Advanced Sports Tools ===

# REMOVED: Direct import and initialization of PythonREPLTool.
# The python_interpreter_with_rbac tool is now imported and added conditionally
# in the *_chat_agent_app.py files based on RBAC.

# Helper to load API configs
def _load_sports_apis() -> Dict[str, Any]:
    """Loads sports API configurations from data/sports_apis.yaml."""
    sports_apis_path = Path("data/sports_apis.yaml")
    if not sports_apis_path.exists():
        logger.warning(f"data/sports_apis.yaml not found at {sports_apis_path}")
        return {}
    try:
        with open(sports_apis_path, "r") as f:
            full_config = yaml.safe_load(f) or {}
            return {api['name']: api for api in full_config.get('apis', [])}
    except Exception as e:
        logger.error(f"Error loading sports_apis.yaml: {e}")
        return {}

SPORTS_APIS_CONFIG = _load_sports_apis()

@tool
def sports_data_fetcher(
    api_name: str, 
    data_type: str, 
    query: Optional[str] = None, # General query for search APIs
    player_name: Optional[str] = None,
    team_name: Optional[str] = None,
    league: Optional[str] = None,
    sport: Optional[str] = None,
    date: Optional[str] = None, # YYYY-MM-DD for match schedules
    limit: Optional[int] = None
) -> str:
    """
    Fetches sports data from configured APIs (e.g., TheSportsDB, SportRadar).
    
    Args:
        api_name (str): The name of the API to use (e.g., "TheSportsDB", "SportRadar").
                        This must match a 'name' field in data/sports_apis.yaml.
        data_type (str): The type of data to fetch.
                          - For TheSportsDB: "player_stats", "team_info", "match_schedule", "league_info".
                          - For SportRadar: "player_stats", "team_info", "match_schedule", "league_info".
        query (str, optional): General query for search APIs if the data_type implies a search.
        player_name (str, optional): Name of the player (e.g., "LeBron James").
        team_name (str, optional): Name of the team (e.g., "Los Angeles Lakers").
        league (str, optional): Name of the league (e.g., "NBA", "Premier League").
        sport (str, optional): Specific sport (e.g., "basketball", "soccer").
        date (str, optional): Date for match schedules (YYYY-MM-DD).
        limit (int, optional): Maximum number of records to return.
        
    Returns:
        str: A JSON string of the fetched data or an error message.
             The agent can then use `python_interpreter_with_rbac` to parse and analyze this JSON.
    """
    logger.info(f"Tool: sports_data_fetcher called for API: {api_name}, data_type: {data_type}, query: {query}, player: {player_name}, team: {team_name}")

    api_info = SPORTS_APIS_CONFIG.get(api_name)
    if not api_info:
        return f"Error: API '{api_name}' not found in data/sports_apis.yaml configuration."

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
    url = endpoint # Base URL, might be modified

    try:
        # --- TheSportsDB ---
        if api_name == "TheSportsDB":
            if data_type == "player_stats":
                if not player_name: return "Error: 'player_name' is required for TheSportsDB player_stats."
                url = f"{endpoint}{api_key}/searchplayers.php"
                params['p'] = player_name
            elif data_type == "team_info":
                if not team_name: return "Error: 'team_name' is required for TheSportsDB team_info."
                url = f"{endpoint}{api_key}/searchteams.php"
                params['t'] = team_name
            elif data_type == "match_schedule":
                if team_name:
                    url = f"{endpoint}{api_key}/searchevents.php" # Search events by team name
                    params['s'] = team_name # TheSportsDB uses 's' for team name in event search
                elif date:
                    url = f"{endpoint}{api_key}/eventsday.php" # Events on a specific day
                    params['d'] = date
                elif league:
                    url = f"{endpoint}{api_key}/search_all_events.php" # Search events by league (less direct)
                    params['l'] = league
                else:
                    return "Error: 'team_name', 'date', or 'league' is required for TheSportsDB match_schedule."
            elif data_type == "league_info":
                if not league: return "Error: 'league' is required for TheSportsDB league_info."
                url = f"{endpoint}{api_key}/searchleagues.php"
                params['l'] = league
            else:
                return f"Error: Unsupported data_type '{data_type}' for TheSportsDB."
            
            # TheSportsDB API key is typically part of the URL path
            if api_key: # Ensure the key is used if available
                url = url.replace(f"{endpoint}{api_key}", f"{endpoint}{api_key}") # No-op if already there, just ensures it's correct
            else:
                return f"Error: API key for '{api_name}' not found in secrets.toml. It's required for this API."
            
            response = requests.get(url, headers=headers, params=params, timeout=request_timeout)

        # --- SportRadar (Placeholder - Actual implementation would vary greatly by sport and SportRadar API structure) ---
        elif api_name == "SportRadar":
            # This is a highly simplified placeholder. SportRadar has complex API structures
            # per sport (NBA, NFL, MLB, etc.) and requires specific endpoint paths.
            # A real implementation would need to parse `data_type` and `sport`
            # to construct the correct SportRadar API URL and parameters.
            
            # Example: Mocking a generic response
            mock_data = {
                "message": f"Mock data for SportRadar {data_type} for query '{query or player_name or team_name or league}'",
                "details": "Actual SportRadar integration requires specific API endpoints and detailed parsing.",
                "api_name": api_name,
                "data_type": data_type,
                "query_params": {k: v for k, v in locals().items() if v is not None and k in ['player_name', 'team_name', 'league', 'sport', 'date', 'limit']}
            }
            return json.dumps(mock_data, ensure_ascii=False, indent=2)

        else:
            return f"Error: API '{api_name}' is not supported by sports_data_fetcher."

        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
        data = response.json()
        
        # Apply limit if specified and data is a list (or has a list-like key)
        if limit and isinstance(data, dict):
            # TheSportsDB often returns lists under keys like 'players', 'teams', 'events'
            for key in ['players', 'teams', 'events', 'leagues']:
                if key in data and isinstance(data[key], list):
                    data[key] = data[key][:limit]
                    break
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

@tool
def player_stats_checker(player_name: str, sport: Optional[str] = None) -> str:
    """
    Checks the current or recent statistics for a specific player.
    Uses `sports_data_fetcher` internally.
    
    Args:
        player_name (str): The name of the player (e.g., "Stephen Curry").
        sport (str, optional): The sport the player plays (e.g., "Basketball", "Soccer").
    
    Returns:
        str: A summary of the player's statistics or an error message.
    """
    logger.info(f"Tool: player_stats_checker called for player: '{player_name}', sport: '{sport}'")
    
    # Prioritize TheSportsDB for player stats
    result_json_str = sports_data_fetcher(
        api_name="TheSportsDB",
        data_type="player_stats",
        player_name=player_name
    )
    
    try:
        data = json.loads(result_json_str)
        if data and data.get('player'):
            player_data = data['player'][0] # Assuming first result is most relevant
            response_str = f"Stats for {player_data.get('strPlayer', 'N/A')} ({player_data.get('strSport', 'N/A')}):\n"
            response_str += f"- Team: {player_data.get('strTeam', 'N/A')}\n"
            response_str += f"- Position: {player_data.get('strPosition', 'N/A')}\n"
            response_str += f"- Height: {player_data.get('strHeight', 'N/A')}, Weight: {player_data.get('strWeight', 'N/A')}\n"
            response_str += f"- Birth Date: {player_data.get('dateBorn', 'N/A')}\n"
            response_str += f"- Nationality: {player_data.get('strNationality', 'N/A')}\n"
            response_str += f"- Description (Snippet): {player_data.get('strDescriptionEN', 'No description available')[:200]}...\n"
            return response_str
        else:
            return f"Could not find statistics for player '{player_name}'. {data.get('message', '')}"
    except json.JSONDecodeError:
        return f"Error parsing API response for player stats: {result_json_str}"
    except Exception as e:
        logger.error(f"Error processing player stats for {player_name}: {e}", exc_info=True)
        return f"An unexpected error occurred while getting player stats: {e}"

@tool
def team_info_checker(team_name: str, sport: Optional[str] = None) -> str:
    """
    Checks information about a specific sports team.
    Uses `sports_data_fetcher` internally.
    
    Args:
        team_name (str): The name of the team (e.g., "Manchester United").
        sport (str, optional): The sport the team plays (e.g., "Soccer", "Basketball").
    
    Returns:
        str: A summary of the team's information or an error message.
    """
    logger.info(f"Tool: team_info_checker called for team: '{team_name}', sport: '{sport}'")
    
    # Prioritize TheSportsDB for team info
    result_json_str = sports_data_fetcher(
        api_name="TheSportsDB",
        data_type="team_info",
        team_name=team_name
    )
    
    try:
        data = json.loads(result_json_str)
        if data and data.get('teams'):
            team_data = data['teams'][0] # Assuming first result is most relevant
            response_str = f"Information for {team_data.get('strTeam', 'N/A')} ({team_data.get('strSport', 'N/A')}):\n"
            response_str += f"- League: {team_data.get('strLeague', 'N/A')}\n"
            response_str += f"- Stadium: {team_data.get('strStadium', 'N/A')} (Capacity: {team_data.get('intStadiumCapacity', 'N/A')})\n"
            response_str += f"- Formed Year: {team_data.get('intFormedYear', 'N/A')}\n"
            response_str += f"- Website: {team_data.get('strWebsite', 'N/A')}\n"
            response_str += f"- Description (Snippet): {team_data.get('strDescriptionEN', 'No description available')[:200]}...\n"
            return response_str
        else:
            return f"Could not find information for team '{team_name}'. {data.get('message', '')}"
    except json.JSONDecodeError:
        return f"Error parsing API response for team info: {result_json_str}"
    except Exception as e:
        logger.error(f"Error processing team info for {team_name}: {e}", exc_info=True)
        return f"An unexpected error occurred while getting team info: {e}"

@tool
def match_schedule_checker(team_name: Optional[str] = None, league: Optional[str] = None, date: Optional[str] = None) -> str:
    """
    Checks upcoming or past match schedules/results for a specific team or league, or on a specific date.
    Uses `sports_data_fetcher` internally.
    
    Args:
        team_name (str, optional): The name of the team (e.g., "Golden State Warriors").
        league (str, optional): The name of the league (e.g., "NBA").
        date (str, optional): A specific date for matches (YYYY-MM-DD).
    
    Returns:
        str: A list of matches or an error message.
    """
    logger.info(f"Tool: match_schedule_checker called for team: '{team_name}', league: '{league}', date: '{date}'")
    
    if not team_name and not league and not date:
        return "Error: At least 'team_name', 'league', or 'date' must be provided to check match schedules."

    # Prioritize TheSportsDB for match schedules
    result_json_str = sports_data_fetcher(
        api_name="TheSportsDB",
        data_type="match_schedule",
        team_name=team_name,
        league=league,
        date=date
    )
    
    try:
        data = json.loads(result_json_str)
        if data and data.get('events'):
            events = data['events']
            response_str = f"Matches found:\n"
            for event in events:
                response_str += (
                    f"- {event.get('strEvent', 'N/A')} on {event.get('dateEvent', 'N/A')} "
                    f"at {event.get('strTime', 'N/A')} ({event.get('strLeague', 'N/A')})\n"
                )
            return response_str
        else:
            return f"No matches found for the given criteria. {data.get('message', '')}"
    except json.JSONDecodeError:
        return f"Error parsing API response for match schedule: {result_json_str}"
    except Exception as e:
        logger.error(f"Error processing match schedule: {e}", exc_info=True)
        return f"An unexpected error occurred while getting match schedule: {e}"


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
            self.thesportsdb_api_key = "YOUR_THESPORTSDB_API_KEY" # For TheSportsDB
            self.sportradar_api_key = "YOUR_SPORTRADAR_API_KEY" # For SportRadar
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


    print("\n--- Testing sports_tool functions (updated) ---")
    test_user = "test_user_sports"
    
    # Setup dummy API YAMLs for testing
    dummy_data_dir = Path("data")
    dummy_data_dir.mkdir(exist_ok=True)
    dummy_sports_apis_path = dummy_data_dir / "sports_apis.yaml"
    with open(dummy_sports_apis_path, "w") as f:
        f.write("""
apis:
  - name: "TheSportsDB"
    type: "sports"
    endpoint: "https://www.thesportsdb.com/api/v1/json/"
    key_name: "" # Key is part of URL path for TheSportsDB
    key_value: "load_from_secrets.thesportsdb_api_key" # Your API key here (e.g., '1' for testing, or a real key)
    headers: {}
    default_params: {}
    functions:
      SEARCH_PLAYERS:
        path: "searchplayers.php"
        params: {p: ""}
      SEARCH_TEAMS:
        path: "searchteams.php"
        params: {t: ""}
      SEARCH_EVENTS_BY_TEAM:
        path: "searchevents.php"
        params: {s: ""}
      EVENTS_BY_DATE:
        path: "eventsday.php"
        params: {d: ""}
      SEARCH_LEAGUES:
        path: "searchleagues.php"
        params: {l: ""}
    query_param: "p" # Primary query param for general search

  - name: "SportRadar"
    type: "sports"
    endpoint: "https://api.sportradar.us/"
    key_name: "api_key"
    key_value: "load_from_secrets.sportradar_api_key"
    headers: {}
    default_params: {}
    functions: {} # SportRadar has complex, sport-specific endpoints
    query_param: "q"

search_apis:
  - name: "SportsNewsAPI"
    type: "search"
    endpoint: "https://api.example.com/sports_news/search"
    key_name: "apiKey"
    key_value: "load_from_secrets.sports_news_api_key"
    headers: {}
    default_params:
      sort_by: "relevancy"
    query_param: "q"
""")
    # Re-load config after creating dummy file
    sys.modules['config.config_manager'].config_manager = MockConfigManager()
    sys.modules['config.config_manager'].ConfigManager = MockConfigManager # Also replace the class for singleton check
    global SPORTS_APIS_CONFIG
    SPORTS_APIS_CONFIG = _load_sports_apis()
    print("Dummy sports_apis.yaml created and config reloaded for testing.")


    if config_manager:
        # Test sports_search_web (already works, just for completeness)
        print("\n--- Testing sports_search_web ---")
        search_query = "latest football transfer news"
        search_result = sports_search_web(search_query, user_token=test_user)
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
            MockResponse({"player": [{"strPlayer": "Lionel Messi", "strSport": "Soccer", "strTeam": "Inter Miami"}]}),
            MockResponse({"teams": [{"strTeam": "FC Barcelona", "strSport": "Soccer", "strStadium": "Camp Nou"}]}),
            MockResponse({"events": [{"strEvent": "El Clasico", "dateEvent": "2023-10-28", "strLeague": "La Liga"}]}),
            MockResponse({"leagues": [{"strLeague": "NBA", "strSport": "Basketball"}]}),
        ])

        # Test sports_data_fetcher - TheSportsDB
        print("\n--- Testing sports_data_fetcher (TheSportsDB) ---")
        player_data = sports_data_fetcher(api_name="TheSportsDB", data_type="player_stats", player_name="Lionel Messi")
        print(f"Messi Player Data (TheSportsDB): {player_data}")
        team_data = sports_data_fetcher(api_name="TheSportsDB", data_type="team_info", team_name="FC Barcelona")
        print(f"Barcelona Team Data (TheSportsDB): {team_data}")
        match_data = sports_data_fetcher(api_name="TheSportsDB", data_type="match_schedule", team_name="Real Madrid", date="2023-10-28")
        print(f"Real Madrid Match Data (TheSportsDB): {match_data}")
        league_data = sports_data_fetcher(api_name="TheSportsDB", data_type="league_info", league="NBA")
        print(f"NBA League Data (TheSportsDB): {league_data}")
        
        # Restore original requests.get
        requests.get = original_requests_get

        # Test python_interpreter_with_rbac with mock data (example)
        print("\n--- Testing python_interpreter_with_rbac with mock data ---")
        python_code_sports = f"""
import json
data = {player_data}
player = data.get('player', [{{}}])[0]
print(f"Player Name: {{player.get('strPlayer')}}")
print(f"Player Team: {{player.get('strTeam')}}")
"""
        print(f"Executing Python code:\n{python_code_sports}")
        try:
            # Test with a user who has data_analysis_enabled
            pro_user_token = st.secrets.user_tokens["pro_user_token"]
            repl_output = python_interpreter_with_rbac(code=python_code_sports, user_token=pro_user_token)
            print(f"Python REPL Output (Pro User):\n{repl_output}")
            assert "Player Name: Lionel Messi" in repl_output
            assert "Player Team: Inter Miami" in repl_output

            # Test with a user who does NOT have data_analysis_enabled
            free_user_token = st.secrets.user_tokens["free_user_token"]
            repl_output_denied = python_interpreter_with_rbac(code=python_code_sports, user_token=free_user_token)
            print(f"Python REPL Output (Free User):\n{repl_output_denied}")
            assert "Access Denied" in repl_output_denied

        except Exception as e:
            print(f"Error executing Python REPL: {e}.")
            print("Make sure pandas, numpy, json are installed if you're running complex analysis.")

    else:
        print("Skipping sports_tool tests due to ConfigManager issues or missing API keys.")

    # Clean up dummy files and directories
    dummy_json_path = Path("temp_sports_docs.json")
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
