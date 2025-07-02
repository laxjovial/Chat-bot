# shared_tools/scraper_tool.py

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import logging
from typing import Optional, Dict, Any, List
from langchain_core.tools import tool
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import config_manager for web scraping settings and user tier capabilities
from config.config_manager import config_manager
from utils.user_manager import get_user_tier_capability # For RBAC checks

logger = logging.getLogger(__name__)

# --- Configuration ---
# Get default settings from config_manager
DEFAULT_USER_AGENT = config_manager.get('web_scraping.user_agent', "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_TIMEOUT_SECONDS = config_manager.get('web_scraping.timeout_seconds', 10)
DEFAULT_MAX_SEARCH_RESULTS = config_manager.get('web_scraping.max_search_results', 5)

# --- Helper Functions ---

def _fetch_page_content(url: str, user_agent: str, timeout: int) -> Optional[str]:
    """Fetches content from a single URL."""
    try:
        headers = {'User-Agent': user_agent}
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()  # Raise an exception for HTTP errors
        return response.text
    except requests.exceptions.RequestException as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return None

def _extract_text_from_html(html_content: str, max_chars: int) -> str:
    """Extracts readable text from HTML, limiting by character count."""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove script, style, and other non-content tags
    for script in soup(["script", "style", "header", "footer", "nav", "aside", "form"]):
        script.extract()
    
    text = soup.get_text(separator=' ', strip=True)
    
    # Simple truncation
    if len(text) > max_chars:
        text = text[:max_chars] + "..."
    return text

def _perform_google_search(query: str, api_key: str, cx: str, num_results: int) -> List[Dict[str, str]]:
    """Performs a Google Custom Search API search."""
    search_url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "num": num_results # Number of search results
    }
    try:
        response = requests.get(search_url, params=params, timeout=DEFAULT_TIMEOUT_SECONDS)
        response.raise_for_status()
        search_results = response.json()
        
        items = search_results.get('items', [])
        results = []
        for item in items:
            results.append({
                "title": item.get('title'),
                "link": item.get('link'),
                "snippet": item.get('snippet')
            })
        return results
    except requests.exceptions.RequestException as e:
        logger.error(f"Google Custom Search API failed: {e}")
        return []
    except Exception as e:
        logger.error(f"Error parsing Google Custom Search API response: {e}")
        return []

def _perform_serpapi_search(query: str, api_key: str, num_results: int) -> List[Dict[str, str]]:
    """Performs a SerpAPI Google search."""
    search_url = "https://serpapi.com/search"
    params = {
        "api_key": api_key,
        "q": query,
        "engine": "google",
        "num": num_results # Number of search results
    }
    try:
        response = requests.get(search_url, params=params, timeout=DEFAULT_TIMEOUT_SECONDS)
        response.raise_for_status()
        search_results = response.json()
        
        organic_results = search_results.get('organic_results', [])
        results = []
        for item in organic_results:
            results.append({
                "title": item.get('title'),
                "link": item.get('link'),
                "snippet": item.get('snippet')
            })
        return results
    except requests.exceptions.RequestException as e:
        logger.error(f"SerpAPI search failed: {e}")
        return []
    except Exception as e:
        logger.error(f"Error parsing SerpAPI response: {e}")
        return []

# --- Main Tool Function ---

@tool
def scrape_web(query: str, user_token: str, max_chars: int = 2000) -> str:
    """
    Searches the web for information based on the query and scrapes content from top results.
    It attempts to use configured search APIs (Google Custom Search, SerpAPI) first,
    then falls back to a direct web search if no API is configured or available.
    
    Args:
        query (str): The search query.
        user_token (str): The unique identifier for the user, used for RBAC checks.
        max_chars (int): The maximum number of characters to return from each scraped page's content.
                         This will be capped by the user's tier capability.
    
    Returns:
        str: A concatenated string of titles, links, and snippets from search results,
             followed by scraped content from the top relevant pages.
    """
    logger.info(f"Tool: scrape_web called with query: '{query}' for user: '{user_token}'")

    # --- RBAC Enforcement for Web Search ---
    # Get user's allowed max characters and max results from config
    allowed_max_chars = get_user_tier_capability(user_token, 'web_search_limit_chars', DEFAULT_MAX_SEARCH_RESULTS)
    allowed_max_results = get_user_tier_capability(user_token, 'web_search_max_results', DEFAULT_MAX_SEARCH_RESULTS)

    # Cap the requested max_chars and num_results to the user's allowed limits
    max_chars = min(max_chars, allowed_max_chars)
    num_results = min(DEFAULT_MAX_SEARCH_RESULTS, allowed_max_results) # Use DEFAULT_MAX_SEARCH_RESULTS as an upper bound from config

    if not get_user_tier_capability(user_token, 'web_search_enabled', True): # Assuming web search is generally enabled unless specified
        return "Access Denied: Web search is not enabled for your current tier. Please upgrade your plan."


    search_results = []
    
    # Try Google Custom Search API first
    google_api_key = config_manager.get_secret('google_custom_search.api_key')
    google_cx = config_manager.get_secret('google_custom_search.cx')
    if google_api_key and google_cx:
        logger.info("Attempting Google Custom Search API...")
        search_results = _perform_google_search(query, google_api_key, google_cx, num_results)
        if search_results:
            logger.info(f"Found {len(search_results)} results from Google Custom Search API.")
    
    # Fallback to SerpAPI if Google Custom Search failed or not configured
    if not search_results:
        serpapi_api_key = config_manager.get_secret('serpapi.api_key')
        if serpapi_api_key:
            logger.info("Attempting SerpAPI search...")
            search_results = _perform_serpapi_search(query, serpapi_api_key, num_results)
            if search_results:
                logger.info(f"Found {len(search_results)} results from SerpAPI.")

    # Fallback to direct web search (less effective for targeted results) if no API results
    if not search_results:
        logger.warning("No search API configured or failed. Falling back to generic web search (less effective).")
        # In a real scenario, you'd integrate a direct web search library or a simpler scraping approach
        # For now, we'll just return a message if no API results.
        return "No direct search API results found. Please ensure your search API keys are configured correctly in .streamlit/secrets.toml if you expect specific search functionality."

    combined_content = []
    
    # Add search result snippets
    for i, result in enumerate(search_results):
        combined_content.append(f"--- Search Result {i+1} ---\n")
        combined_content.append(f"Title: {result.get('title', 'N/A')}\n")
        combined_content.append(f"Link: {result.get('link', 'N/A')}\n")
        combined_content.append(f"Snippet: {result.get('snippet', 'N/A')}\n\n")
        
        # Attempt to scrape content from the link if it's a valid URL and within limits
        link = result.get('link')
        if link and urlparse(link).scheme in ['http', 'https']:
            try:
                # Scrape only a limited number of top results to avoid excessive requests
                if i < num_results: # Only scrape up to num_results pages
                    page_content = _fetch_page_content(link, DEFAULT_USER_AGENT, DEFAULT_TIMEOUT_SECONDS)
                    if page_content:
                        extracted_text = _extract_text_from_html(page_content, max_chars)
                        combined_content.append(f"Scraped Content from {link}:\n{extracted_text}\n\n")
            except Exception as e:
                logger.warning(f"Error scraping content from {link}: {e}")
                combined_content.append(f"Error scraping content from {link}: {e}\n\n")

    if not combined_content:
        return "No relevant information found on the web for your query."
        
    return "\n".join(combined_content)

