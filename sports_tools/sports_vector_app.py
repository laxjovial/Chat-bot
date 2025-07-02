# ui/sports_vector_app.py

import streamlit as st
import logging
from pathlib import Path
import os
import shutil

# Assume config_manager and get_user_token exist
from config.config_manager import config_manager
from utils.user_manager import get_current_user, get_user_tier_capability # Import for RBAC

from shared_tools.import_utils import process_upload, clear_indexed_data, SUPPORTED_DOC_EXTS, BASE_UPLOAD_DIR, BASE_VECTOR_DIR
from shared_tools.doc_summarizer import summarize_document # For summarization on upload
from sports_tools.sports_tool import SPORTS_SECTION

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
                self.openai = {"api_key": "sk-your-openai-key-here"} # Required for embeddings and LLM
                self.google = {"api_key": "AIzaSy_YOUR_GOOGLE_API_KEY_HERE"} # Required for Google LLM if used
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

# Define the required tier for this specific page (Upload Sports Docs)
# This should match the 'tier_access' defined in main_app.py for this page.
REQUIRED_TIER_FOR_THIS_PAGE = "basic" 

# Check if user is logged in and has the required tier or admin role
if not current_user:
    st.warning("⚠️ You must be logged in to access this page.")
    st.stop() # Halts execution
else:
    # Import TIER_HIERARCHY from main_app for comparison
    try:
        from main_app import TIER_HIERARCHY
    except ImportError:
        st.error("Error: Could not load tier hierarchy for access control. Please ensure main_app.py is accessible.")
        st.stop()

    if not (user_tier and user_roles and (TIER_HIERARCHY.get(user_tier, -1) >= TIER_HIERARCHY.get(REQUIRED_TIER_FOR_THIS_PAGE, -1) or "admin" in user_roles)):
        st.error(f"🚫 Access Denied: Your current tier ({user_tier.capitalize()}) does not have access to upload Sports Documents. Please upgrade your plan to {REQUIRED_TIER_FOR_THIS_PAGE.capitalize()} or higher.")
        st.stop() # Halts execution
# --- End RBAC Access Check ---


# --- Streamlit UI ---
st.set_page_config(page_title="Upload Sports Docs", page_icon="⬆️", layout="centered")
st.title("Upload & Manage Sports Documents ⬆️")

st.markdown("Upload documents related to sports to enhance the AI Assistant's knowledge base. These documents will be indexed and made searchable via the 'Query Uploaded Sports Docs' app.")

user_token = current_user.get('user_id', 'default') # Get user token for personalization

uploaded_file = st.file_uploader(
    f"Choose a document file (Supported: {', '.join(SUPPORTED_DOC_EXTS)})",
    type=[ext.strip('.') for ext in SUPPORTED_DOC_EXTS]
)

if uploaded_file is not None:
    st.write(f"File selected: {uploaded_file.name}")
    process_and_summarize = st.checkbox("Summarize document after upload?", value=False,
                                        help="If checked, the document will be summarized using the configured LLM after indexing.")
    
    if st.button("Process Document"):
        with st.spinner("Processing and indexing document..."):
            try:
                # Call the generic process_upload with the specific sports section
                message = process_upload(uploaded_file, user_token, SPORTS_SECTION)
                st.success(message)

                if process_and_summarize:
                    st.write("Attempting to summarize the uploaded document...")
                    
                    # To summarize the *uploaded* file, we need its content.
                    # The `uploaded_file` object in Streamlit allows reading its content directly.
                    # Create a temporary file to pass to summarize_document.
                    temp_summarize_path = Path(f"temp_summary_{uploaded_file.name}")
                    try:
                        with open(temp_summarize_path, "wb") as f:
                            f.write(uploaded_file.getvalue()) # Read content from uploaded file object
                        
                        st.info(f"Summarizing '{uploaded_file.name}' (this might take a moment)...")
                        summary = summarize_document(temp_summarize_path)
                        st.subheader("Document Summary:")
                        st.write(summary)
                    except Exception as sum_e:
                        st.warning(f"Could not summarize document: {sum_e}. Ensure your LLM configuration is correct and API keys are valid.")
                        logger.error(f"Summarization failed for {uploaded_file.name}: {sum_e}", exc_info=True)
                    finally:
                        if temp_summarize_path.exists():
                            temp_summarize_path.unlink() # Clean up temp file
            except ValueError as e:
                st.error(f"Upload failed: {e}")
                logger.error(f"File upload failed due to ValueError: {e}", exc_info=True)
            except Exception as e:
                st.error(f"An unexpected error occurred during processing: {e}")
                logger.error(f"File upload/indexing failed: {e}", exc_info=True)

st.markdown("---")
st.header("Clear All Indexed Sports Data")
st.write("This will remove all uploaded files and indexed vector data for the sports section for your user. This action cannot be undone.")

if st.button("Clear All Sports Data", help="This action cannot be undone."):
    with st.spinner("Clearing data..."):
        try:
            # Call the generic clear_indexed_data with the specific sports section
            message = clear_indexed_data(user_token, SPORTS_SECTION)
            st.success(message)
        except Exception as e:
            st.error(f"An error occurred while clearing data: {e}")
            logger.error(f"Data clear failed: {e}", exc_info=True)

# Display current status
st.markdown("---")
st.subheader("Current Sports Data Status:")
upload_path_status = BASE_UPLOAD_DIR / user_token / SPORTS_SECTION
vector_path_status = BASE_VECTOR_DIR / user_token / SPORTS_SECTION

if upload_path_status.exists() and any(upload_path_status.iterdir()):
    st.info(f"📁 **Uploaded files exist** for sports in: `{upload_path_status}`")
else:
    st.info(f"No uploaded files found for sports.")

if vector_path_status.exists() and any(vector_path_status.iterdir()):
    st.info(f"🧠 **Indexed data exists** for sports in: `{vector_path_status}`")
else:
    st.info(f"No indexed data found for sports.")

st.markdown("---")
st.caption(f"Current User Token: `{current_user.get('user_id', 'N/A')}` (for demo purposes)")
st.caption("This app manages the documents that the 'Query Uploaded Sports Docs' app and the 'Sports AI Assistant' use.")
