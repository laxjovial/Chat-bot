# sports_vector_app.py

import streamlit as st
import logging
from pathlib import Path

# Assume config_manager and get_user_token exist
from config.config_manager import config_manager
from utils.user_manager import get_user_token

from shared_tools.import_utils import process_upload, clear_indexed_data, SUPPORTED_DOC_EXTS, BASE_UPLOAD_DIR, BASE_VECTOR_DIR
from shared_tools.doc_summarizer import summarize_document # For summarization on upload
from sports_tools.sports_tool import SPORTS_SECTION

logging.basicConfig(level=logging.INFO)

# --- Configuration ---
def initialize_config():
    """Initializes the config_manager and st.secrets."""
    if not hasattr(st, 'secrets'):
        class MockSecrets:
            def __init__(self):
                self.openai = {"api_key": "sk-your-openai-key-here"} # Required for embeddings and LLM
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
st.set_page_config(page_title="Upload Sports Docs", page_icon="⬆️")
st.title("Upload & Manage Sports Documents ⬆️")

st.write("Upload documents related to sports to enhance the AI Assistant's knowledge base. These documents will be indexed and made searchable.")

user_token = get_user_token() # Get user token for personalization

uploaded_file = st.file_uploader(
    f"Choose a document file (Supported: {', '.join(SUPPORTED_DOC_EXTS)})",
    type=[ext.strip('.') for ext in SUPPORTED_DOC_EXTS]
)

if uploaded_file is not None:
    st.write(f"File selected: {uploaded_file.name}")
    process_and_summarize = st.checkbox("Summarize document after upload?", value=False)
    
    if st.button("Process Document"):
        with st.spinner("Processing and indexing document..."):
            try:
                # Call the generic process_upload with the specific sports section
                message = process_upload(uploaded_file, user_token, SPORTS_SECTION)
                st.success(message)

                if process_and_summarize:
                    st.write("Attempting to summarize the uploaded document...")
                    # To summarize, we need the path where the file was saved.
                    # process_upload saves it, but doesn't return the path directly.
                    # We'll need to reconstruct the path for summarization.
                    # This is a bit of a hack; better design would have process_upload return the saved_path.
                    # For now, let's assume a common naming convention or try to locate it.
                    # A more robust way: modify process_upload to return the saved_path.
                    
                    # For demonstration, let's assume process_upload saved it and we can find it.
                    # In a real app, you'd save the specific file name/ID or have process_upload return it.
                    
                    # This is an imperfect way to get the path; consider revising process_upload
                    # to return the saved file path if summarization is a common follow-up.
                    # The uuid in filename makes it hard to guess.
                    # Let's simplify for this example, assuming the file is available in the upload directory
                    # This needs a better approach if the filename isn't preserved.
                    
                    # A better way would be to pass the saved_path from process_upload.
                    # For now, let's use the temporary file upload for summarization if not saved permanently yet.
                    
                    # If process_upload saved it, you need to know its UUID.
                    # As process_upload doesn't return the exact path, we can't directly summarize the *saved* file.
                    # For demonstration, let's assume we summarize the content directly if we want to.
                    # Or, for simplicity in this Streamlit app context, just summarize the uploaded file's content
                    # *before* it's permanently stored (if temp file is accessible).
                    
                    # For now, let's just make a dummy Path for summarization.
                    # THIS IS A PLACEHOLDER - FOR REAL USE, YOU NEED THE ACTUAL SAVED PATH.
                    # A more robust solution would be to modify process_upload to return the saved_path.
                    
                    # Let's mock a file path to simulate summarization.
                    # In a real scenario, you'd get the actual saved file path from `process_upload`.
                    
                    try:
                        # Create a temporary file to read for summarization if direct path isn't easy
                        temp_summarize_path = Path(f"temp_summary_{uploaded_file.name}")
                        with open(temp_summarize_path, "wb") as f:
                            f.write(uploaded_file.getvalue()) # Read content from uploaded file object
                        
                        st.info(f"Summarizing '{uploaded_file.name}' (this might take a moment)...")
                        summary = summarize_document(temp_summarize_path)
                        st.subheader("Document Summary:")
                        st.write(summary)
                        temp_summarize_path.unlink(missing_ok=True) # Clean up temp file
                    except Exception as sum_e:
                        st.warning(f"Could not summarize document: {sum_e}. Ensure your LLM configuration is correct.")
                        logging.error(f"Summarization failed: {sum_e}", exc_info=True)


            except ValueError as e:
                st.error(f"Upload failed: {e}")
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")
                logging.error(f"File upload/indexing failed: {e}", exc_info=True)

st.markdown("---")
st.header("Clear All Indexed Sports Data")
st.write("This will remove all uploaded files and indexed data for the sports section for your user.")

if st.button("Clear All Sports Data", help="This action cannot be undone."):
    with st.spinner("Clearing data..."):
        try:
            # Call the generic clear_indexed_data with the specific sports section
            message = clear_indexed_data(user_token, SPORTS_SECTION)
            st.success(message)
        except Exception as e:
            st.error(f"An error occurred while clearing data: {e}")
            logging.error(f"Data clear failed: {e}", exc_info=True)

# Display current status
st.markdown("---")
upload_path_status = BASE_UPLOAD_DIR / user_token / SPORTS_SECTION
vector_path_status = BASE_VECTOR_DIR / user_token / SPORTS_SECTION

st.subheader("Current Sports Data Status:")
if upload_path_status.exists() and any(upload_path_status.iterdir()):
    st.info(f"📁 Uploaded files exist for sports in: `{upload_path_status}`")
else:
    st.info(f"No uploaded files found for sports.")

if vector_path_status.exists() and any(vector_path_status.iterdir()):
    st.info(f"🧠 Indexed data exists for sports in: `{vector_path_status}`")
else:
    st.info(f"No indexed data found for sports.")
