# legal_query_app.py

import streamlit as st
import logging
import json
import pandas as pd # Potentially useful for displaying structured data

# Assume config_manager and get_user_token exist
from config.config_manager import config_manager
from utils.user_manager import get_user_token

from legal_tools.legal_tool import (
    legal_search_web, 
    legal_data_fetcher,
    legal_term_explainer,
    contract_analyzer
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
                self.legal_api_key = "YOUR_LEGAL_API_KEY_HERE"
                self.govlaw_api_key = "YOUR_GOVLAW_API_KEY_HERE"
                self.intllaw_api_key = "YOUR_INTLLAW_API_KEY_HERE"
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
st.set_page_config(page_title="Legal Query Tools", page_icon="⚖️", layout="centered")
st.title("Legal Query Tools ⚖️")

st.markdown("Access various legal and law-related tools directly.")
st.warning("**Disclaimer:** This tool provides general information and is NOT a substitute for professional legal advice. Always consult a qualified legal professional for specific legal concerns.")

user_token = get_user_token() # Get user token for personalization

tool_selection = st.selectbox(
    "Select a Legal Tool:",
    (
        "Web Search (General Legal Info)",
        "Legal Term Explainer",
        "Contract Analyzer",
        "Legal Data Fetcher (Advanced)"
    )
)

# --- Web Search ---
if tool_selection == "Web Search (General Legal Info)":
    st.subheader("General Legal Web Search")
    query = st.text_input("Enter your legal web query:", placeholder="e.g., 'recent court decisions on AI', 'intellectual property rights in Europe'")
    max_chars = st.slider("Maximum characters in result snippet:", min_value=100, max_value=5000, value=1500, step=100)

    if st.button("Search Web"):
        if query:
            with st.spinner("Searching the web..."):
                try:
                    result = legal_search_web(query=query, user_token=user_token, max_chars=max_chars)
                    st.subheader("Search Results:")
                    st.markdown(result)
                except Exception as e:
                    st.error(f"An error occurred during web search: {e}")
                    logger.error(f"Web search failed: {e}", exc_info=True)
        else:
            st.warning("Please enter a query to search.")

# --- Legal Term Explainer ---
elif tool_selection == "Legal Term Explainer":
    st.subheader("Legal Term Explainer")
    term_input = st.text_input("Enter a legal term to explain (e.g., 'habeas corpus', 'res judicata', 'due process'):", placeholder="stare decisis")
    
    if st.button("Explain Term"):
        if term_input:
            with st.spinner("Explaining legal term..."):
                try:
                    result = legal_term_explainer(term=term_input)
                    st.subheader(f"Explanation of '{term_input}':")
                    st.markdown(result)
                except Exception as e:
                    st.error(f"An error occurred while explaining the term: {e}")
                    logger.error(f"Legal term explainer failed: {e}", exc_info=True)
        else:
            st.warning("Please enter a legal term.")

# --- Contract Analyzer ---
elif tool_selection == "Contract Analyzer":
    st.subheader("Contract Analyzer")
    st.warning("**Disclaimer:** This tool provides preliminary information and is NOT a substitute for professional legal advice. Always consult a qualified legal professional for contract review.")
    
    contract_file = st.file_uploader(
        "Upload a contract document (e.g., PDF, DOCX, TXT, MD):",
        type=["pdf", "docx", "txt", "md"],
        key="contract_file_uploader"
    )
    
    analysis_type = st.selectbox(
        "Select analysis type:",
        ("summary", "parties", "obligations", "termination_clauses"),
        key="contract_analysis_type"
    )

    if st.button("Analyze Contract"):
        if contract_file is not None:
            # Save the uploaded file temporarily to pass its path to the tool
            temp_upload_dir = Path("temp_uploads") / user_token / "legal"
            temp_upload_dir.mkdir(parents=True, exist_ok=True)
            temp_file_path = temp_upload_dir / contract_file.name
            
            with open(temp_file_path, "wb") as f:
                f.write(contract_file.getvalue())
            
            with st.spinner(f"Analyzing contract for {analysis_type}..."):
                try:
                    result = contract_analyzer(file_path_str=str(temp_file_path), analysis_type=analysis_type)
                    st.subheader(f"Contract Analysis ({analysis_type}):")
                    st.markdown(result)
                except Exception as e:
                    st.error(f"An error occurred during contract analysis: {e}")
                    logger.error(f"Contract analyzer failed: {e}", exc_info=True)
                finally:
                    # Clean up the temporary file
                    if temp_file_path.exists():
                        temp_file_path.unlink()
                    if not any(temp_upload_dir.iterdir()): # Remove empty dir
                        temp_upload_dir.rmdir()
        else:
            st.warning("Please upload a contract document.")

# --- Legal Data Fetcher (Advanced) ---
elif tool_selection == "Legal Data Fetcher (Advanced)":
    st.subheader("Advanced Legal Data Fetcher")
    st.info("This tool directly interacts with configured legal APIs. Note that many real legal APIs require specific access and may have usage limits.")

    api_name = st.selectbox(
        "Select API to use:",
        ("LegalDB", "GovLawAPI", "IntlLawAPI"),
        help="Choose the API best suited for your data type. (Note: These are placeholders in legal_tool.py)"
    )

    data_type_options = []
    if api_name == "LegalDB":
        data_type_options = ["case_law_search", "statute_lookup", "constitutional_law", "international_law"]
    elif api_name == "GovLawAPI":
        data_type_options = ["regulation_search", "legal_news"]
    elif api_name == "IntlLawAPI":
        data_type_options = ["international_law"]

    data_type = st.selectbox(
        "Select Data Type:",
        data_type_options,
        key="legal_data_type_select"
    )

    query_input = st.text_input("Enter Query (e.g., case name, statute title, keyword):", key="query_input_fetcher")
    jurisdiction_input = st.text_input("Enter Jurisdiction (e.g., US Federal, California, UK, EU, International):", key="jurisdiction_input_fetcher")
    year_input = st.number_input("Year (optional):", min_value=0, value=0, step=1, key="year_input_fetcher")
    limit_input = st.number_input("Limit results (optional):", min_value=1, value=5, step=1, key="limit_input_fetcher")

    if st.button("Fetch Legal Data"):
        if not query_input and data_type not in ["constitutional_law", "international_law"] : # Some data types might not strictly need a query if jurisdiction is specified
            st.warning("Please enter a query.")
        else:
            with st.spinner(f"Fetching {data_type} data from {api_name}..."):
                try:
                    result_json_str = legal_data_fetcher(
                        api_name=api_name,
                        data_type=data_type,
                        query=query_input if query_input else None,
                        jurisdiction=jurisdiction_input if jurisdiction_input else None,
                        year=year_input if year_input > 0 else None,
                        limit=limit_input if limit_input > 0 else None
                    )
                    
                    st.subheader("Fetched Data:")
                    try:
                        parsed_data = json.loads(result_json_str)
                        st.json(parsed_data)
                        
                        # Attempt to display as DataFrame if suitable
                        if isinstance(parsed_data, list) and parsed_data:
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
                    logger.error(f"Legal data fetcher failed: {e}", exc_info=True)


st.markdown("---")
st.caption(f"Current User Token: `{get_user_token()}` (for demo purposes)")
st.caption("This app provides direct access to various legal tools. Remember to always consult a legal professional for legal advice.")
