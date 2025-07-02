# news_tools/news_tool.py

import requests
import json
from typing import Optional, List, Dict, Any
from pathlib import Path
import logging
import yaml # Added for loading news_apis.yaml

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

# Constants for the news section
NEWS_SECTION = "news"
DEFAULT_USER_TOKEN = "default" # Or use a proper user management if available

logger = logging.getLogger(__name__)

@tool
def news_search_web(query: str, user_token: str = DEFAULT_USER_TOKEN, max_chars: int = 2000) -> str:
    """
    Searches the web for general news or current events using a smart search fallback mechanism.
    This tool wraps the generic `scrape_web` tool, providing a news-specific interface.
    
    Args:
        query (str): The news-related search query (e.g., "latest political developments", "breakthroughs in science").
        user_token (str): The unique identifier for the user. Defaults to "default".
        max_chars (int): Maximum characters for the returned snippet. Defaults to 2000.
    
    Returns:
        str: A string containing relevant information from the web.
    """
    logger.info(f"Tool: news_search_web called with query: '{query}' for user: '{user_token}'")
    return scrape_web(query=query, user_token=user_token, max_chars=max_chars)

@tool
def news_query_uploaded_docs(query: str, user_token: str = DEFAULT_USER_TOKEN, export: Optional[bool] = False, k: int = 5) -> str:
    """
    Queries previously uploaded and indexed news documents or research papers for a user using vector similarity search.
    This tool wraps the generic `QueryUploadedDocs` tool, fixing the section to "news".
    
    Args:
        query (str): The search query to find relevant news/research documents (e.g., "summary of the economic report I uploaded", "what did I save about renewable energy news").
        user_token (str): The unique identifier for the user. Defaults to "default".
        export (bool): If True, the results will be saved to a file in markdown format. Defaults to False.
        k (int): The number of top relevant documents to retrieve. Defaults to 5.
    
    Returns:
        str: A string containing the combined content of the relevant document chunks,
             or a message indicating no data/results found, or the export path if exported.
    """
    logger.info(f"Tool: news_query_uploaded_docs called with query: '{query}' for user: '{user_token}'")
    return QueryUploadedDocs(query=query, user_token=user_token, section=NEWS_SECTION, export=export, k=k)

@tool
def news_summarize_document_by_path(file_path_str: str) -> str:
    """
    Summarizes a document related to news or current events located at the given file path.
    The file path should be accessible by the system (e.g., in the 'uploads' directory).
    This tool wraps the generic `summarize_document` tool.
    
    Args:
        file_path_str (str): The full path to the document file to be summarized.
                              Example: "uploads/default/news/daily_briefing.pdf"
    
    Returns:
        str: A concise summary of the document content.
    """
    logger.info(f"Tool: news_summarize_document_by_path called for file: '{file_path_str}'")
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

# === Advanced News Tools ===

# Initialize the Python REPL tool.
python_repl = PythonREPLTool()
python_repl.name = "python_interpreter"
python_repl.description = """
Executes Python code. Use this for complex data analysis, calculations, or any task that requires programmatic logic
on structured news data (e.g., analyzing news sentiment, topic modeling on headlines, tracking news frequency).
Input should be a valid Python code string.
The output will be the result of the code execution (stdout/stderr).
You have access to common libraries like pandas, numpy, matplotlib, datetime, json, etc.
Example:
Action: python_interpreter
Action Input:
import json
import pandas as pd
data = json.loads(tool_output) # Assuming tool_output from news_data_fetcher
df = pd.DataFrame(data['articles'])
print(df['title'].head())
"""

# Helper to load API configs
def _load_news_apis() -> Dict[str, Any]:
    """Loads news API configurations from data/news_apis.yaml."""
    news_apis_path = Path("data/news_apis.yaml")
    if not news_apis_path.exists():
        logger.warning(f"data/news_apis.yaml not found at {news_apis_path}")
        return {}
    try:
        with open(news_apis_path, "r") as f:
            full_config = yaml.safe_load(f) or {}
            return {api['name']: api for api in full_config.get('apis', [])}
    except Exception as e:
        logger.error(f"Error loading news_apis.yaml: {e}")
        return {}

