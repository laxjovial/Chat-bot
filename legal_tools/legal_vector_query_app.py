# ui/legal_vector_query_app.py

import streamlit as st
import os
import logging
from utils.vector_db_manager import VectorDBManager
from utils.llm_manager import LLMManager
from utils.user_manager import get_current_user
from config.config_manager import config_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration Initialization ---
# This ensures config_manager is ready and secrets are accessible
def initialize_app_config():
    if not hasattr(st, 'secrets'):
        # This block is mainly for local testing outside of Streamlit's native 'secrets.toml'
        class MockSecrets:
            def __init__(self):
                self.openai = {"api_key": "sk-your-openai-key-here"} # Required for embeddings and LLM
                self.google = {"api_key": "AIzaSy_YOUR_GOOGLE_API_KEY_HERE"} # Required for Google LLM if used
                self.serpapi = {"api_key": "YOUR_SERPAPI_KEY_HERE"}
                self.google_custom_search = {"api_key": "YOUR_GOOGLE_CUSTOM_SEARCH_API_KEY_HERE"}
                self.legal_api_key = "YOUR_LEGAL_API_KEY_HERE"
                self.govlaw_api_key = "YOUR_GOVLAW_API_KEY_HERE"
                self.intllaw_api_key = "YOUR_INTLLAW_API_KEY_HERE"
                self.news_api_key = "YOUR_NEWS_API_KEY_HERE"
                self.sports_api_key = "YOUR_SPORTS_API_KEY_HERE"
                self.weather_api_key = "YOUR_WEATHER_API_KEY_HERE"
                self.email_smtp_user = os.getenv("SMTP_USER", "your_email@example.com")
                self.email_smtp_password = os.getenv("SMTP_PASSWORD", "your_email_password")
        st.secrets = MockSecrets()
        logger.info("Mocked st.secrets for standalone testing.")

    if not config_manager._is_loaded:
        try:
            logger.info("ConfigManager assumed to be initialized by importing. Ensure data/config.yml and other config files exist.")
        except Exception as e:
            st.error(f"Failed to initialize configuration: {e}. Please ensure data/config.yml and .streamlit/secrets.toml are set up correctly.")
            st.stop()

initialize_app_config()


# --- Page Configuration ---
st.set_page_config(page_title="🔎 Query Uploaded Legal Docs", layout="centered")
st.title("🔎 Query Your Uploaded Legal Documents")

# --- Session State Initialization ---
if "legal_vector_db_manager" not in st.session_state:
    st.session_state.legal_vector_db_manager = None
if "legal_llm_manager" not in st.session_state:
    st.session_state.legal_llm_manager = None
if "legal_chat_history" not in st.session_state:
    st.session_state.legal_chat_history = []

# --- User Authentication Check ---
current_user = get_current_user()
if not current_user:
    st.warning("⚠️ You must be logged in to query legal documents.")
    st.stop()

user_id = current_user.get("id")
if not user_id:
    st.error("❌ User ID not found. Please log in again.")
    st.stop()

# --- Initialize Managers (once per session per user) ---
if st.session_state.legal_vector_db_manager is None or st.session_state.legal_vector_db_manager.user_id != user_id:
    try:
        st.session_state.legal_vector_db_manager = VectorDBManager(
            collection_name_prefix="legal_docs",
            user_id=user_id,
            api_key=config_manager.get_secret("openai_api_key"),
            embedding_model_name=config_manager.get("vector_db.embedding_model", "text-embedding-ada-002")
        )
        logger.info(f"Initialized Legal VectorDBManager for user {user_id}")
    except Exception as e:
        st.error(f"Failed to initialize Legal Document Database: {e}")
        st.stop()

if st.session_state.legal_llm_manager is None:
    try:
        st.session_state.legal_llm_manager = LLMManager(
            api_key=config_manager.get_secret("openai_api_key"),
            model_name=config_manager.get("llm.model_name", "gpt-3.5-turbo")
        )
        logger.info("Initialized Legal LLMManager")
    except Exception as e:
        st.error(f"Failed to initialize Legal AI Assistant: {e}")
        st.stop()

vector_db_manager = st.session_state.legal_vector_db_manager
llm_manager = st.session_state.legal_llm_manager

# --- Display Chat History ---
st.markdown("---")
st.subheader("Conversation History")

for message in st.session_state.legal_chat_history:
    if message["role"] == "user":
        st.chat_message("user").write(message["content"])
    else:
        st.chat_message("assistant").write(message["content"])

# --- User Input and Query Processing ---
st.markdown("---")
query = st.chat_input("Ask a question about your legal documents...")

if query:
    st.session_state.legal_chat_history.append({"role": "user", "content": query})
    st.chat_message("user").write(query)

    with st.spinner("Searching and generating response..."):
        try:
            # 1. Retrieve relevant documents from the vector database
            # The number of documents to retrieve can be configured
            num_docs = config_manager.get("vector_db.retrieval_limit", 5)
            retrieved_docs = vector_db_manager.query_documents(query, top_k=num_docs)
            
            if not retrieved_docs:
                response = "I couldn't find any relevant information in your uploaded legal documents. Please try a different query or upload more documents."
            else:
                # 2. Prepare context for the LLM
                context_texts = [doc.page_content for doc in retrieved_docs]
                context_str = "\n\n".join(context_texts)
                
                # Add source information
                sources = "\n\n**Sources:**\n"
                for i, doc in enumerate(retrieved_docs):
                    sources += f"- Document {i+1}: {doc.metadata.get('filename', 'Unknown File')}, Page: {doc.metadata.get('page_number', 'N/A')}\n"

                # 3. Formulate the prompt for the LLM
                system_prompt = (
                    "You are a helpful AI assistant specialized in legal documents. "
                    "Answer the user's question based ONLY on the provided context. "
                    "If the answer cannot be found in the context, state that you don't have enough information. "
                    "Do not make up answers. Provide precise and concise answers.\n\n"
                    "**Context from uploaded legal documents:**\n"
                    f"{context_str}"
                )
                
                # Use a conversational approach with the LLM
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ]
                
                llm_response_content = llm_manager.chat_completion(messages)
                response = f"{llm_response_content}\n{sources}"

            st.session_state.legal_chat_history.append({"role": "assistant", "content": response})
            st.chat_message("assistant").write(response)

        except Exception as e:
            st.error(f"An error occurred while processing your query: {e}")
            logger.exception("Error during legal document query:")

st.markdown("---")
st.info("💡 Tip: Upload more legal documents via the 'Upload Legal Docs' page to enhance query results.")

# --- Clear Chat History Button ---
if st.button("🗑️ Clear Chat History", use_container_width=True):
    st.session_state.legal_chat_history = []
    st.rerun()
