# finance_query_app.py

import streamlit as st
import logging
import json
import pandas as pd # Potentially useful for displaying structured data

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
                self.alphavantage_api_key = "YOUR_ALPHAVANTAGE_API_KEY_HERE"
                self.coingecko_api_key = "YOUR_COINGECKO_API_KEY_HERE"
                self.exchangerate_api_key = "YOUR_EXCHANGERATE_API_KEY_HERE"
                self.financial_news_api_key = "YOUR_FINANCIAL_NEWS_API_KEY_HERE"
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

st.markdown("Query the web for general financial news or fetch specific financial data (e.g., stock prices, crypto, exchange rates).")

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
    
    api_name = st.selectbox(
        "Select API to use:",
        ("AlphaVantage", "CoinGecko", "ExchangeRate-API"),
        help="Choose the API best suited for your data type."
    )

    data_type_options = []
    if api_name == "AlphaVantage":
        data_type_options = ["stock_prices", "company_overview", "global_quote"]
    elif api_name == "CoinGecko":
        data_type_options = ["crypto_price", "crypto_list", "crypto_market_chart"]
    elif api_name == "ExchangeRate-API":
        data_type_options = ["exchange_rate_latest", "exchange_rate_convert"]

    data_type = st.selectbox(
        "Select Data Type:",
        data_type_options,
        key="data_type_select"
    )
    
    # Input fields based on selected API and data type
    symbol = None
    ids = None
    base_currency = None
    target_currency = None
    amount = None
    days = None

    if api_name == "AlphaVantage":
        symbol = st.text_input("Enter Stock Symbol (e.g., AAPL, MSFT):", key="symbol_input_av").upper()
        # start_date and end_date are not directly used by AlphaVantage's TIME_SERIES_DAILY compact
        # but could be passed if 'full' outputsize was parsed or for other functions.
        # For now, keeping it simple as the tool handles the AlphaVantage specifics.

    elif api_name == "CoinGecko":
        if data_type == "crypto_price":
            ids = st.text_input("Enter Crypto IDs (comma-separated, e.g., bitcoin,ethereum):", key="ids_input")
            vs_currencies = st.text_input("Enter Vs Currencies (comma-separated, e.g., usd,eur):", key="vs_currencies_input")
        elif data_type == "crypto_market_chart":
            ids = st.text_input("Enter Crypto ID (e.g., bitcoin):", key="id_input_chart")
            vs_currencies = st.text_input("Enter Vs Currency (e.g., usd):", key="vs_currency_input_chart")
            days = st.number_input("Days (1, 7, 14, 30, 90, 180, 365, max):", min_value=1, value=7, step=1, key="days_input")
        # crypto_list doesn't need additional params

    elif api_name == "ExchangeRate-API":
        if data_type == "exchange_rate_latest":
            base_currency = st.text_input("Enter Base Currency (e.g., USD, EUR):", key="base_currency_latest").upper()
        elif data_type == "exchange_rate_convert":
            base_currency = st.text_input("Enter Base Currency (e.g., USD):", key="base_currency_convert").upper()
            target_currency = st.text_input("Enter Target Currency (e.g., EUR):", key="target_currency_convert").upper()
            amount = st.number_input("Enter Amount to Convert:", min_value=0.01, value=100.0, step=0.01, key="amount_input")


    limit = st.number_input("Limit results (e.g., number of data points for lists/charts):", min_value=1, value=5, step=1)

    if st.button("Fetch Data"):
        # Basic validation for required fields
        validation_error = False
        if api_name == "AlphaVantage" and not symbol and data_type != "crypto_list": # crypto_list doesn't require symbol
            st.warning("Please enter a stock symbol for AlphaVantage queries.")
            validation_error = True
        elif api_name == "CoinGecko":
            if data_type == "crypto_price" and (not ids or not vs_currencies):
                st.warning("Please enter Crypto IDs and Vs Currencies for crypto price.")
                validation_error = True
            elif data_type == "crypto_market_chart" and (not ids or not vs_currencies or not days):
                st.warning("Please enter Crypto ID, Vs Currency, and Days for crypto market chart.")
                validation_error = True
        elif api_name == "ExchangeRate-API":
            if data_type == "exchange_rate_latest" and not base_currency:
                st.warning("Please enter a Base Currency for latest exchange rates.")
                validation_error = True
            elif data_type == "exchange_rate_convert" and (not base_currency or not target_currency or amount is None):
                st.warning("Please enter Base Currency, Target Currency, and Amount for conversion.")
                validation_error = True

        if not validation_error:
            with st.spinner(f"Fetching {data_type} data from {api_name}..."):
                try:
                    result_json_str = finance_data_fetcher(
                        api_name=api_name,
                        data_type=data_type, 
                        symbol=symbol, 
                        base_currency=base_currency,
                        target_currency=target_currency,
                        amount=amount,
                        ids=ids,
                        vs_currencies=vs_currencies,
                        days=days,
                        limit=limit
                    )
                    
                    st.subheader("Fetched Data:")
                    try:
                        parsed_data = json.loads(result_json_str)
                        st.json(parsed_data)
                        
                        # Attempt to display as DataFrame if suitable (e.g., list of results, or specific nested data)
                        if isinstance(parsed_data, list) and parsed_data:
                            try:
                                df = pd.DataFrame(parsed_data)
                                st.subheader("Data as DataFrame:")
                                st.dataframe(df)
                            except Exception as df_e:
                                logger.warning(f"Could not convert fetched list data to DataFrame: {df_e}")
                                st.write("Could not display as DataFrame.")
                        elif isinstance(parsed_data, dict):
                            # Special handling for AlphaVantage Time Series to flatten
                            if api_name == "AlphaVantage" and "Time Series (Daily)" in parsed_data:
                                st.subheader("Daily Time Series Data:")
                                # Flatten the nested dictionary
                                df_data = []
                                for date, values in parsed_data["Time Series (Daily)"].items():
                                    row = {"Date": date}
                                    for k, v in values.items():
                                        row[k.split(' ')[1]] = float(v) # e.g., '1. open' -> 'open'
                                    df_data.append(row)
                                df = pd.DataFrame(df_data)
                                df['Date'] = pd.to_datetime(df['Date'])
                                df.set_index('Date', inplace=True)
                                st.dataframe(df)
                            # Special handling for CoinGecko market chart
                            elif api_name == "CoinGecko" and "prices" in parsed_data:
                                st.subheader("Market Chart Data:")
                                df = pd.DataFrame(parsed_data["prices"], columns=['timestamp', 'price'])
                                df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
                                df.set_index('date', inplace=True)
                                st.dataframe(df[['price']])
                            elif api_name == "ExchangeRate-API" and data_type == "exchange_rate_latest" and "conversion_rates" in parsed_data:
                                st.subheader("Conversion Rates:")
                                rates_df = pd.DataFrame(list(parsed_data["conversion_rates"].items()), columns=['Currency', 'Rate'])
                                st.dataframe(rates_df)
                            elif api_name == "ExchangeRate-API" and data_type == "exchange_rate_convert" and "conversion_result" in parsed_data:
                                st.subheader("Conversion Result:")
                                st.write(f"{parsed_data.get('conversion_result')} {parsed_data.get('target_code')}")
                            else:
                                st.write("Data is a dictionary (single item or overview).")

                    except json.JSONDecodeError:
                        st.write(result_json_str) # If not JSON, display as plain text
                    
                except Exception as e:
                    st.error(f"An error occurred during data fetching: {e}")
                    logger.error(f"Financial data fetcher failed: {e}", exc_info=True)

st.markdown("---")
st.caption(f"Current User Token: `{get_user_token()}` (for demo purposes)")
st.caption("This app uses web scraping and dedicated financial data API tools.")