NEWS_APIS_CONFIG = _load_news_apis()

@tool
def news_data_fetcher(
    api_name: str,
    data_type: str, # e.g., "top_headlines", "everything_search", "sources"
    query: Optional[str] = None, # For search queries (keywords)
    category: Optional[str] = None, # e.g., "business", "technology", "sports", "health"
    country: Optional[str] = None, # e.g., "us", "gb", "de" (ISO 2-letter country code)
    source: Optional[str] = None, # Specific news source ID (e.g., "bbc-news", "cnn")
    language: Optional[str] = "en", # ISO 2-letter language code
    limit: Optional[int] = None # For number of articles
) -> str:
    """
    Fetches news data (headlines, articles, sources) from configured APIs.
    This is a placeholder and needs actual implementation to connect to real news APIs
    like NewsAPI.org, GNews, Mediastack, etc.
    
    Args:
        api_name (str): The name of the API to use (e.g., "NewsAPI", "GNewsAPI").
                        This must match a 'name' field in data/news_apis.yaml.
        data_type (str): The type of news data to fetch (e.g., "top_headlines", "everything_search", "sources").
        query (str, optional): Keywords or phrases for searching articles.
        category (str, optional): Specific news category (e.g., "business", "technology").
        country (str, optional): ISO 2-letter country code for top headlines (e.g., "us", "gb").
        source (str, optional): Specific news source ID (e.g., "bbc-news").
        language (str, optional): ISO 2-letter language code (e.g., "en", "es"). Defaults to "en".
        limit (int, optional): Maximum number of articles to return.
        
    Returns:
        str: A JSON string of the fetched news data or an error message.
             The agent can then use `python_interpreter` to parse and analyze this JSON.
    """
    logger.info(f"Tool: news_data_fetcher called for API: {api_name}, data_type: {data_type}, query: '{query}', category: '{category}', country: '{country}', source: '{source}'")

    api_info = NEWS_APIS_CONFIG.get(api_name)
    if not api_info:
        return f"Error: API '{api_name}' not found in data/news_apis.yaml configuration."

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
    
    if key_name and api_key:
        if key_name.lower() == "authorization": # Handle Bearer tokens
            headers["Authorization"] = f"Bearer {api_key}"
        else:
            default_params[key_name] = api_key
    elif key_name and not api_key:
        logger.warning(f"API key for '{api_name}' not found in secrets.toml. Proceeding without key if API allows.")

    params = {**default_params} # Start with default parameters
    url = endpoint

    try:
        # --- Placeholder/Mock Implementations ---
        if api_name == "NewsAPI":
            if data_type == "top_headlines":
                return json.dumps({
                    "status": "ok",
                    "totalResults": 2,
                    "articles": [
                        {"title": f"Mock Headline: {query or 'Global Economy Update'}", "source": {"name": "Mock News"}, "publishedAt": "2024-07-02T10:00:00Z", "description": "A mock description of a top headline.", "url": "http://mocknews.com/article1"},
                        {"title": "Another Mock Headline", "source": {"name": "Mock News"}, "publishedAt": "2024-07-02T09:30:00Z", "description": "Another mock description.", "url": "http://mocknews.com/article2"}
                    ][:limit if limit else 2]
                })
            elif data_type == "everything_search":
                if not query: return "Error: 'query' is required for everything_search."
                return json.dumps({
                    "status": "ok",
                    "totalResults": 1,
                    "articles": [
                        {"title": f"Search Result for '{query}'", "source": {"name": "Mock Search News"}, "publishedAt": "2024-07-01T15:00:00Z", "description": f"A mock article containing information about '{query}'.", "url": "http://mocksearch.com/article_query"}
                    ][:limit if limit else 1]
                })
            elif data_type == "sources":
                return json.dumps({
                    "status": "ok",
                    "sources": [
                        {"id": "bbc-news", "name": "BBC News", "description": "Provides news, sport, business, arts, culture and more.", "category": "general"},
                        {"id": "cnn", "name": "CNN", "description": "View the latest news and breaking news today for U.S., world, weather, entertainment, politics and health.", "category": "general"}
                    ]
                })
            else:
                return f"Error: Unsupported data_type '{data_type}' for NewsAPI."
        
        elif api_name == "GNewsAPI":
            if data_type == "top_headlines":
                return json.dumps({
                    "totalArticles": 2,
                    "articles": [
                        {"title": f"GNews Mock Headline: {query or 'Tech Innovation'}", "description": "A mock GNews headline about tech.", "source": {"name": "GNews Source"}, "publishedAt": "2024-07-02T11:00:00Z", "url": "http://gnews.com/article1"},
                        {"title": "Another GNews Mock Headline", "description": "Another mock GNews description.", "source": {"name": "GNews Source"}, "publishedAt": "2024-07-02T10:45:00Z", "url": "http://gnews.com/article2"}
                    ][:limit if limit else 2]
                })
            else:
                return f"Error: Unsupported data_type '{data_type}' for GNewsAPI."

        else:
            return f"Error: API '{api_name}' is not supported by news_data_fetcher."

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
def trending_news_checker(category: Optional[str] = "general", country: Optional[str] = "us") -> str:
    """
    Identifies currently trending news topics or top headlines for a given category and country.
    
    Args:
        category (str, optional): The news category (e.g., "business", "technology", "sports", "health"). Defaults to "general".
        country (str, optional): The ISO 2-letter country code (e.g., "us", "gb", "de"). Defaults to "us".
        
    Returns:
        str: A list of trending news headlines or a message indicating no trending news.
    """
    logger.info(f"Tool: trending_news_checker called for category: '{category}', country: '{country}'")
    # This tool leverages news_data_fetcher to get top headlines
    result = news_data_fetcher(api_name="NewsAPI", data_type="top_headlines", category=category, country=country, limit=5)
    
    try:
        parsed_data = json.loads(result)
        articles = parsed_data.get('articles', [])
        if articles:
            trending_headlines = [f"- {article.get('title')} (Source: {article.get('source', {}).get('name')})" for article in articles]
            return f"**Trending News in {country.upper()} ({category.capitalize()}):**\n" + "\n".join(trending_headlines)
        else:
            return f"No trending news found for category '{category}' in '{country.upper()}' at this time."
    except json.JSONDecodeError:
        return f"Could not parse news data: {result}"
    except Exception as e:
        logger.error(f"Error processing trending news: {e}", exc_info=True)
        return f"An error occurred while checking trending news: {e}"


