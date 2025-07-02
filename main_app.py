# main_app.py

import streamlit as st
import os
import sys
import logging
from pathlib import Path

# Ensure the project root is in the Python path
# This is crucial for imports like 'utils.user_manager' to work correctly
# when running Streamlit from a sub-directory or deployed.
current_dir = Path(__file__).parent.absolute()
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import authentication and user management utilities
from utils.user_manager import get_current_user, logout_user, find_user_by_email, authenticate_user, set_current_user, get_user_tier_capability
from utils.email_utils import EmailSender # For sending security alerts on login
from config.config_manager import config_manager # To access tier definitions

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
# Added 'tier_access' property to define minimum tier required to see/access the page.
# 'admin' means only users with 'admin' role can access.
# 'all' means no specific tier restriction (public or general user access).
PAGES = {
    "Home": {"module": "home_page", "tier_access": "all"},
    "Login": {"module": "login_app", "tier_access": "all"},
    "Register": {"module": "register_app", "tier_access": "all"},
    "Forgot Password": {"module": "forgot_password_app", "tier_access": "all"},
    "Reset Password (Token)": {"module": "reset_password_token_app", "tier_access": "all"}, # For direct token link
    "Change Password": {"module": "change_password_app", "tier_access": "basic"}, # Basic and above can change password
    "Lost Access Token": {"module": "lost_token_app", "tier_access": "all"},
    # Agent Chat Interfaces
    "Sports AI Assistant": {"module": "sports_chat_agent_app", "tier_access": "free"}, # Example: Free tier gets Sports
    "Finance AI Assistant": {"module": "finance_chat_agent_app", "tier_access": "basic"}, # Basic gets Finance
    "Entertainment AI Assistant": {"module": "entertainment_chat_agent_app", "tier_access": "basic"}, # Basic gets Entertainment
    "Medical AI Assistant": {"module": "medical_chat_agent_app", "tier_access": "pro"}, # Pro gets Medical
    "Legal AI Assistant": {"module": "legal_chat_agent_app", "tier_access": "pro"}, # Pro gets Legal
    "Weather AI Assistant": {"module": "weather_chat_agent_app", "tier_access": "free"}, # Free tier gets Weather
    "News AI Assistant": {"module": "news_chat_agent_app", "tier_access": "basic"}, # Basic gets News
    # Agent Query Tools
    "Sports Query Tools": {"module": "sports_query_app", "tier_access": "free"},
    "Finance Query Tools": {"module": "finance_query_app", "tier_access": "basic"},
    "Entertainment Query Tools": {"module": "entertainment_query_app", "tier_access": "basic"},
    "Medical Query Tools": {"module": "medical_query_app", "tier_access": "pro"},
    "Legal Query Tools": {"module": "legal_query_app", "tier_access": "pro"},
    "Weather Query Tools": {"module": "weather_query_app", "tier_access": "free"},
    "News Query Tools": {"module": "news_query_app", "tier_access": "basic"},
    # Agent Vector Management (Upload/Query Uploaded Docs)
    "Upload Sports Docs": {"module": "sports_vector_app", "tier_access": "basic"}, # Uploads start from Basic
    "Query Uploaded Sports Docs": {"module": "sports_vector_query_app", "tier_access": "basic"},
    "Upload Finance Docs": {"module": "finance_vector_app", "tier_access": "pro"}, # Finance docs for Pro+
    "Query Uploaded Finance Docs": {"module": "finance_vector_query_app", "tier_access": "pro"},
    "Upload Entertainment Docs": {"module": "entertainment_vector_app", "tier_access": "pro"},
    "Query Uploaded Entertainment Docs": {"module": "entertainment_vector_query_app", "tier_access": "pro"},
    "Upload Medical Docs": {"module": "medical_vector_app", "tier_access": "elite"}, # Medical docs for Elite+
    "Query Uploaded Medical Docs": {"module": "medical_vector_query_app", "tier_access": "elite"},
    "Upload Legal Docs": {"module": "legal_vector_app", "tier_access": "elite"}, # Legal docs for Elite+
    "Query Uploaded Legal Docs": {"module": "legal_vector_query_app", "tier_access": "elite"},
    "Upload Weather Docs": {"module": "weather_vector_app", "tier_access": "basic"}, # Weather docs for Basic+
    "Query Uploaded Weather Docs": {"module": "weather_vector_query_app", "tier_access": "basic"},
    "Upload News Docs": {"module": "news_vector_app", "tier_access": "pro"}, # News docs for Pro+
    "Query Uploaded News Docs": {"module": "news_vector_query_app", "tier_access": "pro"},
    # Admin Pages
    "Admin Dashboard": {"module": "admin_dashboard_app", "tier_access": "admin"} # Only for 'admin' role
}

