# entertainment_tools/entertainment_tool.py

import requests
import json
from typing import Optional, List, Dict, Any
from pathlib import Path
import logging

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

# Constants for the entertainment section
ENTERTAINMENT_SECTION = "entertainment"
DEFAULT_USER_TOKEN = "default" # Or use a proper user management if available

logger = logging.getLogger(__name__)

@tool
def entertainment_search_web(query: str, user_token: str = DEFAULT_USER_TOKEN, max_chars: int = 2000) -> str:
    """
    Searches the web for entertainment-related information (movies, music, series, anime, etc.)
    using a smart search fallback mechanism.
    This tool wraps the generic `scrape_web` tool, providing an entertainment-specific interface.
    
    Args:
        query (str): The entertainment-related search query (e.g., "latest movie releases", "best albums of 2023", "plot of new anime series").
        user_token (str): The unique identifier for the user. Defaults to "default".
        max_chars (int): Maximum characters for the returned snippet. Defaults to 2000.
    
    Returns:
        str: A string containing relevant information from the web.
    """
    logger.info(f"Tool: entertainment_search_web called with query: '{query}' for user: '{user_token}'")
    return scrape_web(query=query, user_token=user_token, max_chars=max_chars)

@tool
def entertainment_query_uploaded_docs(query: str, user_token: str = DEFAULT_USER_TOKEN, export: Optional[bool] = False, k: int = 5) -> str:
    """
    Queries previously uploaded and indexed entertainment documents for a user using vector similarity search.
    This tool wraps the generic `QueryUploadedDocs` tool, fixing the section to "entertainment".
    
    Args:
        query (str): The search query to find relevant entertainment documents (e.g., "summary of the screenplay I uploaded", "details from my music collection notes").
        user_token (str): The unique identifier for the user. Defaults to "default".
        export (bool): If True, the results will be saved to a file in markdown format. Defaults to False.
        k (int): The number of top relevant documents to retrieve. Defaults to 5.
    
    Returns:
        str: A string containing the combined content of the relevant document chunks,
             or a message indicating no data/results found, or the export path if exported.
    """
    logger.info(f"Tool: entertainment_query_uploaded_docs called with query: '{query}' for user: '{user_token}'")
    return QueryUploadedDocs(query=query, user_token=user_token, section=ENTERTAINMENT_SECTION, export=export, k=k)

@tool
def entertainment_summarize_document_by_path(file_path_str: str) -> str:
    """
    Summarizes a document related to entertainment located at the given file path.
    The file path should be accessible by the system (e.g., in the 'uploads' directory).
    This tool wraps the generic `summarize_document` tool.
    
    Args:
        file_path_str (str): The full path to the document file to be summarized.
                              Example: "uploads/default/entertainment/movie_script.pdf"
    
    Returns:
        str: A concise summary of the document content.
    """
    logger.info(f"Tool: entertainment_summarize_document_by_path called for file: '{file_path_str}'")
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

# === Advanced Entertainment Tools ===

# Initialize the Python REPL tool.
# This allows the agent to execute arbitrary Python code, which is powerful for data analysis
# of fetched entertainment data (e.g., analyzing ratings, trends).
python_repl = PythonREPLTool()
python_repl.name = "python_interpreter"
python_repl.description = """
Executes Python code. Use this for complex data analysis, calculations, or any task that requires programmatic logic
on structured entertainment data (e.g., parsing JSON from `entertainment_data_fetcher`, analyzing movie ratings).
Input should be a valid Python code string.
The output will be the result of the code execution (stdout/stderr).
You have access to common libraries like pandas, numpy, matplotlib, datetime, json, etc.
Example:
Action: python_interpreter
Action Input:
import json
data = json.loads(tool_output) # Assuming tool_output is from entertainment_data_fetcher
movie_titles = [item['title'] for item in data if 'title' in item]
print(f"Movies fetched: {', '.join(movie_titles)}")
"""