# CLI Test (optional)
if __name__ == "__main__":
    import streamlit as st
    import shutil
    import os
    from config.config_manager import ConfigManager # Import ConfigManager for testing setup
    from shared_tools.llm_embedding_utils import get_llm # For testing summarization with a real LLM

    logging.basicConfig(level=logging.INFO)

    # Mock Streamlit secrets for local testing if needed
    class MockSecrets:
        def __init__(self):
            self.openai = {"api_key": "sk-mock-openai-key-12345"} # Replace with a real key
            self.google = {"api_key": "AIzaSy-mock-google-key"} # Replace with a real key
            self.ollama = {"api_url": "http://localhost:11434", "model": "llama3"}
            self.serpapi = {"api_key": "YOUR_SERPAPI_KEY"} # For scrape_web testing
            self.google_custom_search = {"api_key": "YOUR_GOOGLE_CUSTOM_SEARCH_API_KEY"} # For scrape_web testing
            self.newsapi_api_key = "YOUR_NEWSAPI_API_KEY" # For NewsAPI.org
            self.gnews_api_key = "YOUR_GNEWS_API_KEY" # For GNews API

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
        # Create dummy API YAMLs for scraper_tool and news_data_fetcher
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
apis: []
search_apis: []
""")
        dummy_finance_apis_path = dummy_data_dir / "finance_apis.yaml"
        with open(dummy_finance_apis_path, "w") as f:
            f.write("""
