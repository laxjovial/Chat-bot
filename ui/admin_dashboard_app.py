# ui/admin_dashboard_app.py

import streamlit as st
import pandas as pd
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

# Assume config_manager and user_manager exist
from config.config_manager import config_manager
from utils.user_manager import (
    get_current_user,
    firestore_db, # Direct access to FirestoreManager
    hash_password,
    validate_password_strength as validate_password_strength_util,
    SecurityConfig # For password length
)

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
                self.firestore = {
                    "type": "service_account",
                    "project_id": "test-project-id",
                    "private_key_id": "test-private-key-id",
                    "private_key": "-----BEGIN PRIVATE KEY-----\\nFAKE_TEST_KEY\\n-----END PRIVATE KEY-----\\n",
                    "client_email": "test-service-account@test-project-id.iam.gserviceaccount.com",
                }
        st.secrets = MockSecrets()
        logger.info("Mocked st.secrets for standalone testing.")
    
    if not config_manager._is_loaded:
        try:
            logger.info("ConfigManager assumed to be initialized by importing. Ensure data/config.yml and other config files exist.")
        except Exception as e:
            st.error(f"Failed to initialize configuration: {e}. Please ensure data/config.yml and .streamlit/secrets.toml are set up correctly.")
            st.stop()

initialize_app_config()

# --- Admin Access Control ---
current_user = get_current_user()
if not current_user or (current_user.get('tier') != 'admin' and 'admin' not in current_user.get('roles', [])):
    st.error("🚫 Access Denied: You must be an administrator to view this page.")
    st.stop() # Halt execution if not authorized

st.set_page_config(page_title="Admin Dashboard", page_icon="📊", layout="wide")
st.title("📊 Admin Dashboard")
st.markdown("Manage users and system settings.")

# --- User Management Functions ---

def get_all_users() -> List[Dict[str, Any]]:
    """Fetches all users from Firestore."""
    try:
        users = firestore_db.get_all_users()
        # Convert datetime objects to string for display in DataFrame
        for user in users:
            if 'created_at' in user and isinstance(user['created_at'], datetime):
                user['created_at'] = user['created_at'].isoformat()
            if 'last_login_at' in user and isinstance(user['last_login_at'], datetime):
                user['last_login_at'] = user['last_login_at'].isoformat()
            if 'locked_until' in user and isinstance(user['locked_until'], datetime):
                user['locked_until'] = user['locked_until'].isoformat()
            # Convert roles list to comma-separated string for display
            if 'roles' in user and isinstance(user['roles'], list):
                user['roles'] = ", ".join(user['roles'])
        return users
    except Exception as e:
        st.error(f"Error fetching users: {e}")
        logger.error(f"Error fetching all users for admin dashboard: {e}", exc_info=True)
        return []

def update_user_data(user_id: str, updates: Dict[str, Any]) -> bool:
    """Updates user data in Firestore."""
    try:
        success, msg = firestore_db.update_user(user_id, updates)
        if success:
            st.success(f"✅ User {user_id} updated successfully: {msg}")
            logger.info(f"Admin updated user {user_id}: {updates}")
            return True
        else:
            st.error(f"❌ Failed to update user {user_id}: {msg}")
            logger.error(f"Admin failed to update user {user_id}: {msg}")
            return False
    except Exception as e:
        st.error(f"An error occurred while updating user {user_id}: {e}")
        logger.error(f"Error updating user {user_id}: {e}", exc_info=True)
        return False

def delete_user_data(user_id: str) -> bool:
    """Deletes a user from Firestore."""
    try:
        success, msg = firestore_db.delete_user(user_id)
        if success:
            st.success(f"✅ User {user_id} deleted successfully: {msg}")
            logger.info(f"Admin deleted user {user_id}")
            return True
        else:
            st.error(f"❌ Failed to delete user {user_id}: {msg}")
            logger.error(f"Admin failed to delete user {user_id}: {msg}")
            return False
    except Exception as e:
        st.error(f"An error occurred while deleting user {user_id}: {e}")
        logger.error(f"Error deleting user {user_id}: {e}", exc_info=True)
        return False

# --- UI Sections ---

st.subheader("User Management")