@tool
def entertainment_data_fetcher(
    api_name: str, 
    query: Optional[str] = None, 
    media_type: Optional[str] = None, # e.g., "movie", "tv", "person", "music", "anime"
    id: Optional[str] = None, # For fetching by specific ID
    year: Optional[int] = None, # For release year
    limit: Optional[int] = None # For number of results
) -> str:
    """
    Fetches entertainment data (movies, series, music, anime) from configured APIs
    like TheMovieDB, OMDbAPI, AniList, etc.
    
    Args:
        api_name (str): The name of the API to use (e.g., "TheMovieDB", "OMDbAPI", "AniList").
                        This must match a 'name' field in data/media_apis.yaml.
        query (str, optional): The search query (e.g., "Inception", "Attack on Titan").
        media_type (str, optional): The type of media to search for (e.g., "movie", "tv", "anime", "artist", "album").
                                    This helps the tool select the correct API endpoint.
        id (str, optional): A specific ID for a media item (e.g., TMDB ID, IMDb ID, AniList ID).
        year (int, optional): Release year for movies/series.
        limit (int, optional): Limit the number of results for searches.
        
    Returns:
        str: A JSON string of the fetched data or an error message.
             The agent can then use `python_interpreter` to parse and analyze this JSON.
    """
    logger.info(f"Tool: entertainment_data_fetcher called for API: {api_name}, query: '{query}', media_type: {media_type}, ID: {id}")

    # Load API configurations from media_apis.yaml
    media_apis_path = Path("data/media_apis.yaml")
    apis_config = {}
    if media_apis_path.exists():
        try:
            with open(media_apis_path, "r") as f:
                full_config = yaml.safe_load(f) or {}
                apis_config = {api['name']: api for api in full_config.get('apis', [])}
        except Exception as e:
            logger.error(f"Error loading media_apis.yaml: {e}")
            return f"Error: Could not load API configurations for entertainment. {e}"
    
    api_info = apis_config.get(api_name)
    if not api_info:
        return f"Error: API '{api_name}' not found in media_apis.yaml configuration."

    endpoint = api_info.get("endpoint")
    key_name = api_info.get("key_name")
    api_key_value_ref = api_info.get("key_value")
    default_params = api_info.get("default_params", {})
    headers = api_info.get("headers", {})

    api_key = None
    if api_key_value_ref and api_key_value_ref.startswith("load_from_secrets."):
        secret_key_path = api_key_value_ref.split("load_from_secrets.")[1]
        api_key = config_manager.get_secret(secret_key_path)
    
    if not api_key:
        return f"Error: API key for '{api_name}' not found in secrets.toml."

    params = {key_name: api_key, **default_params}
    url = endpoint

    # Build request based on API and media type
    if api_name == "TheMovieDB":
        if query and media_type in ["movie", "tv", "person"]:
            url = f"{endpoint}search/{media_type}"
            params['query'] = query
            if year:
                params['year'] = year
        elif id and media_type in ["movie", "tv", "person"]:
            url = f"{endpoint}{media_type}/{id}"
        else:
            return "Error: TheMovieDB requires a query and media_type (movie/tv/person) or an ID."
    
    elif api_name == "OMDbAPI":
        if query and media_type in ["movie", "series", "episode"]:
            params['s'] = query # Search parameter
            params['type'] = media_type
            if year:
                params['y'] = year
        elif id: # OMDbAPI uses IMDb ID for direct lookup
            params['i'] = id
        else:
            return "Error: OMDbAPI requires a query and media_type (movie/series/episode) or an IMDb ID."
    
    elif api_name == "AniList":
        # AniList uses GraphQL, so the request structure is different
        if query and media_type == "anime":
            graphql_query = """
            query ($search: String, $type: MediaType, $perPage: Int) {
              Page (perPage: $perPage) {
                media (search: $search, type: $type) {
                  id
                  title {
                    romaji
                    english
                  }
                  description
                  genres
                  averageScore
                  episodes
                  status
                  startDate { year month day }
                }
              }
            }
            """
            variables = {
                "search": query,
                "type": "ANIME", # AniList GraphQL uses ANIME, MANGA, CHARACTER, STAFF, STUDIO
                "perPage": limit if limit else 5
            }
            # AniList requires POST with JSON body
            try:
                response = requests.post(
                    url, 
                    json={'query': graphql_query, 'variables': variables}, 
                    headers=headers, 
                    timeout=config_manager.get('web_scraping.timeout_seconds', 10)
                )
                response.raise_for_status()
                data = response.json()
                # Extract relevant info from AniList response
                if data and 'data' in data and 'Page' in data['data'] and 'media' in data['data']['Page']:
                    return json.dumps(data['data']['Page']['media'], ensure_ascii=False, indent=2)
                else:
                    return "No results found from AniList."
            except requests.exceptions.RequestException as req_e:
                logger.error(f"AniList API request failed: {req_e}")
                return f"Error fetching from AniList: {req_e}"
            except Exception as e:
                logger.error(f"Error processing AniList response: {e}")
                return f"Error processing AniList response: {e}"
        else:
            return "Error: AniList requires a query and media_type 'anime'."

    else:
        return f"Error: entertainment_data_fetcher not fully implemented for API '{api_name}' or media_type '{media_type}'."

    try:
        response = requests.get(url, headers=headers, params=params, timeout=config_manager.get('web_scraping.timeout_seconds', 10))
        response.raise_for_status()
        data = response.json()
        return json.dumps(data, ensure_ascii=False, indent=2)
    except requests.exceptions.RequestException as req_e:
        logger.error(f"API request failed for {api_name}: {req_e}")
        return f"Error fetching from {api_name}: {req_e}"
    except Exception as e:
        logger.error(f"Error processing {api_name} response: {e}")
        return f"Error processing {api_name} response: {e}"


