# shared_tools/scraper_tool.py

import requests
import yaml
from bs4 import BeautifulSoup
from langchain_core.tools import tool
from typing import Optional, Dict, Any, List
from pathlib import Path
import logging
import os

from config.config_manager import config_manager # Use the new ConfigManager instance

logger = logging.getLogger(__name__)

# === Load search API config from unified YAML ===
def load_search_apis() -> List[Dict[str, Any]]:
    """Loads search API configurations from the central data/media_apis.yaml and data/sports_apis.yaml."""
    search_apis = []
    
    # Load from sports_apis.yaml (for general search APIs like SerpAPI)
    sports_apis_path = Path("data/sports_apis.yaml")
    if sports_apis_path.exists():
        try:
            with open(sports_apis_path, "r") as f:
                all_apis = yaml.safe_load(f) or {}
                if 'search_apis' in all_apis:
                    search_apis.extend([api for api in all_apis['search_apis'] if api.get("type") == "search"])
        except Exception as e:
            logger.warning(f"Warning: Could not load search APIs from {sports_apis_path}: {e}")

    # Load from media_apis.yaml (for general search APIs like Google Custom Search)
    media_apis_path = Path("data/media_apis.yaml")
    if media_apis_path.exists():
        try:
            with open(media_apis_path, "r") as f:
                all_apis = yaml.safe_load(f) or {}
                if 'search_apis' in all_apis:
                    search_apis.extend([api for api in all_apis['search_apis'] if api.get("type") == "search"])
        except Exception as e:
            logger.warning(f"Warning: Could not load search APIs from {media_apis_path}: {e}")

    # Remove duplicates if an API is defined in both files (by name)
    unique_search_apis = []
    seen_names = set()
    for api in search_apis:
        if api['name'] not in seen_names:
            unique_search_apis.append(api)
            seen_names.add(api['name'])

    return unique_search_apis

# Load APIs once when the module is imported
SEARCH_APIS = load_search_apis()