# CLI Test (optional)
if __name__ == "__main__":
    import streamlit as st
    import os
    from config.config_manager import ConfigManager # Import ConfigManager for testing setup
    from unittest.mock import MagicMock

    logging.basicConfig(level=logging.INFO)

    # Mock Streamlit secrets for local testing if needed
    class MockSecrets:
        def __init__(self):
            self.serpapi = {"api_key": "YOUR_SERPAPI_KEY"} # Replace with a real key for testing
            self.google_custom_search = {"api_key": "YOUR_GOOGLE_CUSTOM_SEARCH_API_KEY", "cx": "YOUR_GOOGLE_CX"} # Replace with real keys
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

    # Mock user_manager.find_user_by_token for testing RBAC
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
            
            # Mock config_manager.get for tier capabilities
            mock_tier_configs = {
                "free": {
                    "web_search_limit_chars": 500,
                    "web_search_max_results": 2,
                    "web_search_enabled": True
                },
                "pro": {
                    "web_search_limit_chars": 3000,
                    "web_search_max_results": 7,
                    "web_search_enabled": True
                },
                "elite": {
                    "web_search_limit_chars": 5000,
                    "web_search_max_results": 10,
                    "web_search_enabled": True
                },
                # Add other tiers as needed for testing
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
                'web_scraping': {
                    'user_agent': 'Mozilla/5.0 (Test; Python)',
                    'timeout_seconds': 5,
                    'max_search_results': 5 # Default for config
                },
                'tiers': {
                    'free': {
                        'web_search_limit_chars': 500,
                        'web_search_max_results': 2
                    },
                    'pro': {
                        'web_search_limit_chars': 3000,
                        'web_search_max_results': 7
                    },
                    'elite': {
                        'web_search_limit_chars': 5000,
                        'web_search_max_results': 10
                    },
                    'premium': {
                        'web_search_limit_chars': 10000,
                        'web_search_max_results': 15
                    }
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

    print("\n--- Testing scraper_tool.py with RBAC ---")
    
    # Test with free user
    print("\n--- Free User (limited) ---")
    free_user_token = st.secrets.user_tokens["free_user_token"]
    result_free = scrape_web(query="latest tech news", user_token=free_user_token, max_chars=5000) # Request more than allowed
    print(f"Free User Result (first 500 chars):\n{result_free[:500]}...")
    # Assertions for free user (should be capped)
    assert "..." in result_free # Should be truncated
    # Note: Cannot easily assert num_results from string output, but the internal logic should cap it.

    # Test with pro user
    print("\n--- Pro User (standard) ---")
    pro_user_token = st.secrets.user_tokens["pro_user_token"]
    result_pro = scrape_web(query="stock market analysis", user_token=pro_user_token, max_chars=1000)
    print(f"Pro User Result (first 500 chars):\n{result_pro[:500]}...")

    # Test with admin user
    print("\n--- Admin User (unlimited) ---")
    admin_user_token = st.secrets.user_tokens["admin_user_token"]
    result_admin = scrape_web(query="global warming research", user_token=admin_user_token, max_chars=10000)
    print(f"Admin User Result (first 500 chars):\n{result_admin[:500]}...")

    print("\n--- RBAC tests for scraper_tool completed. ---")

    # Clean up dummy config files (if created by this test script)
    dummy_data_dir = Path("data")
    if dummy_data_dir.exists():
        for f in dummy_data_dir.iterdir():
            if f.is_file():
                os.remove(f)
        if not os.listdir(dummy_data_dir):
            os.rmdir(dummy_data_dir)