# CLI Test (optional)
if __name__ == "__main__":
    import streamlit as st
    import shutil
    import os
    import yaml # Import yaml for creating dummy config files
    from config.config_manager import ConfigManager # Import ConfigManager for testing setup
    from shared_tools.llm_embedding_utils import get_llm # For testing summarization with a real LLM

    logging.basicConfig(level=logging.INFO)

    # Mock Streamlit secrets and config for local testing if needed
    class MockSecrets:
        def __init__(self):
            self.openai = {"api_key": "sk-mock-openai-key-12345"} # Replace with a real key
            self.google = {"api_key": "AIzaSy-mock-google-key"} # Replace with a real key
            self.ollama = {"api_url": "http://localhost:11434", "model": "llama3"}
            self.serpapi = {"api_key": "YOUR_SERPAPI_KEY"} # For scrape_web testing
            self.google_custom_search = {"api_key": "YOUR_GOOGLE_CUSTOM_SEARCH_API_KEY"} # For scrape_web testing
            self.themoviedb_api_key = "YOUR_THEMOVIEDB_API_KEY" # For TheMovieDB
            self.omdbapi_api_key = "YOUR_OMDBAPI_API_KEY" # For OMDbAPI
            # AniList typically doesn't need a direct API key for public queries, but mock if needed
            # self.anilist_api_key = "YOUR_ANILIST_API_KEY"

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
        # Create dummy API YAMLs for scraper_tool and entertainment_data_fetcher
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
apis:
  - name: "TheMovieDB"
    type: "media"
    endpoint: "https://api.themoviedb.org/3/"
    key_name: "api_key"
    key_value: "load_from_secrets.themoviedb_api_key"
    headers: {}
    default_params: {}
    query_param: "query"

  - name: "OMDbAPI"
    type: "media"
    endpoint: "http://www.omdbapi.com/"
    key_name: "apikey"
    key_value: "load_from_secrets.omdbapi_api_key"
    headers: {}
    default_params: {}
    query_param: "s"

  - name: "AniList"
    type: "media"
    endpoint: "https://graphql.anilist.co/"
    key_name: ""
    key_value: ""
    headers:
      Content-Type: "application/json"
      Accept: "application/json"
    default_params: {}
    query_param: "query"

search_apis:
  - name: "GoogleCustomSearch"
    type: "search"
    endpoint: "https://www.googleapis.com/customsearch/v1"
    key_name: "key"
    key_value: "load_from_secrets.google_custom_search_api_key"
    query_param: "q"
    default_params:
      cx: "YOUR_CUSTOM_SEARCH_ENGINE_ID"
      num: 3
            """)
        # Dummy finance_apis.yaml (just to ensure scraper_tool loads correctly)
        dummy_finance_apis_path = dummy_data_dir / "finance_apis.yaml"
        with open(dummy_finance_apis_path, "w") as f:
            f.write("""
