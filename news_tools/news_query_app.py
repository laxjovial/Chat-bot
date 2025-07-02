# news_query_app.py

import streamlit as st
import logging
import json
import pandas as pd # Potentially useful for displaying structured data

# Assume config_manager and get_user_token exist
from config.config_manager import config_manager
from utils.user_manager import get_user_token

from news_tools.news_tool import (
    news_search_web, 
    news_data_fetcher,
    trending_news_checker
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
                self.newsapi_api_key = "YOUR_NEWSAPI_API_KEY_HERE"
                self.gnews_api_key = "YOUR_GNEWS_API_KEY_HERE"
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
st.set_page_config(page_title="News Query Tools", page_icon="📰", layout="centered")
st.title("News Query Tools 📰")

st.markdown("Access various news and current events tools directly.")

user_token = get_user_token() # Get user token for personalization

tool_selection = st.selectbox(
    "Select a News Tool:",
    (
        "Web Search (General News)",
        "Top Headlines",
        "Everything Search (Keywords)",
        "Trending News Checker",
        "News Data Fetcher (Advanced)"
    )
)

# --- Web Search ---
if tool_selection == "Web Search (General News)":
    st.subheader("General News Web Search")
    query = st.text_input("Enter your news web query:", placeholder="e.g., 'latest political developments', 'breakthroughs in renewable energy'")
    max_chars = st.slider("Maximum characters in result snippet:", min_value=100, max_value=5000, value=1500, step=100)

    if st.button("Search Web"):
        if query:
            with st.spinner("Searching the web..."):
                try:
                    result = news_search_web(query=query, user_token=user_token, max_chars=max_chars)
                    st.subheader("Search Results:")
                    st.markdown(result)
                except Exception as e:
                    st.error(f"An error occurred during web search: {e}")
                    logger.error(f"Web search failed: {e}", exc_info=True)
        else:
            st.warning("Please enter a query to search.")

# --- Top Headlines ---
elif tool_selection == "Top Headlines":
    st.subheader("Top Headlines")
    category_input = st.selectbox(
        "Category (optional):",
        ["", "business", "entertainment", "general", "health", "science", "sports", "technology"],
        key="top_headlines_category"
    )
    country_input = st.text_input("Country (ISO 2-letter code, e.g., us, gb, de, optional):", placeholder="us", key="top_headlines_country")
    language_input = st.text_input("Language (ISO 2-letter code, e.g., en, es, optional):", value="en", key="top_headlines_language")
    limit_input = st.number_input("Limit results:", min_value=1, value=5, step=1, key="top_headlines_limit")

    if st.button("Get Top Headlines"):
        with st.spinner("Fetching top headlines..."):
            try:
                result = news_data_fetcher(
                    api_name="NewsAPI", # Using NewsAPI as primary for this
                    data_type="top_headlines",
                    category=category_input if category_input else None,
                    country=country_input if country_input else None,
                    language=language_input if language_input else "en",
                    limit=limit_input
                )
                st.subheader("Top Headlines:")
                try:
                    parsed_data = json.loads(result)
                    articles = parsed_data.get('articles', [])
                    if articles:
                        for article in articles:
                            st.write(f"**{article.get('title')}**")
                            st.write(f"Source: {article.get('source', {}).get('name')} | Published: {article.get('publishedAt')}")
                            st.write(article.get('description'))
                            st.markdown(f"[Read more]({article.get('url')})")
                            st.markdown("---")
                    else:
                        st.info("No headlines found for the selected criteria.")
                except json.JSONDecodeError:
                    st.write(result)
            except Exception as e:
                st.error(f"An error occurred while fetching top headlines: {e}")
                logger.error(f"Top headlines fetch failed: {e}", exc_info=True)

# --- Everything Search (Keywords) ---
elif tool_selection == "Everything Search (Keywords)":
    st.subheader("Comprehensive News Search (Keywords)")
    query_input = st.text_input("Enter keywords for news search:", placeholder="e.g., 'climate change policy', 'new space launch'", key="everything_search_query")
    language_input = st.text_input("Language (ISO 2-letter code, e.g., en, es, optional):", value="en", key="everything_search_language")
    limit_input = st.number_input("Limit results:", min_value=1, value=5, step=1, key="everything_search_limit")

    if st.button("Search All News"):
        if query_input:
            with st.spinner("Searching all news articles..."):
                try:
                    result = news_data_fetcher(
                        api_name="NewsAPI", # Using NewsAPI for everything search
                        data_type="everything_search",
                        query=query_input,
                        language=language_input if language_input else "en",
                        limit=limit_input
                    )
                    st.subheader(f"Search Results for '{query_input}':")
                    try:
                        parsed_data = json.loads(result)
                        articles = parsed_data.get('articles', [])
                        if articles:
                            for article in articles:
                                st.write(f"**{article.get('title')}**")
                                st.write(f"Source: {article.get('source', {}).get('name')} | Published: {article.get('publishedAt')}")
                                st.write(article.get('description'))
                                st.markdown(f"[Read more]({article.get('url')})")
                                st.markdown("---")
                        else:
                            st.info("No articles found for your query.")
                    except json.JSONDecodeError:
                        st.write(result)
                except Exception as e:
                    st.error(f"An error occurred during comprehensive search: {e}")
                    logger.error(f"Everything search failed: {e}", exc_info=True)
        else:
            st.warning("Please enter keywords for your search.")

# --- Trending News Checker ---
elif tool_selection == "Trending News Checker":
    st.subheader("Trending News Checker")
    category_input = st.selectbox(
        "Category (optional):",
        ["", "business", "entertainment", "general", "health", "science", "sports", "technology"],
        key="trending_news_category"
    )
    country_input = st.text_input("Country (ISO 2-letter code, e.g., us, gb, de, optional):", placeholder="us", key="trending_news_country")
    
    if st.button("Check Trending News"):
        with st.spinner("Checking for trending news..."):
            try:
                result = trending_news_checker(
                    category=category_input if category_input else "general",
                    country=country_input if country_input else "us"
                )
                st.subheader("Currently Trending News:")
                st.markdown(result)
            except Exception as e:
                st.error(f"An error occurred while checking trending news: {e}")
                logger.error(f"Trending news checker failed: {e}", exc_info=True)

# --- News Data Fetcher (Advanced) ---
elif tool_selection == "News Data Fetcher (Advanced)":
    st.subheader("Advanced News Data Fetcher")
    st.info("This tool directly interacts with configured news APIs. Note that real news APIs may require specific access and have usage limits.")

    api_name = st.selectbox(
        "Select API to use:",
        ("NewsAPI", "GNewsAPI"),
        key="advanced_news_api_select"
    )

    data_type_options = []
    if api_name == "NewsAPI":
        data_type_options = ["top_headlines", "everything_search", "sources"]
    elif api_name == "GNewsAPI":
        data_type_options = ["top_headlines"]

    data_type = st.selectbox(
        "Select Data Type:",
        data_type_options,
        key="advanced_news_data_type_select"
    )

    query_input_adv = st.text_input("Query (keywords, optional):", key="query_input_adv")
    category_input_adv = st.text_input("Category (optional):", key="category_input_adv")
    country_input_adv = st.text_input("Country (ISO 2-letter code, optional):", key="country_input_adv")
    source_input_adv = st.text_input("Source ID (e.g., bbc-news, cnn, optional):", key="source_input_adv")
    language_input_adv = st.text_input("Language (ISO 2-letter code, optional):", value="en", key="language_input_adv")
    limit_input_adv = st.number_input("Limit results (optional):", min_value=1, value=10, step=1, key="limit_input_adv")

    if st.button("Fetch Advanced News Data"):
        if not (query_input_adv or category_input_adv or country_input_adv or source_input_adv or data_type == "sources"):
            st.warning("Please provide at least a query, category, country, source, or select 'sources' data type.")
        else:
            with st.spinner(f"Fetching {data_type} data from {api_name}..."):
                try:
                    result_json_str = news_data_fetcher(
                        api_name=api_name,
                        data_type=data_type,
                        query=query_input_adv if query_input_adv else None,
                        category=category_input_adv if category_input_adv else None,
                        country=country_input_adv if country_input_adv else None,
                        source=source_input_adv if source_input_adv else None,
                        language=language_input_adv if language_input_adv else "en",
                        limit=limit_input_adv if limit_input_adv > 0 else None
                    )
                    
                    st.subheader("Fetched Data:")
                    try:
                        parsed_data = json.loads(result_json_str)
                        st.json(parsed_data)
                        
                        # Attempt to display articles as DataFrame if suitable
                        if parsed_data.get('articles') and isinstance(parsed_data['articles'], list):
                            try:
                                df = pd.DataFrame(parsed_data['articles'])
                                st.subheader("Articles as DataFrame:")
                                st.dataframe(df[['title', 'source', 'publishedAt', 'url']])
                            except Exception as df_e:
                                logger.warning(f"Could not convert fetched articles to DataFrame: {df_e}")
                                st.write("Could not display as DataFrame.")
                        elif parsed_data.get('sources') and isinstance(parsed_data['sources'], list):
                            try:
                                df = pd.DataFrame(parsed_data['sources'])
                                st.subheader("Sources as DataFrame:")
                                st.dataframe(df[['id', 'name', 'description', 'category', 'language', 'country']])
                            except Exception as df_e:
                                logger.warning(f"Could not convert fetched sources to DataFrame: {df_e}")
                                st.write("Could not display as DataFrame.")
                        elif isinstance(parsed_data, dict):
                            st.write("Data is a dictionary.")

                    except json.JSONDecodeError:
                        st.write(result_json_str) # If not JSON, display as plain text
                    
                except Exception as e:
                    st.error(f"An error occurred during data fetching: {e}")
                    logger.error(f"News data fetcher failed: {e}", exc_info=True)


st.markdown("---")
st.caption(f"Current User Token: `{get_user_token()}` (for demo purposes)")
st.caption("This app provides direct access to various news tools.")
