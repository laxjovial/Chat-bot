# main_app.py

import streamlit as st
import os
import sys
import logging

# Ensure the project root is in the Python path
# This is crucial for imports like 'utils.user_manager' to work correctly
# when running Streamlit from a sub-directory or deployed.
current_dir = Path(__file__).parent.absolute()
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import authentication and user management utilities
from utils.user_manager import get_current_user, logout_user, find_user_by_email, authenticate_user, set_current_user
from utils.email_utils import EmailSender # For sending security alerts on login

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Page Configuration ---
st.set_page_config(
    page_title="Unified AI Assistant",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Session State Initialization ---
if "user_token" not in st.session_state:
    st.session_state.user_token = None
if "current_page" not in st.session_state:
    st.session_state.current_page = "Home"

# --- Page Routing Dictionary ---
# Map page names to their corresponding Streamlit app functions
# We will dynamically import these as needed to avoid circular dependencies and speed up startup
PAGES = {
    "Home": "home_page", # A simple welcome page
    "Login": "login_app",
    "Register": "register_app",
    "Forgot Password": "forgot_password_app",
    "Reset Password (Token)": "reset_password_token_app", # For direct token link
    "Change Password": "change_password_app",
    "Lost Access Token": "lost_token_app",
    # Agent Chat Interfaces
    "Sports AI Assistant": "sports_chat_agent_app",
    "Finance AI Assistant": "finance_chat_agent_app",
    "Entertainment AI Assistant": "entertainment_chat_agent_app",
    "Medical AI Assistant": "medical_chat_agent_app",
    "Legal AI Assistant": "legal_chat_agent_app",
    "Weather AI Assistant": "weather_chat_agent_app",
    "News AI Assistant": "news_chat_agent_app",
    # Agent Query Tools
    "Sports Query Tools": "sports_query_app",
    "Finance Query Tools": "finance_query_app",
    "Entertainment Query Tools": "entertainment_query_app",
    "Medical Query Tools": "medical_query_app",
    "Legal Query Tools": "legal_query_app",
    "Weather Query Tools": "weather_query_app",
    "News Query Tools": "news_query_app",
    # Agent Vector Management
    "Upload Sports Docs": "sports_vector_app",
    "Query Uploaded Sports Docs": "sports_vector_query_app",
    "Upload Finance Docs": "finance_vector_app",
    "Query Uploaded Finance Docs": "finance_vector_query_app",
    "Upload Entertainment Docs": "entertainment_vector_app",
    "Query Uploaded Entertainment Docs": "entertainment_vector_query_app",
    "Upload Medical Docs": "medical_vector_app",
    "Query Uploaded Medical Docs": "medical_vector_query_app",
    "Upload Legal Docs": "legal_vector_app",
    "Query Uploaded Legal Docs": "legal_vector_query_app",
    "Upload Weather Docs": "weather_vector_app",
    "Query Uploaded Weather Docs": "weather_vector_query_app",
    "Upload News Docs": "news_vector_app",
    "Query Uploaded News Docs": "news_vector_query_app",
    # Admin Pages (placeholder for now)
    "Admin Dashboard": "admin_dashboard_app" # Will create this later if requested
}

# --- Dynamic Page Loader ---
def load_page(page_name):
    """Dynamically loads and runs the selected Streamlit app."""
    module_name = PAGES.get(page_name)
    if module_name:
        try:
            # For apps in 'ui' directory
            if module_name in ["login_app", "register_app", "forgot_password_app", 
                               "reset_password_token_app", "change_password_app", "lost_token_app"]:
                module_path = f"ui.{module_name}"
            # For agent chat apps
            elif "chat_agent_app" in module_name:
                module_path = f"ui.{module_name}"
            # For agent query apps
            elif "query_app" in module_name:
                module_path = f"ui.{module_name}"
            # For agent vector apps
            elif "vector_app" in module_name or "vector_query_app" in module_name:
                module_path = f"ui.{module_name}"
            # For admin dashboard (future)
            elif module_name == "admin_dashboard_app":
                module_path = f"ui.{module_name}"
            else: # Home page or other simple pages
                return render_home_page() # Render a simple home page directly

            # Import the module and run its main Streamlit code
            # Note: Streamlit reruns the entire script, so importing modules this way
            # means their top-level Streamlit calls will execute.
            # This is a common pattern but can be optimized for very large apps.
            __import__(module_path)
            logger.info(f"Loaded page: {page_name} from {module_path}")

        except ImportError as e:
            st.error(f"Could not load page '{page_name}'. Module not found: {e}")
            logger.error(f"ImportError for {module_path}: {e}", exc_info=True)
            st.session_state.current_page = "Home" # Fallback
            st.rerun()
        except Exception as e:
            st.error(f"An error occurred while loading page '{page_name}': {e}")
            logger.error(f"Error loading {page_name}: {e}", exc_info=True)
            st.session_state.current_page = "Home" # Fallback
            st.rerun()
    else:
        st.error(f"Page '{page_name}' not found in configuration.")
        st.session_state.current_page = "Home" # Fallback
        st.rerun()

def render_home_page():
    """Renders the simple home page."""
    st.header("Welcome to Your Unified AI Assistant! ✨")
    st.markdown("""
    This is your central hub for interacting with various specialized AI agents.
    
    **Choose an agent from the sidebar to get started:**
    
    * **Sports Agent 🏆:** Get live scores, player stats, team info, and analyze sports data.
    * **Finance Agent 📈:** Track stocks, crypto, get market news, and perform financial analysis.
    * **Entertainment Agent 🎬:** Discover movies, music, series, anime, and get recommendations.
    * **Medical Agent ⚕️:** Check symptoms, get first aid, health tips, and world health updates.
    * **Legal Agent ⚖️:** Explore law, constitution, legal terms, and analyze contracts across jurisdictions.
    * **Weather Agent ☁️:** Get current weather, forecasts, historical data, and climate explanations.
    * **News Agent 📰:** Stay updated with top headlines, search for news, and track trending stories.
    
    Use the navigation in the sidebar to switch between agents and manage your account.
    """)
    st.image("https://placehold.co/800x300/ADD8E6/000000?text=Unified+AI+Assistant+Dashboard", 
             caption="Your intelligent companion for every domain.")


# --- Sidebar Navigation ---
with st.sidebar:
    st.image("https://placehold.co/150x150/ADD8E6/000000?text=AI+Logo", use_column_width=True)
    st.title("Navigation")

    current_user = get_current_user()

    if current_user:
        st.success(f"Logged in as: **{current_user.get('username', 'User')}** (Tier: {current_user.get('tier', 'N/A')})")
        st.markdown("---")

        # Agent Selection
        st.subheader("AI Agents")
        agent_options = [
            "Sports AI Assistant", "Finance AI Assistant", "Entertainment AI Assistant",
            "Medical AI Assistant", "Legal AI Assistant", "Weather AI Assistant", "News AI Assistant"
        ]
        selected_agent = st.radio("Choose an Agent:", agent_options, key="agent_radio")
        if selected_agent and st.session_state.current_page != selected_agent:
            st.session_state.current_page = selected_agent
            st.rerun()

        st.markdown("---")
        st.subheader("Agent Tools & Data")
        tool_options = [
            "Sports Query Tools", "Upload Sports Docs", "Query Uploaded Sports Docs",
            "Finance Query Tools", "Upload Finance Docs", "Query Uploaded Finance Docs",
            "Entertainment Query Tools", "Upload Entertainment Docs", "Query Uploaded Entertainment Docs",
            "Medical Query Tools", "Upload Medical Docs", "Query Uploaded Medical Docs",
            "Legal Query Tools", "Upload Legal Docs", "Query Uploaded Legal Docs",
            "Weather Query Tools", "Upload Weather Docs", "Query Uploaded Weather Docs",
            "News Query Tools", "Upload News Docs", "Query Uploaded News Docs"
        ]
        selected_tool = st.radio("Manage Tools & Data:", tool_options, key="tool_radio")
        if selected_tool and st.session_state.current_page != selected_tool:
            st.session_state.current_page = selected_tool
            st.rerun()

        st.markdown("---")
        st.subheader("Account Management")
        account_options = [
            "Change Password", "Lost Access Token"
        ]
        selected_account_option = st.radio("Account Options:", account_options, key="account_radio")
        if selected_account_option and st.session_state.current_page != selected_account_option:
            st.session_state.current_page = selected_account_option
            st.rerun()
        
        # Admin Dashboard access (only for 'admin' tier)
        if current_user.get('tier') == 'admin' or 'admin' in current_user.get('roles', []):
            st.markdown("---")
            st.subheader("Admin Functions")
            if st.button("📊 Admin Dashboard", use_container_width=True):
                st.session_state.current_page = "Admin Dashboard"
                st.rerun()

        st.markdown("---")
        if st.button("🚪 Logout", type="secondary", use_container_width=True):
            logout_user()
            st.session_state.current_page = "Login" # Redirect to login after logout
            st.rerun()

    else:
        st.subheader("Authentication")
        auth_options = ["Login", "Register", "Forgot Password"]
        selected_auth = st.radio("Choose an option:", auth_options, key="auth_radio")
        if selected_auth and st.session_state.current_page != selected_auth:
            st.session_state.current_page = selected_auth
            st.rerun()

# --- Main Content Area ---
st.markdown("---") # Separator for main content

# If user is not logged in and not on a public auth page, redirect to Login
if not current_user and st.session_state.current_page not in ["Login", "Register", "Forgot Password", "Reset Password (Token)"]:
    st.session_state.current_page = "Login"
    st.rerun()

# Render the selected page
load_page(st.session_state.current_page)

st.markdown("---")
st.caption("Unified AI Assistant - Powered by Streamlit and LangChain")
