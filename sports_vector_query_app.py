# sports_vector_query_app.py

import streamlit as st
import logging

# Assume config_manager and get_user_token exist
from config.config_manager import config_manager
from utils.user_manager import get_user_token

from sports_tools.sports_tool import sports_query_uploaded_docs, SPORTS_SECTION
from shared_tools.vector_utils import BASE_VECTOR_DIR # For checking if vector store exists

logging.basicConfig(level=logging.INFO)

# --- Configuration ---
def initialize_config():
    """Initializes the config_manager and st.secrets."""
    if not hasattr(st, 'secrets'):
        class MockSecrets:
            def __init__(self):
                self.openai = {"api_key": "sk-your-openai-key-here"} # Required for embeddings
        st.secrets = MockSecrets()
        logging.info("Mocked st.secrets for standalone testing.")
    
    if not hasattr(config_manager, '_instance') or config_manager._instance is None:
        try:
            # You might need to create a dummy config.yml in the 'data' directory for initialization
            logging.info("ConfigManager assumed to be initialized by importing. Ensure data/config.yml exists.")
        except Exception as e:
            st.error(f"Failed to initialize configuration: {e}. Please ensure data/config.yml and .streamlit/secrets.toml are set up correctly.")
            st.stop()

initialize_config()


# --- Streamlit UI ---
st.set_page_config(page_title="Query Uploaded Sports Docs", page_icon="📚")
st.title("Query Uploaded Sports Documents 📚")

st.write("Search through documents you've previously uploaded to the Sports AI Assistant's memory.")

user_token = get_user_token() # Get user token for personalization
vector_store_path = BASE_VECTOR_DIR / user_token / SPORTS_SECTION

if not vector_store_path.exists():
    st.info(f"No sports documents have been indexed yet for your user. Please go to the 'Upload Sports Docs' page to add documents.")
else:
    query = st.text_input("Enter your query for uploaded sports documents:")
    k_results = st.slider("Number of top results to retrieve (k):", min_value=1, max_value=10, value=3)
    export_results = st.checkbox("Export results to file?", value=False)

    if st.button("Search Uploaded Documents"):
        if query:
            with st.spinner("Searching indexed documents..."):
                try:
                    result = sports_query_uploaded_docs(query=query, user_token=user_token, export=export_results, k=k_results)
                    st.subheader("Matching Document Chunks:")
                    st.markdown(result)
                except Exception as e:
                    st.error(f"An error occurred during document search: {e}")
                    logging.error(f"Vector query failed: {e}", exc_info=True)
        else:
            st.warning("Please enter a query to search your documents.")
