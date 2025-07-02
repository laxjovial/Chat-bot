# ui/admin_dashboard_app.py

import streamlit as st
import logging
import pandas as pd
from utils.user_manager import get_all_users, update_user_tier_and_roles, get_current_user, get_user_tier_capability
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

# Define the required tier/role for this specific page (Admin Dashboard)
REQUIRED_ROLE_FOR_THIS_PAGE = "admin" 

# Check if user is logged in and has the required role
if not current_user or REQUIRED_ROLE_FOR_THIS_PAGE not in user_roles:
    st.error(f"🚫 Access Denied: You must be an '{REQUIRED_ROLE_FOR_THIS_PAGE.capitalize()}' to access this page.")
    st.stop() # Halts execution
# --- End RBAC Access Check ---


# --- Streamlit UI ---
st.set_page_config(page_title="Admin Dashboard", page_icon="📊", layout="wide")
st.title("Admin Dashboard 📊")

# --- GLOBAL DISCLAIMER ---
st.warning(
    "**Disclaimer:** This Admin Dashboard provides management functionalities for the AI Assistant platform. "
    "Exercise caution when modifying user data, tiers, or roles, as changes can significantly impact user access and system behavior. "
    "This tool is for administrative purposes only and should not be used for emergency situations. "
    "The creators are not liable for any actions taken based on this information."
)
st.markdown("---")
# --- END GLOBAL DISCLAIMER ---


st.subheader("Manage Users")

# Fetch all users
users_data = get_all_users()

if not users_data:
    st.info("No users found in the database.")
else:
    # Convert users_data to a list of dictionaries for DataFrame
    users_list = []
    for user_id, user_info in users_data.items():
        user_dict = {"User ID": user_id}
        user_dict.update(user_info)
        # Ensure 'roles' is a list for display
        if 'roles' in user_dict and isinstance(user_dict['roles'], str):
            user_dict['roles'] = user_dict['roles'].split(',')
        elif 'roles' not in user_dict:
            user_dict['roles'] = []
        users_list.append(user_dict)

    df = pd.DataFrame(users_list)
    
    # Reorder columns for better display
    display_columns = ["User ID", "username", "email", "tier", "roles"]
    # Add any other columns that exist in the DataFrame but not in display_columns
    for col in df.columns:
        if col not in display_columns:
            display_columns.append(col)
    
    df = df[display_columns]

    st.dataframe(df, use_container_width=True)

    st.markdown("---")
    st.subheader("Update User Tier and Roles")

    # Dropdown to select a user
    selected_user_id = st.selectbox("Select User to Update:", df["User ID"].tolist())

    if selected_user_id:
        selected_user_info = next((user for user in users_list if user["User ID"] == selected_user_id), None)

        if selected_user_info:
            st.write(f"**Current details for {selected_user_info.get('username', selected_user_id)}:**")
            st.write(f"Email: {selected_user_info.get('email', 'N/A')}")
            st.write(f"Current Tier: **{selected_user_info.get('tier', 'N/A').capitalize()}**")
            st.write(f"Current Roles: **{', '.join(selected_user_info.get('roles', ['N/A']))}**")

            # Tier selection
            available_tiers = list(TIER_HIERARCHY.keys())
            current_tier_index = available_tiers.index(selected_user_info.get('tier', 'free')) if selected_user_info.get('tier', 'free') in available_tiers else 0
            new_tier = st.selectbox("Select New Tier:", available_tiers, index=current_tier_index)

            # Roles selection
            all_possible_roles = ["user", "admin", "customer_care", "analytics", "dev", "api_manager", "management"] # Expand as needed
            current_roles = selected_user_info.get('roles', [])
            new_roles = st.multiselect("Select New Roles:", all_possible_roles, default=current_roles)

            if st.button("Update User"):
                with st.spinner(f"Updating user {selected_user_id}..."):
                    try:
                        # Convert roles list back to comma-separated string for storage if needed by backend
                        roles_to_store = ",".join(new_roles) if new_roles else ""
                        
                        update_user_tier_and_roles(selected_user_id, new_tier, roles_to_store)
                        st.success(f"Successfully updated user {selected_user_info.get('username', selected_user_id)}!")
                        st.rerun() # Rerun to refresh the user list
                    except Exception as e:
                        st.error(f"Error updating user: {e}")
                        logger.error(f"Failed to update user {selected_user_id}: {e}", exc_info=True)
        else:
            st.error("Selected user not found.")

st.markdown("---")
st.caption(f"Current Admin User Token: `{current_user.get('user_id', 'N/A')}` (for demo purposes)")
