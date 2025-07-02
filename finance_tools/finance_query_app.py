# finance_query_app.py

import streamlit as st
import logging
import json
import pandas as pd

# Assume config_manager and get_user_token exist
from config.config_manager import config_manager
from utils.user_manager import get_user_token

from finance_tools.finance_tool import finance_search_web, finance_data_fetcher

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
                self.alphavantage = {"api_key": "YOUR_ALPHAVANTAGE_API_KEY_HERE"}
                self.financial_news = {"api_key": "YOUR_FINANCIAL_NEWS_API_KEY_HERE"}
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
st.set_page_config(page_title="Finance Web & Data Query", page_icon="📊", layout="centered")
st.title("Finance Web & Data Query 📊")

st.markdown("Query the web for general financial news or fetch specific financial data (e.g., stock prices).")

user_token = get_user_token() # Get user token for personalization

query_type = st.radio("Select Query Type:", ("Web Search", "Financial Data Fetcher"))

if query_type == "Web Search":
    st.subheader("Web Search for Financial News/Information")
    query = st.text_input("Enter your financial web query:", placeholder="e.g., 'latest S&P 500 news', 'impact of interest rates on housing market'")
    max_chars = st.slider("Maximum characters in result snippet:", min_value=100, max_value=5000, value=1500, step=100)

    if st.button("Search Web"):
        if query:
            with st.spinner("Searching the web..."):
                try:
                    result = finance_search_web(query=query, user_token=user_token, max_chars=max_chars)
                    st.subheader("Search Results:")
                    st.markdown(result)
                except Exception as e:
                    st.error(f"An error occurred during web search: {e}")
                    logger.error(f"Web search failed: {e}", exc_info=True)
        else:
            st.warning("Please enter a query to search.")

elif query_type == "Financial Data Fetcher":
    st.subheader("Fetch Specific Financial Data")
    
    data_type = st.selectbox(
        "Select Data Type:",
        ("stock_prices", "company_overview", "earnings_report", "economic_indicator")
    )
    
    symbol = None
    if data_type in ["stock_prices", "company_overview", "earnings_report"]:
        symbol = st.text_input("Enter Stock Symbol (e.g., AAPL, MSFT):", key="symbol_input").upper()
    
    start_date = None
    end_date = None
    if data_type == "stock_prices":
        st.info("Note: The `finance_data_fetcher` is currently a placeholder and provides mock data for stock prices. Actual date range selection will be implemented with real API integration.")
        # start_date = st.date_input("Start Date:", value=pd.to_datetime("2023-01-01"), key="start_date_input")
        # end_date = st.date_input("End Date:", value=pd.to_datetime("2023-01-04"), key="end_date_input")
        # start_date = start_date.strftime("%Y-%m-%d") if start_date else None
        # end_date = end_date.strftime("%Y-%m-%d") if end_date else None

    limit = st.number_input("Limit results (e.g., number of data points):", min_value=1, value=5, step=1)

    if st.button("Fetch Data"):
        if (data_type in ["stock_prices", "company_overview", "earnings_report"] and not symbol) and data_type not in ["economic_indicator"]:
            st.warning("Please enter a stock symbol for the selected data type.")
        else:
            with st.spinner(f"Fetching {data_type} data..."):
                try:
                    # Call the finance_data_fetcher tool
                    result_json_str = finance_data_fetcher(
                        data_type=data_type, 
                        symbol=symbol, 
                        start_date=start_date, 
                        end_date=end_date, 
                        limit=limit
                    )
                    
                    st.subheader("Fetched Data:")
                    try:
                        # Attempt to parse as JSON and display nicely
                        parsed_data = json.loads(result_json_str)
                        st.json(parsed_data)
                        
                        # If it's stock prices, try to display as a DataFrame
                        if data_type == "stock_prices" and isinstance(parsed_data, list):
                            st.subheader("Data as DataFrame:")
                            df = pd.DataFrame(parsed_data)
                            st.dataframe(df)

                    except json.JSONDecodeError:
                        st.write(result_json_str) # If not JSON, display as plain text
                    
                except Exception as e:
                    st.error(f"An error occurred during data fetching: {e}")
                    logger.error(f"Financial data fetcher failed: {e}", exc_info=True)

st.markdown("---")
st.caption(f"Current User Token: `{get_user_token()}` (for demo purposes)")
st.caption("This app uses web scraping and a placeholder financial data fetcher tool.")