@tool
def scrape_web(query: str, user_token: str = "default", max_chars: int = 1000) -> str:
    """
    Smart search fallback: tries configured Search APIs first, then Wikipedia, then Google scraping.
    Returns first valid response or explains failure.
    
    Args:
        query (str): The search query.
        user_token (str): User identifier (for API key retrieval).
        max_chars (int): Maximum characters for the returned snippet.
    """
    # Get user agent from centralized config
    user_agent = config_manager.get('web_scraping.user_agent', "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    request_timeout = config_manager.get('web_scraping.timeout_seconds', 10)
    
    headers = {"User-Agent": user_agent}

    # === 1. Try Search APIs (SerpAPI, GoogleCustomSearch, etc.) ===
    for api in SEARCH_APIS:
        api_name = api.get("name")
        endpoint = api.get("endpoint")
        key_name = api.get("key_name")
        api_key_value_ref = api.get("key_value") # This is now the reference string like "load_from_secrets.serpapi_api_key"
        query_param = api.get("query_param", "q")
        default_params = api.get("default_params", {})

        api_key = None
        if api_key_value_ref and api_key_value_ref.startswith("load_from_secrets."):
            # Use config_manager.get_secret to resolve the actual API key
            secret_key_path = api_key_value_ref.split("load_from_secrets.")[1]
            api_key = config_manager.get_secret(secret_key_path)
        elif api_key_value_ref: # If it's a direct value (not recommended for secrets)
            api_key = api_key_value_ref
        
        if not api_key:
            logger.warning(f"API key for {api_name} not found or configured. Skipping this API.")
            continue

        try:
            params = {query_param: query, key_name: api_key, **default_params}
            
            # Special handling for AniList (GraphQL) - scraper_tool primarily for REST/Web
            if api_name == "AniList" and endpoint == "https://graphql.anilist.co/":
                logger.info(f"Skipping {api_name} in scraper_tool; it uses GraphQL and requires specific handling.")
                continue # AniList is GraphQL and needs specific handling, not generic scraping

            logger.info(f"Attempting to use {api_name} at {endpoint} with params: {params}")
            res = requests.get(endpoint, headers=headers, params=params, timeout=request_timeout)
            res.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
            data = res.json()
            
            snippets = extract_snippets_from_api(data, api_name) # Pass api_name for specific parsing
            if snippets:
                combined_snippets = "\n".join(snippets)
                return f"[From {api_name}] {combined_snippets[:max_chars]}..."
        except requests.exceptions.RequestException as req_e:
            logger.error(f"Request failed for {api_name}: {req_e}")
            if hasattr(req_e, 'response') and req_e.response is not None:
                logger.error(f"Response content: {req_e.response.text}")
        except Exception as e:
            logger.error(f"Error processing {api_name} response: {e}")
            continue

    # === 2. Fallback: Wikipedia Search ===
    try:
        wiki_url = f"https://en.wikipedia.org/w/api.php?action=opensearch&search={query}&limit=1&namespace=0&format=json"
        logger.info(f"Attempting Wikipedia search: {wiki_url}")
        wiki_res = requests.get(wiki_url, headers=headers, timeout=request_timeout).json()
        if wiki_res and len(wiki_res) > 3 and wiki_res[3]:
            page_url = wiki_res[3][0] # URL of the best matching page
            page_res = requests.get(page_url, headers=headers, timeout=request_timeout)
            page_res.raise_for_status()
            soup = BeautifulSoup(page_res.text, "html.parser")
            paras = soup.select("p")
            content = "\n".join([p.get_text().strip() for p in paras if p.get_text().strip()])
            if content:
                return f"[From Wikipedia]\n{content[:max_chars]}..."
    except requests.exceptions.RequestException as req_e:
        logger.error(f"Wikipedia request failed: {req_e}")
    except Exception as e:
        logger.error(f"Error processing Wikipedia response: {e}")


    # === 3. Fallback: Generic Google Search Scrape (less reliable due to anti-bot measures) ===
    # This method is less reliable as Google frequently updates its anti-bot measures.
    # Prefer dedicated search APIs (like SerpAPI) if possible.
    try:
        search_url = f"https://www.google.com/search?q={query.strip().replace(' ', '+')}"
        logger.info(f"Attempting generic Google scrape: {search_url}")
        res = requests.get(search_url, headers=headers, timeout=request_timeout)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        
        # Look for common snippet elements - this is highly prone to breaking
        snippets = []
        for span in soup.find_all("span"):
            if 'class' in span.attrs and ('st' in span['class'] or 'LGOjhe' in span['class']): # Common Google snippet classes
                text = span.get_text().strip()
                if len(text) > 40 and text not in snippets:
                    snippets.append(text)
                if len("\n".join(snippets)) >= max_chars:
                    break
        
        if snippets:
            return f"[From Google Search Scrape]\n" + "\n".join(snippets[:5])[:max_chars] + "..."
    except requests.exceptions.RequestException as req_e:
        logger.error(f"Generic Google scrape failed: {req_e}")
    except Exception as e:
        logger.error(f"Error during generic Google scrape: {e}")

    return "Sorry, I couldn't find relevant information via available search methods."


def extract_snippets_from_api(data: dict, api_name: str) -> list:
    """
    Extracts text snippets from known search API responses. Customize per provider.
    """
    snippets = []
    if api_name == "SerpAPI" and "organic_results" in data:
        for r in data["organic_results"]:
            if r.get("snippet"):
                snippets.append(r["snippet"])
            elif r.get("answer_box") and r["answer_box"].get("snippet"):
                snippets.append(r["answer_box"]["snippet"])
            elif r.get("knowledge_graph") and r["knowledge_graph"].get("description"):
                snippets.append(r["knowledge_graph"]["description"])
    elif api_name == "GoogleCustomSearch" and "items" in data:
        for item in data["items"]:
            if item.get("snippet"):
                snippets.append(item["snippet"])
    # Add logic for other search APIs if you integrate more in the future
    return snippets


# CLI Test (optional)
if __name__ == "__main__":
    import streamlit as st
    import shutil
    
    logging.basicConfig(level=logging.INFO)

    # Mock Streamlit secrets for local testing if needed
    class MockSecrets:
        def __init__(self):
            self.serpapi = {"api_key": "YOUR_SERPAPI_KEY"} # Replace with your real SerpAPI key
            self.google = {"api_key": "YOUR_GOOGLE_API_KEY"} # Replace with your real Google API key
            self.google_custom_search = {"api_key": "YOUR_GOOGLE_CUSTOM_SEARCH_API_KEY"} # Replace with your real GCSE API key
            # Mock other keys if needed by config_manager

    # Mock the global config_manager instance if it's not already initialized
    try:
        from config.config_manager import ConfigManager
        
        # Create dummy config.yml for the ConfigManager to load
        dummy_data_dir = Path("data")
        dummy_data_dir.mkdir(exist_ok=True)
        dummy_config_path = dummy_data_dir / "config.yml"
        with open(dummy_config_path, "w") as f:
            f.write("web_scraping:\n  user_agent: Mozilla/5.0 (Test; Python)\n  timeout_seconds: 5\n")
        
        # Create dummy API YAMLs to be loaded by load_search_apis
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


        # Initialize config_manager with mocked secrets
        if not hasattr(st, 'secrets'):
            st.secrets = MockSecrets()
            print("Mocked st.secrets for standalone testing.")
        
        # Ensure config_manager is a fresh instance for this test run
        # Reset the singleton instance to ensure it reloads with mock data
        ConfigManager._instance = None
        ConfigManager._is_loaded = False
        config_manager = ConfigManager()
        print("ConfigManager initialized for testing.")

    except Exception as e:
        print(f"Could not initialize ConfigManager for testing: {e}. Skipping API-dependent tests.")
        config_manager = None # Set to None to skip tests


    print("\nTesting scrape_web:")
    if config_manager:
        # Example 1: Query that might hit SerpAPI (if key is valid)
        query1 = "current weather in London"
        print(f"\nQuery 1: {query1}")
        result1 = scrape_web(query1)
        print(result1)

        # Example 2: Query that might hit Wikipedia
        query2 = "history of artificial intelligence"
        print(f"\nQuery 2: {query2}")
        result2 = scrape_web(query2)
        print(result2)

        # Example 3: Query that might hit generic Google scrape (less reliable)
        query3 = "latest news on quantum computing"
        print(f"\nQuery 3: {query3}")
        result3 = scrape_web(query3)
        print(result3)

    else:
        print("Skipping scrape_web tests due to ConfigManager issues or missing API keys.")

    # Clean up dummy files
    dummy_data_dir = Path("data")
    if dummy_data_dir.exists():
        if dummy_config_path.exists():
            dummy_config_path.unlink()
        if dummy_sports_apis_path.exists():
            dummy_sports_apis_path.unlink()
        if dummy_media_apis_path.exists():
            dummy_media_apis_path.unlink()
        if not os.listdir(dummy_data_dir): # Only remove if empty
            dummy_data_dir.rmdir()
