# ui/finance_query_app.py

import streamlit as st
import logging
import json
import pandas as pd
from datetime import datetime, timedelta # For date inputs

# Assume config_manager and get_user_token exist
from config.config_manager import config_manager
from utils.user_manager import get_current_user, get_user_tier_capability # Import get_current_user and get_user_tier_capability

from finance_tools.finance_tool import (
    finance_search_web, 
    finance_data_fetcher,
    stock_price_checker,
    crypto_price_checker,
    economic_indicator_checker
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
                self.alpha_vantage = {"api_key": "YOUR_ALPHA_VANTAGE_API_KEY_HERE"}
                self.coinmarketcap = {"api_key": "YOUR_COINMARKETCAP_API_KEY_HERE"}
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

# Define the required tier for this specific page (Finance Query Tools)
# This should match the 'tier_access' defined in main_app.py for this page.
REQUIRED_TIER_FOR_THIS_PAGE = "basic" 

# Check if user is logged in and has the required tier or admin role
if not current_user:
    st.warning("⚠️ You must be logged in to access this page.")
    st.stop() # Halts execution
elif not (user_tier and user_roles and (user_tier == REQUIRED_TIER_FOR_THIS_PAGE or user_tier in ["pro", "elite", "premium"] or "admin" in user_roles)):
    # This check is simplified. A more robust check would use the user_can_access_page function from main_app.
    # For now, we'll check if the user's tier is at or above the required tier, or if they are an admin.
    st.error(f"🚫 Access Denied: Your current tier ({user_tier.capitalize()}) does not have access to the Finance Query Tools. Please upgrade your plan to {REQUIRED_TIER_FOR_THIS_PAGE.capitalize()} or higher.")
    st.stop() # Halts execution
# --- End RBAC Access Check ---


# --- Streamlit UI ---
st.set_page_config(page_title="Finance Query Tools", page_icon="📈", layout="centered")
st.title("Finance Query Tools 📈")

st.markdown("Access various financial and economic tools directly.")

user_token = current_user.get('user_id', 'default') # Get user token for personalization

tool_selection = st.selectbox(
    "Select a Financial Tool:",
    (
        "Web Search (General Financial Info)",
        "Stock Price Checker",
        "Crypto Price Checker",
        "Economic Indicator Checker",
        "Financial Data Fetcher (Advanced)"
    )
)

# --- Web Search ---
if tool_selection == "Web Search (General Financial Info)":
    st.subheader("General Financial Web Search")
    query = st.text_input("Enter your financial web query:", placeholder="e.g., 'impact of inflation on tech stocks', 'latest central bank policies'")
    
    # RBAC for max_chars in web search
    allowed_max_chars = get_user_tier_capability(user_token, 'web_search_limit_chars', 2000)
    max_chars = st.slider(f"Maximum characters in result snippet (Max for your tier: {allowed_max_chars}):", min_value=100, max_value=allowed_max_chars, value=min(1500, allowed_max_chars), step=100)

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

# --- Stock Price Checker ---
elif tool_selection == "Stock Price Checker":
    st.subheader("Stock Price Checker")
    symbol = st.text_input("Enter stock symbol (e.g., AAPL, GOOGL):", placeholder="AAPL")
    
    if st.button("Get Stock Price"):
        if symbol:
            with st.spinner(f"Fetching price for {symbol}..."):
                try:
                    result = stock_price_checker(symbol=symbol)
                    st.subheader(f"Current Price for {symbol.upper()}:")
                    st.markdown(result)
                except Exception as e:
                    st.error(f"An error occurred: {e}")
                    logger.error(f"Stock price check failed: {e}", exc_info=True)
        else:
            st.warning("Please enter a stock symbol.")

# --- Crypto Price Checker ---
elif tool_selection == "Crypto Price Checker":
    st.subheader("Crypto Price Checker")
    symbol = st.text_input("Enter cryptocurrency symbol (e.g., BTC, ETH):", placeholder="BTC")
    
    if st.button("Get Crypto Price"):
        if symbol:
            with st.spinner(f"Fetching price for {symbol}..."):
                try:
                    result = crypto_price_checker(symbol=symbol)
                    st.subheader(f"Current Price for {symbol.upper()}:")
                    st.markdown(result)
                except Exception as e:
                    st.error(f"An error occurred: {e}")
                    logger.error(f"Crypto price check failed: {e}", exc_info=True)
        else:
            st.warning("Please enter a crypto symbol.")

# --- Economic Indicator Checker ---
elif tool_selection == "Economic Indicator Checker":
    st.subheader("Economic Indicator Checker")
    indicator_type = st.selectbox(
        "Select Indicator Type:",
        ("CPI", "GDP", "UnemploymentRate", "InterestRates"),
        key="indicator_type_select"
    )
    
    if st.button("Get Indicator Value"):
        if indicator_type:
            with st.spinner(f"Fetching {indicator_type} value..."):
                try:
                    result = economic_indicator_checker(indicator_type=indicator_type)
                    st.subheader(f"Latest {indicator_type} Value:")
                    st.markdown(result)
                except Exception as e:
                    st.error(f"An error occurred: {e}")
                    logger.error(f"Economic indicator check failed: {e}", exc_info=True)
        else:
            st.warning("Please select an indicator type.")

# --- Financial Data Fetcher (Advanced) ---
elif tool_selection == "Financial Data Fetcher (Advanced)":
    st.subheader("Advanced Financial Data Fetcher")
    st.info("This tool directly interacts with configured financial APIs. Note that many real financial APIs require specific access and may have usage limits.")

    api_name = st.selectbox(
        "Select API to use:",
        ("AlphaVantage", "FinancialModelingPrep", "CoinMarketCap", "CoinGecko"),
        key="advanced_api_select"
    )

    data_type_options = []
    if api_name in ["AlphaVantage", "FinancialModelingPrep"]:
        data_type_options = ["stock_data", "economic_indicator"]
    elif api_name in ["CoinMarketCap", "CoinGecko"]:
        data_type_options = ["crypto_data"]

    data_type = st.selectbox(
        "Select Data Type:",
        data_type_options,
        key="advanced_data_type_select"
    )

    symbol_input = st.text_input("Symbol (e.g., AAPL, BTC):", key="symbol_input_fetcher")
    interval_input = st.text_input("Interval (for historical stock data, e.g., 1min, 5min, daily, weekly, monthly):", key="interval_input_fetcher")
    indicator_type_input = st.text_input("Indicator Type (for economic indicator, e.g., CPI, GDP):", key="indicator_type_input_fetcher")
    start_date_input = st.date_input("Start Date (optional, YYYY-MM-DD):", datetime.today() - timedelta(days=30), key="start_date_input_fetcher")
    end_date_input = st.date_input("End Date (optional, YYYY-MM-DD):", datetime.today(), key="end_date_input_fetcher")
    limit_input = st.number_input("Limit results (optional):", min_value=1, value=5, step=1, key="limit_input_fetcher")

    if st.button("Fetch Advanced Financial Data"):
        if not symbol_input and not indicator_type_input:
            st.warning("Please enter a symbol or an indicator type.")
        else:
            with st.spinner(f"Fetching {data_type} data from {api_name}..."):
                try:
                    result_json_str = finance_data_fetcher(
                        api_name=api_name,
                        data_type=data_type,
                        symbol=symbol_input if symbol_input else None,
                        interval=interval_input if interval_input else None,
                        indicator_type=indicator_type_input if indicator_type_input else None,
                        start_date=str(start_date_input) if start_date_input else None,
                        end_date=str(end_date_input) if end_date_input else None,
                        limit=limit_input if limit_input > 0 else None
                    )
                    
                    st.subheader("Fetched Data:")
                    try:
                        parsed_data = json.loads(result_json_str)
                        st.json(parsed_data)
                        
                        # Attempt to display as DataFrame if suitable
                        if isinstance(parsed_data, dict) and (parsed_data.get('Time Series (Daily)') or parsed_data.get('Time Series (Weekly)') or parsed_data.get('Time Series (Monthly)')):
                            # Alpha Vantage time series
                            time_series_key = next((k for k in parsed_data if 'Time Series' in k), None)
                            if time_series_key:
                                df = pd.DataFrame.from_dict(parsed_data[time_series_key], orient='index')
                                df.index.name = 'Date'
                                st.subheader("Data as DataFrame:")
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
                    logger.error(f"Financial data fetcher failed: {e}", exc_info=True)


st.markdown("---")
st.caption(f"Current User Token: `{current_user.get('user_id', 'N/A')}` (for demo purposes)")
st.caption("This app provides direct access to various financial tools.")