# Define tier hierarchy for comparison
TIER_HIERARCHY = {
    "free": 0,
    "basic": 1,
    "pro": 2,
    "elite": 3,
    "premium": 4,
    "admin": 99 # Admin is highest, separate from regular tiers
}

def user_can_access_page(user_tier: str, user_roles: List[str], required_tier: str) -> bool:
    """Checks if a user can access a page based on their tier and roles."""
    if required_tier == "all":
        return True
    if required_tier == "admin":
        return "admin" in user_roles
    
    # For regular tiers, compare based on hierarchy
    user_level = TIER_HIERARCHY.get(user_tier, -1)
    required_level = TIER_HIERARCHY.get(required_tier, -1)
    return user_level >= required_level

def load_page(page_name):
    """Dynamically loads and runs the selected Streamlit app."""
    page_info = PAGES.get(page_name)
    if page_info:
        module_name = page_info["module"]
        
        # For home page, render directly
        if module_name == "home_page":
            return render_home_page()

        # Determine module path
        module_path_prefix = "ui." # All UI apps are in the 'ui' directory
        module_path = f"{module_path_prefix}{module_name}"

        try:
            # Import the module and run its main Streamlit code
            __import__(module_path)
            logger.info(f"Loaded page: {page_name} from {module_path}")

        except ImportError as e:
            st.error(f"Could not load page '{page_name}'. Module not found: {e}. Please ensure the file exists and is correctly named.")
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
    """)
    
    # Dynamically list agents based on user's tier
    current_user = get_current_user()
    user_tier = current_user.get('tier', 'free')
    user_roles = current_user.get('roles', [])

    agent_descriptions = {
        "Sports AI Assistant": "🏆 Get live scores, player stats, team info, and analyze sports data.",
        "Finance AI Assistant": "📈 Track stocks, crypto, get market news, and perform financial analysis.",
        "Entertainment AI Assistant": "🎬 Discover movies, music, series, anime, and get recommendations.",
        "Medical AI Assistant": "⚕️ Check symptoms, get first aid, health tips, and world health updates.",
        "Legal AI Assistant": "⚖️ Explore law, constitution, legal terms, and analyze contracts across jurisdictions.",
        "Weather AI Assistant": "☁️ Get current weather, forecasts, historical data, and climate explanations.",
        "News AI Assistant": "📰 Stay updated with top headlines, search for news, and track trending stories."
    }

    for agent_name, description in agent_descriptions.items():
        if user_can_access_page(user_tier, user_roles, PAGES[agent_name]["tier_access"]):
            st.markdown(f"* **{agent_name}**: {description}")
        else:
            st.markdown(f"* ~~{agent_name}~~ (Upgrade to {PAGES[agent_name]['tier_access'].capitalize()} tier for access)")

    st.markdown("---")
    st.image("https://placehold.co/800x300/ADD8E6/000000?text=Unified+AI+Assistant+Dashboard", 
             caption="Your intelligent companion for every domain.")


# --- Sidebar Navigation ---
with st.sidebar:
    st.image("https://placehold.co/150x150/ADD8E6/000000?text=AI+Logo", use_column_width=True)
    st.title("Navigation")

    current_user = get_current_user()
    user_tier = current_user.get('tier', 'free')
    user_roles = current_user.get('roles', [])

    if current_user:
        st.success(f"Logged in as: **{current_user.get('username', 'User')}** (Tier: {current_user.get('tier', 'N/A')})")
        st.markdown("---")

        # Filter pages based on user's tier and roles
        available_agent_chat_pages = []
        available_tool_pages = []
        available_account_pages = []
        available_admin_pages = []

        for page_name, page_info in PAGES.items():
            if user_can_access_page(user_tier, user_roles, page_info["tier_access"]):
                if "AI Assistant" in page_name and page_name != "Home":
                    available_agent_chat_pages.append(page_name)
                elif "Query Tools" in page_name or "Upload" in page_name or "Docs" in page_name:
                    available_tool_pages.append(page_name)
                elif page_name in ["Change Password", "Lost Access Token"]:
                    available_account_pages.append(page_name)
                elif page_name == "Admin Dashboard":
                    available_admin_pages.append(page_name)
        
        # Sort agent chat pages alphabetically for better UX
        available_agent_chat_pages.sort()
        available_tool_pages.sort()

        # Agent Selection
        st.subheader("AI Agents")
        if available_agent_chat_pages:
            selected_agent = st.radio("Choose an Agent:", available_agent_chat_pages, key="agent_radio")
            if selected_agent and st.session_state.current_page != selected_agent:
                st.session_state.current_page = selected_agent
                st.rerun()
        else:
            st.info("No agents available for your tier. Upgrade to unlock more!")


        st.markdown("---")
        st.subheader("Agent Tools & Data")
        if available_tool_pages:
            selected_tool = st.radio("Manage Tools & Data:", available_tool_pages, key="tool_radio")
            if selected_tool and st.session_state.current_page != selected_tool:
                st.session_state.current_page = selected_tool
                st.rerun()
        else:
            st.info("No tools or data management options available for your tier. Upgrade to unlock!")


        st.markdown("---")
        st.subheader("Account Management")
        if available_account_pages:
            selected_account_option = st.radio("Account Options:", available_account_pages, key="account_radio")
            if selected_account_option and st.session_state.current_page != selected_account_option:
                st.session_state.current_page = selected_account_option
                st.rerun()
        else:
            st.info("No account options available.")
        
        # Admin Dashboard access (only for 'admin' role)
        if available_admin_pages: # This list will only contain "Admin Dashboard" if user is admin
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
        auth_options = ["Login", "Register", "Forgot Password", "Lost Access Token"] # Lost token is also public
        selected_auth = st.radio("Choose an option:", auth_options, key="auth_radio")
        if selected_auth and st.session_state.current_page != selected_auth:
            st.session_state.current_page = selected_auth
            st.rerun()

# --- Main Content Area ---
st.markdown("---") # Separator for main content

# If user is not logged in and not on a public auth page, redirect to Login
public_pages = ["Login", "Register", "Forgot Password", "Reset Password (Token)", "Lost Access Token", "Home"]
if not current_user and st.session_state.current_page not in public_pages:
    st.session_state.current_page = "Login"
    st.rerun()

# If user is logged in, but tries to access a page they don't have access to (e.g., direct URL manipulation)
if current_user and st.session_state.current_page not in public_pages: # Exclude public pages from this check
    page_info = PAGES.get(st.session_state.current_page)
    if page_info and not user_can_access_page(user_tier, user_roles, page_info["tier_access"]):
        st.error(f"🚫 Access Denied: Your current tier ({user_tier.capitalize()}) does not have access to the '{st.session_state.current_page}' feature. Please upgrade your plan.")
        st.session_state.current_page = "Home" # Redirect to home or a "upgrade" page
        st.rerun()


# Render the selected page
load_page(st.session_state.current_page)

st.markdown("---")
st.caption("Unified AI Assistant - Powered by Streamlit and LangChain")
