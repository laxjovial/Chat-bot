# ui/main_app.py

import streamlit as st
import logging
from utils.user_manager import get_current_user, logout_user, get_user_tier_capability
from config.config_manager import config_manager
import os # Required for config_manager initialization fallback

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


# --- RBAC Configuration ---
# Define a hierarchy for tiers (higher number means higher access)
TIER_HIERARCHY = {
    "free": 0,
    "basic": 1,
    "pro": 2,
    "premium": 3,
    "admin": 99 # Admin has highest access
}

# Define pages and their required tiers/roles
# Pages not listed here are assumed to be "free" or public access.
PAGES = {
    "Home": {"icon": "🏠", "tier_access": "free"},
    "Register": {"icon": "📝", "tier_access": "free"},
    "Login": {"icon": "🔐", "tier_access": "free"},
    "Forgot Password": {"icon": "🔑", "tier_access": "free"},
    "Reset Password (Token)": {"icon": "🔁", "tier_access": "free", "show_in_sidebar": False}, # Hidden from direct sidebar nav
    "Lost Token": {"icon": "❓", "tier_access": "free"},
    "Change Password": {"icon": "⚙️", "tier_access": "basic"}, # Requires basic tier or higher
    "User Profile": {"icon": "👤", "tier_access": "basic"}, # Requires basic tier or higher
    "Admin Dashboard": {"icon": "📊", "tier_access": "admin"}, # Admin only
    "AI Assistant": {"icon": "🤖", "tier_access": "basic"}, # Basic tier or higher
    "Medical AI Assistant": {"icon": "⚕️", "tier_access": "pro"}, # Pro tier or higher
    "Legal AI Assistant": {"icon": "⚖️", "tier_access": "premium"}, # Premium tier or higher
    "Upload Medical Docs": {"icon": "⬆️", "tier_access": "pro"}, # Pro tier or higher
    "Query Uploaded Medical Docs": {"icon": "🔎", "tier_access": "pro"}, # Pro tier or higher
    "Upload Legal Docs": {"icon": "⬆️", "tier_access": "premium"}, # Premium tier or higher
    "Query Uploaded Legal Docs": {"icon": "🔎", "tier_access": "premium"}, # Premium tier or higher
    "Medical Query Tools": {"icon": "💊", "tier_access": "pro"}, # Pro tier or higher
    "Legal Query Tools": {"icon": "📚", "tier_access": "premium"}, # Premium tier or higher
    "News & Media Tools": {"icon": "📰", "tier_access": "basic"}, # Basic tier or higher
    "Sports Tools": {"icon": "⚽", "tier_access": "basic"}, # Basic tier or higher
    "Weather Tools": {"icon": "☀️", "tier_access": "basic"}, # Basic tier or higher
    "Image Generation": {"icon": "🖼️", "tier_access": "pro"}, # Pro tier or higher
    "Image Analysis": {"icon": "👁️", "tier_access": "pro"}, # Pro tier or higher
    "Audio Generation": {"icon": "🎵", "tier_access": "pro"}, # Pro tier or higher
    "Video Analysis": {"icon": "🎥", "tier_access": "pro"}, # Pro tier or higher
}