# Display all users in a DataFrame
all_users = get_all_users()
if all_users:
    df_users = pd.DataFrame(all_users)
    # Select columns to display
    display_cols = ['user_id', 'username', 'email', 'tier', 'roles', 'is_active', 
                    'last_login_at', 'login_attempts', 'locked_until', 'created_at']
    df_display = df_users[display_cols]
    st.dataframe(df_display, use_container_width=True)
else:
    st.info("No users found in the system.")

st.markdown("---")
st.subheader("Edit User")

user_id_to_edit = st.text_input("Enter User ID to Edit:")

if user_id_to_edit:
    user_to_edit = firestore_db.get_user(user_id_to_edit)
    if user_to_edit:
        st.write(f"Editing user: **{user_to_edit.get('username', 'N/A')}** ({user_to_edit.get('email', 'N/A')})")

        with st.form("edit_user_form"):
            new_username = st.text_input("Username:", value=user_to_edit.get('username', ''))
            new_email = st.text_input("Email:", value=user_to_edit.get('email', ''))
            new_tier = st.selectbox("Tier:", ["free", "pro", "admin"], index=["free", "pro", "admin"].index(user_to_edit.get('tier', 'free')))
            
            # Convert roles string back to list for editing
            current_roles_str = user_to_edit.get('roles', '')
            current_roles_list = [r.strip() for r in current_roles_str.split(',')] if current_roles_str else []
            
            # Allow multi-select for roles
            all_possible_roles = ["user", "admin", "super_admin", "content_moderator", "support_agent"] # Define all possible roles
            new_roles = st.multiselect("Roles:", options=all_possible_roles, default=current_roles_list)

            new_is_active = st.checkbox("Is Active:", value=user_to_edit.get('is_active', True))
            
            # Admin can reset password (without knowing old one)
            st.markdown("#### Reset User Password (Optional)")
            reset_password = st.checkbox("Reset password for this user?")
            new_password = ""
            confirm_new_password = ""
            if reset_password:
                new_password = st.text_input("New Password:", type="password", key="admin_new_pass")
                confirm_new_password = st.text_input("Confirm New Password:", type="password", key="admin_confirm_new_pass")

            submitted = st.form_submit_button("Update User")

            if submitted:
                updates = {
                    "username": new_username,
                    "email": new_email,
                    "tier": new_tier,
                    "roles": new_roles, # Save as list
                    "is_active": new_is_active
                }

                if reset_password:
                    if not new_password or not confirm_new_password:
                        st.error("❌ New password fields cannot be empty if resetting password.")
                        submitted = False # Prevent update
                    elif new_password != confirm_new_password:
                        st.error("❌ New passwords do not match.")
                        submitted = False # Prevent update
                    else:
                        is_strong, strength_msg = validate_password_strength_util(new_password, SecurityConfig.PASSWORD_MIN_LENGTH)
                        if not is_strong:
                            st.error(f"❌ Password strength: {strength_msg}")
                            submitted = False # Prevent update
                        else:
                            hashed_pass, salt = hash_password(new_password)
                            updates["hashed_password"] = hashed_pass
                            updates["salt"] = salt
                            st.info("Password will be reset.")
                
                if submitted: # Re-check submitted after password validation
                    if update_user_data(user_id_to_edit, updates):
                        st.experimental_rerun() # Refresh page to show updated data
    else:
        st.warning("User ID not found.")

st.markdown("---")
st.subheader("Delete User")
user_id_to_delete = st.text_input("Enter User ID to Delete (Type 'CONFIRM' to proceed):")

if user_id_to_delete and st.button("Delete User", type="secondary"):
    if user_id_to_delete == current_user['user_id']:
        st.error("❌ You cannot delete your own account from here.")
    elif st.text_input("Type 'CONFIRM' to delete:", key="confirm_delete_user") == "CONFIRM":
        if delete_user_data(user_id_to_delete):
            st.experimental_rerun() # Refresh page to show updated data
    else:
        st.warning("Please type 'CONFIRM' to confirm deletion.")

st.markdown("---")
st.subheader("System Information (Placeholder)")
st.info("Additional system-wide administrative functions can be added here, such as:")
st.markdown("""
- **View System Logs:** Access detailed application logs.
- **Manage API Keys:** Securely manage API keys used by different agents.
- **Database Backup/Restore:** Tools for data management.
- **Agent Configuration:** Adjust global settings for AI agents.
""")

st.markdown("---")
st.caption(f"Logged in as Admin: **{current_user.get('username')}**")
