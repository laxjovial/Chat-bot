# legal_vector_query_app.py

import streamlit as st
import logging
from pathlib import Path

# Assume config_manager and get_user_token exist
from config.config_manager import config_manager
from utils.user_manager import get_user_token

from legal_tools.legal_tool import legal_query_uploaded_docs, LEGAL_SECTION
from shared_tools.vector_utils import BASE_VECTOR_DIR # For checking if vector store exists

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration Initialization ---
def initialize_app_config():
    """
    Initializes the config_manager and ensures Streamlit secrets are accessible.
    This function is called once at the start of the app.
    """
    if not hasattr(st, 'secrets'):
        # This block is mainly for local testing outside of Streamlit's native 'secrets.toml'
        class MockSecrets:
            def __init__(self):
                self.openai = {"api_key": "sk-your-openai-key-here"} # Required for embeddings
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
st.set_page_config(page_title="Query Uploaded Legal Docs", page_icon="📚", layout="centered")
st.title("Query Uploaded Legal Documents 📚")

st.markdown("Search through legal documents (case law, statutes, contracts, etc.) you've previously uploaded to the Legal AI Assistant's memory for the 'legal' section.")
st.warning("**Disclaimer:** This tool provides general information and is NOT a substitute for professional legal advice. Always consult a qualified legal professional for specific legal concerns.")


user_token = get_user_token() # Get user token for personalization
vector_store_path = BASE_VECTOR_DIR / user_token / LEGAL_SECTION

# Check if the vector store for the current user and legal section exists
if not vector_store_path.exists() or not any(vector_store_path.iterdir()):
    st.info(f"No legal documents have been indexed yet for your user. Please go to the 'Upload Legal Docs' page to add documents.")
else:
    query = st.text_input("Enter your query for uploaded legal documents:", 
                           placeholder="e.g., 'What are the key terms in the employment contract I uploaded?', 'Summarize the court ruling on intellectual property.'")
    k_results = st.slider("Number of top results to retrieve (k):", min_value=1, max_value=10, value=3)
    export_results = st.checkbox("Export results to file?", value=False, 
                                 help="If checked, the search results will be saved to a markdown file in your exports directory.")

    if st.button("Search Uploaded Documents"):
        if query:
            with st.spinner("Searching indexed documents..."):
                try:
                    # Call the legal_query_uploaded_docs tool
                    result = legal_query_uploaded_docs(query=query, user_token=user_token, export=export_results, k=k_results)
                    st.subheader("Matching Document Chunks:")
                    st.markdown(result)
                except Exception as e:
                    st.error(f"An error occurred during document search: {e}")
                    logger.error(f"Vector query failed: {e}", exc_info=True)
        else:
            st.warning("Please enter a query to search your documents.")

st.markdown("---")
st.caption(f"Current User Token: `{get_user_token()}` (for demo purposes)")
st.caption("This app queries documents you've uploaded and indexed specifically for legal topics.")
