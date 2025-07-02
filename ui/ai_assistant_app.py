# ui/ai_assistant_app.py

import streamlit as st
import logging
from utils.llm_manager import LLMManager
from utils.user_manager import get_current_user, get_user_tier_capability
from config.config_manager import config_manager
from shared_tools.python_interpreter_tool import python_interpreter_with_rbac # For data analysis tool

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
                self.openai = {"api_key": "sk-your-openai-key-here"}
                self.google = {"api_key": "AIzaSy_YOUR_GOOGLE_API_KEY_HERE"}
                self.serpapi = {"api_key": "YOUR_SERPAPI_KEY_HERE"}
                self.google_custom_search = {"api_key": "YOUR_GOOGLE_CUSTOM_SEARCH_API_KEY_HERE"}
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

# Define the required tier for this specific page (AI Assistant)
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
        st.error(f"🚫 Access Denied: Your current tier ({user_tier.capitalize()}) does not have access to the AI Assistant. Please upgrade your plan to {REQUIRED_TIER_FOR_THIS_PAGE.capitalize()} or higher.")
        st.stop() # Halts execution
# --- End RBAC Access Check ---


# --- Streamlit UI ---
st.set_page_config(page_title="AI Assistant", page_icon="🤖", layout="centered")
st.title("AI Assistant 🤖")

# --- GLOBAL DISCLAIMER ---
st.warning(
    "**Disclaimer:** This AI Assistant provides information for educational and general purposes only. "
    "It is not a substitute for professional advice (legal, medical, financial, etc.) and should not be used for emergency situations. "
    "Always consult a qualified professional for specific concerns. The creators are not liable for any actions taken based on this information."
)
st.markdown("---")
# --- END GLOBAL DISCLAIMER ---


# Session state for chat history
if "messages" not in st.session_state:
    st.session_state.messages = []
if "llm_manager" not in st.session_state:
    st.session_state.llm_manager = None

# Initialize LLMManager once per session
if st.session_state.llm_manager is None:
    try:
        st.session_state.llm_manager = LLMManager(
            api_key=config_manager.get_secret("openai_api_key"), # Uses OpenAI by default
            model_name=config_manager.get("llm.model_name", "gpt-3.5-turbo")
        )
        logger.info("Initialized LLMManager for AI Assistant.")
    except Exception as e:
        st.error(f"Failed to initialize AI Assistant: {e}. Please check your API key and configuration.")
        st.stop()

llm_manager = st.session_state.llm_manager
user_token = current_user.get('user_id', 'default') # Get user token for personalization

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# React to user input
if prompt := st.chat_input("Ask me anything..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.spinner("Thinking..."):
        # Determine available tools based on user's tier
        available_tools = []
        
        # Always include web search for general AI Assistant
        from shared_tools.scraper_tool import scrape_web
        available_tools.append(scrape_web)

        # Conditionally add Python interpreter based on user's tier capability
        if get_user_tier_capability(user_token, 'data_analysis_enabled', False):
            available_tools.append(python_interpreter_with_rbac)
            logger.info(f"Python interpreter added for user {user_token} (Tier: {user_tier})")
        else:
            logger.info(f"Python interpreter NOT added for user {user_token} (Tier: {user_tier}) - Data analysis not enabled.")

        try:
            # Get AI response using the LLM and available tools
            full_response = llm_manager.chat_with_agent(prompt, st.session_state.messages, available_tools, user_token)
            
            # Display assistant response in chat message container
            with st.chat_message("assistant"):
                st.markdown(full_response)
            # Add assistant response to chat history
            st.session_state.messages.append({"role": "assistant", "content": full_response})

        except Exception as e:
            st.error(f"An error occurred: {e}")
            logger.exception("Error during AI Assistant chat:")

st.markdown("---")
# Clear chat history button
if st.button("Clear Chat", use_container_width=True):
    st.session_state.messages = []
    st.rerun()

st.caption(f"Current User Token: `{current_user.get('user_id', 'N/A')}` (for demo purposes)")