# --- Streamlit App Setup ---
st.set_page_config(
    page_title="Unified AI Assistant",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Session State Management ---
if "current_page" not in st.session_state:
    st.session_state.current_page = "Home"

# --- User Authentication and RBAC ---
current_user = get_current_user()
is_logged_in = current_user is not None
user_tier = current_user.get('tier', 'free') if is_logged_in else 'free'
user_roles = current_user.get('roles', []) if is_logged_in else []

def has_access(page_name):
    """Checks if the current user has access to a given page."""
    page_info = PAGES.get(page_name, {"tier_access": "free"}) # Default to free access if not specified
    required_tier = page_info.get("tier_access", "free")

    # Admins always have access
    if "admin" in user_roles:
        return True
    
    # Compare user's tier level with required tier level
    user_tier_level = TIER_HIERARCHY.get(user_tier, -1)
    required_tier_level = TIER_HIERARCHY.get(required_tier, -1)
    
    return user_tier_level >= required_tier_level

# --- Sidebar Navigation ---
st.sidebar.title("Unified AI Assistant 🧠")

if is_logged_in:
    st.sidebar.success(f"Welcome, {current_user.get('username', 'User')}!")
    st.sidebar.info(f"Your Tier: **{user_tier.capitalize()}**")
    if user_roles:
        st.sidebar.caption(f"Roles: {', '.join([role.capitalize() for role in user_roles])}")
    
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        logout_user()
        st.session_state.current_page = "Login" # Redirect to login after logout
        st.rerun()
else:
    st.sidebar.info("Please Login or Register.")

st.sidebar.header("Navigation")

# Dynamic sidebar based on user's access
for page_name, page_info in PAGES.items():
    if page_info.get("show_in_sidebar", True): # Only show pages explicitly marked or defaulting to True
        if has_access(page_name):
            icon = page_info.get("icon", "📄")
            if st.sidebar.button(f"{icon} {page_name}", key=f"nav_{page_name}", use_container_width=True):
                st.session_state.current_page = page_name
                st.rerun()
        else:
            # Optionally show disabled link or just hide it
            icon = page_info.get("icon", "📄")
            # st.sidebar.button(f"🚫 {icon} {page_name} (Upgrade)", key=f"nav_{page_name}_disabled", disabled=True, use_container_width=True)
            pass # Hide pages without access for cleaner UI

st.sidebar.markdown("---")
st.sidebar.caption("© 2024 Unified AI Assistant")

# --- Main Content Area ---
def render_page():
    """Renders the selected page content."""
    page = st.session_state.current_page

    # Check access again before rendering (redundant but safe)
    if not has_access(page):
        st.error(f"🚫 You do not have permission to view '{page}'. Please select an accessible page or upgrade your plan.")
        st.session_state.current_page = "Home" # Redirect to home if access is lost
        st.rerun()
        return

    if page == "Home":
        st.title("Welcome to Unified AI Assistant 🧠")
        st.markdown("""
            Your all-in-one AI platform for various needs, from general assistance to specialized medical and legal queries.
            
            **Features:**
            * **Secure User Management:** Register, Login, Change Password, Recover Lost Tokens.
            * **Role-Based Access Control (RBAC):** Access features based on your subscription tier (Free, Basic, Pro, Premium, Admin).
            * **AI Assistant:** General purpose conversational AI.
            * **Specialized AI Assistants:**
                * **Medical AI Assistant:** For health-related queries (Pro tier).
                * **Legal AI Assistant:** For law-related inquiries (Premium tier).
            * **Document Management:** Upload and query your own medical or legal documents.
            * **Integrated Tools:** News & Media, Sports, Weather, Image Generation/Analysis, Audio Generation, Video Analysis.
            
            Use the sidebar to navigate through the different functionalities.
        """)
        st.image("https://placehold.co/800x400/ADD8E6/000000?text=Unified+AI+Assistant+Dashboard", caption="Unified AI Assistant Dashboard", use_column_width=True)
        st.markdown("---")
        st.subheader("Get Started:")
        if not is_logged_in:
            st.info("If you are new, please **Register** to create an account. Otherwise, **Login** to access your features.")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📝 Register Now", use_container_width=True):
                    st.session_state.current_page = "Register"
                    st.rerun()
            with col2:
                if st.button("🔐 Login", use_container_width=True):
                    st.session_state.current_page = "Login"
                    st.rerun()
        else:
            st.info("You are logged in! Explore the features using the navigation menu.")
            if st.button("🤖 Start Chatting with AI Assistant", use_container_width=True):
                st.session_state.current_page = "AI Assistant"
                st.rerun()

    elif page == "Register":
        from ui.register_app import st_app as register_app
        register_app()
    elif page == "Login":
        from ui.login_app import st_app as login_app
        login_app()
    elif page == "Forgot Password":
        from ui.forgot_password_app import st_app as forgot_password_app
        forgot_password_app()
    elif page == "Reset Password (Token)":
        from ui.reset_password_token_app import st_app as reset_password_token_app
        reset_password_token_app()
    elif page == "Lost Token":
        from ui.lost_token_app import st_app as lost_token_app
        lost_token_app()
    elif page == "Change Password":
        from ui.change_password_app import st_app as change_password_app
        change_password_app()
    elif page == "User Profile":
        from ui.user_profile_app import st_app as user_profile_app
        user_profile_app()
    elif page == "Admin Dashboard":
        from ui.admin_dashboard_app import st_app as admin_dashboard_app
        admin_dashboard_app()
    elif page == "AI Assistant":
        from ui.ai_assistant_app import st_app as ai_assistant_app
        ai_assistant_app()
    elif page == "Medical AI Assistant":
        from ui.medical_ai_assistant_app import st_app as medical_ai_assistant_app
        medical_ai_assistant_app()
    elif page == "Legal AI Assistant":
        from ui.legal_ai_assistant_app import st_app as legal_ai_assistant_app
        legal_ai_assistant_app()
    elif page == "Upload Medical Docs":
        from ui.medical_vector_app import st_app as medical_vector_app
        medical_vector_app()
    elif page == "Query Uploaded Medical Docs":
        from ui.medical_vector_query_app import st_app as medical_vector_query_app
        medical_vector_query_app()
    elif page == "Upload Legal Docs":
        from ui.legal_vector_app import st_app as legal_vector_app
        legal_vector_app()
    elif page == "Query Uploaded Legal Docs":
        from ui.legal_vector_query_app import st_app as legal_vector_query_app
        legal_vector_query_app()
    elif page == "Medical Query Tools":
        from ui.medical_query_app import st_app as medical_query_app
        medical_query_app()
    elif page == "Legal Query Tools":
        from ui.legal_query_app import st_app as legal_query_app
        legal_query_app()
    elif page == "News & Media Tools":
        from ui.news_media_app import st_app as news_media_app
        news_media_app()
    elif page == "Sports Tools":
        from ui.sports_app import st_app as sports_app
        sports_app()
    elif page == "Weather Tools":
        from ui.weather_app import st_app as weather_app
        weather_app()
    elif page == "Image Generation":
        from ui.image_generation_app import st_app as image_generation_app
        image_generation_app()
    elif page == "Image Analysis":
        from ui.image_analysis_app import st_app as image_analysis_app
        image_analysis_app()
    elif page == "Audio Generation":
        from ui.audio_generation_app import st_app as audio_generation_app
        audio_generation_app()
    elif page == "Video Analysis":
        from ui.video_analysis_app import st_app as video_analysis_app
        video_analysis_app()
    else:
        st.error("Page not found.")
        st.session_state.current_page = "Home"
        st.rerun()

# Render the selected page
render_page()