apis: []
search_apis: []
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

    print("\n--- Testing entertainment_tool functions ---")
    test_user = "test_user_entertainment"
    
    if config_manager:
        # Test entertainment_search_web
        print("\n--- Testing entertainment_search_web ---")
        search_query = "new sci-fi series on Netflix"
        search_result = entertainment_search_web(search_query, user_token=test_user)
        print(f"Search Result for '{search_query}':\n{search_result[:500]}...")

        # Prepare dummy data for entertainment_query_uploaded_docs
        print("\n--- Preparing dummy data for entertainment_query_uploaded_docs ---")
        dummy_json_path = Path("temp_entertainment_docs.json")
        dummy_data = [
            {"id": 1, "text": "My notes on the plot of 'Dune: Part Two' and its differences from the book.", "category": "movie"},
            {"id": 2, "text": "A review of the latest album by Taylor Swift, focusing on its lyrical themes.", "category": "music"},
            {"id": 3, "text": "Character analysis for Eren Yeager in 'Attack on Titan' season 4.", "category": "anime"}
        ]
        with open(dummy_json_path, "w", encoding="utf-8") as f:
            json.dump(dummy_data, f)
        
        # Load documents from the dummy JSON for build_vectorstore
        loaded_docs_for_vector = load_docs_from_json_file(dummy_json_path)
        for i, doc in enumerate(loaded_docs_for_vector):
            doc.page_content = dummy_data[i]["text"]

        build_vectorstore(test_user, ENTERTAINMENT_SECTION, loaded_docs_for_vector, chunk_size=200, chunk_overlap=0)
        print(f"Vectorstore built for {ENTERTAINMENT_SECTION}.")

        # Test entertainment_query_uploaded_docs
        print("\n--- Testing entertainment_query_uploaded_docs ---")
        doc_query = "What did I write about Dune Part Two?"
        doc_results = entertainment_query_uploaded_docs(doc_query, user_token=test_user)
        print(f"Query uploaded docs for '{doc_query}':\n{doc_results}")

        doc_query_export = "Tell me about Taylor Swift's new album."
        doc_results_export = entertainment_query_uploaded_docs(doc_query_export, user_token=test_user, export=True)
        print(f"Query uploaded docs with export for '{doc_query_export}':\n{doc_results_export}")
        
        # Test entertainment_summarize_document_by_path
        print("\n--- Testing entertainment_summarize_document_by_path ---")
        # Create a dummy upload directory and file
        test_upload_dir = Path("uploads") / test_user / ENTERTAINMENT_SECTION
        test_upload_dir.mkdir(parents=True, exist_ok=True)
        summarize_file_path = test_upload_dir / "entertainment_review.txt"
        with open(summarize_file_path, "w") as f:
            f.write("This review covers the intricate plot and character development of the new fantasy series. " * 30 + 
                    "The visual effects are stunning, but the pacing sometimes drags in the middle episodes. " * 20 +
                    "Overall, it's a promising start to what could be a great saga." * 25)
        print(f"Created dummy file for summarization: {summarize_file_path}")

        summary_result = entertainment_summarize_document_by_path(str(summarize_file_path))
        print(summary_result)

        # Test entertainment_data_fetcher
        print("\n--- Testing entertainment_data_fetcher ---")
        # Test TheMovieDB search
        tmdb_movie_search = entertainment_data_fetcher(api_name="TheMovieDB", query="Inception", media_type="movie")
        print(f"TheMovieDB 'Inception' search:\n{tmdb_movie_search[:500]}...")

        # Test OMDbAPI search
        omdb_series_search = entertainment_data_fetcher(api_name="OMDbAPI", query="Breaking Bad", media_type="series")
        print(f"OMDbAPI 'Breaking Bad' search:\n{omdb_series_search[:500]}...")

        # Test AniList search (GraphQL)
        anilist_anime_search = entertainment_data_fetcher(api_name="AniList", query="Jujutsu Kaisen", media_type="anime")
        print(f"AniList 'Jujutsu Kaisen' search:\n{anilist_anime_search[:500]}...")

        # Test python_interpreter
        print("\n--- Testing python_interpreter with fetched data ---")
        python_code_for_tmdb = f"""
import json
data = {tmdb_movie_search}
if 'results' in data:
    first_movie = data['results'][0]
    print(f"First movie title: {{first_movie.get('title')}}")
    print(f"Overview: {{first_movie.get('overview')[:100]}}...")
else:
    print("No results found in TMDB data.")
"""
        print(f"Executing Python code:\n{python_code_for_tmdb}")
        try:
            repl_output = python_repl.run(python_code_for_tmdb)
            print(f"Python REPL Output:\n{repl_output}")
        except Exception as e:
            print(f"Error executing Python REPL: {e}. Make sure pandas, numpy, json are installed.")


    else:
        print("Skipping entertainment_tool tests due to ConfigManager issues or missing API keys.")

    # Clean up dummy files and directories
    if Path("exports").exists() and (Path("exports") / test_user).exists():
        shutil.rmtree(Path("exports") / test_user, ignore_errors=True)
    if Path("uploads").exists() and (Path("uploads") / test_user).exists():
        shutil.rmtree(Path("uploads") / test_user, ignore_errors=True)
    if BASE_VECTOR_DIR.exists() and (BASE_VECTOR_DIR / test_user).exists():
        shutil.rmtree(BASE_VECTOR_DIR / test_user, ignore_errors=True)
    if dummy_json_path.exists():
        dummy_json_path.unlink()
    
    dummy_data_dir = Path("data")
    if dummy_data_dir.exists():
        # Remove only if contents are dummy files created by this script
        if dummy_config_path.exists():
            os.remove(dummy_config_path)
        if dummy_sports_apis_path.exists():
            os.remove(dummy_sports_apis_path)
        if dummy_media_apis_path.exists():
            os.remove(dummy_media_apis_path)
        if dummy_finance_apis_path.exists():
            os.remove(dummy_finance_apis_path)
        if not os.listdir(dummy_data_dir):
            os.rmdir(dummy_data_dir)
