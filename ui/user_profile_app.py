# ui/user_profile_app.py

import streamlit as st
import logging
from utils.user_manager import get_current_user, get_user_tier_capability
from config.config_manager import config_manager
from main_app import TIER_HIERARCHY # Import TIER_HIERARCHY for comparison

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
                self.openai = {"api_key": "sk-your-openai-key-here"} # Example, not directly used here but needed for other parts
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

# Define the required tier for this specific page (User Profile)
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
        st.error(f"🚫 Access Denied: Your current tier ({user_tier.capitalize()}) does not have access to your User Profile. Please upgrade your plan to {REQUIRED_TIER_FOR_THIS_PAGE.capitalize()} or higher.")
        st.stop() # Halts execution
# --- End RBAC Access Check ---


# --- Streamlit UI ---
st.set_page_config(page_title="User Profile", page_icon="👤", layout="centered")
st.title("User Profile 👤")

# --- GLOBAL DISCLAIMER ---
st.warning(
    "**Disclaimer:** This User Profile page displays your account information. "
    "While we strive for accuracy, please report any discrepancies. "
    "This tool is for informational purposes only and should not be used for emergency situations. "
    "The creators are not liable for any actions taken based on this information."
)
st.markdown("---")
# --- END GLOBAL DISCLAIMER ---


if current_user:
    st.subheader(f"Welcome, {current_user.get('username', 'User')}!")
    st.write(f"**User ID:** `{current_user.get('user_id', 'N/A')}`")
    st.write(f"**Email:** `{current_user.get('email', 'N/A')}`")
    st.write(f"**Current Tier:** **{current_user.get('tier', 'N/A').capitalize()}**")
    st.write(f"**Roles:** **{', '.join(current_user.get('roles', ['N/A']))}**")

    st.markdown("---")
    st.subheader("Account Actions")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Change Password", use_container_width=True):
            st.session_state.current_page = "Change Password"
            st.rerun()
    with col2:
        if st.button("Manage Subscriptions (Future)", use_container_width=True, disabled=True):
            st.info("Subscription management features are coming soon!")

    st.markdown("---")
    st.caption("Your profile information is securely stored.")
else:
    st.warning("You are not logged in. Please log in to view your profile.")
    if st.button("Go to Login"):
        st.session_state.current_page = "Login"
        st.rerun()