apis: []
search_apis: []
""")
        dummy_medical_apis_path = dummy_data_dir / "medical_apis.yaml"
        with open(dummy_medical_apis_path, "w") as f:
            f.write("""
apis: []
search_apis: []
""")
        dummy_legal_apis_path = dummy_data_dir / "legal_apis.yaml"
        with open(dummy_legal_apis_path, "w") as f:
            f.write("""
apis: []
search_apis: []
""")
        dummy_weather_apis_path = dummy_data_dir / "weather_apis.yaml"
        with open(dummy_weather_apis_path, "w") as f:
            f.write("""
apis: []
search_apis: []
""")
        dummy_news_apis_path = dummy_data_dir / "news_apis.yaml"
        with open(dummy_news_apis_path, "w") as f:
            f.write("""
apis:
  - name: "NewsAPI"
    type: "news"
    endpoint: "https://newsapi.org/v2/"
    key_name: "apiKey"
    key_value: "load_from_secrets.newsapi_api_key"
    headers: {}
    default_params: {}
    functions:
      top_headlines: {path: "top-headlines"}
      everything_search: {path: "everything"}
      sources: {path: "sources"}
    query_param: "q"

  - name: "GNewsAPI"
    type: "news"
    endpoint: "https://gnews.io/api/v4/"
    key_name: "token"
    key_value: "load_from_secrets.gnews_api_key"
    headers: {}
    default_params: {}
    functions:
      top_headlines: {path: "top-headlines"}
    query_param: "q"
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

    print("\n--- Testing news_tool functions ---")
    test_user = "test_user_news"
    
    if config_manager:
        # Test news_search_web
        print("\n--- Testing news_search_web ---")
        search_query = "latest developments in AI ethics"
        search_result = news_search_web(search_query, user_token=test_user)
        print(f"Search Result for '{search_query}':\n{search_result[:500]}...")

        # Prepare dummy data for news_query_uploaded_docs
        print("\n--- Preparing dummy data for news_query_uploaded_docs ---")
        dummy_json_path = Path("temp_news_docs.json")
        dummy_data = [
            {"id": 1, "text": "An article discussing the rise of generative AI in content creation.", "topic": "AI"},
            {"id": 2, "text": "Summary of a report on global climate change initiatives.", "topic": "environment"},
            {"id": 3, "text": "My notes on the recent political election results.", "topic": "politics"}
        ]
        with open(dummy_json_path, "w", encoding="utf-8") as f:
            json.dump(dummy_data, f)
        
        # Load documents from the dummy JSON for build_vectorstore
        loaded_docs_for_vector = load_docs_from_json_file(dummy_json_path)
        for i, doc in enumerate(loaded_docs_for_vector):
            doc.page_content = dummy_data[i]["text"]

        build_vectorstore(test_user, NEWS_SECTION, loaded_docs_for_vector, chunk_size=200, chunk_overlap=0)
        print(f"Vectorstore built for {NEWS_SECTION}.")

        # Test news_query_uploaded_docs
        print("\n--- Testing news_query_uploaded_docs ---")
        doc_query = "What did I save about AI?"
        doc_results = news_query_uploaded_docs(doc_query, user_token=test_user)
        print(f"Query uploaded docs for '{doc_query}':\n{doc_results}")

        # Test news_summarize_document_by_path
        print("\n--- Testing news_summarize_document_by_path ---")
        # Create a dummy upload directory and file
        test_upload_dir = Path("uploads") / test_user / NEWS_SECTION
        test_upload_dir.mkdir(parents=True, exist_ok=True)
        summarize_file_path = test_upload_dir / "news_brief.txt"
        with open(summarize_file_path, "w") as f:
            f.write("This news brief covers the latest quarterly earnings reports from major tech companies. " * 30 + 
                    "Apple reported strong iPhone sales, while Google saw growth in its cloud division. " * 20 +
                    "Amazon's e-commerce revenue slightly missed expectations but AWS continued its robust performance." * 25)
        print(f"Created dummy file for summarization: {summarize_file_path}")

        summary_result = news_summarize_document_by_path(str(summarize_file_path))
        print(summary_result)

        # Test news_data_fetcher (mocked)
        print("\n--- Testing news_data_fetcher (mocked) ---")
        top_headlines_us = news_data_fetcher(api_name="NewsAPI", data_type="top_headlines", country="us")
        print(f"Top Headlines (US, NewsAPI): {top_headlines_us[:200]}...")
        search_ai = news_data_fetcher(api_name="NewsAPI", data_type="everything_search", query="artificial intelligence")
        print(f"Everything Search (AI, NewsAPI): {search_ai[:200]}...")
        gnews_headlines = news_data_fetcher(api_name="GNewsAPI", data_type="top_headlines", category="technology")
        print(f"GNews Top Headlines (Technology): {gnews_headlines[:200]}...")

        # Test trending_news_checker
        print("\n--- Testing trending_news_checker ---")
        trending_tech_news = trending_news_checker(category="technology", country="gb")
        print(f"Trending Tech News (GB): {trending_tech_news}")

        # Test python_interpreter (example with mock data)
        print("\n--- Testing python_interpreter with mock data ---")
        python_code_news_data = """
import json
import pandas as pd
mock_articles = '''{
    "articles": [
        {"title": "AI in Healthcare", "source": "Tech News", "sentiment": "positive"},
        {"title": "Market Downturn", "source": "Finance Daily", "sentiment": "negative"},
        {"title": "New Sports League", "source": "Sports Weekly", "sentiment": "positive"}
    ]
}'''
data = json.loads(mock_articles)
df = pd.DataFrame(data['articles'])
sentiment_counts = df['sentiment'].value_counts()
print(f"Article sentiment distribution:\n{sentiment_counts}")
"""
        print(f"Executing Python code:\n{python_code_news_data}")
        try:
            repl_output = python_repl.run(python_code_news_data)
            print(f"Python REPL Output:\n{repl_output}")
        except Exception as e:
            print(f"Error executing Python REPL: {e}. Make sure pandas, numpy, json are installed.")


    else:
        print("Skipping news_tool tests due to ConfigManager issues or missing API keys.")

    # Clean up dummy files and directories
    dummy_json_path = Path("temp_news_docs.json")
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
        dummy_medical_apis_path = dummy_data_dir / "medical_apis.yaml"
        dummy_legal_apis_path = dummy_data_dir / "legal_apis.yaml"
        dummy_weather_apis_path = dummy_data_dir / "weather_apis.yaml"
        dummy_news_apis_path = dummy_data_dir / "news_apis.yaml"

        if dummy_config_path.exists(): os.remove(dummy_config_path)
        if dummy_sports_apis_path.exists(): os.remove(dummy_sports_apis_path)
        if dummy_media_apis_path.exists(): os.remove(dummy_media_apis_path)
        if dummy_finance_apis_path.exists(): os.remove(dummy_finance_apis_path)
        if dummy_medical_apis_path.exists(): os.remove(dummy_medical_apis_path)
        if dummy_legal_apis_path.exists(): os.remove(dummy_legal_apis_path)
        if dummy_weather_apis_path.exists(): os.remove(dummy_weather_apis_path)
        if dummy_news_apis_path.exists(): os.remove(dummy_news_apis_path)
        if not os.listdir(dummy_data_dir):
            os.rmdir(dummy_data_dir)
